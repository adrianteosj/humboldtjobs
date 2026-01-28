"""
Tier 3 Local Employers Scrapers

Handles various ATS platforms used by local Humboldt County employers:
- ADP WorkforceNow (Blue Lake Casino)
- Paycom (Bear River Casino)
- enterTimeOnline (Green Diamond)
- UltiPro/UKG (North Coast Co-op)
"""

import requests
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import logging

from .base import BaseScraper, JobData
from config import (
    USER_AGENT,
    BLUE_LAKE_CASINO_ADP_URL,
    BEAR_RIVER_CASINO_PAYCOM_URL,
    GREEN_DIAMOND_ATS_URL,
    NORTH_COAST_COOP_UKG_URL,
    LACO_ASSOCIATES_ADP_URL,
    DANCO_GROUP_URL,
    EUREKA_NATURAL_FOODS_URL,
)

logger = logging.getLogger(__name__)


class ADPScraper(BaseScraper):
    """Generic scraper for ADP WorkforceNow career portals"""
    
    def __init__(self, source_key: str, employer_name: str, adp_url: str, category: str = "Other"):
        super().__init__(source_key)
        self.source_key = source_key
        self.employer_name = employer_name
        self.adp_url = adp_url
        self.category = category
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name} via ADP WorkforceNow...")
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Headed mode needed for ADP
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.adp_url, wait_until="networkidle")
                
                # Wait for specific job content to appear
                page.wait_for_selector('text=Current Openings', timeout=15000)
                page.wait_for_timeout(8000)  # Additional wait for job list to render
                
                # Get the full page text content
                body_text = page.locator('body').inner_text()
                
                # Parse jobs from body text using regex pattern
                # Job listings follow pattern: "Job Title\nLocation, CA, US\nX days ago, Job Type"
                # More generic pattern to catch all job titles
                job_pattern = re.compile(
                    r'([A-Z][A-Za-z0-9&\s\-/]+?(?:Attendant|Officer|Bartender|Roller|Supervisor|Dishwasher|Pool|Dealer|Person|Server|Cook|Clerk|Manager|Host|Technician|Alices|I{1,3}))\s+'
                    r'(Blue Lake[,\s]*(?:Blue Lake)?[,\s]*CA[,\s]*US?)\s+'
                    r'(\d+\+?\s*days?\s*ago)\s*,?\s*(Full Time|Part Time|FT or PT)?',
                    re.IGNORECASE | re.DOTALL
                )
                
                matches = job_pattern.findall(body_text)
                
                # Deduplicate matches by title
                seen = set()
                unique_matches = []
                for m in matches:
                    title = m[0].strip()
                    if title not in seen:
                        seen.add(title)
                        unique_matches.append(m)
                matches = unique_matches
                
                for match in matches:
                    title = match[0].strip()
                    location = match[1].strip()
                    date_str = match[2].strip()
                    job_type = match[3].strip() if match[3] else None
                    
                    # Normalize job type
                    if job_type == 'FT or PT':
                        job_type = 'Full Time or Part Time'
                    
                    # Parse date
                    posted_date = self._parse_relative_date(date_str)
                    
                    # Create unique source_id and URL by including job title
                    title_slug = re.sub(r'[^a-z0-9]+', '-', title.lower())[:30]
                    source_id = f"adp_{self.source_key}_{title_slug}"
                    # Append title as fragment for uniqueness while still linking to main page
                    unique_url = f"{self.adp_url}#job={title_slug}"
                    
                    # Try to get salary by clicking on the job
                    salary_text = None
                    try:
                        # Click on job title to open detail view
                        job_link = page.locator(f'text="{title}"').first
                        if job_link.is_visible(timeout=2000):
                            job_link.click()
                            page.wait_for_timeout(2000)
                            
                            # Look for salary in the detail view
                            detail_text = page.locator('body').inner_text()
                            salary_match = re.search(
                                r'Salary\s*Range[:\s]*\$[\d,.]+\s*(?:To|[-–])\s*\$[\d,.]+\s*(?:Hourly|Per Hour)?',
                                detail_text,
                                re.IGNORECASE
                            )
                            if salary_match:
                                salary_text = salary_match.group(0).replace('Salary Range:', '').replace('Salary Range', '').strip()
                                self.logger.info(f"    Found salary for {title}: {salary_text}")
                            
                            # Go back to listing
                            back_btn = page.locator('text="Back"').first
                            if back_btn.is_visible(timeout=1000):
                                back_btn.click()
                                page.wait_for_timeout(1500)
                    except Exception as e:
                        self.logger.debug(f"Could not fetch salary for {title}: {e}")
                    
                    job = JobData(
                        source_id=source_id,
                        source_name=f"adp_{self.source_key}",
                        title=title,
                        url=unique_url,
                        employer=self.employer_name,
                        category=self.category,
                        location=location,
                        job_type=job_type,
                        posted_date=posted_date,
                        salary_text=salary_text,
                    )
                    
                    if self.validate_job(job):
                        jobs.append(job)
                
            except Exception as e:
                self.logger.error(f"Error scraping {self.employer_name}: {e}")
            finally:
                browser.close()
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Find "Current Openings" heading to locate job section
        openings_text = soup.find(string=re.compile(r'Current Openings.*\d+ of \d+', re.I))
        
        # ADP job listings are in container divs with cursor=pointer attribute
        # Each job card contains: job title link, location, date, job type
        job_rows = soup.select('div[cursor="pointer"]')
        
        for row in job_rows:
            # Get the job title from the link
            title_link = row.select_one('a[href="#"]')
            if not title_link:
                continue
            
            title_div = title_link.select_one('div div')
            if not title_div:
                continue
            
            title = title_div.get_text(strip=True)
            
            # Skip non-job items
            if not title or len(title) < 3:
                continue
            if title.lower() in ['sign in', 'career center', 'current openings', 'language', 
                                 'privacy', 'legal', 'requirements', 'artificial intelligence',
                                 'learn more about the tribe', 'search', 'go to page', 'page']:
                continue
            
            # Get all text from the row
            row_text = row.get_text(' ', strip=True)
            
            # Extract location (look for Blue Lake, CA pattern)
            location = "Blue Lake, CA"
            loc_match = re.search(r'(Blue Lake(?:,?\s*(?:Blue Lake)?)?[,\s]*CA[,\s]*US?)', row_text, re.I)
            if loc_match:
                location = loc_match.group(1).strip()
            
            # Extract job type
            job_type = None
            if 'Full Time' in row_text:
                job_type = 'Full Time'
            elif 'Part Time' in row_text or 'FT or PT' in row_text:
                job_type = 'Part Time'
            
            # Extract posted date
            posted_date = None
            date_match = re.search(r'(\d+)\+?\s*days?\s*ago', row_text, re.I)
            if date_match:
                posted_date = self._parse_relative_date(date_match.group(0))
            
            # Generate unique source ID
            source_id = f"adp_{self.source_key}_{title.lower().replace(' ', '_')[:30]}"
            
            job = JobData(
                source_id=source_id,
                source_name=f"adp_{self.source_key}",
                title=title,
                url=self.adp_url,  # ADP URLs are dynamic, use base URL
                employer=self.employer_name,
                category=self.category,
                location=location,
                job_type=job_type,
                posted_date=posted_date,
            )
            
            if self.validate_job(job):
                jobs.append(job)
        
        return jobs
    
    def _parse_relative_date(self, date_str: str) -> Optional[datetime]:
        """Parse relative dates like '28 days ago', '30+ days ago'"""
        try:
            match = re.search(r'(\d+)\+?\s*days?\s*ago', date_str, re.I)
            if match:
                days = int(match.group(1))
                from datetime import timedelta
                return datetime.now() - timedelta(days=days)
        except:
            pass
        return None


