"""
Engineer Agent - Scraper Debugging Specialist

Role: Debug scrapers, analyze HTML, diagnose issues, suggest code fixes.

This agent ONLY focuses on technical scraper issues. It does not:
- Validate data quality (that's QAAgent)
- Analyze market trends (that's AnalystAgent)
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .base import BaseAgent, AgentRole, AgentResponse, ActionType

logger = logging.getLogger(__name__)


@dataclass
class ScraperDiagnostic:
    """Input data for scraper debugging"""
    scraper_name: str
    scraper_code: Optional[str] = None
    html_sample: Optional[str] = None
    error_message: Optional[str] = None
    expected_jobs: Optional[int] = None
    actual_jobs: int = 0
    last_successful_run: Optional[str] = None
    url: Optional[str] = None


class EngineerAgent(BaseAgent):
    """
    Engineer Agent specializes in scraper debugging and maintenance.
    
    Responsibilities:
    - Diagnose why a scraper returns 0 jobs
    - Analyze HTML structure changes
    - Suggest code fixes for broken scrapers
    - Identify selector changes needed
    - Detect anti-scraping measures
    """
    
    @property
    def role(self) -> AgentRole:
        return AgentRole.ENGINEER
    
    @property
    def system_prompt(self) -> str:
        return """You are a Data Engineer Agent specializing in web scraping.

YOUR ROLE: Debug and fix web scrapers that aren't working correctly.

YOU MUST ONLY:
- Analyze HTML to find job listing elements
- Identify CSS selectors or XPath for job data
- Diagnose why scrapers return 0 jobs
- Detect website structure changes
- Suggest specific code fixes
- Identify anti-scraping measures (CAPTCHAs, JavaScript rendering, rate limiting)

YOU MUST NOT:
- Validate job data quality (that's the QA Agent's job)
- Analyze job market trends (that's the Analyst Agent's job)
- Make business decisions about which jobs to keep

COMMON SCRAPER ISSUES:
1. Website HTML structure changed (new selectors needed)
2. JavaScript-rendered content (need Playwright/Selenium)
3. Anti-bot protection (CAPTCHA, Cloudflare)
4. Rate limiting (need delays)
5. Session/cookie requirements
6. API endpoint changes
7. Empty job board (legitimately no jobs posted)

RESPONSE FORMAT (JSON only):
{
    "diagnosis": "brief description of the issue",
    "root_cause": "STRUCTURE_CHANGE|JS_RENDERING|ANTI_BOT|RATE_LIMIT|API_CHANGE|NO_JOBS|UNKNOWN",
    "confidence": 0.0-1.0,
    "selectors": {
        "job_list": "suggested CSS selector for job container",
        "job_title": "selector for title",
        "job_url": "selector for link"
    },
    "code_fix": "specific code changes needed",
    "recommendations": ["list of action items"]
}"""
    
    def diagnose_scraper(self, diagnostic: ScraperDiagnostic) -> AgentResponse:
        """
        Diagnose why a scraper isn't returning jobs.
        
        Args:
            diagnostic: ScraperDiagnostic with context about the issue
            
        Returns:
            AgentResponse with diagnosis and fix suggestions
        """
        context_parts = [
            f"SCRAPER: {diagnostic.scraper_name}",
            f"URL: {diagnostic.url or 'Not provided'}",
            f"EXPECTED JOBS: {diagnostic.expected_jobs or 'Unknown'}",
            f"ACTUAL JOBS: {diagnostic.actual_jobs}",
        ]
        
        if diagnostic.error_message:
            context_parts.append(f"ERROR: {diagnostic.error_message}")
        
        if diagnostic.last_successful_run:
            context_parts.append(f"LAST SUCCESS: {diagnostic.last_successful_run}")
        
        prompt = "\n".join(context_parts)
        
        if diagnostic.html_sample:
            # Truncate HTML to avoid token limits
            html_truncated = diagnostic.html_sample[:4000]
            prompt += f"\n\nHTML SAMPLE (truncated):\n```html\n{html_truncated}\n```"
        
        if diagnostic.scraper_code:
            code_truncated = diagnostic.scraper_code[:2000]
            prompt += f"\n\nCURRENT SCRAPER CODE:\n```python\n{code_truncated}\n```"
        
        prompt += """

Diagnose the issue and provide:
1. What's causing the scraper to fail?
2. What selectors should be used?
3. What code changes are needed?

