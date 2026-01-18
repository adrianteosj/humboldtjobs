"""
Small City Job Scrapers for Humboldt County
- City of Blue Lake
- City of Ferndale  
- City of Trinidad

Enhanced with PDF scraping support for job announcements.
"""
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from dateutil import parser as date_parser

from .base import BaseScraper, JobData
from config import USER_AGENT
from processing.pdf_scraper import is_pdf_available, scrape_pdf


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
                jobs = self._parse_html(html, page)
                
                # Enrich jobs with parsed salary and experience detection
                self.enrich_jobs(jobs)
                
                self.logger.info(f"  Found {len(jobs)} jobs from City of Blue Lake")
            except Exception as e:
                self.logger.error(f"  Error scraping Blue Lake: {e}")
            
            browser.close()
        
        return jobs
    
    def _parse_html(self, html: str, page=None) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Look for job content in main article/content area
        content = soup.find('article') or soup.find('main') or soup.find('div', class_='entry-content')
        
        if not content:
            content = soup
        
        # First, look for PDF links to job announcements
        pdf_links = content.find_all('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        
        for pdf_link in pdf_links:
            pdf_url = pdf_link.get('href', '')
            link_text = pdf_link.get_text(strip=True)
            
            # Check if this looks like a job-related PDF
            if not self._is_job_related_pdf(link_text, pdf_url):
                continue
            
            # Build full URL if relative
            if pdf_url and not pdf_url.startswith('http'):
                pdf_url = f"{self.base_url}{pdf_url}" if pdf_url.startswith('/') else f"{self.base_url}/{pdf_url}"
            
            # Try to scrape the PDF
            if is_pdf_available():
                self.logger.info(f"    Scraping PDF: {pdf_url}")
                pdf_data = scrape_pdf(pdf_url)
                
                if pdf_data:
                    title = pdf_data.title or link_text
                    if not title or len(title) < 5:
                        title = link_text
                    
                    job = JobData(
                        source_id=f"blue_lake_{title[:30].replace(' ', '_')}",
                        source_name="blue_lake",
                        title=title,
                        url=self.jobs_url,  # Link to main page for better UX
                        employer="City of Blue Lake",
                        category="Government",
                        location=pdf_data.location or "Blue Lake, CA",
                        salary_text=pdf_data.salary_text,
                        salary_min=pdf_data.salary_min,
                        salary_max=pdf_data.salary_max,
                        salary_type=pdf_data.salary_type,
                        description=pdf_data.description,
                        requirements=pdf_data.requirements,
                        benefits=pdf_data.benefits,
                        job_type=pdf_data.job_type,
                        experience_level=pdf_data.experience_level,
                        education_required=pdf_data.education,
                        department=pdf_data.department,
                    )
                    
                    if self.validate_job(job):
                        if not any(j.title == title for j in jobs):
                            jobs.append(job)
                            continue
        
        # Fall back to HTML parsing for jobs without PDFs
        job_elements = content.find_all(['h2', 'h3', 'h4', 'strong', 'b'])
        
        for elem in job_elements:
            title = elem.get_text(strip=True)
            
            # Filter for job-like titles
            if not self._is_job_title(title):
                continue
            
            # Skip if we already got this job from PDF
            if any(j.title == title for j in jobs):
                continue
            
            try:
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
    
    def _is_job_related_pdf(self, text: str, url: str) -> bool:
        """Check if a PDF link is job-related."""
        combined = (text + ' ' + url).lower()
        job_keywords = ['job', 'position', 'employment', 'announcement', 'opening', 
                       'recruit', 'vacancy', 'application', 'career']
        return any(kw in combined for kw in job_keywords)
    
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
                jobs = self._parse_ferndale_html(html)
                
                # Enrich jobs
                self.enrich_jobs(jobs)
                
                self.logger.info(f"  Found {len(jobs)} jobs from City of Ferndale")
            except Exception as e:
                self.logger.error(f"  Error scraping Ferndale: {e}")
            
            browser.close()
        
        return jobs
    
    def _parse_ferndale_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # First, look for PDF job announcements
        pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        
        for pdf_link in pdf_links:
            pdf_url = pdf_link.get('href', '')
            link_text = pdf_link.get_text(strip=True)
            
            if not self._is_job_related_pdf(link_text, pdf_url):
                continue
            
            if pdf_url and not pdf_url.startswith('http'):
                pdf_url = f"{self.base_url}{pdf_url}" if pdf_url.startswith('/') else f"{self.base_url}/{pdf_url}"
            
            if is_pdf_available():
                self.logger.info(f"    Scraping PDF: {pdf_url}")
                pdf_data = scrape_pdf(pdf_url)
                
                if pdf_data:
                    title = pdf_data.title or link_text
                    if not title or len(title) < 5:
                        title = link_text
                    
                    job = JobData(
                        source_id=f"ferndale_{title[:30].replace(' ', '_')}",
                        source_name="ferndale",
                        title=title,
                        url=self.jobs_url,
                        employer="City of Ferndale",
                        category="Government",
                        location=pdf_data.location or "Ferndale, CA",
                        salary_text=pdf_data.salary_text,
                        salary_min=pdf_data.salary_min,
                        salary_max=pdf_data.salary_max,
                        salary_type=pdf_data.salary_type,
                        description=pdf_data.description,
                        requirements=pdf_data.requirements,
                        benefits=pdf_data.benefits,
                        job_type=pdf_data.job_type,
                        experience_level=pdf_data.experience_level,
                        education_required=pdf_data.education,
                        department=pdf_data.department,
                    )
                    
                    if self.validate_job(job):
                        if not any(j.title == title for j in jobs):
                            jobs.append(job)
        
        # Ferndale uses a table to list jobs
        table = soup.find('table')
        
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    if row.find('th'):
                        continue
                    
                    dept_cell = cells[0]
                    position_cell = cells[1]
                    closing_cell = cells[2] if len(cells) > 2 else None
                    
                    title = position_cell.get_text(strip=True)
                    department = dept_cell.get_text(strip=True)
                    
                    if not title or not self._is_job_title(title):
                        continue
                    
                    # Skip if already got from PDF
                    if any(j.title == title for j in jobs):
                        continue
                    
                    closing_date = None
                    if closing_cell:
                        closing_text = closing_cell.get_text(strip=True)
                        if closing_text.lower() != 'open':
                            try:
                                closing_date = date_parser.parse(closing_text)
                            except:
                                pass
                    
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
                            department=department if department else None,
                        )
                        
                        if self.validate_job(job):
                            if not any(j.title == title for j in jobs):
                                jobs.append(job)
                                
                    except Exception as e:
                        self.logger.warning(f"Error parsing Ferndale job: {e}")
        
        if not jobs:
            page_text = soup.get_text().lower()
            if 'no current' in page_text or 'no open' in page_text or 'not currently' in page_text:
                self.logger.info("  No current job openings at City of Ferndale")
        
        return jobs
    
    def _is_job_related_pdf(self, text: str, url: str) -> bool:
        """Check if a PDF link is job-related."""
        combined = (text + ' ' + url).lower()
        job_keywords = ['job', 'position', 'employment', 'announcement', 'opening', 
                       'recruit', 'vacancy', 'application', 'career']
        return any(kw in combined for kw in job_keywords)
    
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
                jobs = self._parse_trinidad_html(html)
                
                # Enrich jobs
                self.enrich_jobs(jobs)
                
                self.logger.info(f"  Found {len(jobs)} jobs from City of Trinidad")
            except Exception as e:
                self.logger.error(f"  Error scraping Trinidad: {e}")
            
            browser.close()
        
        return jobs
    
    def _parse_trinidad_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        content = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
        
        if not content:
            content = soup
        
        page_text = content.get_text().lower()
        if 'no current' in page_text or 'no open' in page_text or 'not currently' in page_text:
            self.logger.info("  No current job openings at City of Trinidad")
            return []
        
        # First, look for PDF job announcements
        pdf_links = content.find_all('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        
        for pdf_link in pdf_links:
            pdf_url = pdf_link.get('href', '')
            link_text = pdf_link.get_text(strip=True)
            
            if not self._is_job_related_pdf(link_text, pdf_url):
                continue
            
            if pdf_url and not pdf_url.startswith('http'):
                pdf_url = f"{self.base_url}{pdf_url}" if pdf_url.startswith('/') else f"{self.base_url}/{pdf_url}"
            
            if is_pdf_available():
                self.logger.info(f"    Scraping PDF: {pdf_url}")
                pdf_data = scrape_pdf(pdf_url)
                
                if pdf_data:
                    title = pdf_data.title or link_text
                    if not title or len(title) < 5:
                        title = link_text
                    
                    job = JobData(
                        source_id=f"trinidad_{title[:30].replace(' ', '_')}",
                        source_name="trinidad",
                        title=title,
                        url=self.jobs_url,
                        employer="City of Trinidad",
                        category="Government",
                        location=pdf_data.location or "Trinidad, CA",
                        salary_text=pdf_data.salary_text,
                        salary_min=pdf_data.salary_min,
                        salary_max=pdf_data.salary_max,
                        salary_type=pdf_data.salary_type,
                        description=pdf_data.description,
                        requirements=pdf_data.requirements,
                        benefits=pdf_data.benefits,
                        job_type=pdf_data.job_type,
                        experience_level=pdf_data.experience_level,
                        education_required=pdf_data.education,
                        department=pdf_data.department,
                    )
                    
                    if self.validate_job(job):
                        if not any(j.title == title for j in jobs):
                            jobs.append(job)
        
        # Fall back to HTML parsing
        job_elements = content.find_all(['h2', 'h3', 'h4', 'strong', 'a'])
        
        for elem in job_elements:
            title = elem.get_text(strip=True)
            
            if not self._is_job_title(title):
                continue
            
            # Skip if already got from PDF
            if any(j.title == title for j in jobs):
                continue
            
            try:
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
    
    def _is_job_related_pdf(self, text: str, url: str) -> bool:
        """Check if a PDF link is job-related."""
        combined = (text + ' ' + url).lower()
        job_keywords = ['job', 'position', 'employment', 'announcement', 'opening', 
                       'recruit', 'vacancy', 'application', 'career']
        return any(kw in combined for kw in job_keywords)
    
    def _is_job_title(self, text: str) -> bool:
        if not text or len(text) < 5 or len(text) > 100:
            return False
        
        job_keywords = ['Position', 'Officer', 'Clerk', 'Director', 'Manager', 
                       'Coordinator', 'Technician', 'Worker', 'Assistant',
                       'Planner', 'Specialist', 'Analyst']
        
        return any(kw.lower() in text.lower() for kw in job_keywords)
