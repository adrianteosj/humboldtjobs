"""
Analyst Agent - Data Analysis & Insights Specialist

Role: Identify trends, anomalies, and generate insights from job data.

This agent ONLY focuses on analysis. It does not:
- Validate individual jobs (that's QAAgent)
- Debug scrapers (that's EngineerAgent)
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from .base import BaseAgent, AgentRole, AgentResponse, ActionType

logger = logging.getLogger(__name__)


@dataclass
class JobStats:
    """Aggregated job statistics for analysis"""
    total_jobs: int
    jobs_by_category: Dict[str, int]
    jobs_by_employer: Dict[str, int]
    jobs_by_location: Dict[str, int]
    jobs_with_salary: int
    new_jobs_today: int
    jobs_removed_today: int
    date: str = None
    
    def __post_init__(self):
        if not self.date:
            self.date = datetime.now().strftime("%Y-%m-%d")


@dataclass  
class HistoricalData:
    """Historical job data for trend analysis"""
    dates: List[str]
    total_jobs: List[int]
    new_jobs: List[int]
    removed_jobs: List[int]


class AnalystAgent(BaseAgent):
    """
    Analyst Agent specializes in data analysis and insights.
    
    Responsibilities:
    - Identify trends in job postings
    - Detect anomalies (sudden drops, unusual patterns)
    - Generate market insights
    - Compare sources and employers
    - Provide actionable recommendations
    """
    
    @property
    def role(self) -> AgentRole:
        return AgentRole.ANALYST
    
    @property
    def system_prompt(self) -> str:
        return """You are a Data Analyst Agent for a job board in Humboldt County, California.

YOUR ROLE: Analyze job market data and provide insights.

YOU MUST ONLY:
- Identify trends in job postings (growing/declining categories)
- Detect anomalies (sudden job count drops, unusual patterns)
- Compare employer hiring patterns
- Analyze salary ranges by category
- Generate actionable insights for job seekers
- Flag data quality concerns for the QA Agent

YOU MUST NOT:
- Validate individual job listings (that's the QA Agent's job)
- Debug scraper code (that's the Engineer Agent's job)
- Make changes to data or code

HUMBOLDT COUNTY CONTEXT:
- Major employers: Cal Poly Humboldt, Providence Healthcare, County government
- Key industries: Education, Healthcare, Government, Timber, Tourism
- Population: ~135,000
- Remote/rural area with limited job market

ANOMALY TRIGGERS:
- Source job count drops >50% from previous run
- New source has 0 jobs (possible scraper issue)
- Salary outliers (>$200k or <$15/hr for non-intern roles)
- Employer suddenly missing from data

RESPONSE FORMAT (JSON only):
{
    "insights": ["list of key insights"],
    "anomalies": [{"type": "...", "description": "...", "severity": "HIGH|MEDIUM|LOW"}],
    "trends": {"growing": ["categories"], "declining": ["categories"]},
    "recommendations": ["actionable items"],
    "market_summary": "brief market overview"
}"""
    
    def analyze_current_state(self, stats: JobStats) -> AgentResponse:
        """
        Analyze current job market state.
        
        Args:
            stats: Current JobStats snapshot
            
        Returns:
            AgentResponse with insights
        """
        # Build context for analysis
        top_employers = sorted(stats.jobs_by_employer.items(), key=lambda x: x[1], reverse=True)[:10]
        top_categories = sorted(stats.jobs_by_category.items(), key=lambda x: x[1], reverse=True)[:10]
        top_locations = sorted(stats.jobs_by_location.items(), key=lambda x: x[1], reverse=True)[:10]
        
        salary_rate = (stats.jobs_with_salary / stats.total_jobs * 100) if stats.total_jobs > 0 else 0
        
        prompt = f"""Analyze this job market snapshot for Humboldt County:

DATE: {stats.date}
TOTAL JOBS: {stats.total_jobs}
NEW TODAY: {stats.new_jobs_today}
REMOVED TODAY: {stats.jobs_removed_today}
JOBS WITH SALARY: {stats.jobs_with_salary} ({salary_rate:.0f}%)

TOP EMPLOYERS:
{chr(10).join([f'  - {emp}: {count} jobs' for emp, count in top_employers])}

TOP CATEGORIES:
{chr(10).join([f'  - {cat}: {count} jobs' for cat, count in top_categories])}

TOP LOCATIONS:
{chr(10).join([f'  - {loc}: {count} jobs' for loc, count in top_locations])}

Provide:
1. Key insights about the job market
2. Any anomalies or concerns
3. Trends you observe
4. Recommendations for job seekers

Respond with JSON only."""

        try:
            response = self._call_llm(prompt)
            result = self._parse_json_response(response)
            
            # Check for anomalies that need action
            anomalies = result.get("anomalies", [])
            has_high_severity = any(a.get("severity") == "HIGH" for a in anomalies)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                action=ActionType.FLAG_REVIEW if has_high_severity else ActionType.NO_ACTION,
                confidence=0.85,
                summary=result.get("market_summary", f"Analyzed {stats.total_jobs} jobs in Humboldt County"),
                details={
                    "date": stats.date,
                    "total_jobs": stats.total_jobs,
                    "insights": result.get("insights", []),
                    "anomalies": anomalies,
                    "trends": result.get("trends", {})
                },
                recommendations=result.get("recommendations", []),
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return AgentResponse(
                agent=self.role,
                success=False,
                action=ActionType.FLAG_REVIEW,
                confidence=0.0,
                summary=f"Analysis failed: {str(e)}",
                details={"error": str(e)},
                recommendations=["Manual analysis required"]
            )
    
    def detect_anomalies(self, current: JobStats, previous: JobStats) -> AgentResponse:
        """
        Detect anomalies by comparing current and previous stats.
        
        Args:
            current: Current JobStats
            previous: Previous JobStats for comparison
            
        Returns:
            AgentResponse with anomalies found
        """
        # Calculate changes
        total_change = current.total_jobs - previous.total_jobs
        total_change_pct = (total_change / previous.total_jobs * 100) if previous.total_jobs > 0 else 0
        
        # Find employer changes
        employer_changes = []
        all_employers = set(current.jobs_by_employer.keys()) | set(previous.jobs_by_employer.keys())
        for emp in all_employers:
            curr_count = current.jobs_by_employer.get(emp, 0)
            prev_count = previous.jobs_by_employer.get(emp, 0)
            if prev_count > 0 and curr_count == 0:
                employer_changes.append(f"{emp}: disappeared (was {prev_count} jobs)")
            elif prev_count > 5 and curr_count < prev_count * 0.5:
                employer_changes.append(f"{emp}: dropped {prev_count} → {curr_count}")
        
        prompt = f"""Detect anomalies in this job data comparison:

