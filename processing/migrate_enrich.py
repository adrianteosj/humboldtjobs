#!/usr/bin/env python3
"""
Data Migration Script - Enrich Existing Jobs

This script enriches existing job records with:
1. Parsed salary data (salary_min, salary_max, salary_type)
2. Experience level detection
3. Education level detection
4. Classification (sub-category) if not already set

Run this after adding new columns to the database.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_session, engine
from db.models import Job, Base
from processing.salary_parser import parse_salary
from processing.experience_detector import detect_experience, get_education_level
from processing.normalizer import JobClassifier
from sqlalchemy import text


def migrate_schema():
    """Add new columns to the jobs table if they don't exist."""
    print("Checking database schema...")
    
    # New columns to add
    new_columns = [
        ("salary_min", "INTEGER"),
        ("salary_max", "INTEGER"),
        ("salary_type", "VARCHAR(20)"),
        ("experience_level", "VARCHAR(20)"),
        ("education_required", "VARCHAR(100)"),
        ("requirements", "TEXT"),
        ("benefits", "TEXT"),
        ("department", "VARCHAR(100)"),
        ("is_remote", "BOOLEAN DEFAULT 0"),
    ]
    
    with engine.connect() as conn:
        # Get existing columns
        result = conn.execute(text("PRAGMA table_info(jobs)"))
        existing_columns = {row[1] for row in result.fetchall()}
        
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                print(f"  Adding column: {col_name} ({col_type})")
                try:
                    conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                except Exception as e:
                    print(f"  Warning: Could not add column {col_name}: {e}")
            else:
                print(f"  Column exists: {col_name}")
    
    print("Schema migration complete.")


def enrich_salaries(session):
    """Parse salary_text and populate salary_min, salary_max, salary_type."""
    print("\nEnriching salary data...")
    
    # Find jobs with salary_text but missing parsed values
    jobs = session.query(Job).filter(
        Job.is_active == True,
        Job.salary_text != None,
        Job.salary_text != '',
        Job.salary_min == None
    ).all()
    
    print(f"  Found {len(jobs)} jobs with unparsed salary data")
    
    updated = 0
    for job in jobs:
        parsed = parse_salary(job.salary_text)
        if parsed.min_annual:
            job.salary_min = parsed.min_annual
            job.salary_max = parsed.max_annual or parsed.min_annual
            job.salary_type = parsed.salary_type
            updated += 1
    
    session.commit()
    print(f"  Updated {updated} jobs with parsed salary data")


def enrich_experience_levels(session):
    """Detect and set experience level for jobs."""
    print("\nDetecting experience levels...")
    
    # Find jobs without experience_level
    jobs = session.query(Job).filter(
        Job.is_active == True,
        Job.experience_level == None
    ).all()
    
    print(f"  Found {len(jobs)} jobs without experience level")
    
    updated = 0
    for job in jobs:
        exp_info = detect_experience(
            job.title,
            job.description,
            job.requirements
        )
        if exp_info.level and exp_info.confidence >= 0.4:
            job.experience_level = exp_info.level
            updated += 1
        
        # Also set education if detected and not already set
        if job.education_required is None and exp_info.education:
            job.education_required = exp_info.education
    
    session.commit()
    print(f"  Updated {updated} jobs with experience level")


def enrich_education_levels(session):
    """Detect and set education requirements for jobs."""
    print("\nDetecting education requirements...")
    
    # Find jobs without education_required
    jobs = session.query(Job).filter(
        Job.is_active == True,
        Job.education_required == None
    ).all()
    
    print(f"  Found {len(jobs)} jobs without education level")
    
    updated = 0
    for job in jobs:
        education = get_education_level(
            job.title,
            job.description,
            job.requirements
        )
        if education:
            job.education_required = education
            updated += 1
    
    session.commit()
    print(f"  Updated {updated} jobs with education level")


def enrich_classifications(session):
    """Set classification (sub-category) for jobs."""
    print("\nSetting job classifications...")
    
    classifier = JobClassifier()
    
    # Find jobs without classification
    jobs = session.query(Job).filter(
        Job.is_active == True,
        Job.classification == None
    ).all()
    
    print(f"  Found {len(jobs)} jobs without classification")
    
    updated = 0
    for job in jobs:
        classification = classifier.classify(job.title, job.category)
        if classification:
            job.classification = classification
            updated += 1
    
    session.commit()
    print(f"  Updated {updated} jobs with classification")


def detect_remote_jobs(session):
    """Detect and flag remote jobs."""
    print("\nDetecting remote jobs...")
    
    # Find jobs that might be remote
    jobs = session.query(Job).filter(
        Job.is_active == True,
        Job.is_remote == False
    ).all()
    
    print(f"  Checking {len(jobs)} jobs for remote work")
    
    remote_keywords = ['remote', 'work from home', 'wfh', 'telecommute', 'telework']
    
    updated = 0
    for job in jobs:
        text = ((job.title or '') + ' ' + (job.description or '')).lower()
        if any(kw in text for kw in remote_keywords):
            job.is_remote = True
            updated += 1
    
    session.commit()
    print(f"  Flagged {updated} jobs as remote")


def print_stats(session):
    """Print statistics about enriched data."""
    print("\n" + "=" * 50)
    print("ENRICHMENT STATISTICS")
    print("=" * 50)
    
    total = session.query(Job).filter(Job.is_active == True).count()
    print(f"Total active jobs: {total}")
    
    with_salary_min = session.query(Job).filter(
        Job.is_active == True,
        Job.salary_min != None
    ).count()
    print(f"Jobs with parsed salary: {with_salary_min} ({100*with_salary_min//total}%)")
    
    with_exp = session.query(Job).filter(
        Job.is_active == True,
        Job.experience_level != None
    ).count()
    print(f"Jobs with experience level: {with_exp} ({100*with_exp//total}%)")
    
    with_edu = session.query(Job).filter(
        Job.is_active == True,
        Job.education_required != None
    ).count()
    print(f"Jobs with education level: {with_edu} ({100*with_edu//total}%)")
    
    with_class = session.query(Job).filter(
        Job.is_active == True,
        Job.classification != None
    ).count()
    print(f"Jobs with classification: {with_class} ({100*with_class//total}%)")
    
    with_desc = session.query(Job).filter(
        Job.is_active == True,
        Job.description != None
    ).count()
    print(f"Jobs with description: {with_desc} ({100*with_desc//total}%)")
    
    remote = session.query(Job).filter(
        Job.is_active == True,
        Job.is_remote == True
    ).count()
    print(f"Remote jobs: {remote}")
    
    print("=" * 50)


def main():
    """Run all enrichment migrations."""
    print("=" * 60)
    print("Humboldt Jobs - Data Enrichment Migration")
    print("=" * 60)
    
    # Step 1: Migrate schema
    migrate_schema()
    
    # Step 2: Get database session
    session = get_session()
    
    try:
        # Step 3: Enrich data
        enrich_salaries(session)
        enrich_experience_levels(session)
        enrich_education_levels(session)
        enrich_classifications(session)
        detect_remote_jobs(session)
        
        # Step 4: Print stats
        print_stats(session)
        
        print("\n✅ Migration complete!")
        print("\nNext steps:")
        print("  1. Run scrapers to get new enriched data: python main.py")
        print("  2. Regenerate static site: python generate_static.py")
        
    finally:
        session.close()


if __name__ == "__main__":
    main()
