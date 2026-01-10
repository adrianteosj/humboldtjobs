"""
CSU Careers Scraper for Cal Poly Humboldt jobs
Scrapes job listings from the California State University careers portal

Uses Playwright for JavaScript rendering since CSU Careers loads jobs dynamically.
"""
import re
from datetime import datetime
from typing import List, Optional
from playwright.sync_api import sync_playwright, Page
from dateutil import parser as date_parser

from .base import BaseScraper, JobData
from config import USER_AGENT


class CSUScraper(BaseScraper):
    """
    Scraper for CSU Careers (Cal Poly Humboldt jobs).
    Uses Playwright to handle JavaScript-rendered content.
    """
    
    BASE_URL = "https://csucareers.calstate.edu"
    SEARCH_URL = "https://csucareers.calstate.edu/en-us/filter/?search=&location=humboldt"
    
    def __init__(self):
        super().__init__("csu")
        self.employer = "Cal Poly Humboldt"
    
    def scrape(self) -> List[JobData]:
        """
        Scrape all CSU Careers jobs for Humboldt location.
        
        Returns:
            List of JobData objects from Cal Poly Humboldt
        """
        all_jobs = []
        
        self.logger.info(f"Scraping {self.employer}...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            
            try:
                all_jobs = self._scrape_all_pages(page)
                self.logger.info(f"  Found {len(all_jobs)} jobs from {self.employer}")
            except Exception as e:
                self.logger.error(f"  Error scraping CSU Careers: {e}")
            
            browser.close()
        
        self.logger.info(f"Total CSU jobs scraped: {len(all_jobs)}")
        return all_jobs
    
    def _scrape_all_pages(self, page: Page) -> List[JobData]:
        """
        Scrape all pages of job listings by navigating to each page URL directly.
        
        Args:
            page: Playwright page object
            
        Returns:
            List of all JobData objects
        """
        all_jobs = []
        page_num = 1
        max_pages = 10  # Safety limit (114 jobs / 20 per page = ~6 pages)
        items_per_page = 20
        
        while page_num <= max_pages:
            # Build page URL
            page_url = f"{self.BASE_URL}/en-us/search/?search=&location=humboldt&page={page_num}&page-items={items_per_page}"
            
            # Navigate to page
            page.goto(page_url, wait_until='networkidle', timeout=30000)
            
            # Wait for job table to load
            try:
                page.wait_for_selector('table', timeout=15000)
            except:
                self.logger.warning(f"No job table found on page {page_num}")
                break
            
            # Parse current page
            jobs = self._parse_page(page)
            
            if not jobs:
                # No more jobs on this page
                break
            
            all_jobs.extend(jobs)
            self.logger.info(f"    Page {page_num}: {len(jobs)} jobs")
            
            # If we got fewer jobs than expected, we're on the last page
            if len(jobs) < items_per_page:
                break
            
            page_num += 1
            self.delay()
        
        return all_jobs
    
    def _parse_page(self, page: Page) -> List[JobData]:
        """
        Parse the current page for job listings.
        
        Args:
            page: Playwright page object
            
        Returns:
            List of JobData objects from this page
        """
        jobs = []
        seen_urls = set()
        
        # Get all table rows
        rows = page.query_selector_all('table tbody tr')
        
        # Jobs are in pairs: job info row + description row
        i = 0
        while i < len(rows):
            try:
                job_row = rows[i]
                
                # Check if this row contains a job link
                link = job_row.query_selector('a[href*="/job/"]')
                if not link:
                    i += 1
                    continue
                
                # Get description from next row if available
                description = None
                if i + 1 < len(rows):
                    desc_row = rows[i + 1]
                    desc_link = desc_row.query_selector('a[href*="/job/"]')
                    if not desc_link:  # It's a description row, not a job row
                        description = desc_row.inner_text().strip()
                        # Clean up "read more" text
                        description = re.sub(r'\.\.\.\s*read more$', '...', description)
                        i += 1  # Skip the description row
                
                job = self._parse_job_row(job_row, link, description)
                if job and self.validate_job(job) and job.url not in seen_urls:
                    jobs.append(job)
                    seen_urls.add(job.url)
                
                i += 1
                
            except Exception as e:
                self.logger.warning(f"Error parsing job row: {e}")
                i += 1
        
        return jobs
    
    def _parse_job_row(self, row, link, description: Optional[str]) -> Optional[JobData]:
        """
        Parse a single job row from the table.
        
        Args:
            row: Playwright element handle for the table row
            link: Playwright element handle for the job link
            description: Optional description from next row
            
        Returns:
            JobData object or None
        """
        # Get href and build full URL
        href = link.get_attribute('href')
        if not href:
            return None
        
        if href.startswith('/'):
            url = f"{self.BASE_URL}{href}"
        else:
            url = href
        
        # Get title from link text
        title = link.inner_text().strip()
        if not title:
            return None
        
        # Extract job ID from URL
        job_id_match = re.search(r'/job/(\d+)/', url)
        source_id = job_id_match.group(1) if job_id_match else url
        
        # Get cells from row
        cells = row.query_selector_all('td')
        
        # Location is usually in second cell
        location = "Arcata, CA"  # Default for Humboldt
        if len(cells) >= 2:
            loc_text = cells[1].inner_text().strip()
            if loc_text and loc_text != "Humboldt":
                location = f"{loc_text}, CA"
        
        # Closing date is usually in third cell
        closing_date = None
        if len(cells) >= 3:
            date_text = cells[2].inner_text().strip()
            closing_date = self._parse_closing_date(date_text)
        
        # Determine category from title
        original_category = self._categorize_from_title(title)
        
        # Determine job type from title
        job_type = self._determine_job_type(title, description)
        
        return JobData(
            source_id=f"csu_{source_id}",
            source_name="csu_humboldt",
            title=title,
            url=url,
            employer=self.employer,
            category="Education",  # Will be normalized
            original_category=original_category,
            location=location,
            description=description[:500] if description else None,
            closing_date=closing_date,
            job_type=job_type,
        )
    
    def _parse_closing_date(self, date_text: str) -> Optional[datetime]:
        """
        Parse closing date from text.
        
        Args:
            date_text: Date string like "Jan 20, 2026" or "Open until filled"
            
        Returns:
            datetime object or None
        """
        if not date_text or 'open until filled' in date_text.lower():
            return None
        
        try:
            return date_parser.parse(date_text)
        except:
            return None
    
    def _categorize_from_title(self, title: str) -> str:
        """
        Determine original category from job title.
        
        Args:
            title: Job title
            
        Returns:
            Category string
        """
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['faculty', 'professor', 'instructor', 'lecturer']):
            return "Faculty/Academic"
        elif any(word in title_lower for word in ['custodian', 'groundsworker', 'maintenance', 'facilities']):
            return "Facilities/Maintenance"
        elif any(word in title_lower for word in ['police', 'dispatcher', 'safety']):
            return "Public Safety"
        elif any(word in title_lower for word in ['analyst', 'specialist', 'manager', 'coordinator']):
            return "Administrative"
        elif any(word in title_lower for word in ['counselor', 'advisor', 'psychotherapist']):
            return "Student Services"
        elif any(word in title_lower for word in ['cook', 'food', 'dining']):
            return "Food Services"
        elif any(word in title_lower for word in ['driver', 'bus']):
            return "Transportation"
        elif any(word in title_lower for word in ['student assistant', 'student worker']):
            return "Student Employment"
        else:
            return "Staff"
    
    def _determine_job_type(self, title: str, description: Optional[str]) -> Optional[str]:
        """
        Determine job type from title and description.
        
        Args:
            title: Job title
            description: Job description
            
        Returns:
            Job type string or None
        """
        text = (title + " " + (description or "")).lower()
        
        if 'tenure-track' in text or 'tenure track' in text:
            return "Tenure-Track"
        elif 'temporary' in text or 'visiting' in text:
            return "Temporary"
        elif 'part-time' in text or 'part time' in text:
            return "Part-time"
        elif 'full-time' in text or 'full time' in text:
            return "Full-time"
        elif 'intermittent' in text:
            return "Intermittent"
        elif 'student assistant' in text:
            return "Student Employment"
        
        return None
