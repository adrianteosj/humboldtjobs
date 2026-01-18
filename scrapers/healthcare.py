"""
Healthcare facility scrapers for Tier 2.
Includes hospitals, FQHCs, tribal health, and community health organizations.
"""
import requests
import re
import time
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
        
        # Final enrichment pass for any jobs that weren't enriched during scraping
        self.enrich_jobs(unique_jobs)
        
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
        
        # Fetch full details for each job using the same Playwright page
        self.logger.info(f"  Fetching detailed info for {len(jobs)} {location} jobs...")
        for job in jobs:
            details = self._fetch_job_details(page, job.url)
            if details:
                # Apply fetched details to job
                self.apply_detail_data(job, details)
                if details.get('salary_text'):
                    self.logger.info(f"    Found salary for {job.title}: {details['salary_text']}")
            time.sleep(0.3)
        
        # Enrich jobs with parsed salary and experience detection
        self.enrich_jobs(jobs)
        
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
    
    def _fetch_job_details(self, page, url: str) -> dict:
        """Fetch detailed job information from individual Providence job page"""
        result = {}
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'lxml')
            text = page.inner_text('body')
            
            # Extract salary
            salary_match = re.search(
                r'Pay\s*Range[:\s]*\$\s*[\d,.]+\s*[-–]\s*\$\s*[\d,.]+',
                text,
                re.IGNORECASE
            )
            if salary_match:
                salary = salary_match.group(0)
                salary = re.sub(r'\$\s+', '$', salary)
                result['salary_text'] = salary
            else:
                # Try other patterns
                salary_match = re.search(
                    r'Compensation\s*(?:is\s*)?(?:between\s*)?\$[\d,]+(?:\.\d+)?\s*(?:to|[-–])\s*\$[\d,]+(?:\.\d+)?\s*(?:per\s*(?:year|hour)|annually|hourly)?',
                    text,
                    re.IGNORECASE
                )
                if salary_match:
                    result['salary_text'] = salary_match.group(0)
                else:
                    salary_match = re.search(
                        r'\$\s*[\d,]+(?:\.\d+)?\s*[-–]\s*\$\s*[\d,]+(?:\.\d+)?\s*(?:per\s*(?:year|hour|month)|annually|hourly|monthly)?',
                        text,
                        re.IGNORECASE
                    )
                    if salary_match:
                        salary = salary_match.group(0)
                        result['salary_text'] = re.sub(r'\$\s+', '$', salary)
            
            # Extract job description
            desc_section = soup.select_one('.job-description, [data-automation-id="jobPostingDescription"]')
            if desc_section:
                result['description'] = desc_section.get_text(strip=True, separator=' ')[:2000]
            else:
                # Try to find description from text patterns
                desc_match = re.search(
                    r'(?:Description|Overview|About\s+(?:the|this)\s+Role)[:\s]*(.{100,1500}?)(?=Requirements|Qualifications|Benefits|$)',
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if desc_match:
                    result['description'] = desc_match.group(1).strip()[:2000]
            
            # Extract requirements
            req_section = soup.select_one('.requirements, .qualifications, [data-automation-id="jobPostingQualifications"]')
            if req_section:
                result['requirements'] = req_section.get_text(strip=True, separator=' ')[:1000]
            else:
                req_match = re.search(
                    r'(?:Required\s+)?(?:Qualifications|Requirements)[:\s]*(.{50,1000}?)(?=Preferred|Benefits|About\s+Providence|$)',
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if req_match:
                    result['requirements'] = req_match.group(1).strip()[:1000]
            
            # Extract benefits
            benefits_section = soup.select_one('.benefits, [data-automation-id="jobPostingBenefits"]')
            if benefits_section:
                result['benefits'] = benefits_section.get_text(strip=True, separator=' ')[:500]
            else:
                benefits_match = re.search(
                    r'(?:Benefits|We\s+Offer)[:\s]*(.{50,500}?)(?=About|Equal|$)',
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
            self.logger.debug(f"Error fetching job details from {url}: {e}")
            return result
    
    def _fetch_job_salary_page(self, page, url: str) -> Optional[str]:
        """Fetch salary from individual Providence job page using Playwright (legacy method)"""
        details = self._fetch_job_details(page, url)
        return details.get('salary_text')


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
        
        # Fetch details for jobs with unique URLs
        self.logger.info(f"  Fetching details for {len(jobs)} jobs...")
        for job in jobs:
            if job.url and job.url != self.careers_url:
                details = self._fetch_job_details(job.url)
                if details:
                    self.apply_detail_data(job, details)
                time.sleep(0.5)
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from Mad River Community Hospital")
        return jobs
    
    def _fetch_job_details(self, url: str) -> dict:
        """Fetch job details from individual job page"""
        result = {}
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return result
            
            soup = BeautifulSoup(response.text, 'lxml')
            text = soup.get_text()
            
            # Extract description
            desc_match = re.search(
                r'(?:Description|Overview|About|Summary)[:\s]*(.{100,2000}?)(?=(?:Requirements|Qualifications|Benefits)|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if desc_match:
                result['description'] = desc_match.group(1).strip()[:2000]
            
            # Extract requirements
            req_match = re.search(
                r'(?:Requirements?|Qualifications?)[:\s]*(.{50,1500}?)(?=(?:Benefits|Salary|Apply)|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if req_match:
                result['requirements'] = req_match.group(1).strip()[:1500]
            
            # Extract salary
            salary_match = re.search(
                r'\$[\d,]+(?:\.\d{2})?\s*[-–]\s*\$[\d,]+(?:\.\d{2})?\s*(?:per\s+)?(?:hour|year|annually|hourly)?',
                text,
                re.IGNORECASE
            )
            if salary_match:
                result['salary_text'] = salary_match.group(0)
            
            # Extract benefits
            benefits_match = re.search(
                r'(?:Benefits?|We\s+Offer)[:\s]*(.{30,800}?)(?=(?:Apply|Equal|$))',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if benefits_match:
                result['benefits'] = benefits_match.group(1).strip()[:800]
            
            return result
        except Exception:
            return result
    
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
        
        # Fetch full details for each job from detail pages
        self.logger.info(f"  Fetching details for {len(jobs)} jobs...")
        for job in jobs:
            if job.url and job.url != self.careers_url:
                details = self._fetch_job_details(job.url)
                if details:
                    self.apply_detail_data(job, details)
                    if details.get('salary_text'):
                        self.logger.info(f"    Found salary for {job.title}: {details['salary_text']}")
                time.sleep(0.5)
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from K'ima:w Medical Center")
        return jobs
    
    def _fetch_job_details(self, url: str) -> dict:
        """Fetch full details from individual job page"""
        result = {}
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return result
            
            soup = BeautifulSoup(response.text, 'lxml')
            text = soup.get_text()
            
            # Extract salary
            salary_match = re.search(
                r'Salary\s*Level[:\s]*(?:Grade\s*\d+\s*)?\(?\$[\d,.]+\s*[-–]\s*\$[\d,.]+\)?',
                text,
                re.IGNORECASE
            )
            if salary_match:
                result['salary_text'] = salary_match.group(0)
            else:
                # Pattern 2: "Salary Range: $X - $Y per hour/year"
                salary_match = re.search(
                    r'Salary\s*(?:Range)?[:\s]*\$?([\d,.]+K?)\s*[-–]\s*\$?([\d,.]+K?)\s*(?:per\s+(?:hour|year)|hourly|annually|/hr|DOE)?',
                    text,
                    re.IGNORECASE
                )
                if salary_match:
                    low, high = salary_match.groups()
                    if 'K' in low.upper() or 'K' in high.upper():
                        result['salary_text'] = f"${low} - ${high}/yr"
                    else:
                        try:
                            low_val = float(low.replace(',', '').replace('K', '000'))
                            if low_val < 200:
                                result['salary_text'] = f"${low} - ${high}/hr"
                            else:
                                result['salary_text'] = f"${low} - ${high}/yr"
                        except:
                            result['salary_text'] = f"${low} - ${high}"
                elif re.search(r'Salary\s*(?:Level)?[:\s]*DOE', text, re.IGNORECASE):
                    result['salary_text'] = "Depends on Experience"
            
            # Extract description
            desc_patterns = [
                r'(?:Position\s+Summary|Job\s+Summary|Description|Overview)[:\s]*(.{100,2000}?)(?=(?:Responsibilities|Requirements|Qualifications|Benefits|Education)|$)',
                r'(?:POSITION\s+SUMMARY|JOB\s+SUMMARY)[:\s]*(.{100,2000}?)(?=(?:RESPONSIBILITIES|REQUIREMENTS)|$)',
            ]
            for pattern in desc_patterns:
                desc_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if desc_match:
                    result['description'] = desc_match.group(1).strip()[:2000]
                    break
            
            # Extract requirements/qualifications
            req_patterns = [
                r'(?:Requirements?|Qualifications?|Minimum\s+Qualifications?)[:\s]*(.{50,1500}?)(?=(?:Benefits|Salary|Application|How to Apply)|$)',
                r'(?:REQUIREMENTS?|QUALIFICATIONS?)[:\s]*(.{50,1500}?)(?=(?:BENEFITS|SALARY)|$)',
            ]
            for pattern in req_patterns:
                req_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if req_match:
                    result['requirements'] = req_match.group(1).strip()[:1500]
                    break
            
            # Extract benefits
            benefits_match = re.search(
                r'(?:Benefits?|We\s+Offer)[:\s]*(.{30,800}?)(?=(?:How to Apply|Application|Equal)|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if benefits_match:
                result['benefits'] = benefits_match.group(1).strip()[:800]
            
            # Extract department
            dept_match = re.search(r'(?:Department|Division)[:\s]*([^\n]{3,50})', text, re.IGNORECASE)
            if dept_match:
                result['department'] = dept_match.group(1).strip()
            
            return result
        except Exception:
            return result
    
    def _fetch_job_salary(self, url: str) -> Optional[str]:
        """Fetch salary from individual job page (legacy method)"""
        details = self._fetch_job_details(url)
        return details.get('salary_text')
    
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


def fetch_paycom_job_salary(page, job_url: str) -> Optional[str]:
    """
    Fetch salary information from a Paycom job detail page.
    
    Args:
        page: Playwright page object
        job_url: URL of the individual job posting
        
    Returns:
        Salary text string or None
    """
    details = fetch_paycom_job_details(page, job_url)
    return details.get('salary_text')


def fetch_paycom_job_details(page, job_url: str) -> dict:
    """
    Fetch full job details from a Paycom job detail page.
    
    Args:
        page: Playwright page object
        job_url: URL of the individual job posting
        
    Returns:
        Dictionary with salary_text, description, requirements, benefits, department
    """
    result = {}
    try:
        page.goto(job_url, wait_until='domcontentloaded', timeout=15000)
        page.wait_for_timeout(2000)
        
        html = page.content()
        soup = BeautifulSoup(html, 'lxml')
        text = soup.get_text()
        
        # Extract salary
        salary_match = re.search(
            r'Salary\s*Range[:\s]*\$[\d,.]+\s*[-–]\s*\$[\d,.]+\s*(?:Hourly|Per Hour|Annually|Per Year)?',
            text,
            re.IGNORECASE
        )
        if salary_match:
            result['salary_text'] = salary_match.group(0).replace('Salary Range:', '').replace('Salary Range', '').strip()
        else:
            # Pattern 2: Just look for salary amounts
            salary_match = re.search(r'\$[\d,.]+\s*[-–]\s*\$[\d,.]+\s*(?:Hourly|Per Hour|Annually)?', text)
            if salary_match:
                result['salary_text'] = salary_match.group(0)
        
        # Extract description - look for common section headers
        desc_patterns = [
            r'(?:Position\s+Overview|Job\s+Summary|Description|Overview|About\s+(?:the|this)\s+Position)[:\s]*(.{100,2000}?)(?=(?:Responsibilities|Requirements|Qualifications|Benefits|Education|Experience|How to Apply)|$)',
            r'(?:POSITION\s+OVERVIEW|JOB\s+SUMMARY|DESCRIPTION)[:\s]*(.{100,2000}?)(?=(?:RESPONSIBILITIES|REQUIREMENTS|QUALIFICATIONS)|$)',
        ]
        for pattern in desc_patterns:
            desc_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if desc_match:
                result['description'] = desc_match.group(1).strip()[:2000]
                break
        
        # Extract requirements
        req_patterns = [
            r'(?:Requirements?|Qualifications?|Minimum\s+Requirements?)[:\s]*(.{50,1500}?)(?=(?:Benefits|Salary|Education|How to Apply|About\s+(?:Us|the\s+Company))|$)',
            r'(?:REQUIREMENTS?|QUALIFICATIONS?|MINIMUM\s+REQUIREMENTS?)[:\s]*(.{50,1500}?)(?=(?:BENEFITS|SALARY|EDUCATION)|$)',
        ]
        for pattern in req_patterns:
            req_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if req_match:
                result['requirements'] = req_match.group(1).strip()[:1500]
                break
        
        # Extract benefits
        benefits_patterns = [
            r'(?:Benefits?|We\s+Offer|Compensation)[:\s]*(.{30,800}?)(?=(?:How to Apply|Equal|About\s+(?:Us|the\s+Company))|$)',
            r'(?:BENEFITS?|WE\s+OFFER|COMPENSATION)[:\s]*(.{30,800}?)(?=(?:HOW TO APPLY|EQUAL)|$)',
        ]
        for pattern in benefits_patterns:
            benefits_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if benefits_match:
                result['benefits'] = benefits_match.group(1).strip()[:800]
                break
        
        # Extract department
        dept_match = re.search(r'(?:Department|Division)[:\s]*([^\n]{3,50})', text, re.IGNORECASE)
        if dept_match:
            result['department'] = dept_match.group(1).strip()
        
        return result
    except Exception:
        return result


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
                
                # Parse job listings
                jobs = self._parse_html(html)
                
                # Fetch full details for each job
                self.logger.info(f"  Fetching details for {len(jobs)} jobs...")
                for job in jobs:
                    details = fetch_paycom_job_details(page, job.url)
                    if details:
                        if details.get('salary_text'):
                            job.salary_text = details['salary_text']
                        if details.get('description'):
                            job.description = details['description']
                        if details.get('requirements'):
                            job.requirements = details['requirements']
                        if details.get('benefits'):
                            job.benefits = details['benefits']
                        if details.get('department'):
                            job.department = details['department']
                    time.sleep(0.5)
                
                # Enrich jobs with parsed salary and experience
                self.enrich_jobs(jobs)
                
                browser.close()
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
        job_data_list = []  # Collect job data first, then fetch salaries
        seen_urls = set()
        
        try:
            # Paycom portals require JavaScript; use Playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(self.careers_url)
                
                # Wait for job listings to load
                page.wait_for_timeout(5000)
                
                # PHASE 1: Collect all job metadata from all pages first
                page_num = 1
                while True:
                    self.logger.info(f"  Collecting jobs from page {page_num}...")
                    
                    # Get all job cards on current page
                    job_cards = page.query_selector_all('a[href*="/jobs/"]')
                    
                    if not job_cards:
                        break
                    
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
                            
                            # Store job data for later processing
                            job_data_list.append({
                                'href': href,
                                'title': title,
                                'job_type': job_type,
                                'location': location,
                                'description': description,
                            })
                        except Exception as e:
                            self.logger.warning(f"Error parsing HSRC job card: {e}")
                            continue
                    
                    # Check if there's a next page
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(500)
                        
                        # Look for next page button dynamically
                        next_page_num = page_num + 1
                        next_page_button = page.locator(f'button:has-text("{next_page_num}")').first
                        
                        # Also try finding ">" or "Next" buttons as fallback
                        if not next_page_button.is_visible():
                            next_page_button = page.locator('button:has-text(">")').first
                        if not next_page_button.is_visible():
                            next_page_button = page.locator('button:has-text("Next")').first
                        
                        if next_page_button.is_visible():
                            next_page_button.click()
                            page.wait_for_timeout(3000)
                            page_num += 1
                            
                            # Safety limit to avoid infinite loops
                            if page_num > 10:
                                self.logger.info("  Reached page limit (10)")
                                break
                        else:
                            self.logger.info(f"  No more pages found after page {page_num}")
                            break
                    except Exception as e:
                        self.logger.warning(f"  Pagination error: {e}")
                        break
                
                # PHASE 2: Fetch full details for each job
                self.logger.info(f"  Fetching details for {len(job_data_list)} jobs...")
                for job_data in job_data_list:
                    details = fetch_paycom_job_details(page, job_data['href'])
                    
                    job = JobData(
                        source_id=f"hsrc_{hash(job_data['href']) % 100000}",
                        source_name="hsrc",
                        title=job_data['title'],
                        url=job_data['href'],
                        employer="Humboldt Senior Resource Center",
                        category="Healthcare",
                        location=job_data['location'],
                        job_type=job_data['job_type'],
                        description=details.get('description') or job_data['description'],
                        salary_text=details.get('salary_text'),
                        requirements=details.get('requirements'),
                        benefits=details.get('benefits'),
                        department=details.get('department'),
                    )
                    if self.validate_job(job):
                        jobs.append(job)
                        if details.get('salary_text'):
                            self.logger.info(f"    Found salary for {job_data['title']}: {details['salary_text']}")
                    time.sleep(0.5)
                
                # Enrich jobs with parsed salary and experience
                self.enrich_jobs(jobs)
                
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
                'mail or in person', 'note:', 'pdf', 'word', 'employmentopportunities',
                'employment opportunities', 'fighting poverty', 'together', 'all rcaa positions',
                'to your computer', 'cellphone', 'tablet', 'save it'
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
            
            # Try to find salary info in nearby text (parent container or siblings)
            salary_text = None
            
            # Look in parent container for salary info
            parent = heading.find_parent()
            if parent:
                # Get all text from the parent and nearby elements
                nearby_text = ""
                # Check siblings and parent text
                for sibling in parent.find_next_siblings()[:3]:  # Check next 3 siblings
                    if hasattr(sibling, 'get_text'):
                        nearby_text += " " + sibling.get_text()
                
                # Also check the immediate next sibling
                next_elem = heading.find_next_sibling()
                if next_elem:
                    if hasattr(next_elem, 'get_text'):
                        nearby_text += " " + next_elem.get_text()
                
                # Also check parent's next sibling (for nested structures)
                parent_next = parent.find_next_sibling()
                if parent_next and hasattr(parent_next, 'get_text'):
                    nearby_text += " " + parent_next.get_text()
                
                # Search for salary patterns
                # Pattern 1: $XX.XX - $XX.XX per hour/year
                salary_match = re.search(
                    r'\$[\d,]+(?:\.\d{2})?\s*(?:-|to)\s*\$[\d,]+(?:\.\d{2})?\s*(?:per\s+)?(?:hour|year|hr|yr|hourly|annually)',
                    nearby_text, re.IGNORECASE
                )
                # Pattern 2: Salary $XX,XXX - $XX,XXX per year
                if not salary_match:
                    salary_match = re.search(
                        r'[Ss]alary\s*\$[\d,]+(?:\.\d{2})?\s*(?:-|to)\s*\$[\d,]+(?:\.\d{2})?\s*(?:per\s+)?(?:hour|year)',
                        nearby_text, re.IGNORECASE
                    )
                # Pattern 3: $XX.XX per hour (single rate)
                if not salary_match:
                    salary_match = re.search(r'\$[\d,]+(?:\.\d{2})?\s*(?:per\s+)?(?:hour|hr|hourly)', nearby_text, re.IGNORECASE)
                
                if salary_match:
                    salary_text = salary_match.group(0).strip()
            
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
                
                # Fetch details for jobs with unique URLs
                self.logger.info(f"  Fetching details for {len(jobs)} jobs...")
                for job in jobs:
                    if job.url and job.url != self.careers_url:
                        details = self._fetch_job_details(page, job.url)
                        if details:
                            self.apply_detail_data(job, details)
                        time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error scraping SoHum Health: {e}")
            finally:
                browser.close()
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from SoHum Health")
        return jobs
    
    def _fetch_job_details(self, page, url: str) -> dict:
        """Fetch job details from individual job page"""
        result = {}
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            page.wait_for_timeout(2000)
            
            text = page.inner_text('body')
            
            # Extract description
            desc_match = re.search(
                r'(?:Description|Overview|About|Summary)[:\s]*(.{100,2000}?)(?=(?:Requirements|Qualifications|Benefits|How to Apply)|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if desc_match:
                result['description'] = desc_match.group(1).strip()[:2000]
            
            # Extract requirements
            req_match = re.search(
                r'(?:Requirements?|Qualifications?)[:\s]*(.{50,1500}?)(?=(?:Benefits|Salary|How to Apply)|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if req_match:
                result['requirements'] = req_match.group(1).strip()[:1500]
            
            # Extract salary
            salary_match = re.search(
                r'\$[\d,]+(?:\.\d{2})?\s*[-–]\s*\$[\d,]+(?:\.\d{2})?\s*(?:per\s+)?(?:hour|year|annually|hourly)?',
                text,
                re.IGNORECASE
            )
            if salary_match:
                result['salary_text'] = salary_match.group(0)
            
            return result
        except Exception:
            return result
    
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
