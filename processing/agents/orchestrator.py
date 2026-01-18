"""
Orchestrator - Multi-Agent Coordinator

Role: Coordinate specialized agents, manage workflows, route tasks.

The Orchestrator:
1. Receives tasks/requests
2. Routes to appropriate agent(s)
3. Manages handoffs between agents
4. Compiles final results
5. Does NOT make decisions itself - delegates to specialists
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .base import AgentRole, AgentResponse, ActionType
from .qa_agent import QAAgent, JobRecord
from .engineer_agent import EngineerAgent, ScraperDiagnostic
from .analyst_agent import AnalystAgent, JobStats

logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """Pre-defined workflow types"""
    POST_SCRAPE = "post_scrape"          # Full QA after scraping
    DATA_REVIEW = "data_review"           # Review existing data
    SCRAPER_DEBUG = "scraper_debug"       # Debug a failing scraper
    MARKET_ANALYSIS = "market_analysis"   # Generate market insights
    FULL_AUDIT = "full_audit"            # Complete system audit


@dataclass
class WorkflowResult:
    """Result from a complete workflow"""
    workflow: WorkflowType
    started_at: datetime
    completed_at: datetime = None
    success: bool = True
    agent_responses: List[AgentResponse] = field(default_factory=list)
    summary: str = ""
    actions_taken: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def complete(self, success: bool = True):
        self.completed_at = datetime.now()
        self.success = success
    
    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0


class Orchestrator:
    """
    Orchestrator coordinates multiple specialized agents.
    
    It does NOT make decisions - it routes tasks to the right agent
    and compiles their responses into actionable results.
    
    Workflow:
    1. Receive request
    2. Determine which agent(s) to involve
    3. Execute agent tasks in proper sequence
    4. Handle handoffs (e.g., QA flags issue → Engineer investigates)
    5. Compile and return results
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize orchestrator with all agents."""
        self.qa_agent = QAAgent(api_key)
        self.engineer_agent = EngineerAgent(api_key)
        self.analyst_agent = AnalystAgent(api_key)
        
        logger.info("Orchestrator initialized with QA, Engineer, and Analyst agents")
    
    def run_workflow(self, workflow: WorkflowType, context: Dict[str, Any]) -> WorkflowResult:
        """
        Run a pre-defined workflow.
        
        Args:
            workflow: Type of workflow to run
            context: Data and parameters for the workflow
            
        Returns:
            WorkflowResult with all agent responses
        """
        result = WorkflowResult(workflow=workflow, started_at=datetime.now())
        
        try:
            if workflow == WorkflowType.POST_SCRAPE:
                self._run_post_scrape(result, context)
            elif workflow == WorkflowType.DATA_REVIEW:
                self._run_data_review(result, context)
            elif workflow == WorkflowType.SCRAPER_DEBUG:
                self._run_scraper_debug(result, context)
            elif workflow == WorkflowType.MARKET_ANALYSIS:
                self._run_market_analysis(result, context)
            elif workflow == WorkflowType.FULL_AUDIT:
                self._run_full_audit(result, context)
            else:
                raise ValueError(f"Unknown workflow: {workflow}")
            
            result.complete(success=True)
            
        except Exception as e:
            logger.error(f"Workflow {workflow.value} failed: {e}")
            result.summary = f"Workflow failed: {str(e)}"
            result.complete(success=False)
        
        return result
    
    def _run_post_scrape(self, result: WorkflowResult, context: Dict[str, Any]):
        """
        Post-scrape workflow:
        1. QA Agent validates new jobs
        2. If sources returned 0 jobs, Engineer Agent diagnoses
        3. Analyst Agent checks for anomalies
        
        Context required:
        - jobs: List[JobRecord] - newly scraped jobs
        - source_results: Dict[str, int] - jobs per source
        - previous_stats: JobStats - for comparison (optional)
        """
        jobs = context.get("jobs", [])
        source_results = context.get("source_results", {})
        
        logger.info(f"Post-scrape workflow: {len(jobs)} jobs from {len(source_results)} sources")
        
        # Step 1: QA Agent validates jobs
        if jobs:
            logger.info("Step 1: QA Agent validating jobs...")
            qa_response = self.qa_agent.validate_batch(jobs)
            
            approved = len(qa_response.get("approved", []))
            quarantined = len(qa_response.get("quarantined", []))
            flagged = len(qa_response.get("flagged", []))
            
            result.agent_responses.extend(qa_response.get("approved", []))
            result.agent_responses.extend(qa_response.get("quarantined", []))
            result.agent_responses.extend(qa_response.get("flagged", []))
            
            result.actions_taken.append(f"QA validated {len(jobs)} jobs: {approved} approved, {quarantined} quarantined, {flagged} flagged")
            
            # Collect quarantined job IDs for action
            if quarantined > 0:
                quarantine_ids = [r.details.get("job_id") for r in qa_response.get("quarantined", [])]
                result.recommendations.append(f"Quarantine {quarantined} false positive jobs: {quarantine_ids}")
        
        # Step 2: Engineer Agent checks failed sources
        failed_sources = [src for src, count in source_results.items() if count == 0]
        if failed_sources:
            logger.info(f"Step 2: Engineer Agent diagnosing {len(failed_sources)} failed sources...")
            for source in failed_sources:
                diagnostic = ScraperDiagnostic(
                    scraper_name=source,
                    actual_jobs=0,
                    url=context.get("source_urls", {}).get(source)
                )
                eng_response = self.engineer_agent.diagnose_scraper(diagnostic)
                result.agent_responses.append(eng_response)
                
                if eng_response.action == ActionType.FIX_REQUIRED:
                    result.recommendations.append(f"Fix required for {source}: {eng_response.summary}")
            
            result.actions_taken.append(f"Engineer diagnosed {len(failed_sources)} failed sources")
        
        # Step 3: Analyst checks for anomalies
        if context.get("current_stats") and context.get("previous_stats"):
            logger.info("Step 3: Analyst Agent checking for anomalies...")
            analyst_response = self.analyst_agent.detect_anomalies(
                context["current_stats"],
                context["previous_stats"]
            )
            result.agent_responses.append(analyst_response)
            
            if analyst_response.action == ActionType.FLAG_REVIEW:
                result.recommendations.extend(analyst_response.recommendations)
            
            result.actions_taken.append("Analyst checked for anomalies")
        
        # Compile summary
        result.summary = f"Post-scrape review complete. {len(jobs)} jobs processed, {len(failed_sources)} sources need attention."
    
    def _run_data_review(self, result: WorkflowResult, context: Dict[str, Any]):
        """
        Data review workflow:
        1. QA Agent reviews specified jobs
        2. QA Agent scores sources
        
        Context required:
        - jobs: List[JobRecord] - jobs to review
        - sources: List[str] - sources to score (optional)
        """
        jobs = context.get("jobs", [])
        sources = context.get("sources", [])
        
        logger.info(f"Data review workflow: {len(jobs)} jobs, {len(sources)} sources")
        
        # Step 1: QA validates jobs
        if jobs:
            qa_response = self.qa_agent.validate_batch(jobs)
            
            approved = len(qa_response.get("approved", []))
            quarantined = len(qa_response.get("quarantined", []))
            flagged = len(qa_response.get("flagged", []))
            
            result.agent_responses.extend(qa_response.get("quarantined", []))
            result.agent_responses.extend(qa_response.get("flagged", []))
            
            result.actions_taken.append(f"Reviewed {len(jobs)} jobs: {approved} OK, {quarantined} issues, {flagged} uncertain")
            
            if quarantined > 0:
                quarantine_ids = [r.details.get("job_id") for r in qa_response.get("quarantined", [])]
                result.recommendations.append(f"Remove {quarantined} false positive jobs: IDs {quarantine_ids}")
        
        # Step 2: Score sources
        if sources:
            jobs_by_source = {}
            for job in jobs:
                src = job.source_name or "unknown"
                if src not in jobs_by_source:
                    jobs_by_source[src] = []
                jobs_by_source[src].append(job)
            
            for source in sources:
                if source in jobs_by_source:
                    score_response = self.qa_agent.score_source(source, jobs_by_source[source])
                    result.agent_responses.append(score_response)
                    
                    score = score_response.details.get("quality_score", 0)
                    if score < 70:
                        result.recommendations.append(f"Source '{source}' has low quality score ({score}/100)")
            
            result.actions_taken.append(f"Scored {len(sources)} sources")
        
        result.summary = f"Data review complete. Reviewed {len(jobs)} jobs across {len(sources)} sources."
    
    def _run_scraper_debug(self, result: WorkflowResult, context: Dict[str, Any]):
        """
        Scraper debug workflow:
        1. Engineer Agent diagnoses the issue
        2. Engineer Agent suggests fixes
        
        Context required:
        - scraper_name: str
        - url: str (optional)
        - html: str (optional)
        - code: str (optional)
        - error: str (optional)
        """
        scraper_name = context.get("scraper_name", "unknown")
        
        logger.info(f"Scraper debug workflow: {scraper_name}")
        
        # Step 1: Diagnose
        diagnostic = ScraperDiagnostic(
            scraper_name=scraper_name,
            url=context.get("url"),
            html_sample=context.get("html"),
            scraper_code=context.get("code"),
            error_message=context.get("error"),
            actual_jobs=context.get("actual_jobs", 0)
        )
        
        diag_response = self.engineer_agent.diagnose_scraper(diagnostic)
        result.agent_responses.append(diag_response)
        result.actions_taken.append(f"Diagnosed {scraper_name}: {diag_response.details.get('root_cause', 'unknown')}")
        
        # Step 2: If HTML provided, analyze it
        if context.get("html"):
            html_response = self.engineer_agent.analyze_html(
                context.get("url", ""),
                context["html"]
            )
            result.agent_responses.append(html_response)
            
            selectors = html_response.details.get("selectors", {})
            if selectors:
                result.recommendations.append(f"Suggested selectors: {selectors}")
        
        # Step 3: If code provided and fix needed, suggest fix
        if context.get("code") and diag_response.action == ActionType.FIX_REQUIRED:
            fix_response = self.engineer_agent.suggest_fix(
                context["code"],
                diag_response.summary
            )
            result.agent_responses.append(fix_response)
            
            if fix_response.details.get("fixed_code"):
                result.recommendations.append("Code fix suggested - see details")
        
        result.summary = f"Scraper debug complete for {scraper_name}. Root cause: {diag_response.details.get('root_cause', 'unknown')}"
        result.recommendations.extend(diag_response.recommendations)
    
    def _run_market_analysis(self, result: WorkflowResult, context: Dict[str, Any]):
        """
        Market analysis workflow:
        1. Analyst generates current state analysis
        2. Analyst generates report
        
        Context required:
        - stats: JobStats
        - previous_stats: JobStats (optional)
        - report_period: str (optional, default 'weekly')
        """
        stats = context.get("stats")
        if not stats:
            raise ValueError("stats required for market analysis")
        
        logger.info(f"Market analysis workflow: {stats.total_jobs} total jobs")
        
        # Step 1: Analyze current state
        analysis = self.analyst_agent.analyze_current_state(stats)
        result.agent_responses.append(analysis)
        result.actions_taken.append("Analyzed current market state")
        
        # Step 2: Compare with previous if available
        if context.get("previous_stats"):
            anomaly_check = self.analyst_agent.detect_anomalies(
                stats, 
                context["previous_stats"]
            )
            result.agent_responses.append(anomaly_check)
            result.actions_taken.append("Compared with previous period")
            
            if anomaly_check.action == ActionType.FLAG_REVIEW:
                result.recommendations.extend(anomaly_check.recommendations)
        
        # Step 3: Generate report
        report_period = context.get("report_period", "weekly")
        report = self.analyst_agent.generate_report(stats, report_period)
        result.agent_responses.append(report)
        result.actions_taken.append(f"Generated {report_period} report")
        
        result.summary = analysis.summary
        result.recommendations.extend(analysis.recommendations)
    
    def _run_full_audit(self, result: WorkflowResult, context: Dict[str, Any]):
        """
        Full audit workflow - runs all checks:
        1. QA reviews all jobs
        2. QA scores all sources
        3. Analyst analyzes market
        4. Engineer checks any failing sources
        
        Context required:
        - jobs: List[JobRecord]
        - stats: JobStats
        - source_results: Dict[str, int]
        """
        logger.info("Full audit workflow starting...")
        
        # Run data review
        self._run_data_review(result, context)
        
        # Run market analysis
        if context.get("stats"):
            self._run_market_analysis(result, context)
        
        # Check failed sources
        source_results = context.get("source_results", {})
        failed_sources = [src for src, count in source_results.items() if count == 0]
        
        for source in failed_sources:
            self._run_scraper_debug(result, {
                "scraper_name": source,
                "actual_jobs": 0
            })
        
        result.summary = f"Full audit complete. {len(context.get('jobs', []))} jobs, {len(failed_sources)} sources need attention."
    
    def quick_qa(self, jobs: List[JobRecord]) -> Dict[str, List[AgentResponse]]:
        """
        Quick QA check - just validate jobs without full workflow.
        
        Args:
            jobs: List of JobRecord to validate
            
        Returns:
            Dict with approved, quarantined, flagged lists
        """
        return self.qa_agent.validate_batch(jobs)
    
    def debug_scraper(self, scraper_name: str, **kwargs) -> AgentResponse:
        """
        Quick scraper debug - just diagnose without full workflow.
        """
        diagnostic = ScraperDiagnostic(
            scraper_name=scraper_name,
            **kwargs
        )
        return self.engineer_agent.diagnose_scraper(diagnostic)
    
    def get_market_insights(self, stats: JobStats) -> AgentResponse:
        """
        Quick market insights - just analyze without full workflow.
        """
        return self.analyst_agent.analyze_current_state(stats)
    
    def run_qa_review(self, session, auto_quarantine: bool = True) -> Dict[str, Any]:
        """
        Run AI QA review on all active jobs and optionally auto-quarantine bad ones.
        
        This is the main QA gate that should run before generating the static site.
        
        Args:
            session: Database session
            auto_quarantine: If True, automatically quarantine jobs marked by AI
            
        Returns:
            Dict with review results and actions taken
        """
        from db.models import Job
        from datetime import datetime
        
        logger.info("=" * 60)
        logger.info("AI QA REVIEW - Reviewing all active jobs")
        logger.info("=" * 60)
        
        # Get all active, non-quarantined jobs
        jobs = session.query(Job).filter(
            Job.is_active == True,
            Job.is_quarantined == False
        ).all()
        
        if not jobs:
            logger.info("No jobs to review.")
            return {"total": 0, "approved": 0, "quarantined": 0, "flagged": 0}
        
        logger.info(f"Found {len(jobs)} active jobs to review")
        
        # Convert to JobRecord format for QA agent
        job_records = [
            JobRecord(
                id=job.id,
                title=job.title,
                employer=job.employer,
                location=job.location or "",
                url=job.url,
                salary=job.salary_text,
                description=job.description,
                source_name=job.source_name
            )
            for job in jobs
        ]
        
        # Run AI QA review
        results = self.qa_agent.validate_batch(job_records)
        
        approved_count = len(results.get("approved", []))
        quarantined_responses = results.get("quarantined", [])
        flagged_responses = results.get("flagged", [])
        
        # Auto-quarantine if enabled
        quarantined_count = 0
        if auto_quarantine and quarantined_responses:
            quarantine_ids = [r.details.get("job_id") for r in quarantined_responses if r.details.get("job_id")]
            
            logger.info(f"\nAuto-quarantining {len(quarantine_ids)} false positives...")
            
            for response in quarantined_responses:
                job_id = response.details.get("job_id")
                if job_id:
                    job = session.query(Job).filter(Job.id == job_id).first()
                    if job:
                        reason = response.recommendations[0] if response.recommendations else "Flagged by AI QA"
                        job.is_quarantined = True
                        job.qa_reviewed_at = datetime.utcnow()
                        job.qa_reason = reason[:255]
                        quarantined_count += 1
                        logger.info(f"  ❌ Quarantined: \"{job.title}\" from {job.employer} - {reason}")
            
            session.commit()
        
        # Log flagged jobs that need human review
        if flagged_responses:
            logger.info(f"\n⚠️  {len(flagged_responses)} jobs flagged for human review:")
            for response in flagged_responses[:10]:  # Show first 10
                job_id = response.details.get("job_id")
                job = session.query(Job).filter(Job.id == job_id).first() if job_id else None
                if job:
                    logger.info(f"  ⚠️  \"{job.title}\" from {job.employer}")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("QA REVIEW SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  Total reviewed:  {len(jobs)}")
        logger.info(f"  ✓ Approved:      {approved_count}")
        logger.info(f"  ❌ Quarantined:  {quarantined_count}")
        logger.info(f"  ⚠️  Flagged:      {len(flagged_responses)}")
        logger.info("=" * 60)
        
        return {
            "total": len(jobs),
            "approved": approved_count,
            "quarantined": quarantined_count,
            "flagged": len(flagged_responses),
            "quarantined_ids": [r.details.get("job_id") for r in quarantined_responses],
            "flagged_ids": [r.details.get("job_id") for r in flagged_responses]
        }
    
    def run_engineer_debug(self, source_name: str) -> AgentResponse:
        """Run Engineer Agent to debug a scraper."""
        diagnostic = ScraperDiagnostic(scraper_name=source_name, actual_jobs=0)
        return self.engineer_agent.diagnose_scraper(diagnostic)
    
    def run_analyst_analysis(self, session) -> AgentResponse:
        """Run Analyst Agent for market analysis."""
        from db.models import Job
        from sqlalchemy import func
        
        # Build stats from database
        total = session.query(func.count(Job.id)).filter(Job.is_active == True).scalar()
        by_category = dict(session.query(Job.category, func.count(Job.id)).filter(Job.is_active == True).group_by(Job.category).all())
        by_employer = dict(session.query(Job.employer, func.count(Job.id)).filter(Job.is_active == True).group_by(Job.employer).all())
        
        stats = JobStats(
            total_jobs=total,
            jobs_by_category=by_category,
            jobs_by_employer=by_employer
        )
        
        return self.analyst_agent.analyze_current_state(stats)
