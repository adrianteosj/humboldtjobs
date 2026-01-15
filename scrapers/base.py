"""
Base scraper class and JobData dataclass
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import time
import logging

from config import REQUEST_DELAY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@dataclass
class JobData:
    """Standardized job data structure used across all scrapers"""
    source_id: str
    source_name: str
    title: str
    url: str
    employer: str
    category: str = "Other"  # Will be normalized later
    original_category: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    salary_text: Optional[str] = None
    job_type: Optional[str] = None
    posted_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None


class BaseScraper(ABC):
    """Abstract base class for all job scrapers"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"scraper.{name}")
    
    @abstractmethod
    def scrape(self) -> List[JobData]:
        """
        Scrape jobs from the source.
        Must be implemented by subclasses.
        
        Returns:
            List of JobData objects
        """
        pass
    
    def delay(self):
        """Polite delay between requests to avoid overwhelming servers"""
        time.sleep(REQUEST_DELAY)
    
    # Common patterns that indicate scraping errors, not real job titles
    INVALID_TITLE_PATTERNS = [
        'skip to content', 'skip to main', 'skip navigation',
        'javascript', 'click here', 'read more', 'learn more',
        'view details', 'apply now', 'loading', 'please wait',
        'menu', 'navigation', 'login', 'sign in',
        'cookie', 'accept', 'decline', 'close', 'back to top',
        'indeed', 'days ago'  # Buttons/metadata picked up by mistake
    ]
    
    # URLs that are clearly not job listings
    INVALID_URL_PATTERNS = [
        '#content', '#main', '#skip', '/benefits/', '/about/',
        '/contact/', '/login/', '/signin/', '/faq/', '/privacy/',
        '/terms/', '/cookie/', 'javascript:', 'mailto:', 'tel:'
    ]
    
    def validate_job(self, job: JobData) -> bool:
        """
        Validate that a job has required fields and is a real job listing.
        
        Args:
            job: JobData object to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not job.title:
            self.logger.warning("Job missing title, skipping")
            return False
        if not job.url:
            self.logger.warning(f"Job '{job.title}' missing URL, skipping")
            return False
        if not job.employer:
            self.logger.warning(f"Job '{job.title}' missing employer, skipping")
            return False
        
        # Normalize title - remove excessive whitespace/newlines
        title_clean = ' '.join(job.title.split())
        title_lower = title_clean.lower().strip()
        
        # Check for multi-line titles (indicates scraping error)
        if '\n' in job.title or len(job.title) - len(title_clean) > 5:
            self.logger.warning(f"Multi-line/malformed job title: '{job.title[:50]}...', skipping")
            return False
        
        # Check for invalid title patterns
        for pattern in self.INVALID_TITLE_PATTERNS:
            if pattern in title_lower:
                self.logger.warning(f"Invalid job title pattern '{pattern}' found in '{job.title}', skipping")
                return False
        
        # Check for too-short titles (less than 3 real characters)
        if len(title_lower) < 3:
            self.logger.warning(f"Job title too short: '{job.title}', skipping")
            return False
        
        # Check if title contains at least some letters (not just numbers/symbols)
        if not any(c.isalpha() for c in title_lower):
            self.logger.warning(f"Job title has no letters: '{job.title}', skipping")
            return False
        
        # Check for invalid URL patterns
        url_lower = job.url.lower()
        for pattern in self.INVALID_URL_PATTERNS:
            if pattern in url_lower:
                self.logger.warning(f"Invalid URL pattern '{pattern}' found in '{job.url}', skipping")
                return False
        
        return True
