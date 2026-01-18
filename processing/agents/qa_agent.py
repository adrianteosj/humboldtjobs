"""
QA Agent - Data Quality Assurance Specialist

Role: Validate job data quality, score sources, approve or quarantine jobs.

This agent ONLY focuses on data validation. It does not:
- Debug scrapers (that's EngineerAgent)
- Analyze trends (that's AnalystAgent)
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .base import BaseAgent, AgentRole, AgentResponse, ActionType

logger = logging.getLogger(__name__)


@dataclass
class JobRecord:
    """Structured job data for QA review"""
    id: int
    title: str
    employer: str
    location: str
    url: str
    salary: Optional[str] = None
    description: Optional[str] = None
    source_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "employer": self.employer,
            "location": self.location,
            "url": self.url,
            "salary": self.salary,
            "description": self.description[:200] if self.description else None,
            "source_name": self.source_name
        }


class QAAgent(BaseAgent):
    """
    QA Agent specializes in data quality validation.
    
    Responsibilities:
    - Validate job titles are real job titles (not UI elements)
    - Check URLs point to specific jobs (not generic pages)
    - Verify locations are in Humboldt County
    - Score data completeness
    - Approve, quarantine, or flag jobs for review
    """
    
    @property
    def role(self) -> AgentRole:
        return AgentRole.QA
    
    @property
    def system_prompt(self) -> str:
        return """You are a Data Quality Assurance Agent for a job board.

YOUR ROLE: Validate job listings for data quality issues.

YOU MUST ONLY:
- Check if job titles are real job titles (not UI elements like "View", "Apply", "Click here")
- Verify URLs point to specific job listings (not generic /careers or /jobs pages)
- Confirm locations are in or near Humboldt County, California
- Score data completeness (salary, description present)
- Make APPROVE/QUARANTINE/FLAG decisions

YOU MUST NOT:
- Debug scraper code (that's the Engineer Agent's job)
- Analyze market trends (that's the Analyst Agent's job)
- Suggest new features or improvements

HUMBOLDT COUNTY LOCATIONS (valid):
Eureka, Arcata, McKinleyville, Fortuna, Blue Lake, Ferndale, Trinidad, Hoopa, 
Willow Creek, Garberville, Rio Dell, Loleta, Crescent City, Klamath, Scotia,
Miranda, Redway, Myers Flat, Weott, Orick, Weitchpec, Salyer, Humboldt County

FALSE POSITIVE PATTERNS (should QUARANTINE):
- Titles like: "View", "Apply", "Click", "Display*", "Learn More", "See All", "Current Openings"
- URLs ending in: /careers, /employment, /jobs (without specific job ID)
- Generic link text scraped as job titles

RESPONSE FORMAT (JSON only):
{
    "decision": "APPROVE" | "QUARANTINE" | "FLAG_REVIEW",
    "confidence": 0.0-1.0,
    "quality_score": 0-100,
    "issues": ["list of issues found"],
    "reasons": ["reasons for decision"]
}"""
    
    def validate_job(self, job: JobRecord) -> AgentResponse:
        """
        Validate a single job record.
        
        Args:
            job: JobRecord to validate
            
        Returns:
            AgentResponse with validation result
        """
        prompt = f"""Validate this job listing:

TITLE: {job.title}
EMPLOYER: {job.employer}
LOCATION: {job.location}
URL: {job.url}
SALARY: {job.salary or 'Not provided'}
DESCRIPTION: {job.description[:200] if job.description else 'Not provided'}

Check for:
1. Is the title a real job title or a UI element/link text?
2. Does the URL point to a specific job or a generic careers page?
3. Is the location in Humboldt County?
4. What is the data completeness score?

