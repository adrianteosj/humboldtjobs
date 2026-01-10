"""
Scrapers for Banks and Financial Institutions in Humboldt County
- Coast Central Credit Union (Custom HTML)
- Compass Community Credit Union (Custom HTML)
- Tri Counties Bank (UKG/UltiPro)
- Redwood Capital Bank (Simple HTML - typically no openings)
- Columbia Bank (Workday)
"""

import requests
import re
import time
import logging
from typing import List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .base import BaseScraper, JobData
from config import (
    USER_AGENT, REQUEST_DELAY,
    COAST_CENTRAL_CU_URL, COMPASS_CCU_URL, TRI_COUNTIES_BANK_UKG_URL,
    REDWOOD_CAPITAL_BANK_URL, COLUMBIA_BANK_WORKDAY_URL
)


class CoastCentralCUScraper(BaseScraper):
    """Scraper for Coast Central Credit Union (Custom HTML)"""
    
    def __init__(self):
        super().__init__("coast_central_cu")
        self.base_url = COAST_CENTRAL_CU_URL
        self.employer_name = "Coast Central Credit Union"
        self.category = "Administrative"

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.base_url, wait_until="networkidle")
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Coast Central lists jobs as buttons in accordion format
            # Look for buttons that contain job titles
            job_buttons = soup.find_all('button')
            
            for button in job_buttons:
                title = button.get_text(strip=True)
                
                # Skip non-job entries
                if not title or len(title) < 5:
                    continue
                if 'Secret Shopper' in title:
                    continue
                    
                # Check if it looks like a job title
                job_keywords = ['representative', 'officer', 'administrator', 'manager', 
                               'specialist', 'analyst', 'teller', 'associate', 'coordinator',
                               'loan', 'system']
                is_job = any(kw in title.lower() for kw in job_keywords)
                
                if not is_job:
                    continue
                
                # Determine location from title or default
                location = "Eureka, CA"
                if 'mckinleyville' in title.lower():
                    location = "McKinleyville, CA"
                
                job = JobData(
                    source_id=f"cccu_{title.lower().replace(' ', '_')[:30]}",
                    source_name="coast_central_cu",
                    title=title,
                    url=self.base_url,
                    employer=self.employer_name,
                    category=self.category,
                    location=location,
                )
                if self.validate_job(job):
                    jobs.append(job)
                    
        except Exception as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class CompassCCUScraper(BaseScraper):
    """Scraper for Compass Community Credit Union (Custom HTML)"""
    
    def __init__(self):
        super().__init__("compass_ccu")
        self.base_url = COMPASS_CCU_URL
        self.employer_name = "Compass Community Credit Union"
        self.category = "Administrative"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Compass CCU lists jobs as h4 headings
            job_headings = soup.find_all('h4')
            
            for heading in job_headings:
                title = heading.get_text(strip=True)
                
                # Skip non-job headings
                if not title or len(title) < 5:
                    continue
                    
                # Check if it looks like a job title
                job_keywords = ['representative', 'officer', 'administrator', 'manager', 
                               'specialist', 'analyst', 'teller', 'associate', 'coordinator',
                               'part-time', 'full-time']
                is_job = any(kw in title.lower() for kw in job_keywords)
                
                if not is_job:
                    continue
                
                job = JobData(
                    source_id=f"compass_{title.lower().replace(' ', '_')[:30]}",
                    source_name="compass_ccu",
                    title=title,
                    url=self.base_url,
                    employer=self.employer_name,
                    category=self.category,
                    location="Eureka, CA",
                )
                if self.validate_job(job):
                    jobs.append(job)
                    
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class TriCountiesBankScraper(BaseScraper):
    """Scraper for Tri Counties Bank (UKG/UltiPro)"""
    
    def __init__(self):
        super().__init__("tri_counties_bank")
        self.base_url = TRI_COUNTIES_BANK_UKG_URL
        self.employer_name = "Tri Counties Bank"
        self.category = "Administrative"

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.base_url, wait_until="networkidle")
                
                # Wait for job listings to load
                page.wait_for_timeout(3000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # UKG/UltiPro job listings
            # Look for job links or job cards
            job_links = soup.select('a[href*="OpportunityDetail"]')
            
            seen_titles = set()
            for link in job_links:
                try:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    
                    if not title or len(title) < 3:
                        continue
                    
                    # Skip duplicates
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    
                    # Filter for Humboldt County locations
                    # Check parent element for location info
                    parent = link.find_parent('div') or link.find_parent('tr')
                    location_text = parent.get_text() if parent else ''
                    
                    humboldt_cities = ['eureka', 'arcata', 'fortuna', 'mckinleyville', 
                                       'blue lake', 'ferndale', 'humboldt']
                    is_humboldt = any(city in location_text.lower() for city in humboldt_cities)
                    
                    if not is_humboldt:
                        continue
                    
                    # Extract location
                    location = "Humboldt County, CA"
                    for city in ['Eureka', 'Arcata', 'Fortuna', 'McKinleyville']:
                        if city.lower() in location_text.lower():
                            location = f"{city}, CA"
                            break
                    
                    url = href if href.startswith('http') else f"https://recruiting.ultipro.com{href}"
                    
                    job = JobData(
                        source_id=f"tcb_{title.lower().replace(' ', '_')[:30]}",
                        source_name="tri_counties_bank",
                        title=title,
                        url=url,
                        employer=self.employer_name,
                        category=self.category,
                        location=location,
                    )
                    if self.validate_job(job):
                        jobs.append(job)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing Tri Counties job: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class RedwoodCapitalBankScraper(BaseScraper):
    """Scraper for Redwood Capital Bank (Simple HTML)"""
    
    def __init__(self):
        super().__init__("redwood_capital_bank")
        self.base_url = REDWOOD_CAPITAL_BANK_URL
        self.employer_name = "Redwood Capital Bank"
        self.category = "Administrative"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Check if there are any positions
            page_text = soup.get_text().lower()
            
            if 'no positions available' in page_text or 'currently no positions' in page_text:
                self.logger.info(f"  No current positions at {self.employer_name}")
                return jobs
            
            # Look for job listings if they exist
            # Typically would be in h3/h4 tags or list items
            job_headings = soup.find_all(['h3', 'h4', 'strong'])
            
            for heading in job_headings:
                title = heading.get_text(strip=True)
                
                # Check if it looks like a job title
                job_keywords = ['representative', 'officer', 'administrator', 'manager', 
                               'specialist', 'analyst', 'teller', 'associate', 'coordinator']
                is_job = any(kw in title.lower() for kw in job_keywords)
                
                if not is_job:
                    continue
                
                job = JobData(
                    source_id=f"rcb_{title.lower().replace(' ', '_')[:30]}",
                    source_name="redwood_capital_bank",
                    title=title,
                    url=self.base_url,
                    employer=self.employer_name,
                    category=self.category,
                    location="Eureka, CA",
                )
                if self.validate_job(job):
                    jobs.append(job)
                    
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class ColumbiaBankScraper(BaseScraper):
    """Scraper for Columbia Bank (Workday)"""
    
    def __init__(self):
        super().__init__("columbia_bank")
        self.base_url = COLUMBIA_BANK_WORKDAY_URL
        self.employer_name = "Columbia Bank"
        self.category = "Administrative"

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.base_url, wait_until="networkidle")
                
                # Wait for job listings to load
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Workday job listings - look for job links
            job_links = soup.select('a[href*="/job/"]')
            
            seen_ids = set()
            for link in job_links:
                try:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    
                    if not title or len(title) < 3:
                        continue
                    
                    # Extract job ID
                    job_id_match = re.search(r'/job/([^/]+)', href)
                    job_id = job_id_match.group(1) if job_id_match else title[:20]
                    
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    
                    # Check for Humboldt County locations
                    parent = link.find_parent('li') or link.find_parent('div')
                    location_text = parent.get_text() if parent else ''
                    
                    humboldt_cities = ['eureka', 'arcata', 'fortuna', 'mckinleyville', 'humboldt']
                    is_humboldt = any(city in location_text.lower() for city in humboldt_cities)
                    
                    if not is_humboldt:
                        continue
                    
                    # Extract location
                    location = "Humboldt County, CA"
                    for city in ['Eureka', 'Arcata', 'Fortuna', 'McKinleyville']:
                        if city.lower() in location_text.lower():
                            location = f"{city}, CA"
                            break
                    
                    url = href if href.startswith('http') else f"https://columbiabank.wd108.myworkdayjobs.com{href}"
                    
                    job = JobData(
                        source_id=f"columbia_{job_id}",
                        source_name="columbia_bank",
                        title=title,
                        url=url,
                        employer=self.employer_name,
                        category=self.category,
                        location=location,
                    )
                    if self.validate_job(job):
                        jobs.append(job)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing Columbia Bank job: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


# Export all scrapers
__all__ = [
    'CoastCentralCUScraper',
    'CompassCCUScraper',
    'TriCountiesBankScraper',
    'RedwoodCapitalBankScraper',
    'ColumbiaBankScraper',
]