class BlueLakeCasinoScraper(ADPScraper):
    """Scraper for Blue Lake Casino (ADP WorkforceNow)"""
    
    def __init__(self):
        super().__init__(
            source_key='blue_lake_casino',
            employer_name='Blue Lake Casino Hotel',
            adp_url=BLUE_LAKE_CASINO_ADP_URL,
            category='Hospitality'
        )


class LACOAssociatesScraper(ADPScraper):
    """Scraper for LACO Associates (ADP WorkforceNow) - Engineering/Surveying/Planning"""
    
    def __init__(self):
        super().__init__(
            source_key='laco_associates',
            employer_name='LACO Associates',
            adp_url=LACO_ASSOCIATES_ADP_URL,
            category='Technical'
        )


class PaycomScraper(BaseScraper):
    """Generic scraper for Paycom career portals"""
    
    def __init__(self, source_key: str, employer_name: str, paycom_url: str, category: str = "Other"):
        super().__init__(source_key)
        self.source_key = source_key
        self.employer_name = employer_name
        self.paycom_url = paycom_url
        self.category = category
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name} via Paycom...")
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.paycom_url, wait_until="domcontentloaded")
                
                # Accept cookies if present
                try:
                    cookie_btn = page.locator('button:has-text("Accept Cookies")')
                    if cookie_btn.is_visible(timeout=3000):
                        cookie_btn.click()
                        page.wait_for_timeout(1000)
                except:
                    pass
                
                # Wait for job listings or "no jobs" message
                page.wait_for_timeout(5000)
                
                html = page.content()
                
                # Check if there are no jobs
                if "Currently no jobs available" in html:
                    self.logger.info(f"  No jobs currently available at {self.employer_name}")
                    return []
                
                jobs = self._parse_html(html)
                
            except Exception as e:
                self.logger.error(f"Error scraping {self.employer_name}: {e}")
            finally:
                browser.close()
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Paycom job listings (structure varies)
        job_cards = soup.select('div[class*="job-card"], div[class*="job-listing"]')
        
        for card in job_cards:
            title_elem = card.select_one('a, h3, h4')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            
            # Extract location
            location_elem = card.select_one('span[class*="location"], div[class*="location"]')
            location = location_elem.get_text(strip=True) if location_elem else "Loleta, CA"
            
            # Generate unique source ID
            source_id = f"paycom_{self.source_key}_{title.lower().replace(' ', '_')[:30]}"
            
            job = JobData(
                source_id=source_id,
                source_name=f"paycom_{self.source_key}",
                title=title,
                url=self.paycom_url,
                employer=self.employer_name,
                category=self.category,
                location=location,
            )
            
            if self.validate_job(job):
                jobs.append(job)
        
        return jobs


