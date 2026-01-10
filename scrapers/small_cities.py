"""
Small City Job Scrapers for Humboldt County
- City of Blue Lake
- City of Ferndale  
- City of Trinidad
"""
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from dateutil import parser as date_parser

from .base import BaseScraper, JobData
from config import USER_AGENT


class BlueLakeScraper(BaseScraper):
    """
    Scraper for City of Blue Lake jobs.
    https://bluelake.ca.gov/employment-opportunities/
    """
    
    def __init__(self):
        super().__init__("blue_lake")
        self.base_url = "https://bluelake.ca.gov"
        self.jobs_url = "https://bluelake.ca.gov/employment-opportunities/"
    
    def scrape(self) -> List[JobData]:
        self.logger.info("Scraping City of Blue Lake jobs...")
        
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.jobs_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                
                html = page.content()
                jobs = self._parse_html(html)
                self.logger.info(f"  Found {len(jobs)} jobs from City of Blue Lake")
            except Exception as e:
                self.logger.error(f"  Error scraping Blue Lake: {e}")
            
            browser.close()
        
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Look for job content in main article/content area
        content = soup.find('article') or soup.find('main') or soup.find('div', class_='entry-content')
        
        if not content:
            content = soup
        
        # Look for job titles - typically in headers or bold text
        job_elements = content.find_all(['h2', 'h3', 'h4', 'strong', 'b'])
        
        for elem in job_elements:
            title = elem.get_text(strip=True)
            
            # Filter for job-like titles
            if not self._is_job_title(title):
                continue
            
            try:
                # Always use the employment page URL (not PDF links)
                # PDFs don't provide a good user experience
                url = self.jobs_url
                
                # Get surrounding text for details
                parent = elem.find_parent(['div', 'p', 'section'])
                salary_text = None
                description = None
                
                if parent:
                    text = parent.get_text()
                    salary_match = re.search(r'\$[\d,]+(?:\.\d{2})?(?:\s*[-–]\s*\$[\d,]+(?:\.\d{2})?)?(?:\s*(?:per|/)\s*(?:hour|hr|month|year|annually))?', text, re.IGNORECASE)
                    if salary_match:
                        salary_text = salary_match.group(0)
                    
                    description = text[:300] if len(text) > 10 else None
                
                job = JobData(
                    source_id=f"blue_lake_{title[:30].replace(' ', '_')}",
                    source_name="blue_lake",
                    title=title,
                    url=url,
                    employer="City of Blue Lake",
                    category="Government",
                    location="Blue Lake, CA",
                    salary_text=salary_text,
                    description=description,
                )
                
                if self.validate_job(job):
                    if not any(j.title == title for j in jobs):
                        jobs.append(job)
                        
            except Exception as e:
                self.logger.warning(f"Error parsing Blue Lake job: {e}")
        
        return jobs
    
    def _is_job_title(self, text: str) -> bool:
        """Check if text looks like a job title."""
        if not text or len(text) < 5 or len(text) > 100:
            return False
        
        job_keywords = ['Position', 'Officer', 'Clerk', 'Director', 'Manager', 
                       'Coordinator', 'Technician', 'Worker', 'Assistant', 
                       'Specialist', 'Supervisor', 'Engineer', 'Analyst']
        
        return any(kw.lower() in text.lower() for kw in job_keywords)


