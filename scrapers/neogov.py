"""
NEOGOV Scraper for government job postings using Playwright
Scrapes 4 government agencies: County of Humboldt, Eureka, Fortuna, Yurok Tribe

Uses Playwright for JavaScript rendering since NEOGOV loads jobs dynamically.
"""
import re
import time
from datetime import datetime, timedelta
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page

from .base import BaseScraper, JobData
from config import USER_AGENT


# NEOGOV sources with base URLs
# Note: City of Arcata uses their own website, not NEOGOV - see arcata.py scraper
NEOGOV_SOURCES = {
    'humboldt_county': {
        'name': 'County of Humboldt',
        'base_url': 'https://www.governmentjobs.com/careers/humboldtcountyca',
        'location': 'Eureka, CA',
    },
    'eureka': {
        'name': 'City of Eureka',
        'base_url': 'https://www.governmentjobs.com/careers/eurekaca',
        'location': 'Eureka, CA',
    },
    'fortuna': {
        'name': 'City of Fortuna',
        'base_url': 'https://www.governmentjobs.com/careers/fortunaca',
        'location': 'Fortuna, CA',
    },
    'yurok_tribe': {
        'name': 'Yurok Tribe',
        'base_url': 'https://www.governmentjobs.com/careers/yuroktribe',
        'location': 'Klamath, CA',
    },
}