class BearRiverCasinoScraper(PaycomScraper):
    """Scraper for Bear River Casino (Paycom)"""
    
    def __init__(self):
        super().__init__(
            source_key='bear_river_casino',
            employer_name='Bear River Casino Resort',
            paycom_url=BEAR_RIVER_CASINO_PAYCOM_URL,
            category='Hospitality'
        )


class EnterTimeOnlineScraper(BaseScraper):
    """Scraper for enterTimeOnline/Cornerstone ATS platforms"""
    
    def __init__(self, source_key: str, employer_name: str, ats_url: str, 
                 category: str = "Other", location_filter: Optional[List[str]] = None):
        super().__init__(source_key)
        self.source_key = source_key
        self.employer_name = employer_name
        self.ats_url = ats_url
        self.category = category
        self.location_filter = [loc.lower() for loc in location_filter] if location_filter else []
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name} via enterTimeOnline...")
        jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.ats_url, wait_until="domcontentloaded")
                page.wait_for_selector('div[class*="job"], li[class*="job"], heading', timeout=15000)
                page.wait_for_timeout(3000)
                
                html = page.content()
                jobs = self._parse_html(html)
                
            except Exception as e:
                self.logger.error(f"Error scraping {self.employer_name}: {e}")
            finally:
                browser.close()
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Find job listings - enterTimeOnline uses various structures
        job_containers = soup.select('div[class*="generic"]')
        
        # Find all job links
        job_links = soup.select('a[href*="#"]')
        
        seen = set()
        for link in job_links:
            title = link.get_text(strip=True)
            
            # Skip non-job titles
            if not title or title in seen:
                continue
            if title.lower() in ['skip to main content', 'log in', 'apply', 'previous page', 
                                 'next page', 'page']:
                continue
            if len(title) < 3:
                continue
            
            seen.add(title)
            
            # Find parent for location info
            parent = link.find_parent('div')
            location = None
            job_type = None
            job_category = None
            
            if parent:
                # Look for location
                loc_match = re.search(r'(Korbel|Klamath Falls|Seattle|Shelton)[,\s]*(CA|OR|WA)?', 
                                     parent.get_text(), re.I)
                if loc_match:
                    location = loc_match.group(0).strip()
                
                # Look for job type
                type_match = re.search(r'(Full Time|Part Time)', parent.get_text(), re.I)
                if type_match:
                    job_type = type_match.group(1)
                
                # Look for category
                cat_match = re.search(r'(FORESTRY|UNION|SEASONAL|ABD|CONSVPLN)', parent.get_text())
                if cat_match:
                    job_category = cat_match.group(1)
            
            # Apply location filter if specified
            if self.location_filter and location:
                if not any(loc in location.lower() for loc in self.location_filter):
                    continue
            
            source_id = f"eto_{self.source_key}_{title.lower().replace(' ', '_')[:30]}"
            
            job = JobData(
                source_id=source_id,
                source_name=f"eto_{self.source_key}",
                title=title,
                url=self.ats_url,
                employer=self.employer_name,
                category=self.category,
                location=location or "California",
                job_type=job_type,
            )
            
            if self.validate_job(job):
                jobs.append(job)
        
        return jobs


