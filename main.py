#!/usr/bin/env python3
"""
Humboldt County Jobs Aggregator - CLI Entry Point

Usage:
    python main.py                    # Run all scrapers
    python main.py --sources neogov   # Run specific scraper
    python main.py --list             # List recent jobs
    python main.py --stats            # Show statistics
"""

import argparse
import logging
from datetime import datetime
from typing import List, Optional

from db.database import init_db, get_session
from db.models import Job, Employer, ScrapeLog, SalaryIssueLog
from scrapers import (
    NEOGOVScraper, CSUScraper, EdJoinScraper, ArcataScraper,
    WiyotScraper, RioDellScraper, RedwoodsScraper,
    BlueLakeScraper, FerndaleScraper, TrinidadScraper,
    # Tier 2 Healthcare
    OpenDoorHealthScraper, ProvidenceScraper, MadRiverHospitalScraper,
    UnitedIndianHealthScraper, KimawMedicalScraper, HospiceOfHumboldtScraper,
    HumboldtSeniorResourceScraper, RCAAScraper, SoHumHealthScraper,
    # Tier 3 Local Employers
    BlueLakeCasinoScraper, BearRiverCasinoScraper, GreenDiamondScraper,
    NorthCoastCoopScraper, LACOAssociatesScraper, EurekaNaturalFoodsScraper,
    DancoGroupScraper,
    # Tier 3B National Retailers
    DollarGeneralScraper, WalgreensScraper, TJMaxxScraper, CostcoScraper,
    SafewayScraper, WalmartScraper,
    # Tier 3B Banks
    CoastCentralCUScraper, CompassCCUScraper, TriCountiesBankScraper,
    RedwoodCapitalBankScraper, ColumbiaBankScraper,
    # Tier 3B Nonprofit/Social Services
    RRHCScraper, TwoFeathersScraper, ChangingTidesScraper,
    # Tier 3C Additional Employers
    RCEAScraper, FoodForPeopleScraper, BGCRedwoodsScraper,
    KokatatScraper, LostCoastBreweryScraper, MurphysMarketsScraper,
    CypressGroveScraper, DriscollsScraper, WinCoFoodsScraper,
    GroceryOutletScraper, HarborFreightScraper, AceHardwareScraper,
    SierraPacificScraper, CVSHealthScraper, RiteAidScraper,
    StarbucksScraper, FedExScraper, UPSScraper, PGEScraper,
    HumboldtSawmillScraper, HumboldtCreameryScraper, AlexandreFamilyFarmScraper,
    PacificSeafoodScraper, ArcataHouseScraper, PiersonBuildingScraper,
    CCraneScraper, JonesFamilyTreeServiceScraper,
    JobData
)
from processing import CategoryNormalizer, deduplicate_by_url
from processing.normalizer import normalize_location

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_ai_qa_review(session) -> dict:
    """
    Run AI QA review on active jobs to catch false positives.
    
    This reviews job TITLES using Gemini AI and auto-quarantines bad ones.
    
    Args:
        session: Database session
        
    Returns:
        Dict with QA results
    """
    import os
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        # Try loading from .env
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('GEMINI_API_KEY')
        except ImportError:
            pass
    
    if not api_key:
        print("\n  ⚠️  Skipping AI QA review (GEMINI_API_KEY not found)")
        return {"skipped": True}
    
    try:
        from processing.agents.orchestrator import Orchestrator
        
        print("\n  🤖 Running AI QA review on job titles...")
        orchestrator = Orchestrator(api_key)
        results = orchestrator.run_qa_review(session, auto_quarantine=True)
        
        if results.get("quarantined", 0) > 0:
            print(f"    ❌ Quarantined {results['quarantined']} false positives")
        else:
            print(f"    ✓ All {results.get('approved', 0)} job titles look valid")
        
        return results
        
    except Exception as e:
        logger.error(f"AI QA review failed: {e}")
        print(f"\n  ⚠️  AI QA review failed: {e}")
        return {"error": str(e)}