Respond with JSON only."""

        try:
            response = self._call_llm(prompt)
            result = self._parse_json_response(response)
            
            # Map decision to ActionType
            decision_map = {
                "APPROVE": ActionType.APPROVE,
                "QUARANTINE": ActionType.QUARANTINE,
                "FLAG_REVIEW": ActionType.FLAG_REVIEW
            }
            
            decision = result.get("decision", "FLAG_REVIEW").upper()
            action = decision_map.get(decision, ActionType.FLAG_REVIEW)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                action=action,
                confidence=float(result.get("confidence", 0.5)),
                summary=f"Job '{job.title}' at {job.employer}: {decision}",
                details={
                    "job_id": job.id,
                    "quality_score": result.get("quality_score", 50),
                    "issues": result.get("issues", []),
                },
                recommendations=result.get("reasons", []),
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"QA validation failed for job {job.id}: {e}")
            return AgentResponse(
                agent=self.role,
                success=False,
                action=ActionType.FLAG_REVIEW,
                confidence=0.0,
                summary=f"QA validation failed: {str(e)}",
                details={"job_id": job.id, "error": str(e)},
                recommendations=["Manual review required due to validation error"]
            )
    
    def validate_batch(self, jobs: List[JobRecord], check_all: bool = True) -> Dict[str, List[AgentResponse]]:
        """
        Validate multiple jobs using AI.
        
        AI reviews ALL jobs to catch edge cases that rules would miss.
        Jobs are processed in batches for efficiency.
        
        Args:
            jobs: List of JobRecord objects
            check_all: Deprecated - AI now reviews all jobs by default
            
        Returns:
            Dict with 'approved', 'quarantined', 'flagged' lists
        """
        results = {
            "approved": [],
            "quarantined": [],
            "flagged": []
        }
        
        if not jobs:
            return results
        
        logger.info(f"QA Agent reviewing {len(jobs)} jobs with AI...")
        
        # Process in chunks of 20 to balance API efficiency and accuracy
        CHUNK_SIZE = 20
        for i in range(0, len(jobs), CHUNK_SIZE):
            chunk = jobs[i:i + CHUNK_SIZE]
            chunk_num = (i // CHUNK_SIZE) + 1
            total_chunks = (len(jobs) + CHUNK_SIZE - 1) // CHUNK_SIZE
            
            logger.info(f"  Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} jobs)...")
            
            # Batch validate chunk with AI
            chunk_results = self._validate_batch_prompt(chunk)
            results["approved"].extend(chunk_results.get("approved", []))
            results["quarantined"].extend(chunk_results.get("quarantined", []))
            results["flagged"].extend(chunk_results.get("flagged", []))
        
        logger.info(f"QA Review complete: {len(results['approved'])} approved, "
                   f"{len(results['quarantined'])} quarantined, {len(results['flagged'])} flagged")
        
        return results
    
    def _filter_suspicious_jobs(self, jobs: List[JobRecord]) -> List[JobRecord]:
        """
        Filter to jobs that have suspicious patterns worth checking.
        
        Suspicious patterns:
        - Short titles (< 15 chars)
        - Titles that look like UI elements
        - URLs pointing to generic pages
        - Missing key data
        """
        suspicious = []
        
        # Patterns that suggest UI elements or link text
        ui_patterns = [
            'view', 'click', 'apply', 'see ', 'learn', 'more', 'display',
            'current opening', 'job opening', 'position', 'career'
        ]
        
        # Generic URL endings that suggest non-specific job pages
        generic_url_patterns = [
            '/careers', '/careers/', '/employment', '/employment/',
            '/jobs', '/jobs/', '/job-openings', 'jobs.aspx'
        ]
        
        for job in jobs:
            is_suspicious = False
            
            # Check title length
            if len(job.title) < 15:
                is_suspicious = True
            
            # Check for UI patterns in title
            title_lower = job.title.lower()
            if any(pattern in title_lower for pattern in ui_patterns):
                is_suspicious = True
            
            # Check for generic URLs
            url_lower = job.url.lower()
            if any(url_lower.endswith(pattern) for pattern in generic_url_patterns):
                is_suspicious = True
            
            # Check for special characters that suggest scraping artifacts
            if '*' in job.title or job.title.startswith('[') or job.title.startswith('('):
                is_suspicious = True
            
            if is_suspicious:
                suspicious.append(job)
        
        return suspicious
    
    def _validate_batch_prompt(self, jobs: List[JobRecord]) -> Dict[str, List[AgentResponse]]:
        """Validate job titles using AI - focused on catching false positives"""
        
        # Just send titles with IDs for fast review
        titles_text = "\n".join([
            f"{job.id}: {job.title}"
            for job in jobs
        ])
        
        prompt = f"""Review these {len(jobs)} job titles. Identify any that are NOT real job titles.

FALSE POSITIVES to QUARANTINE:
- Navigation text: "View Jobs", "Current Openings", "Apply Now", "Click Here", "Learn More"
- Menu items: "Loans", "Services", "About", "Contact", "Home"
- Generic text: "Any Position", "Hiring Pool", "Jobs", "Careers", "Employment"
- Page headers: city names, company names alone
- Scraping artifacts: "Display*", "Search", text with asterisks

VALID job titles have a specific role like:
- "Registered Nurse", "Cashier", "Teacher", "Administrative Assistant"
- Even unusual ones like "Geomorphologist" are valid if they describe a specific role

JOB TITLES TO REVIEW:
{titles_text}

Respond with JSON array ONLY (no other text):
[{{"id": 123, "ok": true}}, {{"id": 456, "ok": false, "reason": "navigation link"}}]

