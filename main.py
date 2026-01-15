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
            existing.job_type = job_data.job_type
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
                job_type=job_data.job_type,
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
    
    args = parser.parse_args()
    
    if args.list:
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