def save_jobs(jobs: List[JobData], session, normalizer: CategoryNormalizer) -> tuple:
    """
    Save jobs to database with category normalization.
    
    Args:
        jobs: List of JobData objects
        session: Database session
        normalizer: CategoryNormalizer instance
        
    Returns:
        Tuple of (inserted_count, updated_count, new_job_urls)
    """
    inserted = 0
    updated = 0
    new_job_urls = []  # Track URLs of newly inserted jobs
    
    for job_data in jobs:
        # Normalize category
        normalized_category = normalizer.normalize(
            title=job_data.title,
            original_category=job_data.original_category,
            employer=job_data.employer
        )
        
        # Normalize location to "City, CA" format
        normalized_location = normalize_location(job_data.location)
        
        # Check if job already exists by URL
        existing = session.query(Job).filter(Job.url == job_data.url).first()
        
        if existing:
            # Update existing job
            existing.title = job_data.title
            existing.employer = job_data.employer
            existing.category = normalized_category
            existing.original_category = job_data.original_category
            existing.location = normalized_location
            existing.description = job_data.description
            existing.salary_text = job_data.salary_text
            existing.salary_min = job_data.salary_min
            existing.salary_max = job_data.salary_max
            existing.salary_type = job_data.salary_type
            existing.job_type = job_data.job_type
            existing.experience_level = job_data.experience_level
            existing.education_required = job_data.education_required
            existing.requirements = job_data.requirements
            existing.benefits = job_data.benefits
            existing.department = job_data.department
            existing.is_remote = job_data.is_remote
            existing.posted_date = job_data.posted_date
            existing.closing_date = job_data.closing_date
            existing.updated_at = datetime.utcnow()
            existing.is_active = True
            updated += 1
        else:
            # Insert new job
            job = Job(
                source_id=job_data.source_id,
                source_name=job_data.source_name,
                title=job_data.title,
                employer=job_data.employer,
                category=normalized_category,
                original_category=job_data.original_category,
                location=normalized_location,
                url=job_data.url,
                description=job_data.description,
                salary_text=job_data.salary_text,
                salary_min=job_data.salary_min,
                salary_max=job_data.salary_max,
                salary_type=job_data.salary_type,
                job_type=job_data.job_type,
                experience_level=job_data.experience_level,
                education_required=job_data.education_required,
                requirements=job_data.requirements,
                benefits=job_data.benefits,
                department=job_data.department,
                is_remote=job_data.is_remote,
                posted_date=job_data.posted_date,
                closing_date=job_data.closing_date,
            )
            session.add(job)
            new_job_urls.append(job_data.url)
            inserted += 1
    
    session.commit()
    return inserted, updated, new_job_urls


def update_employer_counts(session):
    """
    Update or create employer records with job counts.
    
    Args:
        session: Database session
    """
    # Get job counts by employer
    from sqlalchemy import func
    
    employer_counts = (
        session.query(Job.employer, func.count(Job.id), Job.category)
        .filter(Job.is_active == True)
        .group_by(Job.employer)
        .all()
    )
    
    for employer_name, count, category in employer_counts:
        employer = session.query(Employer).filter(Employer.name == employer_name).first()
        
        if employer:
            employer.job_count = count
            employer.category = category
        else:
            employer = Employer(
                name=employer_name,
                category=category,
                job_count=count
            )
            session.add(employer)
    
    session.commit()