class GreenDiamondScraper(EnterTimeOnlineScraper):
    """Scraper for Green Diamond Resource Company (enterTimeOnline) - Humboldt County jobs only"""
    
    def __init__(self):
        super().__init__(
            source_key='green_diamond',
            employer_name='Green Diamond Resource Company',
            ats_url=GREEN_DIAMOND_ATS_URL,
            category='Forestry',
            location_filter=['korbel', 'humboldt', 'ca']  # Filter for Humboldt County
        )


class UKGScraper(BaseScraper):
    """Scraper for UKG/UltiPro recruiting portals"""
    
    def __init__(self, source_key: str, employer_name: str, ukg_url: str, category: str = "Other"):
        super().__init__(source_key)
        self.source_key = source_key
        self.employer_name = employer_name
        self.ukg_url = ukg_url
        self.category = category
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name} via UKG/UltiPro...")
        jobs = []
        valid_jobs = []
        stale_count = 0
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page.goto(self.ukg_url, wait_until="domcontentloaded")
                page.wait_for_selector('h3 a, heading a', timeout=15000)
                page.wait_for_timeout(3000)
                
                html = page.content()
                jobs = self._parse_html(html)
                
                # Fetch full details for each job from detail pages
                self.logger.info(f"  Fetching details for {len(jobs)} jobs...")
                for job in jobs:
                    details = self._fetch_job_details(page, job.url)
                    if details:
                        # Check if job is stale/unavailable
                        if details.get('is_stale'):
                            stale_count += 1
                            continue  # Skip this job
                        
                        self.apply_detail_data(job, details)
                        if details.get('salary_text'):
                            self.logger.debug(f"    Found salary for {job.title}: {details['salary_text']}")
                    
                    valid_jobs.append(job)
                    import time
                    time.sleep(0.5)
                
                if stale_count > 0:
                    self.logger.info(f"  Skipped {stale_count} stale/unavailable jobs")
                
            except Exception as e:
                self.logger.error(f"Error scraping {self.employer_name}: {e}")
            finally:
                browser.close()
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(valid_jobs)
        
        self.logger.info(f"  Found {len(valid_jobs)} jobs from {self.employer_name}")
        return valid_jobs
    
    # Patterns that indicate a job is no longer available
    STALE_JOB_PATTERNS = [
        "this opportunity is currently not available",
        "this position has been filled",
        "job no longer available",
        "posting has expired",
        "position is no longer available",
        "job posting has been removed",
        "opportunity is no longer accepting",
    ]
    
    def _is_job_stale(self, text: str) -> bool:
        """Check if page text indicates the job is no longer available."""
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in self.STALE_JOB_PATTERNS)
    
    def _fetch_job_details(self, page, url: str) -> dict:
        """
        Fetch full job details from UKG job detail page.
        
        Returns dict with job details, or {'is_stale': True} if job is no longer available.
        """
        result = {}
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(2000)
            
            text = page.inner_text('body')
            
            # Check if job is stale/unavailable
            if self._is_job_stale(text):
                self.logger.info(f"    Job no longer available: {url}")
                result['is_stale'] = True
                return result
            
            # Extract salary - Pattern 1: "Hourly Range: $17.11 USD to $21.40 USD"
            salary_match = re.search(
                r'Hourly\s*Range[:\s]*\$([\d.]+)\s*(?:USD)?\s*to\s*\$([\d.]+)\s*(?:USD)?',
                text,
                re.IGNORECASE
            )
            if salary_match:
                low, high = salary_match.groups()
                result['salary_text'] = f"${low} - ${high}/hr"
            
            # Pattern 2: "Rate: $16.90 USD per hour" (single value)
            if 'salary_text' not in result:
                salary_match = re.search(
                    r'Rate[:\s]*\$([\d.]+)\s*(?:USD)?\s*(?:per\s+hour|hourly|/hr)?',
                    text,
                    re.IGNORECASE
                )
                if salary_match:
                    rate = salary_match.group(1)
                    result['salary_text'] = f"${rate}/hr"
            
            # Pattern 3: "Salary Range: $X to $Y" or "Pay Range: $X to $Y"
            if 'salary_text' not in result:
                salary_match = re.search(
                    r'(?:Salary|Pay)\s*Range[:\s]*\$([\d,.]+)\s*(?:USD)?\s*to\s*\$([\d,.]+)\s*(?:USD)?',
                    text,
                    re.IGNORECASE
                )
                if salary_match:
                    low, high = salary_match.groups()
                    try:
                        low_val = float(low.replace(',', ''))
                        if low_val < 200:
                            result['salary_text'] = f"${low} - ${high}/hr"
                        else:
                            result['salary_text'] = f"${low} - ${high}/yr"
                    except:
                        result['salary_text'] = f"${low} - ${high}"
            
            # Pattern 4: "Starting at $X.XX per hour"
            if 'salary_text' not in result:
                salary_match = re.search(
                    r'(?:Starting\s+(?:at|wage)[:\s]*)\$([\d.]+)\s*(?:per\s+hour|hourly|/hr)?',
                    text,
                    re.IGNORECASE
                )
                if salary_match:
                    rate = salary_match.group(1)
                    result['salary_text'] = f"${rate}/hr (starting)"
            
            # Check for "Based on Experience" indicator
            if 'salary_text' not in result:
                if re.search(r'Starting wage is based upon', text, re.IGNORECASE):
                    result['salary_text'] = "Based on Experience"
            
            # Extract description - look for Job Details or Position Summary section
            # Be more specific to avoid capturing boilerplate text
            desc_match = re.search(
                r'(?:Job\s+Details|Position\s+Summary|Description)\s*\n+(.{100,2000}?)(?=\n\n(?:Department|Requirements|Qualifications|Minimum|Skills|Benefits|Education|Customer|Essential)|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if desc_match:
                desc_text = desc_match.group(1).strip()
                # Clean up: remove lines that are clearly boilerplate
                boilerplate_phrases = [
                    'are representative only',
                    'reserves the right to revise',
                    'other duties as assigned',
                    'reasonable accommodations',
                ]
                # Only use description if it doesn't start with boilerplate
                if not any(phrase in desc_text[:100].lower() for phrase in boilerplate_phrases):
                    result['description'] = desc_text[:2000]
            
            # Fallback: try to get a cleaner description from specific sections
            if 'description' not in result:
                # Look for customer experience or department operations sections (for retail jobs)
                section_match = re.search(
                    r'(?:Customer\s+Experience|Position\s+Overview)[:\s]*(.{50,1500}?)(?=\n\n|Department|Requirements|$)',
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if section_match:
                    result['description'] = section_match.group(1).strip()[:1500]
            
            # Extract requirements
            req_match = re.search(
                r'(?:Requirements?|Qualifications?|Minimum\s+Requirements?)[:\s]*(.{50,1500}?)(?=(?:Benefits|Salary|Rate|Application|How to Apply|Equal)|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if req_match:
                result['requirements'] = req_match.group(1).strip()[:1500]
            
            # Extract benefits
            benefits_match = re.search(
                r'(?:Benefits?|We\s+Offer)[:\s]*(.{30,800}?)(?=(?:Apply|Equal|About)|$)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if benefits_match:
                result['benefits'] = benefits_match.group(1).strip()[:800]
            
            # AI FALLBACK: If salary not found by regex, try AI extraction
            if 'salary_text' not in result:
                try:
                    from processing.ai_extractor import extract_with_ai, is_ai_available
                    if is_ai_available():
                        self.logger.debug(f"    Using AI fallback for salary extraction")
                        ai_result = extract_with_ai(
                            page_text=text[:3000],
                            job_title=url.split('/')[-1] if '/' in url else '',
                            extract_salary=True,
                            extract_description=False
                        )
                        if ai_result and ai_result.salary_text and ai_result.confidence >= 0.5:
                            result['salary_text'] = ai_result.salary_text
                            # Also set parsed values if available
                            if ai_result.salary_min:
                                if ai_result.salary_type == 'hourly':
                                    result['salary_min'] = int(ai_result.salary_min * 2080)
                                    result['salary_max'] = int((ai_result.salary_max or ai_result.salary_min) * 2080)
                                else:
                                    result['salary_min'] = int(ai_result.salary_min)
                                    result['salary_max'] = int(ai_result.salary_max or ai_result.salary_min)
                            self.logger.info(f"    AI extracted salary: {ai_result.salary_text}")
                except Exception as ai_e:
                    self.logger.debug(f"    AI fallback failed: {ai_e}")
            
            return result
        except Exception as e:
            self.logger.debug(f"Error fetching details from {url}: {e}")
            return result
    
    def _fetch_job_salary(self, page, url: str) -> Optional[str]:
        """Fetch salary from UKG job detail page (legacy method)"""
        details = self._fetch_job_details(page, url)
        return details.get('salary_text')
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # UKG uses heading elements with links for job titles
        job_headings = soup.select('h3 a[href*="OpportunityDetail"]')
        
        for heading in job_headings:
            title = heading.get_text(strip=True)
            if not title:
                continue
            
            # Get the URL
            href = heading.get('href', '')
            if href.startswith('/'):
                url = f"https://recruiting2.ultipro.com{href}"
            else:
                url = self.ukg_url
            
            # Find the job card container - need to go up several levels
            # The h3 is inside multiple nested divs - we need the card container
            container = heading.find_parent('h3')
            if container:
                # Go up to find the job card (contains all job info including location)
                for _ in range(5):  # Traverse up to 5 levels
                    parent = container.find_parent('div')
                    if parent:
                        container = parent
                        # Check if this container has the location info
                        if container.find(string=re.compile(r'CA\s*\d{5}', re.I)):
                            break
            
            location = "Humboldt County, CA"
            job_type = None
            posted_date = None
            req_number = None
            job_category = None
            
            if container:
                # Extract location - look for full address pattern like "Arcata, CA 95521, USA"
                loc_elem = container.find(string=re.compile(r'(Eureka|Arcata|Fortuna|McKinleyville),\s*CA\s*\d{5}', re.I))
                if loc_elem:
                    loc_text = loc_elem.strip()
                    # Extract just "City, CA" from "City, CA 95521, USA"
                    loc_match = re.match(r'((?:Eureka|Arcata|Fortuna|McKinleyville)),\s*CA', loc_text, re.I)
                    if loc_match:
                        city = loc_match.group(1).title()
                        location = f"{city}, CA"
                
                # Extract job type (schedule)
                schedule_elem = container.find(string=re.compile(r'Full Time|Part Time', re.I))
                if schedule_elem:
                    job_type = schedule_elem.strip()
                
                # Extract requisition number for unique ID
                req_elem = container.find(string=re.compile(r'[A-Z]{5}\d{6}'))
                if req_elem:
                    req_number = req_elem.strip()
                
                # Extract posted date
                date_elem = container.find(string=re.compile(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+,?\s*\d{4}|Today', re.I))
                if date_elem:
                    posted_date = self._parse_date(date_elem.strip())
                
                # Extract job category (for location fallback)
                cat_elem = container.find(string=re.compile(r'BU\s+Eureka|BU\s+Arcata|NBU\s+Eureka', re.I))
                if cat_elem:
                    job_category = cat_elem.strip()
                    # Use category as location fallback if location not found
                    if location == "Humboldt County, CA":
                        if 'Arcata' in job_category:
                            location = "Arcata, CA"
                        elif 'Eureka' in job_category:
                            location = "Eureka, CA"
            
            # Use requisition number for unique ID if available
            source_id = f"ukg_{self.source_key}_{req_number or title.lower().replace(' ', '_')[:30]}"
            
            job = JobData(
                source_id=source_id,
                source_name=f"ukg_{self.source_key}",
                title=title,
                url=url,
                employer=self.employer_name,
                category=self.category,
                location=location,
                job_type=job_type,
                posted_date=posted_date,
            )
            
            if self.validate_job(job):
                jobs.append(job)
        
        return jobs
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date strings like 'Jan 4, 2026', 'Today'"""
        from dateutil import parser as date_parser
        try:
            if date_str.lower() == 'today':
                return datetime.now()
            return date_parser.parse(date_str)
        except:
            return None


class NorthCoastCoopScraper(UKGScraper):
    """Scraper for North Coast Co-op (UKG/UltiPro)"""
    
    def __init__(self):
        super().__init__(
            source_key='north_coast_coop',
            employer_name='North Coast Co-op',
            ukg_url=NORTH_COAST_COOP_UKG_URL,
            category='Retail'
        )


class EurekaNaturalFoodsScraper(BaseScraper):
    """Scraper for Eureka Natural Foods (Simple HTML page)"""
    
    def __init__(self):
        super().__init__('eureka_natural_foods')
        self.source_key = 'eureka_natural_foods'
        self.employer_name = 'Eureka Natural Foods'
        self.url = EUREKA_NATURAL_FOODS_URL
        self.category = 'Retail'
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find job listings - they're in headings with links to PDFs
            # Look for links containing job descriptions (PDFs)
            job_links = soup.find_all('a', href=re.compile(r'\.pdf$'))
            
            for link in job_links:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                # Skip the general application PDF
                if 'application' in title.lower() and 'dishwasher' not in title.lower():
                    continue
                
                # Clean up title (remove leading dash)
                title = title.lstrip('-').strip()
                
                if not title or len(title) < 3:
                    continue
                
                # Determine location from page content
                location = "McKinleyville, CA"  # Current openings are in McKinleyville
                
                source_id = f"enf_{title.lower().replace(' ', '_')[:30]}"
                
                job = JobData(
                    source_id=source_id,
                    source_name='eureka_natural_foods',
                    title=title,
                    url=self.url,  # Use main employment page, not PDF links
                    employer=self.employer_name,
                    category=self.category,
                    location=location,
                )
                
                if self.validate_job(job):
                    jobs.append(job)
                    
        except Exception as e:
            self.logger.error(f"Error scraping {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class DancoGroupScraper(BaseScraper):
    """Scraper for Danco Group (Simple HTML page with application categories)"""
    
    def __init__(self):
        super().__init__('danco_group')
        self.source_key = 'danco_group'
        self.employer_name = 'Danco Group'
        self.url = DANCO_GROUP_URL
        self.category = 'Construction'
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = self.session.get(self.url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find job application links - they're in /careers/ path
            job_links = soup.find_all('a', href=re.compile(r'/careers/'))
            
            seen_titles = set()
            for link in job_links:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                # Skip general application and duplicates
                if title.lower() == 'general application':
                    continue
                if title in seen_titles:
                    continue
                if not title or len(title) < 3:
                    continue
                
                seen_titles.add(title)
                
                # Build full URL
                if href.startswith('/'):
                    full_url = f"https://www.danco-group.com{href}"
                else:
                    full_url = href
                
                source_id = f"danco_{title.lower().replace(' ', '_')[:30]}"
                
                job = JobData(
                    source_id=source_id,
                    source_name='danco_group',
                    title=title,
                    url=full_url,
                    employer=self.employer_name,
                    category=self.category,
                    location="Arcata, CA",  # Danco is based in Arcata
                )
                
                if self.validate_job(job):
                    jobs.append(job)
            
            # Fetch salary for each job from detail pages
            self.logger.info(f"  Fetching salary details for {len(jobs)} jobs...")
            for job in jobs:
                salary = self._fetch_job_salary(job.url)
                if salary:
                    job.salary_text = salary
                    self.logger.debug(f"    Found salary for {job.title}: {salary}")
                import time
                time.sleep(0.3)
                    
        except Exception as e:
            self.logger.error(f"Error scraping {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs
    
    def _fetch_job_salary(self, url: str) -> Optional[str]:
        """
        Fetch salary from Danco Group job detail page.
        
        Danco shows salary as "Salary: $15.00 - $20.00 per hour"
        """
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            text = soup.get_text()
            
            # Pattern 1: "Salary: $15.00 - $20.00 per hour"
            salary_match = re.search(
                r'Salary[:\s]*\$([\d.]+)\s*[-–]\s*\$([\d.]+)\s*(?:per\s*hour|hourly|/hr)?',
                text,
                re.IGNORECASE
            )
            if salary_match:
                low, high = salary_match.groups()
                return f"${low} - ${high}/hr"
            
            # Pattern 2: "Pay: $X - $Y"
            salary_match = re.search(
                r'(?:Pay|Wage|Rate)[:\s]*\$([\d.]+)\s*[-–]\s*\$([\d.]+)',
                text,
                re.IGNORECASE
            )
            if salary_match:
                low, high = salary_match.groups()
                try:
                    if float(low) < 200:
                        return f"${low} - ${high}/hr"
                except:
                    pass
                return f"${low} - ${high}"
            
            # Pattern 3: Single salary "Salary: $X per hour"
            salary_match = re.search(
                r'(?:Salary|Pay|Wage)[:\s]*\$([\d.]+)\s*(?:per\s*hour|hourly|/hr)',
                text,
                re.IGNORECASE
            )
            if salary_match:
                rate = salary_match.group(1)
                return f"${rate}/hr"
            
            return None
        except Exception:
            return None