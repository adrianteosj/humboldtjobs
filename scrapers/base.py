"""
Base scraper class and JobData dataclass
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import time
import logging
import requests
from bs4 import BeautifulSoup

from config import REQUEST_DELAY
from processing.salary_parser import parse_salary
from processing.experience_detector import detect_experience, get_education_level
from processing.pdf_scraper import scrape_pdf, is_pdf_available

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
    salary_min: Optional[int] = None  # Parsed minimum salary (annual)
    salary_max: Optional[int] = None  # Parsed maximum salary (annual)
    salary_type: Optional[str] = None  # hourly, monthly, annual, daily
    job_type: Optional[str] = None  # Full-time, Part-time, etc.
    experience_level: Optional[str] = None  # Entry, Mid, Senior
    education_required: Optional[str] = None  # HS, AA, BA, MA, PhD
    requirements: Optional[str] = None  # Qualifications text
    benefits: Optional[str] = None  # Benefits information
    department: Optional[str] = None  # Department within employer
    is_remote: bool = False  # Remote work option
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
    
    def enrich_job(self, job: JobData) -> JobData:
        """
        Enrich a job with parsed salary and experience level detection.
        
        Args:
            job: JobData object to enrich
            
        Returns:
            The same JobData object with enriched fields
        """
        # Parse salary if we have salary text but no parsed values
        if job.salary_text and job.salary_min is None:
            parsed = parse_salary(job.salary_text)
            job.salary_min = parsed.min_annual
            job.salary_max = parsed.max_annual
            job.salary_type = parsed.salary_type
        
        # Detect experience level if not already set
        if job.experience_level is None:
            exp_info = detect_experience(
                job.title,
                job.description,
                job.requirements
            )
            if exp_info.level and exp_info.confidence >= 0.4:
                job.experience_level = exp_info.level
            
            # Also get education if not set
            if job.education_required is None and exp_info.education:
                job.education_required = exp_info.education
        
        # Detect education separately if still not set
        if job.education_required is None:
            education = get_education_level(
                job.title,
                job.description,
                job.requirements
            )
            if education:
                job.education_required = education
        
        # Detect remote work from title or description
        if not job.is_remote:
            text = (job.title + ' ' + (job.description or '')).lower()
            if 'remote' in text or 'work from home' in text or 'wfh' in text:
                job.is_remote = True
        
        return job
    
    def enrich_jobs(self, jobs: List[JobData]) -> List[JobData]:
        """
        Enrich a list of jobs.
        
        Args:
            jobs: List of JobData objects
            
        Returns:
            List of enriched JobData objects
        """
        for job in jobs:
            self.enrich_job(job)
        return jobs
    
    def fetch_detail_page(self, url: str, session: Optional[requests.Session] = None) -> Optional[dict]:
        """
        Fetch and parse a job detail page.
        Override in subclasses for site-specific parsing.
        
        Args:
            url: URL of the job detail page
            session: Optional requests session to reuse
            
        Returns:
            Dictionary with extracted data or None on failure
        """
        try:
            s = session or requests.Session()
            response = s.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0 HumboldtJobs/1.0'},
                timeout=30
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Basic extraction - override in subclasses for specific sites
            result = {}
            
            # Try to find description
            for selector in ['#job-description', '.job-description', '.description', 
                           '[class*="description"]', 'article', 'main']:
                elem = soup.select_one(selector)
                if elem:
                    result['description'] = elem.get_text(strip=True, separator=' ')[:2000]
                    break
            
            # Try to find requirements
            for selector in ['#requirements', '.requirements', '.qualifications',
                           '[class*="requirement"]', '[class*="qualification"]']:
                elem = soup.select_one(selector)
                if elem:
                    result['requirements'] = elem.get_text(strip=True, separator=' ')[:1000]
                    break
            
            # Try to find salary
            for selector in ['#salary', '.salary', '[class*="salary"]', 
                           '[class*="compensation"]', '[class*="pay"]']:
                elem = soup.select_one(selector)
                if elem:
                    result['salary_text'] = elem.get_text(strip=True)[:200]
                    break
            
            return result if result else None
            
        except Exception as e:
            self.logger.warning(f"Failed to fetch detail page {url}: {e}")
            return None
    
    def fetch_pdf_data(self, url: str) -> Optional[dict]:
        """
        Download and extract data from a PDF job posting.
        
        Args:
            url: URL of the PDF file
            
        Returns:
            Dictionary with extracted data or None on failure
        """
        if not is_pdf_available():
            self.logger.warning("PDF scraping not available - pdfplumber not installed")
            return None
        
        try:
            pdf_data = scrape_pdf(url)
            if not pdf_data:
                return None
            
            return {
                'title': pdf_data.title,
                'description': pdf_data.description,
                'requirements': pdf_data.requirements,
                'benefits': pdf_data.benefits,
                'salary_text': pdf_data.salary_text,
                'salary_min': pdf_data.salary_min,
                'salary_max': pdf_data.salary_max,
                'salary_type': pdf_data.salary_type,
                'job_type': pdf_data.job_type,
                'experience_level': pdf_data.experience_level,
                'education_required': pdf_data.education,
                'department': pdf_data.department,
                'location': pdf_data.location,
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to scrape PDF {url}: {e}")
            return None
    
    def apply_detail_data(self, job: JobData, detail_data: dict) -> JobData:
        """
        Apply data from a detail page or PDF to a job.
        Only fills in missing fields, doesn't overwrite existing data.
        
        Args:
            job: JobData object to update
            detail_data: Dictionary of data from detail page
            
        Returns:
            Updated JobData object
        """
        for field, value in detail_data.items():
            if value and hasattr(job, field):
                current = getattr(job, field)
                # Only set if current value is None or empty
                if current is None or (isinstance(current, str) and not current.strip()):
                    setattr(job, field, value)
        
        return job