def run_scrapers(sources: Optional[List[str]] = None):
    """
    Run specified scrapers and save results to database.
    
    Args:
        sources: List of source names to run, or None for all
    """
    import time
    start_time = time.time()
    
    # Initialize database
    init_db()
    session = get_session()
    normalizer = CategoryNormalizer()
    
    # Available scrapers - organized by tier
    all_scrapers = {
        # Tier 1 - Major sources
        'neogov': NEOGOVScraper,
        'csu': CSUScraper,
        'edjoin': EdJoinScraper,
        'arcata': ArcataScraper,
        # Tier 2 - Tribal/Community/College
        'wiyot': WiyotScraper,
        'rio_dell': RioDellScraper,
        'redwoods': RedwoodsScraper,
        # Tier 2 - Small Cities
        'blue_lake': BlueLakeScraper,
        'ferndale': FerndaleScraper,
        'trinidad': TrinidadScraper,
        # Tier 2 - Healthcare
        'open_door': OpenDoorHealthScraper,
        'providence': ProvidenceScraper,
        'mad_river': MadRiverHospitalScraper,
        'uihs': UnitedIndianHealthScraper,
        'kimaw': KimawMedicalScraper,
        'hospice': HospiceOfHumboldtScraper,
        'hsrc': HumboldtSeniorResourceScraper,
        'rcaa': RCAAScraper,
        'sohum': SoHumHealthScraper,
        # Tier 3 - Local Employers
        'blue_lake_casino': BlueLakeCasinoScraper,
        'bear_river_casino': BearRiverCasinoScraper,
        'green_diamond': GreenDiamondScraper,
        'north_coast_coop': NorthCoastCoopScraper,
        'laco': LACOAssociatesScraper,
        'eureka_natural_foods': EurekaNaturalFoodsScraper,
        'danco': DancoGroupScraper,
        # Tier 3B - National Retailers
        'dollar_general': DollarGeneralScraper,
        'walgreens': WalgreensScraper,
        'tj_maxx': TJMaxxScraper,
        'costco': CostcoScraper,
        'safeway': SafewayScraper,
        'walmart': WalmartScraper,
        # Tier 3B - Banks
        'coast_central': CoastCentralCUScraper,
        'compass_ccu': CompassCCUScraper,
        'tri_counties': TriCountiesBankScraper,
        'redwood_capital': RedwoodCapitalBankScraper,
        'columbia_bank': ColumbiaBankScraper,
        # Tier 3B - Nonprofit/Social Services
        'rrhc': RRHCScraper,
        'two_feathers': TwoFeathersScraper,
        'changing_tides': ChangingTidesScraper,
        # Tier 3C - Additional Local and Regional Employers
        'rcea': RCEAScraper,
        'food_for_people': FoodForPeopleScraper,
        'bgc_redwoods': BGCRedwoodsScraper,
        'kokatat': KokatatScraper,
        'lost_coast_brewery': LostCoastBreweryScraper,
        'murphys_markets': MurphysMarketsScraper,
        'cypress_grove': CypressGroveScraper,
        'driscolls': DriscollsScraper,
        'winco': WinCoFoodsScraper,
        'grocery_outlet': GroceryOutletScraper,
        'harbor_freight': HarborFreightScraper,
        'ace_hardware': AceHardwareScraper,
        'sierra_pacific': SierraPacificScraper,
        'cvs': CVSHealthScraper,
        'rite_aid': RiteAidScraper,
        'starbucks': StarbucksScraper,
        'fedex': FedExScraper,
        'ups': UPSScraper,
        'pge': PGEScraper,
        'humboldt_sawmill': HumboldtSawmillScraper,
        'humboldt_creamery': HumboldtCreameryScraper,
        'alexandre_farm': AlexandreFamilyFarmScraper,
        'pacific_seafood': PacificSeafoodScraper,
        'arcata_house': ArcataHouseScraper,
        'pierson_building': PiersonBuildingScraper,
        'c_crane': CCraneScraper,
        'jones_tree': JonesFamilyTreeServiceScraper,
    }
    
    # Select scrapers to run
    if sources:
        scrapers = {k: v for k, v in all_scrapers.items() if k in sources}
    else:
        scrapers = all_scrapers
    
    all_jobs = []
    total_inserted = 0
    total_updated = 0
    source_errors = {}  # Track errors per source
    
    print("\n" + "=" * 60)
    print("  HUMBOLDT COUNTY JOBS AGGREGATOR")
    print("=" * 60 + "\n")
    
    for name, scraper_class in scrapers.items():
        print(f"\n  Running {name.upper()} scraper...")
        print("-" * 40)
        
        try:
            scraper = scraper_class()
            jobs = scraper.scrape()
            all_jobs.extend(jobs)
            
            print(f"    Found: {len(jobs)} jobs")
            
        except Exception as e:
            error_msg = str(e)[:200]  # Truncate long errors
            source_errors[name] = error_msg
            logger.error(f"Error running {name} scraper: {e}")
            print(f"    Error: {e}")
    
    # Deduplicate by URL
    print(f"\n  Deduplicating {len(all_jobs)} jobs...")
    unique_jobs = deduplicate_by_url(all_jobs)
    print(f"    Unique jobs: {len(unique_jobs)}")
    
    # Save to database
    print("\n  Saving to database...")
    total_inserted, total_updated, new_job_urls = save_jobs(unique_jobs, session, normalizer)
    
    # Update employer counts
    update_employer_counts(session)
    
    # Run AI QA review on new/updated jobs
    qa_results = run_ai_qa_review(session)
    
    # Deactivate stale jobs (not updated in 7+ days)
    from datetime import timedelta
    stale_cutoff = datetime.utcnow() - timedelta(days=7)
    stale_jobs = session.query(Job).filter(
        Job.is_active == True,
        Job.updated_at < stale_cutoff
    ).all()
    
    jobs_deactivated = 0
    if stale_jobs:
        print(f"\n  Deactivating {len(stale_jobs)} stale jobs (not seen in 7+ days)...")
        for job in stale_jobs:
            job.is_active = False
            jobs_deactivated += 1
        session.commit()
    
    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"    Total jobs scraped:  {len(all_jobs)}")
    print(f"    Unique jobs:         {len(unique_jobs)}")
    print(f"    New jobs inserted:   {total_inserted}")
    print(f"    Jobs updated:        {total_updated}")
    if jobs_deactivated > 0:
        print(f"    Jobs deactivated:    {jobs_deactivated} (stale)")
    if qa_results.get("quarantined", 0) > 0:
        print(f"    QA quarantined:      {qa_results['quarantined']} (false positives)")
    
    # Show database stats
    active_count = session.query(Job).filter(Job.is_active == True).count()
    employer_count = session.query(Employer).count()
    print(f"    Active jobs in DB:   {active_count}")
    print(f"    Employers tracked:   {employer_count}")
    
    # Show source errors if any
    if source_errors:
        print(f"\n  ⚠️  Sources with errors: {len(source_errors)}")
        for src, err in source_errors.items():
            print(f"       - {src}: {err[:60]}...")
    
    # Log this scrape run with new job URLs and errors
    import json
    from collections import Counter
    
    duration = int(time.time() - start_time)
    
    # Calculate salary stats by employer
    active_jobs = session.query(Job).filter(Job.is_active == True).all()
    salary_stats = {}
    emp_totals = Counter(j.employer for j in active_jobs)
    emp_with_salary = Counter(j.employer for j in active_jobs if j.salary_text)
    
    for emp in emp_totals:
        total = emp_totals[emp]
        has_salary = emp_with_salary.get(emp, 0)
        missing = total - has_salary
        rate = int(100 * has_salary / total) if total > 0 else 0
        salary_stats[emp] = {
            'total': total,
            'has_salary': has_salary,
            'missing': missing,
            'rate': rate
        }
    
    scrape_log = ScrapeLog(
        jobs_inserted=total_inserted,
        jobs_updated=total_updated,
        jobs_total=active_count,
        jobs_deactivated=jobs_deactivated,
        duration_seconds=duration,
        new_job_urls=json.dumps(new_job_urls) if new_job_urls else None,
        source_errors=json.dumps(source_errors) if source_errors else None,
        salary_stats=json.dumps(salary_stats)
    )
    session.add(scrape_log)
    session.commit()
    
    # Log salary issues for employers with poor salary coverage
    for emp, stats in salary_stats.items():
        if stats['rate'] < 50 and stats['total'] > 0:  # Log if <50% salary coverage
            # Get source name for this employer
            emp_job = session.query(Job).filter(
                Job.employer == emp, 
                Job.is_active == True
            ).first()
            source_name = emp_job.source_name if emp_job else 'unknown'
            
            issue_log = SalaryIssueLog(
                source_name=source_name,
                employer=emp,
                jobs_total=stats['total'],
                jobs_with_salary=stats['has_salary'],
                jobs_missing_salary=stats['missing'],
                salary_rate=stats['rate']
            )
            session.add(issue_log)
    session.commit()
    
    print(f"\n    Scrape duration:     {duration}s")
    print("=" * 60 + "\n")
    
    # Show comparison to previous scrape
    previous_scrape = (
        session.query(ScrapeLog)
        .filter(ScrapeLog.id != scrape_log.id)
        .order_by(ScrapeLog.scraped_at.desc())
        .first()
    )
    if previous_scrape:
        print(f"  📊 Compared to last scrape ({previous_scrape.scraped_at.strftime('%b %d, %Y')}):")
        jobs_diff = active_count - previous_scrape.jobs_total
        if jobs_diff > 0:
            print(f"     +{jobs_diff} net new jobs")
        elif jobs_diff < 0:
            print(f"     {jobs_diff} jobs (some removed/expired)")
        else:
            print(f"     No change in total jobs")
        print()
    
    session.close()


