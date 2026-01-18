"""
CivicPlus Job Scrapers for Wiyot Tribe and City of Rio Dell
These sites use CivicPlus government website templates.
"""
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from dateutil import parser as date_parser

from .base import BaseScraper, JobData
from config import USER_AGENT


class WiyotScraper(BaseScraper):
    """
    Scraper for Wiyot Tribe jobs.
    https://www.wiyot.us/Jobs.aspx
    """
    
    def __init__(self):
        super().__init__("wiyot")
        self.base_url = "https://www.wiyot.us"
        self.jobs_url = "https://www.wiyot.us/Jobs.aspx"
    
    def scrape(self) -> List[JobData]:
        self.logger.info("Scraping Wiyot Tribe jobs...")
        
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.jobs_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                
                html = page.content()
                jobs = self._parse_html(html)
                self.logger.info(f"  Found {len(jobs)} jobs from Wiyot Tribe")
            except Exception as e:
                self.logger.error(f"  Error scraping Wiyot: {e}")
            
            browser.close()
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # CivicPlus job listings are in div.listing or similar
        # Look for job title links
        job_links = soup.find_all('a', href=re.compile(r'JobDetails\.aspx'))
        
        for link in job_links:
            try:
                title = link.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                
                href = link.get('href', '')
                if href.startswith('/'):
                    url = f"{self.base_url}{href}"
                else:
                    url = f"{self.base_url}/{href}"
                
                # Extract job ID from URL
                job_id_match = re.search(r'JobID=(\d+)', url)
                job_id = job_id_match.group(1) if job_id_match else url
                
                # Find parent container for more details
                container = link.find_parent(['div', 'tr', 'li'])
                
                description = None
                closing_date = None
                
                if container:
                    # Look for description text
                    desc_elem = container.find('p') or container.find('div', class_='description')
                    if desc_elem:
                        description = desc_elem.get_text(strip=True)[:500]
                    
                    # Look for date
                    date_text = container.get_text()
                    date_match = re.search(r'Open Until Filled|(\d{1,2}/\d{1,2}/\d{4})', date_text)
                    if date_match and date_match.group(1):
                        closing_date = self._parse_date(date_match.group(1))
                
                job = JobData(
                    source_id=f"wiyot_{job_id}",
                    source_name="wiyot",
                    title=title,
                    url=url,
                    employer="Wiyot Tribe",
                    category="Government",
                    location="Loleta, CA",
                    description=description,
                    closing_date=closing_date,
                )
                
                if self.validate_job(job):
                    jobs.append(job)
                    
            except Exception as e:
                self.logger.warning(f"Error parsing Wiyot job: {e}")
        
        # Also look for featured jobs (different structure)
        # Wiyot uses "Featured Job Opportunities" section with h3 titles
        featured_sections = soup.find_all(['div', 'section'], class_=re.compile(r'featured|listing'))
        
        # Also find by h3 headers that look like job titles
        all_h3s = soup.find_all('h3')
        
        # List of non-job titles to skip (navigation elements, etc.)
        skip_titles = [
            'featured job opportunities', 'job opportunities', 'tools', 'categories',
            'live edit', 'site links', 'connect with us', 'quick links', 'steps',
            'about', 'contact', 'search', 'navigation', 'menu', 'footer',
            'site tools', 'share', 'accessibility'
        ]
        
        for h3 in all_h3s:
            title = h3.get_text(strip=True)
            
            # Filter for job-like titles
            if not title or len(title) < 5:
                continue
            if title.lower() in skip_titles:
                continue
            
            # Check if already captured
            if any(j.title == title for j in jobs):
                continue
            
            try:
                # Find link near the h3
                link = h3.find('a', href=True) or h3.find_next('a', href=True)
                if link:
                    href = link.get('href', '')
                    if href.startswith('/'):
                        url = f"{self.base_url}{href}"
                    elif href.startswith('http'):
                        url = href
                    else:
                        url = self.jobs_url
                else:
                    url = self.jobs_url
                
                # Get description from nearby paragraph
                description = None
                parent = h3.find_parent(['div', 'section', 'article'])
                if parent:
                    desc_elem = parent.find('p')
                    if desc_elem:
                        desc_text = desc_elem.get_text(strip=True)
                        # Avoid picking up category names as descriptions
                        if len(desc_text) > 20 and 'Department' not in desc_text:
                            description = desc_text[:500]
                
                job = JobData(
                    source_id=f"wiyot_{title[:30].replace(' ', '_')}",
                    source_name="wiyot",
                    title=title,
                    url=url,
                    employer="Wiyot Tribe",
                    category="Government",
                    location="Loleta, CA",
                    description=description,
                )
                
                if self.validate_job(job):
                    jobs.append(job)
                    
            except Exception as e:
                self.logger.warning(f"Error parsing Wiyot h3 job: {e}")
        
        return jobs
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        try:
            return date_parser.parse(date_str)
        except:
            return None


