"""
Healthcare facility scrapers for Tier 2.
Includes hospitals, FQHCs, tribal health, and community health organizations.
"""
import requests
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.sync_api import sync_playwright

from .base import BaseScraper, JobData
from config import USER_AGENT


class ProvidenceScraper(BaseScraper):
    """
    Scraper for Providence hospitals (St. Joseph, Redwood Memorial).
    Uses providence.jobs search with location filter.
    """
    
    def __init__(self):
        super().__init__("providence")
        self.base_url = "https://providence.jobs"
        # Search for Eureka and Fortuna (both Providence locations in Humboldt)
        self.search_locations = ["Eureka", "Fortuna"]
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def scrape(self) -> List[JobData]:
        """Scrape Providence jobs"""
        self.logger.info("Scraping Providence Health (St. Joseph & Redwood Memorial)...")
        
        all_jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            
            for location in self.search_locations:
                try:
                    jobs = self._scrape_location(page, location)
                    all_jobs.extend(jobs)
                except Exception as e:
                    self.logger.error(f"Error scraping {location}: {e}")
                self.delay()
            
            browser.close()
        
        # Deduplicate by URL
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)
        
        self.logger.info(f"  Found {len(unique_jobs)} unique jobs from Providence")
        return unique_jobs
    
    def _scrape_location(self, page, location: str) -> List[JobData]:
        """Scrape jobs from a specific location"""
        jobs = []
        search_url = f"{self.base_url}/jobs/?location={location}"
        
        self.logger.info(f"  Fetching {search_url}")
        page.goto(search_url, wait_until="domcontentloaded")
        
        # Wait for job listings to load
        try:
            page.wait_for_selector('li[class*="listitem"], a[href*="/job/"]', timeout=15000)
        except:
            self.logger.info(f"    No job listings found for {location}")
            return []
        
        # Wait for dynamic content
        page.wait_for_timeout(3000)
        
        while True:
            html = page.content()
            page_jobs = self._parse_html(html, location)
            
            if not page_jobs:
                break
            
            # Add new jobs
            new_count = 0
            existing_urls = {j.url for j in jobs}
            for job in page_jobs:
                if job.url not in existing_urls:
                    jobs.append(job)
                    new_count += 1
            
            self.logger.info(f"    Found {len(page_jobs)} jobs on page, {new_count} new")
            
            # Check for "Next" button and click it
            next_button = page.locator('button:has-text("Next")').first
            if next_button.is_visible():
                next_button.click()
                page.wait_for_timeout(2000)  # Wait for page load
            else:
                break
            
            self.delay()
        
        return jobs
    
    def _parse_html(self, html: str, location: str) -> List[JobData]:
        """Parse Providence job listings from HTML"""
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Find job links - Providence uses list items with job links
        job_links = soup.select('a[href*="/job/"]')
        
        for link in job_links:
            try:
                job = self._parse_job_link(link, location)
                if job and self.validate_job(job):
                    jobs.append(job)
            except Exception as e:
                self.logger.warning(f"Error parsing job link: {e}")
        
        return jobs
    
    def _parse_job_link(self, link, location: str) -> Optional[JobData]:
        """Parse a single job link element"""
        href = link.get('href', '')
        
        # Skip non-job links
        if not href or '/job/' not in href:
            return None
        
        # Get title from h2 inside the link
        title_elem = link.select_one('h2')
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        
        if not title or len(title) < 3:
            return None
        
        # Build full URL
        if href.startswith('/'):
            url = f"{self.base_url}{href}"
        elif href.startswith('https://rr.jobsyn.org'):
            # External redirect link - use as is
            url = href
        elif not href.startswith('http'):
            url = f"{self.base_url}/{href}"
        else:
            url = href
        
        # Extract job ID from URL
        job_id_match = re.search(r'/([A-F0-9]{32})/job/', href) or re.search(r'jobsyn\.org/([A-F0-9]+)', href)
        job_id = job_id_match.group(1) if job_id_match else hash(href) % 1000000
        
        # Determine employer/location based on search
        if location.lower() == 'fortuna':
            employer = "Providence Redwood Memorial Hospital"
            job_location = "Fortuna, CA"
        else:
            employer = "Providence St. Joseph Hospital"
            job_location = "Eureka, CA"
        
        # Infer job type from title
        job_type = None
        title_lower = title.lower()
        if 'full time' in title_lower or 'full-time' in title_lower:
            job_type = "Full-time"
        elif 'part time' in title_lower or 'part-time' in title_lower:
            job_type = "Part-time"
        elif 'per diem' in title_lower:
            job_type = "Per Diem"
        
        return JobData(
            source_id=f"providence_{job_id}",
            source_name="providence",
            title=title,
            url=url,
            employer=employer,
            category="Healthcare",
            location=job_location,
            job_type=job_type,
        )