def list_jobs(limit: int = 20, category: Optional[str] = None, employer: Optional[str] = None):
    """
    List recent jobs from the database.
    
    Args:
        limit: Maximum number of jobs to show
        category: Filter by category
        employer: Filter by employer
    """
    init_db()
    session = get_session()
    
    query = session.query(Job).filter(Job.is_active == True)
    
    if category:
        query = query.filter(Job.category == category)
    if employer:
        query = query.filter(Job.employer.ilike(f"%{employer}%"))
    
    jobs = query.order_by(Job.scraped_at.desc()).limit(limit).all()
    
    print(f"\n  Recent Jobs ({len(jobs)} shown):\n")
    print("-" * 70)
    
    for job in jobs:
        print(f"  {job.title}")
        print(f"    Employer: {job.employer}")
        print(f"    Category: {job.category} | Location: {job.location or 'N/A'}")
        print(f"    URL: {job.url}")
        if job.closing_date:
            print(f"    Closes: {job.closing_date.strftime('%Y-%m-%d')}")
        print()
    
    session.close()


def show_stats():
    """Show database statistics."""
    init_db()
    session = get_session()
    
    from sqlalchemy import func
    
    print("\n" + "=" * 60)
    print("  DATABASE STATISTICS")
    print("=" * 60)
    
    # Total active jobs
    total = session.query(Job).filter(Job.is_active == True).count()
    print(f"\n  Total Active Jobs: {total}")
    
    # Jobs by category
    print("\n  Jobs by Category:")
    print("-" * 40)
    categories = (
        session.query(Job.category, func.count(Job.id))
        .filter(Job.is_active == True)
        .group_by(Job.category)
        .order_by(func.count(Job.id).desc())
        .all()
    )
    for cat, count in categories:
        print(f"    {cat}: {count}")
    
    # Jobs by source
    print("\n  Jobs by Source:")
    print("-" * 40)
    sources = (
        session.query(Job.source_name, func.count(Job.id))
        .filter(Job.is_active == True)
        .group_by(Job.source_name)
        .order_by(func.count(Job.id).desc())
        .all()
    )
    for source, count in sources:
        print(f"    {source}: {count}")
    
    # Top employers
    print("\n  Top 10 Employers:")
    print("-" * 40)
    employers = (
        session.query(Employer)
        .order_by(Employer.job_count.desc())
        .limit(10)
        .all()
    )
    for emp in employers:
        print(f"    {emp.name}: {emp.job_count} jobs")
    
    print("\n" + "=" * 60 + "\n")
    session.close()