class NEOGOVScraper(BaseScraper):
    """
    Scraper for NEOGOV job pages using Playwright for JS rendering.
    Government jobs from local agencies in Humboldt County.
    """
    
    def __init__(self):
        super().__init__("neogov")
        self.sources = NEOGOV_SOURCES
    
    def scrape(self) -> List[JobData]:
        """
        Scrape all NEOGOV pages using Playwright with full detail fetching.
        
        Returns:
            List of JobData objects from all government sources
        """
        all_jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            
            for source_key, source_config in self.sources.items():
                self.logger.info(f"Scraping {source_config['name']}...")
                
                try:
                    jobs = self._scrape_source(page, source_key, source_config)
                    
                    # Fetch details for each job
                    self.logger.info(f"  Fetching details for {len(jobs)} jobs...")
                    for job in jobs:
                        details = self._fetch_job_details(page, job.url)
                        if details:
                            self.apply_detail_data(job, details)
                        time.sleep(0.5)  # Be polite
                    
                    all_jobs.extend(jobs)
                    self.logger.info(f"  Found {len(jobs)} jobs from {source_config['name']}")
                except Exception as e:
                    self.logger.error(f"  Error scraping {source_key}: {e}")
                
                self.delay()
            
            browser.close()
        
        self.logger.info(f"Total NEOGOV jobs scraped: {len(all_jobs)}")
        
        # Enrich all jobs with parsed salary and experience detection
        self.enrich_jobs(all_jobs)
        
        return all_jobs
    
    def _scrape_source(self, page: Page, source_key: str, config: dict) -> List[JobData]:
        """
        Scrape all pages from a single NEOGOV source.
        
        Args:
            page: Playwright page object
            source_key: Internal key for the source
            config: Configuration dict with 'name', 'base_url', 'location'
            
        Returns:
            List of JobData objects from this source
        """
        all_jobs = []
        
        # Navigate to the careers page
        page.goto(config['base_url'], wait_until='networkidle', timeout=30000)
        
        # Wait for job listings to load - use 'attached' state instead of 'visible'
        # because some NEOGOV pages have elements that are present but not considered visible
        try:
            page.wait_for_selector('a[href*="/jobs/"]', state='attached', timeout=10000)
        except:
            # Try waiting a bit longer and check if elements are present
            page.wait_for_timeout(3000)
            job_links = page.query_selector_all('a[href*="/jobs/"]')
            if not job_links:
                self.logger.warning(f"No job links found for {source_key}")
                return []
        
        # Collect all pages
        page_num = 1
        max_pages = 5
        
        while page_num <= max_pages:
            # Parse current page
            jobs = self._parse_page(page, source_key, config)
            all_jobs.extend(jobs)
            
            # Check for next page
            next_button = page.query_selector('a:has-text("Next")')
            if next_button and next_button.is_visible():
                next_button.click()
                page.wait_for_load_state('networkidle')
                page_num += 1
                self.delay()
            else:
                break
        
        return all_jobs
    
    def _parse_page(self, page: Page, source_key: str, config: dict) -> List[JobData]:
        """
        Parse the current page for job listings.
        
        Args:
            page: Playwright page object
            source_key: Source key
            config: Source configuration
            
        Returns:
            List of JobData objects from this page
        """
        jobs = []
        seen_urls = set()
        
        # Try table layout first (has better structured data, e.g., Yurok Tribe)
        job_items = page.query_selector_all('tr:has(a[href*="/jobs/"])')
        
        # If no table rows found, fall back to list layout (most NEOGOV sites)
        if not job_items:
            job_items = page.query_selector_all('li:has(a[href*="/jobs/"])')
        
        for item in job_items:
            try:
                job = self._parse_job_item(item, source_key, config)
                if job and self.validate_job(job) and job.url not in seen_urls:
                    jobs.append(job)
                    seen_urls.add(job.url)
            except Exception as e:
                self.logger.warning(f"Error parsing job item: {e}")
        
        return jobs
    
    def _parse_job_item(self, item, source_key: str, config: dict) -> Optional[JobData]:
        """
        Parse a single job list item or table row.
        
        Args:
            item: Playwright element handle for the list item or table row
            source_key: Source key
            config: Source configuration
            
        Returns:
            JobData object or None
        """
        # Find the job link
        link = item.query_selector('a[href*="/jobs/"]')
        if not link:
            return None
        
        href = link.get_attribute('href')
        if not href:
            return None
        
        # Build full URL
        if href.startswith('/'):
            url = f"https://www.governmentjobs.com{href}"
        else:
            url = href
        
        # Get title from link text
        title = link.inner_text().strip()
        # Clean up title
        title = re.sub(r'\s*Link will be opened in a flyout\.?', '', title)
        title = re.sub(r'\s*New Job\s*$', '', title)
        title = re.sub(r'^New\s+', '', title)
        title = title.strip()
        
        if not title:
            return None
        
        # Extract job ID from URL
        job_id_match = re.search(r'/jobs/(\d+)/', url)
        source_id = job_id_match.group(1) if job_id_match else url
        
        # Get additional details from the item
        item_text = item.inner_text()
        
        # For table rows, try to extract from table cells
        cells = item.query_selector_all('td')
        if cells and len(cells) >= 5:
            # Table layout (e.g., Yurok Tribe)
            # The first column is a rowheader (th), so td cells start at:
            # 0: Job Type, 1: Salary, 2: Closing, 3: Posted, 4: Category, 5: Division, 6: Location, 7: Job Number, 8: Department
            location = config['location']
            salary_text = None
            job_type = None
            original_category = None
            posted_date = None
            closing_date = None
            
            for i, cell in enumerate(cells):
                cell_text = cell.inner_text().strip()
                
                # Job Type (Full-time, Part-time, etc.) - column 0
                if i == 0 and cell_text:
                    job_type_match = re.search(
                        r'(Full[-\s]?Time|Part[-\s]?Time|Extra[-\s]?help|Temporary|Contract|Seasonal|Exempt|Non[-\s]?Exempt)',
                        cell_text,
                        re.IGNORECASE
                    )
                    if job_type_match:
                        job_type = cell_text
                
                # Salary - column 1
                if i == 1 and '$' in cell_text:
                    salary_text = cell_text
                
                # Closing date - column 2
                if i == 2 and cell_text and cell_text != 'Continuous':
                    closing_date = self._parse_date_string(cell_text)
                
                # Posted date - column 3
                if i == 3 and cell_text:
                    posted_date = self._parse_date_string(cell_text)
                
                # Category - column 4
                if i == 4 and cell_text:
                    original_category = cell_text
                
                # Location - column 6
                if i == 6 and cell_text:
                    location = cell_text
            
            return JobData(
                source_id=f"neogov_{source_id}",
                source_name=f"neogov_{source_key}",
                title=title,
                url=url,
                employer=config['name'],
                category="Government",
                original_category=original_category,
                location=location,
                description=None,
                salary_text=salary_text,
                job_type=job_type,
                posted_date=posted_date,
                closing_date=closing_date,
            )
        
        # List layout (standard NEOGOV)
        # Extract location (city, state pattern)
        location = config['location']
        location_match = re.search(r'\n([A-Za-z\s/]+,\s*CA)\n', item_text)
        if location_match:
            location = location_match.group(1).strip()
        
        # Extract salary
        salary_text = None
        salary_match = re.search(
            r'\$[\d,]+(?:\.\d{2})?\s*-\s*\$[\d,]+(?:\.\d{2})?\s*(?:Hourly|Annually|Monthly)?',
            item_text
        )
        if salary_match:
            salary_text = salary_match.group(0)
        
        # Extract job type (Full-time, Part-time, Extra-help)
        job_type = None
        job_type_match = re.search(
            r'(Full-time|Part-time|Extra-help|Temporary|Contract|Seasonal)',
            item_text,
            re.IGNORECASE
        )
        if job_type_match:
            job_type = job_type_match.group(1)
        
        # Extract category
        original_category = None
        category_match = re.search(r'Category:\s*([^\n]+)', item_text)
        if category_match:
            original_category = category_match.group(1).strip()
        
        # Extract posted date
        posted_date = None
        posted_match = re.search(
            r'Posted\s+(more than\s+)?(\d+)\s+(day|week|month)s?\s+ago',
            item_text,
            re.IGNORECASE
        )
        if posted_match:
            posted_date = self._parse_relative_date(posted_match)
        
        # Also check for "Posted 1 day ago" or "Posted yesterday"
        if not posted_date:
            if 'Posted 1 day ago' in item_text or 'Posted yesterday' in item_text:
                posted_date = datetime.now() - timedelta(days=1)
        
        # Extract closing date
        closing_date = None
        # Pattern: "Closes in X days/weeks"
        closing_match = re.search(
            r'Closes\s+in\s+(\d+)\s+(day|week|month)s?',
            item_text,
            re.IGNORECASE
        )
        if closing_match:
            closing_date = self._parse_closing_date(closing_match)
        
        # Check for "Continuous" (no closing date)
        if 'Continuous' in item_text:
            closing_date = None  # Continuous recruitment
        
        # Extract description (first long text block)
        description = None
        lines = item_text.split('\n')
        for line in lines:
            line = line.strip()
            # Skip short lines, date lines, category lines, location lines
            if (len(line) > 100 and 
                'Posted' not in line and 
                'Category:' not in line and
                'Closes' not in line and
                not re.match(r'^[A-Za-z\s]+,\s*CA$', line) and
                '$' not in line[:20]):
                description = line[:500]
                break
        
        return JobData(
            source_id=f"neogov_{source_id}",
            source_name=f"neogov_{source_key}",
            title=title,
            url=url,
            employer=config['name'],
            category="Government",
            original_category=original_category,
            location=location,
            description=description,
            salary_text=salary_text,
            job_type=job_type,
            posted_date=posted_date,
            closing_date=closing_date,
        )
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string in MM/DD/YY format.
        
        Args:
            date_str: Date string like '01/05/26'
            
        Returns:
            datetime object or None
        """
        if not date_str:
            return None
        
        try:
            # Try MM/DD/YY format
            if re.match(r'\d{2}/\d{2}/\d{2}', date_str):
                return datetime.strptime(date_str, '%m/%d/%y')
            # Try MM/DD/YYYY format
            elif re.match(r'\d{2}/\d{2}/\d{4}', date_str):
                return datetime.strptime(date_str, '%m/%d/%Y')
        except ValueError:
            pass
        
        return None
    
    def _parse_relative_date(self, match) -> Optional[datetime]:
        """
        Parse a relative date like 'Posted 3 weeks ago'.
        
        Args:
            match: Regex match object
            
        Returns:
            datetime object or None
        """
        try:
            more_than = match.group(1) is not None
            amount = int(match.group(2))
            unit = match.group(3).lower()
            
            # If "more than", add a bit extra
            if more_than:
                amount += 1
            
            if unit == 'day':
                return datetime.now() - timedelta(days=amount)
            elif unit == 'week':
                return datetime.now() - timedelta(weeks=amount)
            elif unit == 'month':
                return datetime.now() - timedelta(days=amount * 30)
        except:
            pass
        
        return None
    
    def _parse_closing_date(self, match) -> Optional[datetime]:
        """
        Parse a closing date like 'Closes in 3 weeks'.
        
        Args:
            match: Regex match object
            
        Returns:
            datetime object or None
        """
        try:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            
            if unit == 'day':
                return datetime.now() + timedelta(days=amount)
            elif unit == 'week':
                return datetime.now() + timedelta(weeks=amount)
            elif unit == 'month':
                return datetime.now() + timedelta(days=amount * 30)
        except:
            pass
        
        return None
    
    def _fetch_job_details(self, page: Page, url: str) -> dict:
        """
        Fetch detailed job information from a NEOGOV job detail page.
        
        Args:
            page: Playwright page object
            url: URL of the job posting
            
        Returns:
            Dictionary with extracted details
        """
        result = {}
        try:
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(2000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract full job description
            desc_elem = soup.select_one('#job-description-details, .job-posting__description, [data-testid="job-description"]')
            if desc_elem:
                result['description'] = desc_elem.get_text(strip=True, separator=' ')[:2000]
            
            # Extract requirements/qualifications
            for selector in ['#requirements', '.job-posting__qualifications', '#minimum-qualifications', '#qualifications']:
                req_elem = soup.select_one(selector)
                if req_elem:
                    result['requirements'] = req_elem.get_text(strip=True, separator=' ')[:1000]
                    break
            
            # Extract from labeled sections
            text = page.inner_text('body')
            
            # Look for Minimum Qualifications section
            if 'requirements' not in result:
                min_qual_match = re.search(
                    r'(?:Minimum|Required)\s+Qualifications?[:\s]*(.{50,1000}?)(?=Desired|Preferred|Benefits|Supplemental|How to Apply|$)',
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if min_qual_match:
                    result['requirements'] = min_qual_match.group(1).strip()[:1000]
            
            # Extract benefits
            benefits_match = re.search(
                r'(?:Benefits?|We\s+Offer)[:\s]*(.{50,500}?)(?=Supplemental|How to Apply|Equal|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if benefits_match:
                result['benefits'] = benefits_match.group(1).strip()[:500]
            
            # Extract department
            dept_match = re.search(r'(?:Department|Division|Unit)[:\s]*([^\n]{3,50})', text, re.IGNORECASE)
            if dept_match:
                result['department'] = dept_match.group(1).strip()
            
            return result
        except Exception as e:
            self.logger.debug(f"Error fetching NEOGOV job details from {url}: {e}")
            return result
    
    def scrape_with_details(self) -> List[JobData]:
        """
        Scrape all NEOGOV pages with full detail fetching.
        This is slower but gets more complete data.
        
        Returns:
            List of JobData objects with full details
        """
        all_jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            
            for source_key, source_config in self.sources.items():
                self.logger.info(f"Scraping {source_config['name']} (with details)...")
                
                try:
                    jobs = self._scrape_source(page, source_key, source_config)
                    
                    # Fetch details for each job
                    self.logger.info(f"  Fetching details for {len(jobs)} jobs...")
                    for job in jobs:
                        details = self._fetch_job_details(page, job.url)
                        if details:
                            self.apply_detail_data(job, details)
                        time.sleep(0.5)  # Be polite
                    
                    all_jobs.extend(jobs)
                    self.logger.info(f"  Found {len(jobs)} jobs from {source_config['name']}")
                except Exception as e:
                    self.logger.error(f"  Error scraping {source_key}: {e}")
                
                self.delay()
            
            browser.close()
        
        # Enrich all jobs
        self.enrich_jobs(all_jobs)
        
        self.logger.info(f"Total NEOGOV jobs scraped: {len(all_jobs)}")
        return all_jobs