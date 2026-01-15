"""
Scrapers for National Retail Chains in Humboldt County
- Dollar General (iCIMS API)
- Walgreens (HTML)
- TJ Maxx (Workday/Phenom)
- Costco (iCIMS)
- Safeway/Albertsons (Oracle HCM Cloud)
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
    DOLLAR_GENERAL_API_URL, DOLLAR_GENERAL_LOCATION, DOLLAR_GENERAL_RADIUS,
    WALGREENS_SEARCH_URL, TJ_MAXX_SEARCH_URL, COSTCO_SEARCH_URL,
    SAFEWAY_EUREKA_URL, SAFEWAY_ARCATA_URL, WALMART_SEARCH_URL
)


class DollarGeneralScraper(BaseScraper):
    """Scraper for Dollar General (iCIMS API)"""
    
    def __init__(self):
        super().__init__("dollar_general")
        self.api_url = DOLLAR_GENERAL_API_URL
        self.location = DOLLAR_GENERAL_LOCATION
        self.radius = DOLLAR_GENERAL_RADIUS
        self.employer_name = "Dollar General"
        self.category = "Retail"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        page = 1
        
        while True:
            params = {
                'keywords': '',
                'location': self.location,
                'stretch': self.radius,
                'page': page,
                'sortBy': 'relevance',
                'descending': 'false',
                'internal': 'false'
            }
            
            try:
                response = self.session.get(self.api_url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                job_list = data.get('jobs', [])
                if not job_list:
                    break
                    
                for job_item in job_list:
                    # Jobs are nested under 'data' key
                    job_data = job_item.get('data', job_item)
                    job = self._parse_job(job_data)
                    if job and self.validate_job(job):
                        jobs.append(job)
                
                # Check if there are more pages
                total = data.get('total', 0)
                if page * 10 >= total:  # Default page size is 10
                    break
                    
                page += 1
                time.sleep(REQUEST_DELAY)
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
                break
        
        # Fetch salary for each job from detail pages
        if jobs:
            self.logger.info(f"  Fetching salary details for {len(jobs)} jobs...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page_obj = browser.new_page(user_agent=USER_AGENT)
                
                for job in jobs:
                    salary = self._fetch_job_salary(page_obj, job.url)
                    if salary:
                        job.salary_text = salary
                        self.logger.debug(f"    Found salary for {job.title}: {salary}")
                    time.sleep(0.5)
                
                browser.close()
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs
    
    def _fetch_job_salary(self, page, url: str) -> Optional[str]:
        """
        Fetch salary from Dollar General job detail page.
        
        Dollar General shows salary as "New Hire Starting Pay Range: X.XX - Y.YY"
        """
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)  # Wait for JS to render
            
            text = page.inner_text('body')
            
            # Pattern: "New Hire Starting Pay Range: 16.90 - 17.00"
            salary_match = re.search(
                r'(?:New\s+Hire\s+)?(?:Starting\s+)?Pay\s+Range[:\s]*([\d.]+)\s*[-–]\s*([\d.]+)',
                text,
                re.IGNORECASE
            )
            if salary_match:
                low, high = salary_match.groups()
                return f"${low} - ${high}/hr"
            
            # Fallback: look for any dollar range
            salary_match = re.search(
                r'\$([\d.]+)\s*[-–]\s*\$([\d.]+)\s*(?:/hr|hourly|per hour)?',
                text,
                re.IGNORECASE
            )
            if salary_match:
                low, high = salary_match.groups()
                try:
                    if float(low) < 100:  # Likely hourly
                        return f"${low} - ${high}/hr"
                except:
                    pass
                return f"${low} - ${high}"
            
            return None
        except Exception as e:
            self.logger.debug(f"Error fetching salary from {url}: {e}")
            return None

    def _parse_job(self, data: dict) -> Optional[JobData]:
        try:
            job_id = data.get('req_id', data.get('slug', ''))
            title = data.get('title', '').strip()
            
            if not title:
                return None
            
            # Extract location from title (format: "TITLE in CITY, STATE STORE#")
            location = "Humboldt County, CA"
            if ' in ' in title:
                loc_part = title.split(' in ')[-1]
                # Extract city and state
                loc_match = re.match(r'([A-Z\s]+),\s*([A-Z]{2})', loc_part)
                if loc_match:
                    city = loc_match.group(1).strip().title()
                    state = loc_match.group(2)
                    location = f"{city}, {state}"
            
            # Build URL
            url = f"https://careers.dollargeneral.com/jobs/{job_id}?lang=en-us"
            
            # Job type from position_type field
            position_type = data.get('position_type', '')
            job_type = None
            if 'Full' in position_type:
                job_type = 'Full-Time'
            elif 'Part' in position_type:
                job_type = 'Part-Time'
            
            # Clean up title - remove store number and location suffix
            clean_title = title.split(' in ')[0].strip() if ' in ' in title else title
            
            return JobData(
                source_id=f"dg_{job_id}",
                source_name="dollar_general",
                title=clean_title,
                url=url,
                employer=self.employer_name,
                category=self.category,
                location=location,
                job_type=job_type,
            )
        except Exception as e:
            self.logger.warning(f"Error parsing Dollar General job: {e}")
            return None


class WalgreensScraper(BaseScraper):
    """Scraper for Walgreens (HTML parsing with salary from detail pages)"""
    
    def __init__(self):
        super().__init__("walgreens")
        self.search_url = WALGREENS_SEARCH_URL
        self.employer_name = "Walgreens"
        self.category = "Retail"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until="networkidle")
                
                # Wait for job listings to load
                page.wait_for_selector('ul li a[href*="/job/"]', timeout=15000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Find all job links in the results list
            job_links = soup.select('ul li a[href*="/job/"]')
            
            for link in job_links:
                try:
                    href = link.get('href', '')
                    if not href or '/job/' not in href:
                        continue
                    
                    # Extract title from h2 inside the link
                    title_elem = link.select_one('h2')
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    
                    if not title:
                        continue
                    
                    # Extract location (text after the h2)
                    location_text = link.get_text(strip=True)
                    location = location_text.replace(title, '').strip()
                    if not location:
                        location = "Humboldt County, CA"
                    
                    # Build full URL
                    url = f"https://jobs.walgreens.com{href}" if href.startswith('/') else href
                    
                    # Generate unique ID from URL
                    job_id = href.split('/')[-1] if href else title.lower().replace(' ', '_')
                    
                    job = JobData(
                        source_id=f"walgreens_{job_id}",
                        source_name="walgreens",
                        title=title,
                        url=url,
                        employer=self.employer_name,
                        category=self.category,
                        location=location,
                    )
                    if self.validate_job(job):
                        jobs.append(job)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing Walgreens job: {e}")
                    continue
            
            # Fetch salary from detail pages
            if jobs:
                self.logger.info(f"  Fetching salary details for {len(jobs)} jobs...")
                self._fetch_salaries(jobs)
                    
        except Exception as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs
    
    def _fetch_salaries(self, jobs: List[JobData]):
        """Fetch salary info from job detail pages"""
        for job in jobs:
            try:
                response = self.session.get(job.url, timeout=10)
                if response.status_code == 200:
                    # Look for salary pattern: "Salary:$XX - $XX / Hourly" or "Salary Range: $XX - $XX / Hourly"
                    salary_match = re.search(
                        r'Salary(?:\s*Range)?[:\s]*\$(\d+(?:\.\d{2})?)\s*-\s*\$(\d+(?:\.\d{2})?)\s*/?\s*(?:Hourly|Hour|hr)',
                        response.text,
                        re.IGNORECASE
                    )
                    if salary_match:
                        job.salary_text = f"${salary_match.group(1)} - ${salary_match.group(2)}/hour"
                        self.logger.info(f"    Found salary for {job.title}: {job.salary_text}")
                self.delay()
            except Exception as e:
                self.logger.debug(f"Error fetching salary for {job.title}: {e}")


class TJMaxxScraper(BaseScraper):
    """Scraper for TJ Maxx (Workday/Phenom platform)"""
    
    def __init__(self):
        super().__init__("tj_maxx")
        self.search_url = TJ_MAXX_SEARCH_URL
        self.employer_name = "TJ Maxx"
        self.category = "Retail"

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until="networkidle")
                
                # Wait for job listings to load
                page.wait_for_selector('ul li a[href*="/job/"]', timeout=15000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Find all job links
            job_links = soup.select('ul li a[href*="/job/"]')
            
            for link in job_links:
                try:
                    href = link.get('href', '')
                    if not href or '/job/' not in href:
                        continue
                    
                    # Extract job ID from URL (e.g., REQ15889)
                    job_id_match = re.search(r'/job/([A-Z0-9]+)/', href)
                    job_id = job_id_match.group(1) if job_id_match else ''
                    
                    # Extract title from the link text
                    title_text = link.get_text(strip=True)
                    # Title is usually at the start, before "Job ID is"
                    title_match = re.match(r'^([^J]+?)(?:\s*Job ID is|\s*REQ)', title_text)
                    title = title_match.group(1).strip() if title_match else title_text.split('Job ID')[0].strip()
                    
                    if not title:
                        continue
                    
                    # Extract location (usually contains "Eureka, California")
                    location = "Eureka, CA"
                    if 'California' in title_text:
                        loc_match = re.search(r'([A-Za-z\s]+,\s*California)', title_text)
                        if loc_match:
                            location = loc_match.group(1).replace('California', 'CA')
                    
                    url = href if href.startswith('http') else f"https://jobs.tjx.com{href}"
                    
                    job = JobData(
                        source_id=f"tjmaxx_{job_id}",
                        source_name="tj_maxx",
                        title=title,
                        url=url,
                        employer=self.employer_name,
                        category=self.category,
                        location=location,
                    )
                    if self.validate_job(job):
                        jobs.append(job)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing TJ Maxx job: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class CostcoScraper(BaseScraper):
    """Scraper for Costco (iCIMS platform)"""
    
    def __init__(self):
        super().__init__("costco")
        self.search_url = COSTCO_SEARCH_URL
        self.employer_name = "Costco"
        self.category = "Retail"

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until="networkidle")
                
                # Wait for job listings to load
                page.wait_for_selector('a[href*="/jobs/"]', timeout=15000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Find all job links that contain job IDs
            job_links = soup.select('a[href*="/jobs/"][href*="lang=en-us"]')
            
            seen_ids = set()
            for link in job_links:
                try:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # Extract job ID from URL
                    job_id_match = re.search(r'/jobs/(\d+)', href)
                    if not job_id_match:
                        continue
                    job_id = job_id_match.group(1)
                    
                    # Skip duplicates
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    
                    # Extract title from link text
                    title = link.get_text(strip=True)
                    if not title:
                        continue
                    
                    # Build URL
                    url = f"https://careers.costco.com/jobs/{job_id}?lang=en-us"
                    
                    job = JobData(
                        source_id=f"costco_{job_id}",
                        source_name="costco",
                        title=title,
                        url=url,
                        employer=self.employer_name,
                        category=self.category,
                        location="Eureka, CA",
                    )
                    if self.validate_job(job):
                        jobs.append(job)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing Costco job: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class SafewayScraper(BaseScraper):
    """Scraper for Safeway/Albertsons (Oracle HCM Cloud)"""
    
    def __init__(self):
        super().__init__("safeway")
        self.eureka_url = SAFEWAY_EUREKA_URL
        self.arcata_url = SAFEWAY_ARCATA_URL
        self.employer_name = "Safeway"
        self.category = "Retail"

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        seen_ids = set()
        
        # Scrape both Eureka and Arcata locations
        for url, location_name in [(self.eureka_url, "Eureka"), (self.arcata_url, "Arcata")]:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.goto(url, wait_until="networkidle")
                    
                    # Wait for job listings to load
                    page.wait_for_timeout(5000)  # Extra wait for Oracle HCM
                    page.wait_for_selector('a[href*="/job/"]', timeout=20000)
                    
                    html = page.content()
                    browser.close()
                
                soup = BeautifulSoup(html, 'lxml')
                
                # Find all job links
                job_links = soup.select('a[href*="/job/"]')
                
                for link in job_links:
                    try:
                        href = link.get('href', '')
                        if not href or '/job/' not in href:
                            continue
                        
                        # Extract job ID from URL
                        job_id_match = re.search(r'/job/(\d+)', href)
                        if not job_id_match:
                            continue
                        job_id = job_id_match.group(1)
                        
                        # Skip duplicates
                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)
                        
                        # Get parent li element to extract full job info
                        parent_li = link.find_parent('li')
                        if parent_li:
                            full_text = parent_li.get_text(separator=' ', strip=True)
                        else:
                            full_text = link.get_text(strip=True)
                        
                        # Extract title (everything before "Banner")
                        title = full_text.split('Banner')[0].strip()
                        if not title or len(title) < 3:
                            continue
                        
                        # Extract location from the full text
                        location = f"{location_name}, CA"
                        if 'EUREKA' in full_text.upper():
                            location = "Eureka, CA"
                        elif 'ARCATA' in full_text.upper():
                            location = "Arcata, CA"
                        elif 'FORTUNA' in full_text.upper():
                            location = "Fortuna, CA"
                        elif 'CRESCENT CITY' in full_text.upper():
                            location = "Crescent City, CA"
                        
                        # Build full URL
                        url_full = href if href.startswith('http') else f"https://eofd.fa.us6.oraclecloud.com{href}"
                        
                        job = JobData(
                            source_id=f"safeway_{job_id}",
                            source_name="safeway",
                            title=title,
                            url=url_full,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
                            
                    except Exception as e:
                        self.logger.warning(f"Error parsing Safeway job: {e}")
                        continue
                        
            except Exception as e:
                self.logger.error(f"Error fetching jobs from {self.employer_name} ({location_name}): {e}")
            
            time.sleep(REQUEST_DELAY)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class WalmartScraper(BaseScraper):
    """Scraper for Walmart (JavaScript-rendered site)"""
    
    def __init__(self):
        super().__init__("walmart")
        self.search_url = WALMART_SEARCH_URL
        self.employer_name = "Walmart"
        self.category = "Retail"

    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until="networkidle")
                
                # Wait for job cards to load
                page.wait_for_timeout(5000)
                
                # Check for job cards - Walmart uses a specific structure
                try:
                    page.wait_for_selector('div[data-testid="job-card"]', timeout=10000)
                except:
                    # Try alternative selectors
                    pass
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Walmart job cards contain title, location, and salary info
            # Look for job card containers
            job_cards = soup.select('div[class*="job-card"], div[class*="JobCard"], article')
            
            # Also try finding by job title patterns
            if not job_cards:
                # Look for any container with job-like content
                all_divs = soup.find_all('div')
                for div in all_divs:
                    text = div.get_text()
                    if 'Wal-Mart' in text and ('Associate' in text or 'Technician' in text):
                        # Found potential job container
                        job_cards.append(div)
            
            seen_titles = set()
            
            # Parse job information from the page
            # Look for specific job title patterns
            page_text = soup.get_text()
            
            # Common Walmart job titles to look for
            job_patterns = [
                r'(Pharmacy Sales Associate)',
                r'(Janitorial Associate)',
                r'(Backroom Team Associate)',
                r'(Pharmacy Technician)',
                r'(Cashier)',
                r'(Stocker)',
                r'(Cart Attendant)',
                r'(Fresh Food Associate)',
                r'(Deli Associate)',
                r'(Bakery Associate)',
                r'(Meat Cutter)',
            ]
            
            for pattern in job_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    title = match.strip()
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    
                    # Create unique URL with title hash for deduplication
                    unique_url = f"{self.search_url}#{title.lower().replace(' ', '-')}"
                    
                    job = JobData(
                        source_id=f"walmart_{title.lower().replace(' ', '_')}",
                        source_name="walmart",
                        title=title,
                        url=unique_url,
                        employer=self.employer_name,
                        category=self.category,
                        location="Eureka, CA",
                    )
                    if self.validate_job(job):
                        jobs.append(job)
            
            # If no jobs found via patterns, try parsing the HTML structure
            if not jobs:
                # Look for links that might be job listings
                links = soup.find_all('a')
                for link in links:
                    text = link.get_text(strip=True)
                    if any(kw in text.lower() for kw in ['associate', 'technician', 'cashier', 'stocker']):
                        if text not in seen_titles and len(text) > 5:
                            seen_titles.add(text)
                            unique_url = f"{self.search_url}#{text.lower().replace(' ', '-')[:30]}"
                            job = JobData(
                                source_id=f"walmart_{text.lower().replace(' ', '_')[:30]}",
                                source_name="walmart",
                                title=text,
                                url=unique_url,
                                employer=self.employer_name,
                                category=self.category,
                                location="Eureka, CA",
                            )
                            if self.validate_job(job):
                                jobs.append(job)
                    
        except Exception as e:
            self.logger.error(f"Error fetching jobs from {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


# Export all scrapers
__all__ = [
    'DollarGeneralScraper',
    'WalgreensScraper', 
    'TJMaxxScraper',
    'CostcoScraper',
    'SafewayScraper',
    'WalmartScraper',
]
