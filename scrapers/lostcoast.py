"""
Lost Coast Outpost Job Scraper
https://lostcoastoutpost.com/jobs/

Local news site with community job listings.
"""
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from dateutil import parser as date_parser

from .base import BaseScraper, JobData
from config import USER_AGENT


class LostCoastOutpostScraper(BaseScraper):
    """
    Scraper for Lost Coast Outpost job listings.
    """
    
    def __init__(self):
        super().__init__("lostcoast")
        self.base_url = "https://lostcoastoutpost.com"
        self.jobs_url = "https://lostcoastoutpost.com/jobs/"
    
    def scrape(self) -> List[JobData]:
        self.logger.info("Scraping Lost Coast Outpost jobs...")
        
        all_jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.jobs_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                
                html = page.content()
                all_jobs = self._parse_html(html)
                self.logger.info(f"  Found {len(all_jobs)} jobs from Lost Coast Outpost")
                
            except Exception as e:
                self.logger.error(f"  Error scraping Lost Coast Outpost: {e}")
            
            browser.close()
        
        return all_jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # LCO job listings are typically in article or div containers
        # Look for job links
        job_containers = soup.find_all(['article', 'div'], class_=re.compile(r'job|listing|post'))
        
        if not job_containers:
            # Try finding all links to job pages
            job_links = soup.find_all('a', href=re.compile(r'/jobs/\d+|/job/'))
            
            for link in job_links:
                try:
                    title = link.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    
                    href = link.get('href', '')
                    url = f"{self.base_url}{href}" if href.startswith('/') else href
                    
                    # Extract job ID
                    id_match = re.search(r'/jobs?/(\d+)', url)
                    job_id = id_match.group(1) if id_match else href
                    
                    # Get parent container for employer/details
                    container = link.find_parent(['div', 'article', 'li'])
                    
                    employer = "Humboldt County Employer"
                    location = "Humboldt County, CA"
                    
                    if container:
                        text = container.get_text()
                        # Try to extract employer from text
                        # Patterns like "Company Name - Location" or "at Company Name"
                        emp_match = re.search(r'(?:at|by)\s+([A-Z][^-\n]+?)(?:\s*-|$)', text)
                        if emp_match:
                            employer = emp_match.group(1).strip()
                    
                    job = JobData(
                        source_id=f"lco_{job_id}",
                        source_name="lostcoast",
                        title=title,
                        url=url,
                        employer=employer,
                        category=self._determine_category(title),
                        location=location,
                    )
                    
                    if self.validate_job(job):
                        jobs.append(job)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing LCO job: {e}")
        else:
            for container in job_containers:
                try:
                    title_elem = container.find(['h2', 'h3', 'h4', 'a'])
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    
                    link = container.find('a', href=True)
                    if link:
                        href = link.get('href', '')
                        url = f"{self.base_url}{href}" if href.startswith('/') else href
                    else:
                        continue
                    
                    id_match = re.search(r'/jobs?/(\d+)', url)
                    job_id = id_match.group(1) if id_match else title[:20]
                    
                    # Extract employer
                    employer = "Humboldt County Employer"
                    emp_elem = container.find(class_=re.compile(r'company|employer|author'))
                    if emp_elem:
                        employer = emp_elem.get_text(strip=True)
                    
                    job = JobData(
                        source_id=f"lco_{job_id}",
                        source_name="lostcoast",
                        title=title,
                        url=url,
                        employer=employer,
                        category=self._determine_category(title),
                        location="Humboldt County, CA",
                    )
                    
                    if self.validate_job(job):
                        jobs.append(job)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing LCO job container: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        return jobs
    
    def _determine_category(self, title: str) -> str:
        """Determine job category based on title."""
        title_lower = title.lower()
        
        if any(kw in title_lower for kw in ['teacher', 'instructor', 'tutor', 'educator']):
            return "Education"
        if any(kw in title_lower for kw in ['nurse', 'medical', 'health', 'dental', 'therapist']):
            return "Healthcare"
        if any(kw in title_lower for kw in ['police', 'officer', 'deputy', 'firefighter']):
            return "Public Safety"
        if any(kw in title_lower for kw in ['manager', 'director', 'coordinator', 'administrator']):
            return "Administrative"
        if any(kw in title_lower for kw in ['maintenance', 'mechanic', 'technician', 'custodian']):
            return "Maintenance"
        if any(kw in title_lower for kw in ['cook', 'chef', 'server', 'bartender', 'restaurant']):
            return "Food Service"
        if any(kw in title_lower for kw in ['retail', 'sales', 'cashier', 'store']):
            return "Retail"
        
        return "Other"