def run_ai_qa(auto_quarantine: bool = False):
    """Run AI-powered QA review on all jobs."""
    from processing import get_orchestrator
    from processing.agents.qa_agent import JobRecord
    
    init_db()
    session = get_session()
    
    print("\n" + "=" * 60)
    print("  AI DATA QUALITY REVIEW")
    print("  Powered by Gemini AI - QA Agent")
    print("=" * 60 + "\n")
    
    # Load all active jobs
    jobs = session.query(Job).filter(Job.is_active == True).all()
    print(f"  Reviewing {len(jobs)} active jobs...\n")
    
    # Convert to JobRecord format
    job_records = [
        JobRecord(
            id=j.id,
            title=j.title,
            employer=j.employer,
            location=j.location or "",
            url=j.url,
            salary=j.salary_text,
            description=j.description,
            source_name=j.source_name
        )
        for j in jobs
    ]
    
    # Run QA
    orchestrator = get_orchestrator()
    results = orchestrator.quick_qa(job_records)
    
    approved = len(results.get("approved", []))
    quarantined = results.get("quarantined", [])
    flagged = results.get("flagged", [])
    
    print(f"  ✅ Approved: {approved}")
    print(f"  ❌ Quarantine: {len(quarantined)}")
    print(f"  ⚠️  Flagged for review: {len(flagged)}")
    
    if quarantined:
        print("\n  QUARANTINED (false positives):")
        print("-" * 50)
        for response in quarantined:
            job_id = response.details.get("job_id")
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                print(f"    ID {job_id}: \"{job.title}\" at {job.employer}")
                if response.recommendations:
                    print(f"      Reason: {response.recommendations[0]}")
        
        if auto_quarantine:
            print("\n  Auto-quarantining...")
            for response in quarantined:
                job_id = response.details.get("job_id")
                job = session.query(Job).filter(Job.id == job_id).first()
                if job:
                    session.delete(job)
            session.commit()
            print(f"  ✅ Removed {len(quarantined)} false positives")
    
    if flagged:
        print("\n  FLAGGED FOR MANUAL REVIEW:")
        print("-" * 50)
        for response in flagged[:10]:  # Show first 10
            job_id = response.details.get("job_id")
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                print(f"    ID {job_id}: \"{job.title}\" at {job.employer}")
    
    print("\n" + "=" * 60 + "\n")
    session.close()


def run_ai_debug(scraper_name: str):
    """Run AI-powered scraper debugging."""
    from processing import get_engineer_agent
    
    print("\n" + "=" * 60)
    print(f"  AI SCRAPER DEBUG: {scraper_name}")
    print("  Powered by Gemini AI - Engineer Agent")
    print("=" * 60 + "\n")
    
    engineer = get_engineer_agent()
    
    # Try to get the scraper code
    scraper_code = None
    try:
        import importlib
        module = importlib.import_module(f"scrapers.{scraper_name}")
        import inspect
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and 'Scraper' in name:
                scraper_code = inspect.getsource(obj)
                break
    except Exception as e:
        print(f"  Could not load scraper code: {e}")
    
    response = engineer.process({
        "action": "diagnose",
        "scraper_name": scraper_name,
        "code": scraper_code,
        "actual_jobs": 0
    })
    
    print(f"  Diagnosis: {response.summary}")
    print(f"  Root Cause: {response.details.get('root_cause', 'Unknown')}")
    print(f"  Confidence: {response.confidence:.0%}")
    
    if response.recommendations:
        print("\n  Recommendations:")
        for rec in response.recommendations:
            print(f"    • {rec}")
    
    if response.details.get("code_fix"):
        print("\n  Suggested Code Fix:")
        print("-" * 50)
        print(response.details["code_fix"])
    
    print("\n" + "=" * 60 + "\n")


# ============================================================================
# SCRAPER WATCHLIST - Scrapers that need extra attention/testing
# ============================================================================

WATCHLIST_SCRAPERS = {
    # Scrapers with known issues or complex extraction
    'safeway': {
        'class': 'SafewayScraper',
        'reason': 'Oracle HCM - complex salary extraction',
        'expected_salary_rate': 0.5,  # At least 50% should have salary
    },
    'walgreens': {
        'class': 'WalgreensScraper', 
        'reason': 'Salary regex patterns need validation',
        'expected_salary_rate': 0.3,
    },
    'north_coast_coop': {
        'class': 'NorthCoastCoopScraper',
        'reason': 'UKG platform - salary + stale job detection',
        'expected_salary_rate': 0.5,
    },
    'humboldt_creamery': {
        'class': 'HumboldtCreameryScraper',
        'reason': 'Location filtering (multi-location company)',
        'expected_salary_rate': 0.0,  # Salary not always available
    },
    'neogov': {
        'class': 'NEOGOVScraper',
        'reason': 'Playwright-based, many government jobs',
        'expected_salary_rate': 0.2,  # Government jobs often hide salary
    },
}


