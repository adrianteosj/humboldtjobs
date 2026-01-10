"""
Anomaly Detection for Scraped Job Data

This module provides tools to detect and flag potentially invalid job entries
that may have been incorrectly scraped from source websites.
"""
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class AnomalyType(Enum):
    """Types of anomalies that can be detected."""
    SHORT_TITLE = "short_title"
    NAVIGATION_ELEMENT = "navigation_element"
    FILE_REFERENCE = "file_reference"
    DUPLICATE_EMPLOYER = "duplicate_employer"
    MALFORMED_URL = "malformed_url"
    MISSING_FIELDS = "missing_fields"
    SUSPICIOUS_PATTERN = "suspicious_pattern"


@dataclass
class Anomaly:
    """Represents a detected anomaly in job data."""
    job_id: int
    job_title: str
    source_name: str
    anomaly_type: AnomalyType
    description: str
    severity: str  # 'low', 'medium', 'high'
    
    def __str__(self):
        return f"[{self.severity.upper()}] {self.anomaly_type.value}: {self.job_title[:50]} - {self.description}"


class AnomalyDetector:
    """
    Detects anomalies in scraped job data.
    
    Usage:
        detector = AnomalyDetector()
        anomalies = detector.analyze_jobs(session)
        for anomaly in anomalies:
            print(anomaly)
    """
    
    # Navigation/UI elements that are often mistakenly scraped
    NAVIGATION_PATTERNS = [
        r'^live\s*edit$',
        r'^site\s*(links|tools|map)$',
        r'^connect\s*with\s*us$',
        r'^quick\s*links$',
        r'^steps$',
        r'^share$',
        r'^tools$',
        r'^categories$',
        r'^menu$',
        r'^footer$',
        r'^header$',
        r'^navigation$',
        r'^contact(\s*us)?$',
        r'^about(\s*us)?$',
        r'^home$',
        r'^search$',
        r'^accessibility$',
        r'^privacy\s*policy$',
        r'^terms',
        r'^copyright',
        r'^powered\s*by',
        # Job portal navigation elements
        r'^saved\s*jobs',
        r'^your\s*job\s*cart',
        r'^job\s*alerts?',
        r'^my\s*applications?',
        r'^my\s*profile',
        r'^sign\s*in',
        r'^create\s*account',
        r'^register$',
        r'^login$',
        r'^follow\s*us',
        r'^see\s*all\s*jobs',
    ]
    
    # Patterns that indicate file references instead of job titles
    FILE_PATTERNS = [
        r'\.pdf\s*\d+[,.]?\d*\s*(kb|mb|bytes?)$',
        r'\.docx?\s*\d+[,.]?\d*\s*(kb|mb|bytes?)$',
        r'\.xlsx?\s*\d+[,.]?\d*\s*(kb|mb|bytes?)$',
        r'^download\s',
        r'^attachment',
    ]
    
    # Social media patterns
    SOCIAL_PATTERNS = [
        r'facebook',
        r'twitter',
        r'instagram',
        r'linkedin',
        r'youtube',
        r'tiktok',
    ]
    
    # Suspicious employer patterns (usually parsing errors)
    SUSPICIOUS_EMPLOYER_PATTERNS = [
        r'^\d+\s*hours?\s*(day|per|/)',
        r'^including\s',
        r'^\d+\s*days?\s*(per|/)',
        r'^unknown',
        r'^\s*$',
    ]
    
    def __init__(self):
        self.navigation_regex = [re.compile(p, re.IGNORECASE) for p in self.NAVIGATION_PATTERNS]
        self.file_regex = [re.compile(p, re.IGNORECASE) for p in self.FILE_PATTERNS]
        self.social_regex = [re.compile(p, re.IGNORECASE) for p in self.SOCIAL_PATTERNS]
        self.employer_regex = [re.compile(p, re.IGNORECASE) for p in self.SUSPICIOUS_EMPLOYER_PATTERNS]
    
    def analyze_jobs(self, session) -> List[Anomaly]:
        """
        Analyze all active jobs in the database for anomalies.
        
        Args:
            session: SQLAlchemy database session
            
        Returns:
            List of Anomaly objects
        """
        from db.models import Job
        
        jobs = session.query(Job).filter(Job.is_active == True).all()
        anomalies = []
        
        for job in jobs:
            job_anomalies = self._check_job(job)
            anomalies.extend(job_anomalies)
        
        return sorted(anomalies, key=lambda a: (
            {'high': 0, 'medium': 1, 'low': 2}[a.severity],
            a.anomaly_type.value
        ))
    
    def _check_job(self, job) -> List[Anomaly]:
        """Check a single job for anomalies."""
        anomalies = []
        
        # Check for short titles
        if len(job.title) < 5:
            anomalies.append(Anomaly(
                job_id=job.id,
                job_title=job.title,
                source_name=job.source_name,
                anomaly_type=AnomalyType.SHORT_TITLE,
                description=f"Title too short ({len(job.title)} chars)",
                severity='high'
            ))
        
        # Check for navigation elements
        for pattern in self.navigation_regex:
            if pattern.match(job.title):
                anomalies.append(Anomaly(
                    job_id=job.id,
                    job_title=job.title,
                    source_name=job.source_name,
                    anomaly_type=AnomalyType.NAVIGATION_ELEMENT,
                    description="Title matches navigation/UI element pattern",
                    severity='high'
                ))
                break
        
        # Check for file references
        for pattern in self.file_regex:
            if pattern.search(job.title):
                anomalies.append(Anomaly(
                    job_id=job.id,
                    job_title=job.title,
                    source_name=job.source_name,
                    anomaly_type=AnomalyType.FILE_REFERENCE,
                    description="Title appears to be a file reference",
                    severity='high'
                ))
                break
        
        # Check for social media links
        for pattern in self.social_regex:
            if pattern.search(job.title) or (job.url and pattern.search(job.url)):
                anomalies.append(Anomaly(
                    job_id=job.id,
                    job_title=job.title,
                    source_name=job.source_name,
                    anomaly_type=AnomalyType.SUSPICIOUS_PATTERN,
                    description="Contains social media reference",
                    severity='medium'
                ))
                break
        
        # Check for malformed employer names
        for pattern in self.employer_regex:
            if pattern.match(job.employer):
                anomalies.append(Anomaly(
                    job_id=job.id,
                    job_title=job.title,
                    source_name=job.source_name,
                    anomaly_type=AnomalyType.DUPLICATE_EMPLOYER,
                    description=f"Suspicious employer name: '{job.employer[:30]}...'",
                    severity='medium'
                ))
                break
        
        # Check for missing critical fields
        if not job.url or job.url == job.title:
            anomalies.append(Anomaly(
                job_id=job.id,
                job_title=job.title,
                source_name=job.source_name,
                anomaly_type=AnomalyType.MALFORMED_URL,
                description="Missing or invalid URL",
                severity='medium'
            ))
        
        # Check for URLs that don't look like job postings
        if job.url:
            suspicious_url_patterns = [
                r'/facebook$', r'/twitter$', r'/instagram$',
                r'QuickLinks\.aspx', r'/contact', r'/about',
            ]
            for pattern in suspicious_url_patterns:
                if re.search(pattern, job.url, re.IGNORECASE):
                    anomalies.append(Anomaly(
                        job_id=job.id,
                        job_title=job.title,
                        source_name=job.source_name,
                        anomaly_type=AnomalyType.MALFORMED_URL,
                        description=f"URL doesn't look like a job posting",
                        severity='medium'
                    ))
                    break
        
        return anomalies
    
    def get_summary(self, anomalies: List[Anomaly]) -> Dict:
        """Get a summary of anomalies by type and severity."""
        summary = {
            'total': len(anomalies),
            'by_severity': {'high': 0, 'medium': 0, 'low': 0},
            'by_type': {},
            'by_source': {},
        }
        
        for a in anomalies:
            summary['by_severity'][a.severity] += 1
            summary['by_type'][a.anomaly_type.value] = summary['by_type'].get(a.anomaly_type.value, 0) + 1
            summary['by_source'][a.source_name] = summary['by_source'].get(a.source_name, 0) + 1
        
        return summary