class RioDellScraper(BaseScraper):
    """
    Scraper for City of Rio Dell jobs.
    https://www.cityofriodell.ca.gov/282/Employment
    """
    
    def __init__(self):
        super().__init__("rio_dell")
        self.base_url = "https://www.cityofriodell.ca.gov"
        self.jobs_url = "https://www.cityofriodell.ca.gov/282/Employment"
    
    def scrape(self) -> List[JobData]:
        self.logger.info("Scraping City of Rio Dell jobs...")
        
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.jobs_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                
                html = page.content()
                jobs = self._parse_html(html)
                self.logger.info(f"  Found {len(jobs)} jobs from City of Rio Dell")
            except Exception as e:
                self.logger.error(f"  Error scraping Rio Dell: {e}")
            
            browser.close()
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Rio Dell lists jobs in the main content area
        # Look for job titles (usually bold or in headers)
        content = soup.find('div', class_='fr-view') or soup.find('article') or soup.find('main')
        
        if not content:
            content = soup
        
        # Find all bold text that could be job titles
        job_titles = content.find_all(['strong', 'b', 'h2', 'h3'])
        
        for title_elem in job_titles:
            title = title_elem.get_text(strip=True)
            
            # Filter to likely job titles
            job_keywords = ['Police', 'Officer', 'Superintendent', 'Manager', 'Director', 
                           'Clerk', 'Technician', 'Worker', 'Assistant', 'Coordinator']
            
            if not any(kw in title for kw in job_keywords):
                continue
            
            if len(title) < 5 or len(title) > 100:
                continue
            
            try:
                # Get parent section for more details
                parent = title_elem.find_parent(['div', 'section', 'p'])
                
                salary_text = None
                description = None
                job_type = None
                
                if parent:
                    text = parent.get_text()
                    
                    # Extract salary
                    salary_match = re.search(r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?(?:\s*(?:annually|per year|hourly))?', text, re.IGNORECASE)
                    if salary_match:
                        salary_text = salary_match.group(0)
                    
                    # Extract job type
                    if 'Full-Time' in text or 'Full Time' in text:
                        job_type = 'Full-Time'
                    elif 'Part-Time' in text or 'Part Time' in text:
                        job_type = 'Part-Time'
                    
                    # Get description (first paragraph after title)
                    next_p = title_elem.find_next('p')
                    if next_p:
                        description = next_p.get_text(strip=True)[:500]
                
                # Always use the employment page URL (not PDF links)
                # PDFs don't provide a good user experience
                url = self.jobs_url
                
                job = JobData(
                    source_id=f"rio_dell_{title[:30].replace(' ', '_')}",
                    source_name="rio_dell",
                    title=title,
                    url=url,
                    employer="City of Rio Dell",
                    category="Government",
                    location="Rio Dell, CA",
                    description=description,
                    salary_text=salary_text,
                    job_type=job_type,
                )
                
                if self.validate_job(job):
                    # Avoid duplicates
                    if not any(j.title == title for j in jobs):
                        jobs.append(job)
                        
            except Exception as e:
                self.logger.warning(f"Error parsing Rio Dell job: {e}")
        
        return jobs