def run_test_watchlist(verbose: bool = True) -> dict:
    """
    Test watchlist scrapers without saving to database.
    
    Returns dict with test results for each scraper.
    """
    from scrapers import (
        SafewayScraper, WalgreensScraper, NorthCoastCoopScraper,
        HumboldtCreameryScraper, NEOGOVScraper
    )
    
    scraper_classes = {
        'safeway': SafewayScraper,
        'walgreens': WalgreensScraper,
        'north_coast_coop': NorthCoastCoopScraper,
        'humboldt_creamery': HumboldtCreameryScraper,
        'neogov': NEOGOVScraper,
    }
    
    print("\n" + "=" * 70)
    print("  WATCHLIST SCRAPER TEST MODE")
    print("  Testing problematic scrapers before full scrape")
    print("=" * 70 + "\n")
    
    results = {}
    all_passed = True
    
    for name, config in WATCHLIST_SCRAPERS.items():
        print(f"\n  Testing: {name.upper()}")
        print(f"  Reason: {config['reason']}")
        print("-" * 50)
        
        try:
            scraper_class = scraper_classes.get(name)
            if not scraper_class:
                print(f"    ⚠️  Scraper class not found")
                continue
            
            scraper = scraper_class()
            jobs = scraper.scrape()
            
            # Calculate metrics
            total = len(jobs)
            with_salary = sum(1 for j in jobs if j.salary_text)
            with_description = sum(1 for j in jobs if j.description and len(j.description) > 50)
            salary_rate = with_salary / total if total > 0 else 0
            desc_rate = with_description / total if total > 0 else 0
            
            # Check for issues
            issues = []
            
            if total == 0:
                issues.append("NO JOBS FOUND - scraper may be broken")
            
            if salary_rate < config['expected_salary_rate']:
                issues.append(f"Low salary rate: {salary_rate:.0%} (expected {config['expected_salary_rate']:.0%}+)")
            
            # Check for garbled descriptions
            bad_desc_count = 0
            for job in jobs:
                if job.description:
                    desc_lower = job.description.lower()[:50]
                    if any(bad in desc_lower for bad in ['are representative only', 'reserves the right']):
                        bad_desc_count += 1
            
            if bad_desc_count > 0:
                issues.append(f"{bad_desc_count} jobs with garbled descriptions")
            
            # Print results
            passed = len(issues) == 0
            status = "✓ PASS" if passed else "✗ FAIL"
            
            print(f"    Jobs found:       {total}")
            print(f"    With salary:      {with_salary}/{total} ({salary_rate:.0%})")
            print(f"    With description: {with_description}/{total} ({desc_rate:.0%})")
            print(f"    Status:           {status}")
            
            if issues:
                all_passed = False
                print(f"    Issues:")
                for issue in issues:
                    print(f"      ⚠️  {issue}")
            
            if verbose and total > 0:
                print(f"\n    Sample jobs:")
                for job in jobs[:3]:
                    salary_str = job.salary_text or "No salary"
                    print(f"      • {job.title[:40]}... | {salary_str}")
            
            results[name] = {
                'total': total,
                'with_salary': with_salary,
                'salary_rate': salary_rate,
                'with_description': with_description,
                'issues': issues,
                'passed': passed,
            }
            
        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            results[name] = {
                'total': 0,
                'error': str(e),
                'passed': False,
            }
            all_passed = False
    
    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    
    passed_count = sum(1 for r in results.values() if r.get('passed'))
    failed_count = len(results) - passed_count
    
    print(f"\n    Passed: {passed_count}/{len(results)}")
    print(f"    Failed: {failed_count}/{len(results)}")
    
    if all_passed:
        print(f"\n    ✅ All watchlist scrapers passed! Safe to run full scrape.")
    else:
        print(f"\n    ⚠️  Some scrapers have issues. Review before full scrape.")
        print(f"       Run with --sources to skip problematic scrapers.")
    
    print("\n" + "=" * 70 + "\n")
    
    return results