class MadRiverHospitalScraper(BaseScraper):
    """Scraper for Mad River Community Hospital (WordPress)"""
    
    def __init__(self):
        super().__init__("mad_river")
        self.base_url = "https://www.madriverhospital.com"
        self.careers_url = "https://www.madriverhospital.com/careers"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def scrape(self) -> List[JobData]:
        """Scrape Mad River Community Hospital jobs"""
        self.logger.info("Scraping Mad River Community Hospital...")
        
        try:
            response = self.session.get(self.careers_url)
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Failed to fetch Mad River careers page: {e}")
            return []
        
        jobs = self._parse_html(response.text)
        self.logger.info(f"  Found {len(jobs)} jobs from Mad River Community Hospital")
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        """Parse Mad River job listings"""
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Look for job listings in various formats
        # WordPress sites vary widely in structure
        job_containers = soup.select('.job-listing, .career-listing, article.job, div.job-post')
        
        if not job_containers:
            # Try finding links to job postings
            job_links = soup.select('a[href*="career"], a[href*="job"], a[href*="position"]')
            for link in job_links:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                # Filter out navigation/generic links
                if len(title) < 5 or title.lower() in ['careers', 'jobs', 'apply', 'back']:
                    continue
                
                if href and not href.startswith('http'):
                    href = f"{self.base_url}{href}"
                
                job = JobData(
                    source_id=f"mad_river_{hash(href) % 10000}",
                    source_name="mad_river",
                    title=title,
                    url=href or self.careers_url,
                    employer="Mad River Community Hospital",
                    category="Healthcare",
                    location="Arcata, CA",
                )
                if self.validate_job(job):
                    jobs.append(job)
        else:
            for container in job_containers:
                job = self._parse_job_container(container)
                if job and self.validate_job(job):
                    jobs.append(job)
        
        return jobs
    
    def _parse_job_container(self, container) -> Optional[JobData]:
        """Parse a job container element"""
        title_elem = container.select_one('h2, h3, h4, .job-title, a')
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        
        link_elem = container.select_one('a[href]')
        url = link_elem.get('href', self.careers_url) if link_elem else self.careers_url
        
        if url and not url.startswith('http'):
            url = f"{self.base_url}{url}"
        
        return JobData(
            source_id=f"mad_river_{hash(url) % 10000}",
            source_name="mad_river",
            title=title,
            url=url,
            employer="Mad River Community Hospital",
            category="Healthcare",
            location="Arcata, CA",
        )


