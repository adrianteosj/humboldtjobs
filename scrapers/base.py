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
    
    def validate_job(self, job: JobData) -> bool:
        """
        Validate that a job has required fields.
        
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
        return True