CURRENT ({current.date}):
  Total: {current.total_jobs}
  New: {current.new_jobs_today}
  Removed: {current.jobs_removed_today}

PREVIOUS ({previous.date}):
  Total: {previous.total_jobs}

CHANGE: {total_change:+d} jobs ({total_change_pct:+.1f}%)

EMPLOYER CHANGES:
{chr(10).join([f'  - {c}' for c in employer_changes]) if employer_changes else '  None significant'}

Identify any anomalies that need attention:
- Sudden drops in job counts
- Missing employers
- Unusual patterns

Respond with JSON:
{{
    "anomalies": [
        {{"type": "...", "description": "...", "severity": "HIGH|MEDIUM|LOW", "action": "..."}}
    ],
    "summary": "overall assessment",
    "requires_investigation": true/false
}}"""

        try:
            response = self._call_llm(prompt)
            result = self._parse_json_response(response)
            
            anomalies = result.get("anomalies", [])
            requires_investigation = result.get("requires_investigation", False)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                action=ActionType.FLAG_REVIEW if requires_investigation else ActionType.NO_ACTION,
                confidence=0.9,
                summary=result.get("summary", f"Compared {current.date} vs {previous.date}"),
                details={
                    "current_date": current.date,
                    "previous_date": previous.date,
                    "total_change": total_change,
                    "change_percent": total_change_pct,
                    "anomalies": anomalies,
                    "employer_changes": employer_changes
                },
                recommendations=[a.get("action", "") for a in anomalies if a.get("action")],
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return AgentResponse(
                agent=self.role,
                success=False,
                action=ActionType.FLAG_REVIEW,
                confidence=0.0,
                summary=f"Anomaly detection failed: {str(e)}",
                details={"error": str(e)},
                recommendations=["Manual comparison required"]
            )
    
    def generate_report(self, stats: JobStats, period: str = "weekly") -> AgentResponse:
        """
        Generate a comprehensive market report.
        
        Args:
            stats: Current JobStats
            period: Report period (daily, weekly, monthly)
            
        Returns:
            AgentResponse with formatted report
        """
        top_employers = sorted(stats.jobs_by_employer.items(), key=lambda x: x[1], reverse=True)[:15]
        top_categories = sorted(stats.jobs_by_category.items(), key=lambda x: x[1], reverse=True)
        
        prompt = f"""Generate a {period} job market report for Humboldt County:

SNAPSHOT DATE: {stats.date}
TOTAL ACTIVE JOBS: {stats.total_jobs}
JOBS WITH SALARY INFO: {stats.jobs_with_salary}

EMPLOYERS (top 15):
{chr(10).join([f'  {emp}: {count}' for emp, count in top_employers])}

CATEGORIES:
{chr(10).join([f'  {cat}: {count}' for cat, count in top_categories])}

Write a professional report with:
1. Executive summary (2-3 sentences)
2. Key highlights
3. Market trends
4. Recommendations for job seekers
5. Data quality notes

Respond with JSON:
{{
    "title": "report title",
    "executive_summary": "...",
    "highlights": ["..."],
    "trends": ["..."],
    "job_seeker_tips": ["..."],
    "data_notes": ["..."]
}}"""

        try:
            response = self._call_llm(prompt)
            result = self._parse_json_response(response)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                action=ActionType.NO_ACTION,
                confidence=0.9,
                summary=result.get("executive_summary", f"{period.capitalize()} report generated"),
                details={
                    "title": result.get("title", f"Humboldt Jobs {period.capitalize()} Report"),
                    "period": period,
                    "date": stats.date,
                    "highlights": result.get("highlights", []),
                    "trends": result.get("trends", []),
                    "job_seeker_tips": result.get("job_seeker_tips", []),
                    "data_notes": result.get("data_notes", [])
                },
                recommendations=result.get("job_seeker_tips", []),
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return AgentResponse(
                agent=self.role,
                success=False,
                action=ActionType.FLAG_REVIEW,
                confidence=0.0,
                summary=f"Report generation failed: {str(e)}",
                details={"error": str(e)},
                recommendations=["Manual report creation required"]
            )
    
    def process(self, data: Any) -> AgentResponse:
        """
        Main entry point - routes to appropriate method.
        
        Args:
            data: JobStats or dict with 'action' key
        """
        if isinstance(data, JobStats):
            return self.analyze_current_state(data)
        elif isinstance(data, dict):
            action = data.get("action")
            if action == "analyze":
                return self.analyze_current_state(data["stats"])
            elif action == "detect_anomalies":
                return self.detect_anomalies(data["current"], data["previous"])
            elif action == "report":
                return self.generate_report(data["stats"], data.get("period", "weekly"))
        
        raise ValueError(f"AnalystAgent cannot process data type: {type(data)}")