class UnitedIndianHealthScraper(BaseScraper):
    """Scraper for United Indian Health Services (ADP WorkforceNow)"""
    
    # Humboldt County locations only - exclude Del Norte County (Crescent City, Smith River, Klamath)
    HUMBOLDT_LOCATIONS = ['arcata', 'eureka']
    
    def __init__(self):
        super().__init__("uihs")
        self.base_url = "https://workforcenow.adp.com"
        self.careers_url = "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=447f2bd0-2d4d-4f2a-9bae-3f5453ebc910&ccId=19000101_000001&lang=en_US&selectedMenuKey=CurrentOpenings"
    
    def scrape(self) -> List[JobData]:
        """Scrape United Indian Health Services jobs from ADP WorkforceNow"""
        self.logger.info("Scraping United Indian Health Services (ADP)...")
        
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.careers_url, wait_until="networkidle")
                page.wait_for_timeout(5000)  # Wait for dynamic content
                
                # Click "View all" if present to see all jobs
                try:
                    view_all = page.locator('button:has-text("View all")').first
                    if view_all.is_visible():
                        view_all.click()
                        page.wait_for_timeout(5000)
                except:
                    pass
                
                # Parse using text content approach
                jobs = self._parse_text_content(page)
                
            except Exception as e:
                self.logger.error(f"Error scraping UIHS: {e}")
            finally:
                browser.close()
        
        self.logger.info(f"  Found {len(jobs)} jobs from United Indian Health Services (Humboldt County only)")
        return jobs
    
    def _parse_text_content(self, page) -> List[JobData]:
        """Parse UIHS jobs from page text content"""
        jobs = []
        
        # Get all visible text
        all_text = page.inner_text('body')
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        # Job keywords that indicate a job title
        job_keywords = ['Manager', 'Medical', 'Dentist', 'Provider', 'Technician', 
                        'PA/FNP', 'Counselor', 'Representative', 'Physician', 
                        'Assistant', 'MD', 'DO', 'Billing']
        
        current_job = None
        
        for i, line in enumerate(lines):
            # Check if this looks like a job title
            if len(line) > 10 and any(kw in line for kw in job_keywords):
                # Skip navigation items
                if line.lower() in ['search', 'sign in', 'career center', 'current openings']:
                    continue
                
                # Save previous job if it was a Humboldt job with location in title
                if current_job and current_job['is_humboldt'] and current_job['location']:
                    job = self._create_job(current_job)
                    if job and self.validate_job(job):
                        if not any(j.title == job.title for j in jobs):
                            jobs.append(job)
                
                # Check if location is in the title (e.g., "Medical Assistant-Eureka Location")
                is_humboldt_title = any(loc in line.lower() for loc in self.HUMBOLDT_LOCATIONS)
                
                current_job = {
                    'title': line,
                    'is_humboldt': is_humboldt_title,
                    'location': None
                }
                
                # Infer location from title if present
                if 'eureka' in line.lower():
                    current_job['location'] = 'Eureka, CA'
                elif 'arcata' in line.lower():
                    current_job['location'] = 'Arcata, CA'
            
            # Check if this is a location line (contains CA, US)
            elif current_job and ('CA, US' in line or ', CA,' in line):
                loc_lower = line.lower()
                
                # Check if this is a Humboldt County location
                if 'arcata' in loc_lower:
                    current_job['location'] = 'Arcata, CA'
                    current_job['is_humboldt'] = True
                elif 'eureka' in loc_lower:
                    current_job['location'] = 'Eureka, CA'
                    current_job['is_humboldt'] = True
                
                # Save job if it's in Humboldt County
                if current_job['is_humboldt']:
                    job = self._create_job(current_job)
                    if job and self.validate_job(job):
                        # Avoid duplicates
                        if not any(j.title == job.title for j in jobs):
                            jobs.append(job)
                
                current_job = None
        
        # Don't forget the last job if it had location in title
        if current_job and current_job['is_humboldt'] and current_job['location']:
            job = self._create_job(current_job)
            if job and self.validate_job(job):
                if not any(j.title == job.title for j in jobs):
                    jobs.append(job)
        
        return jobs
    
    def _create_job(self, job_data: dict) -> Optional[JobData]:
        """Create JobData from parsed job info"""
        title = job_data['title']
        location = job_data.get('location', 'Humboldt County, CA')
        
        # Clean title - remove closing date info
        title = re.sub(r'\s*-?\s*Closes?\s*\d{1,2}/\d{1,2}/\d{2,4}', '', title).strip()
        title = re.sub(r'\s*-?\s*Closes?\s*\d{2}/\d{2}/\d{4}', '', title).strip()
        
        # Create unique source ID
        source_id = f"uihs_{hash(title + location) % 100000}"
        
        return JobData(
            source_id=source_id,
            source_name="uihs",
            title=title,
            url=self.careers_url,
            employer="United Indian Health Services",
            category="Healthcare",
            location=location,
        )