Use "ok": true for valid titles, "ok": false for false positives."""

        try:
            response = self._call_llm(prompt)
            results_list = self._parse_json_response(response)
            
            if not isinstance(results_list, list):
                results_list = results_list.get("results", results_list.get("jobs", []))
            
            results = {"approved": [], "quarantined": [], "flagged": []}
            job_map = {job.id: job for job in jobs}
            reviewed_ids = set()
            
            for item in results_list:
                job_id = item.get("id")
                is_ok = item.get("ok", True)
                reason = item.get("reason", "")
                
                job = job_map.get(job_id)
                if not job:
                    continue
                
                reviewed_ids.add(job_id)
                
                if is_ok:
                    action = ActionType.APPROVE
                    summary = f"Valid title: '{job.title}'"
                else:
                    action = ActionType.QUARANTINE
                    summary = f"False positive: '{job.title}' - {reason}"
                
                agent_response = AgentResponse(
                    agent=self.role,
                    success=True,
                    action=action,
                    confidence=0.9,
                    summary=summary,
                    details={"job_id": job_id},
                    recommendations=[reason] if reason else []
                )
                
                if action == ActionType.APPROVE:
                    results["approved"].append(agent_response)
                else:
                    results["quarantined"].append(agent_response)
            
            # Auto-approve any jobs not explicitly mentioned (AI only flags bad ones)
            for job in jobs:
                if job.id not in reviewed_ids:
                    results["approved"].append(AgentResponse(
                        agent=self.role,
                        success=True,
                        action=ActionType.APPROVE,
                        confidence=0.85,
                        summary=f"Valid title: '{job.title}'",
                        details={"job_id": job.id}
                    ))
            
            return results
            
        except Exception as e:
            logger.error(f"Batch validation failed: {e}")
            # On error, approve all (fail open) but log the issue
            return {
                "approved": [
                    AgentResponse(
                        agent=self.role,
                        success=True,
                        action=ActionType.APPROVE,
                        confidence=0.5,
                        summary=f"Auto-approved (QA error): '{job.title}'",
                        details={"job_id": job.id},
                        recommendations=["QA review failed, manual check recommended"]
                    )
                    for job in jobs
                ],
                "quarantined": [],
                "flagged": []
            }
    
    def score_source(self, source_name: str, jobs: List[JobRecord]) -> AgentResponse:
        """
        Generate a quality score for a data source.
        
        Args:
            source_name: Name of the scraper/source
            jobs: All jobs from this source
            
        Returns:
            AgentResponse with quality score and assessment
        """
        if not jobs:
            return AgentResponse(
                agent=self.role,
                success=True,
                action=ActionType.MONITOR,
                confidence=1.0,
                summary=f"Source '{source_name}' has no jobs to score",
                details={"source": source_name, "job_count": 0, "quality_score": 0},
                recommendations=["Check if scraper is working correctly"]
            )
        
        # Calculate basic metrics
        total = len(jobs)
        with_salary = sum(1 for j in jobs if j.salary)
        with_description = sum(1 for j in jobs if j.description and len(j.description) > 50)
        
        # Simple heuristic score
        completeness = ((with_salary / total) * 40 + (with_description / total) * 40 + 20)
        
        prompt = f"""Score this data source for quality:

SOURCE: {source_name}
TOTAL JOBS: {total}
JOBS WITH SALARY: {with_salary} ({with_salary/total*100:.0f}%)
JOBS WITH DESCRIPTION: {with_description} ({with_description/total*100:.0f}%)

SAMPLE TITLES:
{chr(10).join(['- ' + j.title for j in jobs[:10]])}

Rate the source quality (0-100) and provide recommendations.

Respond with JSON:
{{
    "quality_score": 0-100,
    "grade": "A|B|C|D|F",
    "strengths": ["list"],
    "weaknesses": ["list"],
    "recommendations": ["list"]
}}"""

        try:
            response = self._call_llm(prompt)
            result = self._parse_json_response(response)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                action=ActionType.NO_ACTION,
                confidence=0.9,
                summary=f"Source '{source_name}' scored {result.get('quality_score', completeness)}/100 (Grade: {result.get('grade', 'C')})",
                details={
                    "source": source_name,
                    "job_count": total,
                    "quality_score": result.get("quality_score", completeness),
                    "grade": result.get("grade", "C"),
                    "strengths": result.get("strengths", []),
                    "weaknesses": result.get("weaknesses", [])
                },
                recommendations=result.get("recommendations", [])
            )
            
        except Exception as e:
            logger.error(f"Source scoring failed: {e}")
            return AgentResponse(
                agent=self.role,
                success=False,
                action=ActionType.FLAG_REVIEW,
                confidence=0.0,
                summary=f"Source scoring failed: {str(e)}",
                details={"source": source_name, "error": str(e)},
                recommendations=["Manual review required"]
            )
    
    def process(self, data: Any) -> AgentResponse:
        """
        Main entry point - routes to appropriate method.
        
        Args:
            data: Can be a single JobRecord, list of JobRecords, or dict with 'action' key
        """
        if isinstance(data, JobRecord):
            return self.validate_job(data)
        elif isinstance(data, list):
            results = self.validate_batch(data)
            return AgentResponse(
                agent=self.role,
                success=True,
                action=ActionType.NO_ACTION,
                confidence=1.0,
                summary=f"Batch validated: {len(results['approved'])} approved, {len(results['quarantined'])} quarantined, {len(results['flagged'])} flagged",
                details=results
            )
        elif isinstance(data, dict) and data.get("action") == "score_source":
            return self.score_source(data["source_name"], data["jobs"])
        else:
            raise ValueError(f"QAAgent cannot process data type: {type(data)}")