def run_health_check() -> dict:
    """
    Run health checks on scraped data in the database.
    
    Checks:
    - Salary coverage by employer
    - Description quality
    - Location validity
    - Stale job detection
    """
    from db.database import init_db, get_session
    from db.models import Job
    from sqlalchemy import func
    from processing.agents.qa_agent import HUMBOLDT_LOCATIONS, NON_HUMBOLDT_LOCATIONS, BAD_DESCRIPTION_PATTERNS
    import re
    
    init_db()
    session = get_session()
    
    print("\n" + "=" * 70)
    print("  SCRAPER HEALTH CHECK")
    print("  Validating data quality in database")
    print("=" * 70 + "\n")
    
    jobs = session.query(Job).filter(Job.is_active == True).all()
    total = len(jobs)
    
    if total == 0:
        print("    No active jobs in database.")
        return {}
    
    # 1. Salary coverage by employer
    print("  1. SALARY COVERAGE BY EMPLOYER")
    print("-" * 50)
    
    from collections import Counter
    emp_totals = Counter(j.employer for j in jobs)
    emp_with_salary = Counter(j.employer for j in jobs if j.salary_text)
    
    low_salary_employers = []
    for emp in sorted(emp_totals.keys()):
        total_emp = emp_totals[emp]
        with_sal = emp_with_salary.get(emp, 0)
        rate = with_sal / total_emp if total_emp > 0 else 0
        
        if rate < 0.3 and total_emp >= 2:  # Less than 30% salary coverage
            low_salary_employers.append((emp, with_sal, total_emp, rate))
    
    if low_salary_employers:
        print(f"    ⚠️  Employers with low salary coverage (<30%):")
        for emp, with_sal, total_emp, rate in low_salary_employers[:10]:
            print(f"       {emp}: {with_sal}/{total_emp} ({rate:.0%})")
    else:
        print(f"    ✓ All employers have good salary coverage")
    
    # 2. Description quality
    print(f"\n  2. DESCRIPTION QUALITY")
    print("-" * 50)
    
    bad_descriptions = []
    for job in jobs:
        if job.description:
            for pattern in BAD_DESCRIPTION_PATTERNS:
                if re.match(pattern, job.description.strip(), re.IGNORECASE):
                    bad_descriptions.append((job.id, job.title, job.employer, job.description[:50]))
                    break
    
    if bad_descriptions:
        print(f"    ⚠️  {len(bad_descriptions)} jobs with garbled descriptions:")
        for job_id, title, emp, desc in bad_descriptions[:5]:
            print(f"       ID {job_id}: {title[:30]}... at {emp}")
            print(f"          Desc: \"{desc}...\"")
    else:
        print(f"    ✓ All descriptions look valid")
    
    # 3. Location validity
    print(f"\n  3. LOCATION VALIDITY")
    print("-" * 50)
    
    invalid_locations = []
    for job in jobs:
        if job.location:
            loc_lower = job.location.lower()
            # Check if explicitly NOT in Humboldt
            for non_humboldt in NON_HUMBOLDT_LOCATIONS:
                if non_humboldt in loc_lower:
                    invalid_locations.append((job.id, job.title, job.employer, job.location))
                    break
    
    if invalid_locations:
        print(f"    ⚠️  {len(invalid_locations)} jobs with non-Humboldt locations:")
        for job_id, title, emp, loc in invalid_locations[:5]:
            print(f"       ID {job_id}: {title[:30]}... at {emp}")
            print(f"          Location: {loc}")
    else:
        print(f"    ✓ All locations appear valid")
    
    # 4. Data completeness summary
    print(f"\n  4. DATA COMPLETENESS SUMMARY")
    print("-" * 50)
    
    with_salary = sum(1 for j in jobs if j.salary_text)
    with_desc = sum(1 for j in jobs if j.description and len(j.description) > 50)
    with_location = sum(1 for j in jobs if j.location)
    
    print(f"    Total active jobs:    {total}")
    print(f"    With salary:          {with_salary} ({with_salary/total:.0%})")
    print(f"    With description:     {with_desc} ({with_desc/total:.0%})")
    print(f"    With location:        {with_location} ({with_location/total:.0%})")
    
    # Overall health score
    health_score = (
        (with_salary / total * 30) +  # Salary worth 30 points
        (with_desc / total * 30) +     # Description worth 30 points
        (with_location / total * 20) + # Location worth 20 points
        (1 - len(bad_descriptions) / total) * 10 +  # Quality worth 10 points
        (1 - len(invalid_locations) / total) * 10   # Location accuracy worth 10 points
    )
    
    print(f"\n    📊 HEALTH SCORE: {health_score:.0f}/100")
    
    if health_score >= 80:
        print(f"       ✅ Excellent - data quality is good")
    elif health_score >= 60:
        print(f"       ⚠️  Fair - some improvements needed")
    else:
        print(f"       ❌ Poor - significant data quality issues")
    
    print("\n" + "=" * 70 + "\n")
    
    session.close()
    
    return {
        'total_jobs': total,
        'with_salary': with_salary,
        'with_description': with_desc,
        'bad_descriptions': len(bad_descriptions),
        'invalid_locations': len(invalid_locations),
        'health_score': health_score,
        'low_salary_employers': low_salary_employers,
    }


def run_ai_analysis():
    """Run AI-powered market analysis."""
    from processing import get_analyst_agent
    from processing.agents.analyst_agent import JobStats
    from sqlalchemy import func
    from collections import Counter
    
    init_db()
    session = get_session()
    
    print("\n" + "=" * 60)
    print("  AI MARKET ANALYSIS")
    print("  Powered by Gemini AI - Analyst Agent")
    print("=" * 60 + "\n")
    
    # Build stats
    jobs = session.query(Job).filter(Job.is_active == True).all()
    
    stats = JobStats(
        total_jobs=len(jobs),
        jobs_by_category=dict(Counter(j.category for j in jobs)),
        jobs_by_employer=dict(Counter(j.employer for j in jobs)),
        jobs_by_location=dict(Counter(j.location for j in jobs if j.location)),
        jobs_with_salary=sum(1 for j in jobs if j.salary_text),
        new_jobs_today=session.query(Job).filter(
            Job.is_active == True,
            func.date(Job.scraped_at) == func.date(func.now())
        ).count(),
        jobs_removed_today=0
    )
    
    analyst = get_analyst_agent()
    response = analyst.analyze_current_state(stats)
    
    print(f"  {response.summary}\n")
    
    insights = response.details.get("insights", [])
    if insights:
        print("  KEY INSIGHTS:")
        for insight in insights:
            print(f"    • {insight}")
    
    anomalies = response.details.get("anomalies", [])
    if anomalies:
        print("\n  ANOMALIES DETECTED:")
        for anomaly in anomalies:
            severity = anomaly.get("severity", "MEDIUM")
            print(f"    [{severity}] {anomaly.get('description', 'Unknown')}")
    
    trends = response.details.get("trends", {})
    if trends:
        print("\n  TRENDS:")
        if trends.get("growing"):
            print(f"    📈 Growing: {', '.join(trends['growing'])}")
        if trends.get("declining"):
            print(f"    📉 Declining: {', '.join(trends['declining'])}")
    
    if response.recommendations:
        print("\n  RECOMMENDATIONS:")
        for rec in response.recommendations:
            print(f"    • {rec}")
    
    print("\n" + "=" * 60 + "\n")
    session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Humboldt County Jobs Aggregator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                      Run all scrapers
    python main.py -s neogov csu        Run specific scrapers
    python main.py --list               List recent jobs
    python main.py --list -c Education  List education jobs
    python main.py --stats              Show statistics
    python main.py --check              Check for anomalies in data
    python main.py --check --clean      Auto-delete anomalies