class FerndaleScraper(BaseScraper):
    """
    Scraper for City of Ferndale jobs.
    https://ci.ferndale.ca.us/employment/
    """
    
    def __init__(self):
        super().__init__("ferndale")
        self.base_url = "https://ci.ferndale.ca.us"
        self.jobs_url = "https://ci.ferndale.ca.us/employment/"
    
    def scrape(self) -> List[JobData]:
        self.logger.info("Scraping City of Ferndale jobs...")
        
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.jobs_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                
                html = page.content()
                jobs = self._parse_html(html)
                self.logger.info(f"  Found {len(jobs)} jobs from City of Ferndale")
            except Exception as e:
                self.logger.error(f"  Error scraping Ferndale: {e}")
            
            browser.close()
        
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Ferndale uses a table to list jobs
        # Look for table rows with job listings
        table = soup.find('table')
        
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # Skip header row
                    if row.find('th'):
                        continue
                    
                    # Extract department, position, and closing date
                    dept_cell = cells[0]
                    position_cell = cells[1]
                    closing_cell = cells[2] if len(cells) > 2 else None
                    
                    title = position_cell.get_text(strip=True)
                    department = dept_cell.get_text(strip=True)
                    
                    if not title or not self._is_job_title(title):
                        continue
                    
                    # Parse closing date
                    closing_date = None
                    if closing_cell:
                        closing_text = closing_cell.get_text(strip=True)
                        if closing_text.lower() != 'open':
                            try:
                                from dateutil import parser as date_parser
                                closing_date = date_parser.parse(closing_text)
                            except:
                                pass
                    
                    # Always use the employment page URL (not PDF links)
                    url = self.jobs_url
                    
                    try:
                        job = JobData(
                            source_id=f"ferndale_{title[:30].replace(' ', '_')}",
                            source_name="ferndale",
                            title=title,
                            url=url,
                            employer="City of Ferndale",
                            category="Government",
                            location="Ferndale, CA",
                            closing_date=closing_date,
                            description=f"Department: {department}" if department else None,
                        )
                        
                        if self.validate_job(job):
                            if not any(j.title == title for j in jobs):
                                jobs.append(job)
                                
                    except Exception as e:
                        self.logger.warning(f"Error parsing Ferndale job: {e}")
        
        # Fallback: check for "no openings" message
        if not jobs:
            page_text = soup.get_text().lower()
            if 'no current' in page_text or 'no open' in page_text or 'not currently' in page_text:
                self.logger.info("  No current job openings at City of Ferndale")
        
        return jobs
    
    def _is_job_title(self, text: str) -> bool:
        if not text or len(text) < 5 or len(text) > 100:
            return False
        
        job_keywords = ['Position', 'Officer', 'Clerk', 'Director', 'Manager', 
                       'Coordinator', 'Technician', 'Worker', 'Assistant']
        
        return any(kw.lower() in text.lower() for kw in job_keywords)


class TrinidadScraper(BaseScraper):
    """
    Scraper for City of Trinidad jobs.
    https://www.trinidad.ca.gov/employment-opportunities
    """
    
    def __init__(self):
        super().__init__("trinidad")
        self.base_url = "https://www.trinidad.ca.gov"
        self.jobs_url = "https://www.trinidad.ca.gov/employment-opportunities"
    
    def scrape(self) -> List[JobData]:
        self.logger.info("Scraping City of Trinidad jobs...")
        
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.jobs_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                
                html = page.content()
                jobs = self._parse_html(html)
                self.logger.info(f"  Found {len(jobs)} jobs from City of Trinidad")
            except Exception as e:
                self.logger.error(f"  Error scraping Trinidad: {e}")
            
            browser.close()
        
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        content = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
        
        if not content:
            content = soup
        
        page_text = content.get_text().lower()
        if 'no current' in page_text or 'no open' in page_text or 'not currently' in page_text:
            self.logger.info("  No current job openings at City of Trinidad")
            return []
        
        # Look for job links or headers
        job_elements = content.find_all(['h2', 'h3', 'h4', 'strong', 'a'])
        
        for elem in job_elements:
            title = elem.get_text(strip=True)
            
            if not self._is_job_title(title):
                continue
            
            try:
                # Always use the employment page URL (not PDF links)
                # PDFs don't provide a good user experience
                url = self.jobs_url
                
                job = JobData(
                    source_id=f"trinidad_{title[:30].replace(' ', '_')}",
                    source_name="trinidad",
                    title=title,
                    url=url,
                    employer="City of Trinidad",
                    category="Government",
                    location="Trinidad, CA",
                )
                
                if self.validate_job(job):
                    if not any(j.title == title for j in jobs):
                        jobs.append(job)
                        
            except Exception as e:
                self.logger.warning(f"Error parsing Trinidad job: {e}")
        
        return jobs
    
    def _is_job_title(self, text: str) -> bool:
        if not text or len(text) < 5 or len(text) > 100:
            return False
        
        job_keywords = ['Position', 'Officer', 'Clerk', 'Director', 'Manager', 
                       'Coordinator', 'Technician', 'Worker', 'Assistant',
                       'Planner', 'Specialist', 'Analyst']
        
        return any(kw.lower() in text.lower() for kw in job_keywords)
