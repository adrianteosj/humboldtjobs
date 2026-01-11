#!/usr/bin/env python3
"""
Migration script to add classification (sub-category) to existing jobs.
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import text, inspect
from db.database import get_session, engine
from db.models import Job
from processing.normalizer import JobClassifier

def migrate_classifications():
    """Classify all existing jobs based on their title and category."""
    session = get_session()
    classifier = JobClassifier()
    
    # Check if column exists
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('jobs')]
    
    if 'classification' not in columns:
        print("Adding 'classification' column to jobs table...")
        try:
            session.execute(text("ALTER TABLE jobs ADD COLUMN classification VARCHAR(100)"))
            session.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error adding column: {e}")
            session.rollback()
            return
    else:
        print("Column 'classification' already exists.")
    
    # Get all active jobs
    jobs = session.query(Job).filter(Job.is_active == True).all()
    
    print(f"Classifying {len(jobs)} jobs...")
    
    updated = 0
    classification_counts = {}
    
    for job in jobs:
        classification = classifier.classify(job.title, job.category)
        if classification:
            job.classification = classification
            updated += 1
            
            # Track counts
            key = f"{job.category} -> {classification}"
            classification_counts[key] = classification_counts.get(key, 0) + 1
    
    session.commit()
    
    print(f"\nUpdated {updated} jobs with classifications")
    print("\nClassification breakdown:")
    for key, count in sorted(classification_counts.items(), key=lambda x: -x[1]):
        print(f"  {key}: {count}")
    
    session.close()

if __name__ == "__main__":
    migrate_classifications()