Testing & Health Checks:
    python main.py --test-watchlist     Test problematic scrapers (no DB changes)
    python main.py --health-check       Check data quality in database
    
AI Agent Commands:
    python main.py --ai-qa              AI reviews data quality
    python main.py --ai-qa --clean      AI reviews and auto-removes false positives
    python main.py --ai-debug sohum     AI debugs a failing scraper
    python main.py --ai-analyze         AI analyzes job market trends
        """
    )
    
    parser.add_argument(
        '--sources', '-s',
        nargs='+',
        choices=[
            'neogov', 'csu', 'edjoin', 'arcata',
            'wiyot', 'rio_dell', 'redwoods',
            'blue_lake', 'ferndale', 'trinidad',
            # Healthcare
            'open_door', 'providence', 'mad_river', 'uihs',
            'kimaw', 'hospice', 'hsrc', 'rcaa', 'sohum',
            # Local Employers
            'blue_lake_casino', 'bear_river_casino', 'green_diamond', 'north_coast_coop', 'laco',
            'eureka_natural_foods', 'danco',
            # National Retailers
            'dollar_general', 'walgreens', 'tj_maxx', 'costco', 'safeway', 'walmart',
            # Banks
            'coast_central', 'compass_ccu', 'tri_counties', 'redwood_capital', 'columbia_bank',
            # Nonprofit/Social Services
            'rrhc', 'two_feathers', 'changing_tides',
            # Additional Local and Regional Employers
            'rcea', 'food_for_people', 'bgc_redwoods', 'kokatat',
            'lost_coast_brewery', 'murphys_markets', 'cypress_grove', 'driscolls',
            'winco', 'grocery_outlet', 'harbor_freight', 'ace_hardware',
            'sierra_pacific', 'cvs', 'rite_aid', 'starbucks', 'fedex', 'ups', 'pge',
            'humboldt_sawmill', 'humboldt_creamery', 'alexandre_farm', 'pacific_seafood',
            'arcata_house', 'pierson_building', 'c_crane', 'jones_tree',
            'all'
        ],
        default=['all'],
        help='Sources to scrape (default: all)'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List recent jobs from database'
    )
    
    parser.add_argument(
        '--limit', '-n',
        type=int,
        default=20,
        help='Number of jobs to list (default: 20)'
    )
    
    parser.add_argument(
        '--category', '-c',
        type=str,
        help='Filter jobs by category'
    )
    
    parser.add_argument(
        '--employer', '-e',
        type=str,
        help='Filter jobs by employer (partial match)'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )
    
    parser.add_argument(
        '--check',
        action='store_true',
        help='Run anomaly detection on scraped data'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Automatically delete high-severity anomalies'
    )
    
    # AI Agent arguments
    parser.add_argument(
        '--ai-qa',
        action='store_true',
        help='Run AI-powered QA review on all jobs'
    )
    
    parser.add_argument(
        '--ai-debug',
        type=str,
        metavar='SCRAPER',
        help='AI debugs a specific scraper (e.g., --ai-debug sohum)'
    )
    
    parser.add_argument(
        '--ai-analyze',
        action='store_true',
        help='AI analyzes job market trends and anomalies'
    )
    
    # Watchlist and health check arguments
    parser.add_argument(
        '--test-watchlist',
        action='store_true',
        help='Test problematic scrapers before full scrape (no DB changes)'
    )
    
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Run health checks on data in the database'
    )
    
    args = parser.parse_args()
    
    # Handle commands
    if args.test_watchlist:
        run_test_watchlist(verbose=True)
    elif args.health_check:
        run_health_check()
    elif args.ai_qa:
        run_ai_qa(auto_quarantine=args.clean)
    elif args.ai_debug:
        run_ai_debug(args.ai_debug)
    elif args.ai_analyze:
        run_ai_analysis()
    elif args.list:
        list_jobs(
            limit=args.limit,
            category=args.category,
            employer=args.employer
        )
    elif args.stats:
        show_stats()
    elif args.check:
        from processing import run_anomaly_check
        run_anomaly_check(auto_delete=args.clean, dry_run=not args.clean)
    else:
        sources = None if 'all' in args.sources else args.sources
        run_scrapers(sources)


if __name__ == '__main__':
    main()
