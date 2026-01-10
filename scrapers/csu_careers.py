"""
CSU Careers Scraper for Cal Poly Humboldt job postings
https://csucareers.calstate.edu/en-us/filter/?location=humboldt
"""
import requests
import re
from datetime import datetime
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .base import BaseScraper, JobData
from config import CSU_CAREERS_BASE_URL, CSU_CAREERS_FILTER_URL, CSU_CAREERS_LOCATION, USER_AGENT


class CSUCareersScraper(BaseScraper):
    """
    Scraper for CSU Careers (PageUp) - Cal Poly Humboldt positions.
    """
    
    def __init__(self):
        super().__init__("csu_careers")
        self.base_url = CSU_CAREERS_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def scrape(self) -> List[JobData]:
        """
        Scrape CSU Careers for Cal Poly Humboldt positions.
        
        Returns:
            List of JobData objects
        """
        self.logger.info("Scraping CSU Careers (Cal Poly Humboldt)...")
        
        all_jobs = []
        
        try:
            # First, get the main filtered page
            jobs = self._scrape_filtered_page()
            all_jobs.extend(jobs)
            self.logger.info(f"  Found {len(jobs)} jobs")
            
        except Exception as e:
            self.logger.error(f"Error scraping CSU Careers: {e}")
        
        self.logger.info(f"Total CSU Careers jobs scraped: {len(all_jobs)}")
        return all_jobs
    
    def _scrape_filtered_page(self) -> List[JobData]:
        """
        Scrape the filtered results page.
        
        Returns:
            List of JobData objects
        """
        # Build URL with Humboldt filter
        url = CSU_CAREERS_FILTER_URL
        params = {
            'location': CSU_CAREERS_LOCATION,
        }
        
        response = self.session.get(url, params=params, timeout=30)
        
        if response.status_code != 200:
            self.logger.error(f"HTTP {response.status_code} from CSU Careers")
            return []
        
        return self._parse_html(response.text)
    
    def _parse_html(self, html: str) -> List[JobData]:
        """
        Parse the HTML response for job listings.
        
        Args:
            html: HTML content string
            
        Returns:
            List of JobData objects
        """
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # PageUp uses tables for job listings
        # Look for job links in the format /en-us/job/{id}/{slug}
        job_links = soup.find_all('a', href=re.compile(r'/en-us/job/\d+/'))
        
        # Also try table rows
        if not job_links:
            table = soup.find('table')
            if table:
                job_links = table.find_all('a', href=re.compile(r'/job/'))
        
        # Track seen URLs to avoid duplicates
        seen_urls = set()
        
        for link in job_links:
            try:
                job = self._parse_job_link(link, soup)
                if job and self.validate_job(job) and job.url not in seen_urls:
                    jobs.append(job)
                    seen_urls.add(job.url)
            except Exception as e:
                self.logger.warning(f"Error parsing job link: {e}")
        
        return jobs
    
    def _parse_job_link(self, link, soup: BeautifulSoup) -> Optional[JobData]:
        """
        Parse a job link element and its surrounding context.
        
        Args:
            link: BeautifulSoup anchor element
            soup: Full page soup for context
            
        Returns:
            JobData object or None
        """
        href = link.get('href', '')
        if not href:
            return None
        
        # Build full URL
        if href.startswith('/'):
            url = f"{self.base_url}{href}"
        else:
            url = href
        
        # Get title from link text
        title = link.get_text(strip=True)
        if not title:
            return None
        
        # Extract job ID from URL
        job_id_match = re.search(r'/job/(\d+)/', url)
        source_id = job_id_match.group(1) if job_id_match else url
        
        # Try to find the row containing this link for additional info
        row = link.find_parent('tr')
        
        closing_date = None
        location = "Arcata, CA"
        job_type = None
        original_category = None
        
        if row:
            # Parse table cells
            cells = row.find_all('td')
            for cell in cells:
                text = cell.get_text(strip=True)
                
                # Check for date pattern
                date_match = re.search(r'([A-Za-z]{3}\s+\d{1,2},\s+\d{4})', text)
                if date_match and not closing_date:
                    try:
                        closing_date = date_parser.parse(date_match.group(1))
                    except (ValueError, TypeError):
                        pass
                
                # Check for location
                if 'Humboldt' in text or 'Arcata' in text:
                    location = text
        
        # Categorize based on title
        category = self._categorize_job(title)
        
        return JobData(
            source_id=f"csu_{source_id}",
            source_name="csu_humboldt",
            title=title,
            url=url,
            employer="Cal Poly Humboldt",
            category=category,
            original_category=original_category,
            location=location,
            closing_date=closing_date,
            job_type=job_type,
        )
    
    def _categorize_job(self, title: str) -> str:
        """
        Determine job category based on title.
        
        Args:
            title: Job title string
            
        Returns:
            Category string
        """
        title_lower = title.lower()
        
        # Education-related
        if any(kw in title_lower for kw in ['faculty', 'professor', 'instructor', 'lecturer', 'teaching', 'academic']):
            return "Education"
        
        # Administrative
        if any(kw in title_lower for kw in ['coordinator', 'analyst', 'specialist', 'assistant', 'administrator', 'manager', 'director']):
            return "Administrative"
        
        # Technical
        if any(kw in title_lower for kw in ['engineer', 'developer', 'technician', 'it ', 'information technology', 'programmer', 'systems']):
            return "Technical"
        
        # Maintenance/Facilities
        if any(kw in title_lower for kw in ['custodian', 'groundskeeper', 'maintenance', 'facilities', 'groundsworker', 'cook', 'food']):
            return "Maintenance"
        
        # Healthcare
        if any(kw in title_lower for kw in ['nurse', 'health', 'medical', 'counselor', 'psychologist', 'therapist']):
            return "Healthcare"
        
        # Public Safety
        if any(kw in title_lower for kw in ['police', 'dispatcher', 'safety', 'security']):
            return "Public Safety"
        
        return "Education"  # Default for university jobs