class KimawMedicalScraper(BaseScraper):
    """Scraper for K'ima:w Medical Center (Hoopa)"""
    
    def __init__(self):
        super().__init__("kimaw")
        self.base_url = "https://www.kimaw.org"
        self.careers_url = "https://www.kimaw.org/jobs"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def scrape(self) -> List[JobData]:
        """Scrape K'ima:w Medical Center jobs"""
        self.logger.info("Scraping K'ima:w Medical Center...")
        
        try:
            response = self.session.get(self.careers_url)
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Failed to fetch K'ima:w careers page: {e}")
            return []
        
        jobs = self._parse_html(response.text)
        self.logger.info(f"  Found {len(jobs)} jobs from K'ima:w Medical Center")
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        """Parse K'ima:w job listings from their table structure"""
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        seen_titles = set()
        
        # K'ima:w uses a table structure with job links in /hr/job-opening/ path
        job_links = soup.select('a[href*="/hr/job-opening/"], a[href*="/medical/job-opening/"]')
        
        for link in job_links:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            
            # Skip duplicates, headers, and navigation links
            if not title or len(title) < 5:
                continue
            skip_titles = ['title', 'posted date', 'closing date', 'files', 'staff login', 
                          'login', 'sign in', 'apply now', 'careers', 'back']
            if title.lower() in skip_titles:
                continue
            if title in seen_titles:
                continue
            
            seen_titles.add(title)
            
            if href and not href.startswith('http'):
                href = f"{self.base_url}{href}"
            
            # Determine job type from title
            job_type = None
            title_lower = title.lower()
            if 'f/t' in title_lower or 'ft/' in title_lower or 'full' in title_lower:
                job_type = "Full-time"
            elif 'p/t' in title_lower or 'part' in title_lower:
                job_type = "Part-time"
            elif 'temp' in title_lower:
                job_type = "Temporary"
            
            # Clean title - remove job type suffixes
            clean_title = re.sub(r',?\s*(Regular|F/T|FT|P/T|PT|Full\s*Time|Part\s*Time|Temporary)\s*$', '', title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(r'\s*-\s*(F/T|FT|P/T|PT)\s*/?\s*(Regular)?$', '', clean_title, flags=re.IGNORECASE).strip()
            
            job = JobData(
                source_id=f"kimaw_{hash(href) % 100000}",
                source_name="kimaw",
                title=clean_title,
                url=href or self.careers_url,
                employer="K'ima:w Medical Center",
                category="Healthcare",
                location="Hoopa, CA",
                job_type=job_type,
            )
            if self.validate_job(job):
                jobs.append(job)
        
        return jobs


class HospiceOfHumboldtScraper(BaseScraper):
    """Scraper for Hospice of Humboldt (Paycom ATS)"""
    
    def __init__(self):
        super().__init__("hospice")
        self.base_url = "https://www.paycomonline.net"
        self.careers_url = "https://www.paycomonline.net/v4/ats/web.php/portal/C7DCD5CFA20B99C322370C9F9EEA00E2/career-page"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def scrape(self) -> List[JobData]:
        """Scrape Hospice of Humboldt jobs from Paycom portal"""
        self.logger.info("Scraping Hospice of Humboldt (Paycom)...")
        jobs = []
        
        try:
            # Paycom portals often require JavaScript; use Playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                
                page.goto(self.careers_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)  # Wait for dynamic content to load
                
                html = page.content()
                browser.close()
            
            jobs = self._parse_html(html)
        except Exception as e:
            self.logger.error(f"Failed to fetch Hospice careers page: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from Hospice of Humboldt")
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        """Parse Hospice job listings from Paycom portal"""
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Paycom portals list jobs as links with href containing '/jobs/'
        # Each job link contains an h2 with the title, and paragraphs with location/description
        job_links = soup.select('a[href*="/jobs/"]')
        
        for link in job_links:
            href = link.get('href', '')
            
            # Skip non-job links
            if not href or '/jobs/' not in href:
                continue
            
            # Extract job title from h2 inside the link
            title_elem = link.select_one('h2')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            
            # Build full URL
            url = href if href.startswith('http') else f"{self.base_url}{href}"
            
            # Extract location from paragraph (usually format: "Location - City, State ZIP")
            location = "Eureka, CA"
            location_paragraphs = link.select('p')
            for p in location_paragraphs:
                p_text = p.get_text(strip=True)
                # Look for location pattern (contains city/state)
                if 'Eureka' in p_text or 'CA' in p_text:
                    location = p_text
                    break
            
            # Extract job type from nearby elements (e.g., "Benefitted (Full Time)")
            job_type = None
            job_type_elem = link.select_one('[class*="Benefitted"], p')
            for elem in link.select('p, [role="presentation"]'):
                elem_text = elem.get_text(strip=True)
                if 'Full Time' in elem_text or 'Part-Time' in elem_text or 'Benefitted' in elem_text:
                    if 'Full Time' in elem_text:
                        job_type = "Full-time"
                    elif 'Part-Time' in elem_text or 'Part Time' in elem_text:
                        job_type = "Part-time"
                    break
            
            # Extract description snippet
            description = None
            for p in location_paragraphs:
                p_text = p.get_text(strip=True)
                if 'Overview' in p_text or 'Position' in p_text or len(p_text) > 50:
                    description = p_text
                    break
            
            # Extract job ID from URL for unique source_id
            job_id_match = re.search(r'/jobs/(\d+)', href)
            job_id = job_id_match.group(1) if job_id_match else str(hash(title) % 100000)
            
            job = JobData(
                source_id=f"hospice_{job_id}",
                source_name="hospice",
                title=title,
                url=url,
                employer="Hospice of Humboldt",
                category="Healthcare",
                location=location,
                job_type=job_type,
                description=description,
            )
            if self.validate_job(job):
                jobs.append(job)
        
        return jobs


class HumboldtSeniorResourceScraper(BaseScraper):
    """Scraper for Humboldt Senior Resource Center (Paycom ATS)"""
    
    def __init__(self):
        super().__init__("hsrc")
        self.base_url = "https://www.paycomonline.net"
        self.careers_url = "https://www.paycomonline.net/v4/ats/web.php/portal/26A855BC71A6DA61564C6529E594B2E4/career-page"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def scrape(self) -> List[JobData]:
        """Scrape Humboldt Senior Resource Center jobs from Paycom portal"""
        self.logger.info("Scraping Humboldt Senior Resource Center (Paycom)...")
        jobs = []
        seen_urls = set()
        
        try:
            # Paycom portals require JavaScript; use Playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(self.careers_url)
                
                # Wait for job listings to load
                page.wait_for_timeout(5000)
                
                # Process multiple pages
                page_num = 1
                while True:
                    self.logger.info(f"  Processing page {page_num}...")
                    
                    # Get all job cards on current page
                    job_cards = page.query_selector_all('a[href*="/jobs/"]')
                    
                    if not job_cards:
                        break
                    
                    jobs_on_page = 0
                    for card in job_cards:
                        try:
                            href = card.get_attribute('href')
                            if not href or '/jobs/' not in href:
                                continue
                            
                            # Get the card content
                            card_text = card.inner_text()
                            lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                            
                            if not lines:
                                continue
                            
                            # First line is usually the title
                            title = lines[0]
                            
                            # Skip navigation elements and non-job titles
                            skip_titles = ['first page', 'last page', 'forward arrow', 'backward arrow', 
                                         'click here', 'apply now', 'sign in', 'create account', 'login']
                            if title.lower() in skip_titles:
                                continue
                            if len(title) < 5:
                                continue
                            
                            # Extract job type from lines
                            job_type = None
                            for line in lines[1:]:
                                line_lower = line.lower()
                                if 'full-time' in line_lower or 'full time' in line_lower:
                                    job_type = "Full-time"
                                elif 'part-time' in line_lower or 'part time' in line_lower:
                                    job_type = "Part-time"
                                elif 'per diem' in line_lower:
                                    job_type = "Per Diem"
                            
                            # Extract location from lines
                            location = "Eureka, CA"  # Default
                            for line in lines:
                                if ' - ' in line and ('CA' in line or 'Eureka' in line or 'Fortuna' in line or 'Arcata' in line):
                                    # Extract city from location line like "HSRC Fortuna - Fortuna, CA 95540"
                                    if 'Fortuna' in line:
                                        location = "Fortuna, CA"
                                    elif 'Arcata' in line:
                                        location = "Arcata, CA"
                                    elif 'Eureka' in line:
                                        location = "Eureka, CA"
                                    break
                            
                            # Extract description if available
                            description = None
                            for line in lines:
                                if len(line) > 50 and not line.startswith('HSRC'):
                                    description = line[:500]
                                    break
                            
                            # Build full URL
                            if not href.startswith('http'):
                                href = f"{self.base_url}{href}"
                            
                            # Skip if we've already seen this job
                            if href in seen_urls:
                                continue
                            seen_urls.add(href)
                            
                            job = JobData(
                                source_id=f"hsrc_{hash(href) % 100000}",
                                source_name="hsrc",
                                title=title,
                                url=href,
                                employer="Humboldt Senior Resource Center",
                                category="Healthcare",
                                location=location,
                                job_type=job_type,
                                description=description,
                            )
                            if self.validate_job(job):
                                jobs.append(job)
                                jobs_on_page += 1
                        except Exception as e:
                            self.logger.warning(f"Error parsing HSRC job card: {e}")
                            continue
                    
                    # Check if there's a next page - look for page number buttons
                    try:
                        # Scroll down to ensure pagination is visible
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(500)
                        
                        # Check if we can find a "2" page button (indicating there's page 2)
                        page_2_button = page.locator('button:has-text("2")').first
                        
                        # If we're on page 1 and page 2 exists, click it
                        if page_num == 1 and page_2_button.is_visible():
                            page_2_button.click()
                            page.wait_for_timeout(3000)  # Wait for page to load
                            page_num += 1
                        else:
                            # No more pages
                            break
                            
                    except Exception as e:
                        self.logger.info(f"  Pagination ended: {e}")
                        break
                
                browser.close()
                
        except Exception as e:
            self.logger.error(f"Error scraping HSRC Paycom portal: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from Humboldt Senior Resource Center")
        return jobs


class RCAAScraper(BaseScraper):
    """Scraper for Redwood Community Action Agency"""
    
    def __init__(self):
        super().__init__("rcaa")
        self.base_url = "https://rcaa.org"
        self.careers_url = "https://rcaa.org/employment-opportunities"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def scrape(self) -> List[JobData]:
        """Scrape RCAA jobs"""
        self.logger.info("Scraping Redwood Community Action Agency...")
        
        try:
            response = self.session.get(self.careers_url)
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Failed to fetch RCAA careers page: {e}")
            return []
        
        jobs = self._parse_html(response.text)
        self.logger.info(f"  Found {len(jobs)} jobs from RCAA")
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        """Parse RCAA job listings - jobs are in bold headings with salary info below"""
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        seen_titles = set()
        
        # RCAA lists jobs as bold headings (in <strong> or <b> tags) followed by salary info
        # Job titles are typically in ALL CAPS or Title Case
        job_headings = soup.select('strong, b')
        
        for heading in job_headings:
            title = heading.get_text(strip=True)
            
            # Skip non-job headings
            if not title or len(title) < 5:
                continue
            
            # Skip section headers and instructions
            skip_keywords = [
                'how to apply', 'division', 'department', 'click on this link',
                'employment application', 'why work', 'benefits', 'email:', 'fax:',
                'mail or in person', 'note:', 'pdf', 'word'
            ]
            if any(kw in title.lower() for kw in skip_keywords):
                continue
            
            # Skip if title looks like instructions or metadata
            if title.startswith('Click') or 'online' in title.lower():
                continue
            
            # Check if this looks like a job title (has uppercase letters, reasonable length)
            if len(title) > 100:  # Too long to be a job title
                continue
            
            # Normalize title
            clean_title = title.strip()
            
            # Skip duplicates
            if clean_title.lower() in seen_titles:
                continue
            seen_titles.add(clean_title.lower())
            
            # Try to find salary info in nearby text
            salary_text = None
            next_elem = heading.find_next_sibling()
            if next_elem:
                next_text = next_elem.get_text() if hasattr(next_elem, 'get_text') else str(next_elem)
                salary_match = re.search(r'\$[\d,]+(?:\.\d{2})?\s*(?:-|to)\s*\$[\d,]+(?:\.\d{2})?(?:\s*per\s+(?:hour|year))?', next_text, re.IGNORECASE)
                if not salary_match:
                    salary_match = re.search(r'\$[\d,]+(?:\.\d{2})?\s*per\s+hour', next_text, re.IGNORECASE)
                if salary_match:
                    salary_text = salary_match.group(0)
            
            # Always use the careers page URL (not PDF/Word links)
            # PDFs don't provide a good user experience
            job_url = self.careers_url
            
            # Infer category and job type from title/context
            title_lower = clean_title.lower()
            category = "Other"
            job_type = "Full-time"
            
            if any(kw in title_lower for kw in ['director', 'coordinator', 'specialist', 'manager']):
                category = "Administrative"
            elif any(kw in title_lower for kw in ['case worker', 'caseworker', 'supportive services']):
                category = "Other"
            elif any(kw in title_lower for kw in ['restoration', 'field crew', 'energy', 'weatherization']):
                category = "Maintenance"
            
            if 'part-time' in title_lower or 'part time' in title_lower:
                job_type = "Part-time"
            
            job = JobData(
                source_id=f"rcaa_{hash(clean_title) % 100000}",
                source_name="rcaa",
                title=clean_title,
                url=job_url,
                employer="Redwood Community Action Agency",
                category=category,
                location="Eureka, CA",
                salary_text=salary_text,
                job_type=job_type,
            )
            if self.validate_job(job):
                jobs.append(job)
        
        return jobs


class SoHumHealthScraper(BaseScraper):
    """Scraper for SoHum Health / Jerold Phelps Hospital (Paylocity)"""
    
    def __init__(self):
        super().__init__("sohum")
        self.base_url = "https://sohumhealth.org"
        self.careers_url = "https://sohumhealth.org/careers/"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def scrape(self) -> List[JobData]:
        """Scrape SoHum Health jobs"""
        self.logger.info("Scraping SoHum Health / Jerold Phelps Hospital...")
        
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.careers_url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)  # Wait for dynamic content
                
                html = page.content()
                jobs = self._parse_html(html)
                
            except Exception as e:
                self.logger.error(f"Error scraping SoHum Health: {e}")
            finally:
                browser.close()
        
        self.logger.info(f"  Found {len(jobs)} jobs from SoHum Health")
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        """Parse SoHum Health job listings"""
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Look for job listings - Paylocity often embedded via iframe
        # First check for iframe
        iframe = soup.select_one('iframe[src*="paylocity"], iframe[src*="recruiting"]')
        if iframe:
            self.logger.info(f"  Found Paylocity iframe: {iframe.get('src')}")
        
        # Look for job links in main content
        content = soup.select_one('.entry-content, .page-content, main')
        if not content:
            content = soup
        
        job_links = content.select('a[href*="job"], a[href*="career"], a[href*="position"]')
        
        for link in job_links:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            
            if len(title) < 5 or title.lower() in ['careers', 'jobs', 'apply']:
                continue
            
            if href and not href.startswith('http'):
                href = f"{self.base_url}{href}"
            
            job = JobData(
                source_id=f"sohum_{hash(href) % 10000}",
                source_name="sohum",
                title=title,
                url=href or self.careers_url,
                employer="SoHum Health",
                category="Healthcare",
                location="Garberville, CA",
            )
            if self.validate_job(job):
                jobs.append(job)
        
        return jobs