def run_anomaly_check(auto_delete: bool = False, dry_run: bool = True):
    """
    Run anomaly detection on the database.
    
    Args:
        auto_delete: If True, automatically delete high-severity anomalies
        dry_run: If True, don't actually delete (just show what would be deleted)
    """
    from db.database import init_db, get_session
    from db.models import Job
    
    init_db()
    session = get_session()
    
    detector = AnomalyDetector()
    anomalies = detector.analyze_jobs(session)
    summary = detector.get_summary(anomalies)
    
    print("\n" + "=" * 60)
    print("  ANOMALY DETECTION REPORT")
    print("=" * 60)
    
    print(f"\n  Total Anomalies Found: {summary['total']}")
    
    print("\n  By Severity:")
    for severity, count in summary['by_severity'].items():
        if count > 0:
            print(f"    {severity.upper()}: {count}")
    
    print("\n  By Type:")
    for atype, count in summary['by_type'].items():
        print(f"    {atype}: {count}")
    
    print("\n  By Source:")
    for source, count in summary['by_source'].items():
        print(f"    {source}: {count}")
    
    if anomalies:
        print("\n" + "-" * 60)
        print("  ANOMALY DETAILS")
        print("-" * 60)
        
        for anomaly in anomalies:
            print(f"\n  {anomaly}")
            print(f"    Source: {anomaly.source_name}")
    
    # Handle auto-deletion of high-severity issues
    if auto_delete:
        high_severity = [a for a in anomalies if a.severity == 'high']
        
        if high_severity:
            print("\n" + "-" * 60)
            if dry_run:
                print("  DRY RUN - Would delete the following entries:")
            else:
                print("  DELETING high-severity anomalies:")
            print("-" * 60)
            
            for anomaly in high_severity:
                job = session.query(Job).filter(Job.id == anomaly.job_id).first()
                if job:
                    print(f"  - {job.title[:50]} (ID: {job.id})")
                    if not dry_run:
                        session.delete(job)
            
            if not dry_run:
                session.commit()
                print(f"\n  Deleted {len(high_severity)} entries.")
    
    session.close()
    print("\n" + "=" * 60 + "\n")
    
    return anomalies


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Detect anomalies in scraped job data")
    parser.add_argument('--auto-delete', action='store_true', help='Automatically delete high-severity anomalies')
    parser.add_argument('--apply', action='store_true', help='Actually apply deletions (default is dry-run)')
    
    args = parser.parse_args()
    
    run_anomaly_check(
        auto_delete=args.auto_delete,
        dry_run=not args.apply
    )