Respond with JSON only."""

        try:
            response = self._call_llm(prompt)
            result = self._parse_json_response(response)
            
            # Map root cause to action
            root_cause = result.get("root_cause", "UNKNOWN")
            action_map = {
                "STRUCTURE_CHANGE": ActionType.FIX_REQUIRED,
                "JS_RENDERING": ActionType.FIX_REQUIRED,
                "ANTI_BOT": ActionType.FLAG_REVIEW,
                "RATE_LIMIT": ActionType.FIX_REQUIRED,
                "API_CHANGE": ActionType.FIX_REQUIRED,
                "NO_JOBS": ActionType.NO_ACTION,
                "UNKNOWN": ActionType.FLAG_REVIEW
            }
            
            return AgentResponse(
                agent=self.role,
                success=True,
                action=action_map.get(root_cause, ActionType.FLAG_REVIEW),
                confidence=float(result.get("confidence", 0.5)),
                summary=f"Scraper '{diagnostic.scraper_name}': {result.get('diagnosis', 'Unknown issue')}",
                details={
                    "scraper": diagnostic.scraper_name,
                    "root_cause": root_cause,
                    "selectors": result.get("selectors", {}),
                    "code_fix": result.get("code_fix", "")
                },
                recommendations=result.get("recommendations", []),
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Scraper diagnosis failed: {e}")
            return AgentResponse(
                agent=self.role,
                success=False,
                action=ActionType.FLAG_REVIEW,
                confidence=0.0,
                summary=f"Diagnosis failed: {str(e)}",
                details={"scraper": diagnostic.scraper_name, "error": str(e)},
                recommendations=["Manual inspection required"]
            )
    
    def analyze_html(self, url: str, html: str) -> AgentResponse:
        """
        Analyze HTML to find job listing elements.
        
        Args:
            url: The URL of the page
            html: Raw HTML content
            
        Returns:
            AgentResponse with suggested selectors
        """
        # Truncate HTML to fit in context
        html_truncated = html[:6000] if len(html) > 6000 else html
        
        prompt = f"""Analyze this HTML to find job listing elements:

URL: {url}

HTML:
```html
{html_truncated}
```

Find the CSS selectors for:
1. Job listing container (the list/grid of all jobs)
2. Individual job card/item
3. Job title
4. Job URL/link
5. Employer name (if present)
6. Location (if present)
7. Salary (if present)

Respond with JSON:
{{
    "job_container": "CSS selector",
    "job_item": "CSS selector",
    "title": "CSS selector",
    "url": "CSS selector or attribute",
    "employer": "CSS selector or null",
    "location": "CSS selector or null",
    "salary": "CSS selector or null",
    "notes": "any important observations"
}}"""

        try:
            response = self._call_llm(prompt)
            result = self._parse_json_response(response)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                action=ActionType.NO_ACTION,
                confidence=0.8,
                summary=f"HTML analysis complete for {url}",
                details={
                    "url": url,
                    "selectors": result,
                    "notes": result.get("notes", "")
                },
                recommendations=[
                    f"Use '{result.get('job_container', 'N/A')}' for job container",
                    f"Use '{result.get('title', 'N/A')}' for job titles"
                ],
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"HTML analysis failed: {e}")
            return AgentResponse(
                agent=self.role,
                success=False,
                action=ActionType.FLAG_REVIEW,
                confidence=0.0,
                summary=f"HTML analysis failed: {str(e)}",
                details={"url": url, "error": str(e)},
                recommendations=["Manual inspection required"]
            )
    
    def suggest_fix(self, scraper_code: str, issue_description: str) -> AgentResponse:
        """
        Suggest code fixes for a broken scraper.
        
        Args:
            scraper_code: Current scraper Python code
            issue_description: Description of what's broken
            
        Returns:
            AgentResponse with suggested code changes
        """
        code_truncated = scraper_code[:3000] if len(scraper_code) > 3000 else scraper_code
        
        prompt = f"""Fix this scraper code:

ISSUE: {issue_description}

CURRENT CODE:
```python
{code_truncated}
```

Provide the fixed code with explanations.

Respond with JSON:
{{
    "issue_found": "description of the bug",
    "fix_explanation": "what needs to change",
    "fixed_code": "the corrected Python code snippet",
    "testing_suggestions": ["how to verify the fix works"]
}}"""

        try:
            response = self._call_llm(prompt)
            result = self._parse_json_response(response)
            
            return AgentResponse(
                agent=self.role,
                success=True,
                action=ActionType.FIX_REQUIRED,
                confidence=0.7,
                summary=f"Fix suggested: {result.get('issue_found', 'Issue identified')}",
                details={
                    "issue": result.get("issue_found", ""),
                    "explanation": result.get("fix_explanation", ""),
                    "fixed_code": result.get("fixed_code", "")
                },
                recommendations=result.get("testing_suggestions", []),
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Fix suggestion failed: {e}")
            return AgentResponse(
                agent=self.role,
                success=False,
                action=ActionType.FLAG_REVIEW,
                confidence=0.0,
                summary=f"Fix suggestion failed: {str(e)}",
                details={"error": str(e)},
                recommendations=["Manual code review required"]
            )
    
    def process(self, data: Any) -> AgentResponse:
        """
        Main entry point - routes to appropriate method.
        
        Args:
            data: ScraperDiagnostic or dict with 'action' key
        """
        if isinstance(data, ScraperDiagnostic):
            return self.diagnose_scraper(data)
        elif isinstance(data, dict):
            action = data.get("action")
            if action == "analyze_html":
                return self.analyze_html(data["url"], data["html"])
            elif action == "suggest_fix":
                return self.suggest_fix(data["code"], data["issue"])
            elif action == "diagnose":
                diagnostic = ScraperDiagnostic(
                    scraper_name=data.get("scraper_name", "unknown"),
                    url=data.get("url"),
                    html_sample=data.get("html"),
                    error_message=data.get("error"),
                    actual_jobs=data.get("actual_jobs", 0),
                    scraper_code=data.get("code")
                )
                return self.diagnose_scraper(diagnostic)
        
        raise ValueError(f"EngineerAgent cannot process data type: {type(data)}")
