"""
EdJoin Scraper for education job postings in Humboldt County
https://edjoin.org/Home/Jobs?location=humboldt

Uses Playwright for JavaScript rendering and BeautifulSoup for HTML parsing.
"""
import re
from datetime import datetime
from typing import List, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .base import BaseScraper, JobData
from config import USER_AGENT


class EdJoinScraper(BaseScraper):
    """
    Scraper for EdJoin education job board.
    Scrapes K-12 education jobs from Humboldt County schools and districts.
    """
    
    BASE_URL = "https://edjoin.org"
    SEARCH_URL = "https://edjoin.org/Home/Jobs?location=humboldt"
    
    def __init__(self):
        super().__init__("edjoin")
    
    def scrape(self) -> List[JobData]:
        """
        Scrape EdJoin for Humboldt County education jobs.
        
        Returns:
            List of JobData objects from EdJoin
        """
        self.logger.info("Scraping EdJoin (Humboldt County)...")
        
        all_jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            
            try:
                all_jobs = self._scrape_all_pages(page)
                self.logger.info(f"  Found {len(all_jobs)} jobs from EdJoin")
            except Exception as e:
                self.logger.error(f"  Error scraping EdJoin: {e}")
            
            browser.close()
        
        self.logger.info(f"Total EdJoin jobs scraped: {len(all_jobs)}")
        return all_jobs
    
    def _scrape_all_pages(self, page: Page) -> List[JobData]:
        """
        Scrape all pages of EdJoin results.
        
        Args:
            page: Playwright page object
            
        Returns:
            List of all JobData objects
        """
        all_jobs = []
        
        # Navigate to search page
        page.goto(self.SEARCH_URL, wait_until='networkidle', timeout=30000)
        
        # Click Search to trigger the search
        search_button = page.query_selector('button:has-text("Search Now")')
        if search_button:
            search_button.click()
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)
        
        # Dismiss any notification popups
        finish_reading = page.query_selector('button:has-text("Finish Reading")')
        if finish_reading and finish_reading.is_visible():
            finish_reading.click()
            page.wait_for_timeout(500)
        
        # Select 50 rows per page
        rows_select = page.query_selector('select[aria-label="Number of results per page to show"]')
        if rows_select:
            rows_select.select_option('50')
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(1500)
        
        page_num = 1
        max_pages = 10
        
        while page_num <= max_pages:
            # Get page HTML and parse with BeautifulSoup
            html = page.content()
            jobs = self._parse_html(html)
            
            if not jobs:
                break
            
            all_jobs.extend(jobs)
            self.logger.info(f"    Page {page_num}: {len(jobs)} jobs")
            
            # Check for next page
            page_info = page.query_selector('text=/Page \\d+ of \\d+/')
            if page_info:
                text = page_info.inner_text()
                match = re.search(r'Page (\d+) of (\d+)', text)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    if current >= total:
                        break
            
            # Click next page
            next_button = page.query_selector('a:has-text(">")')
            if next_button and next_button.is_visible():
                next_button.click()
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(1000)
                page_num += 1
                self.delay()
            else:
                break
        
        return all_jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        """
        Parse HTML to extract job listings using BeautifulSoup.
        
        Args:
            html: Full page HTML
            
        Returns:
            List of JobData objects
        """
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        seen_urls = set()
        
        # Find all job links that contain the job posting URL
        job_links = soup.find_all('a', href=re.compile(r'/Home/JobPosting/\d+'))
        
        for link in job_links:
            # Only process links that have an h5 (job title heading)
            h5 = link.find('h5')
            if not h5:
                continue
            
            try:
                job = self._parse_job_from_link(link, soup)
                if job and self.validate_job(job) and job.url not in seen_urls:
                    jobs.append(job)
                    seen_urls.add(job.url)
            except Exception as e:
                self.logger.warning(f"Error parsing job: {e}")
        
        return jobs
    
    def _parse_job_from_link(self, link, soup: BeautifulSoup) -> Optional[JobData]:
        """
        Parse a single job from its link element.
        
        Args:
            link: BeautifulSoup tag for the job link
            soup: Full page BeautifulSoup object
            
        Returns:
            JobData object or None
        """
        href = link.get('href', '')
        if not href or '/Home/JobPosting/' not in href:
            return None
        
        # Build full URL
        if href.startswith('/'):
            url = f"{self.BASE_URL}{href}"
        else:
            url = href
        
        # Get title from h5
        h5 = link.find('h5')
        title = h5.get_text(strip=True) if h5 else link.get_text(strip=True)
        
        if not title or len(title) < 5:
            return None
        
        # Extract job ID
        job_id_match = re.search(r'/JobPosting/(\d+)', url)
        job_id = job_id_match.group(1) if job_id_match else href
        
        # Navigate up to find the job card container
        # The structure has the job link nested several levels deep
        # We need to find the container that also has the employer info
        card = self._find_job_card(link)
        
        employer = "Unknown School/District"
        location = "Humboldt County, CA"
        salary_text = None
        closing_date = None
        
        if card:
            # Find the employer text - it's in a paragraph after the job title
            # Pattern: "District Name - City, Humboldt County, CA"
            employer_text = self._extract_employer_text(card)
            if employer_text:
                # Check for Humboldt County Office of Education (HCOE) first
                if 'Humboldt County Office of Education' in employer_text or 'HCOE' in employer_text:
                    employer = "Humboldt County Office of Education"
                    location = "Eureka, Humboldt County, CA"
                # Check for School & College Legal Services
                elif 'School & College Legal Services' in employer_text or 'Legal Services' in employer_text:
                    employer = "School & College Legal Services"
                    location = "Humboldt County, CA"
                else:
                    # Pattern for districts with hyphenated names like "Klamath-Trinity Joint Unified"
                    # Match everything up to " - City," where City doesn't contain "School" or "District"
                    emp_match = re.search(
                        r'^(.+?(?:Schools?|District|Unified|JUHSD|County Office of Education|Academy|HCOE))\s+-\s+([A-Za-z\s]+),\s*Humboldt County,\s*CA',
                        employer_text
                    )
                    if emp_match:
                        employer = emp_match.group(1).strip()
                        city = emp_match.group(2).strip()
                        location = f"{city}, Humboldt County, CA"
                    else:
                        # Simpler pattern - split on " - " followed by a city name
                        emp_match2 = re.match(r'^(.+?)\s+-\s+([A-Za-z][A-Za-z\s]*),\s*Humboldt', employer_text)
                        if emp_match2:
                            employer = emp_match2.group(1).strip()
                            city = emp_match2.group(2).strip()
                            location = f"{city}, Humboldt County, CA"
                        else:
                            # Last resort: if employer still unknown, check URL for HCOE
                            if '/hcoe' in url.lower():
                                employer = "Humboldt County Office of Education"
                                location = "Eureka, Humboldt County, CA"
            
            # Find salary - look for text with $ in the card
            salary_text = self._extract_salary(card)
            
            # Find closing date
            closing_date = self._extract_deadline(card)
        
        return JobData(
            source_id=f"edjoin_{job_id}",
            source_name="edjoin",
            title=title,
            url=url,
            employer=employer,
            category="Education",
            location=location,
            salary_text=salary_text,
            closing_date=closing_date,
        )
    
    def _find_job_card(self, link) -> Optional:
        """
        Find the job card container element by traversing up the DOM.
        
        Args:
            link: BeautifulSoup tag for the job link
            
        Returns:
            BeautifulSoup tag for the card container or None
        """
        # Go up several parent levels to find the card container
        # The job link is deeply nested, we need to find the container
        # that has both the employer info AND the salary
        # Structure: div > div(content) + button + p(salary)
        parent = link.parent
        for _ in range(8):  # Go up max 8 levels to find container with salary
            if parent is None:
                break
            
            # Check if this container has BOTH employer AND salary info
            text = parent.get_text()
            has_employer = 'Humboldt County, CA' in text
            has_salary = bool(re.search(r'\$[\d,]+', text)) or 'Pay dependent' in text
            
            if has_employer and has_salary:
                return parent
            
            parent = parent.parent
        
        # Fallback - look for container with just employer info
        parent = link.parent
        for _ in range(6):
            if parent is None:
                break
            
            text = parent.get_text()
            if 'Humboldt County, CA' in text:
                return parent
            
            parent = parent.parent
        
        # Final fallback
        return link.find_parent('div')
    
    def _extract_employer_text(self, card) -> Optional[str]:
        """
        Extract the employer/location text from the card.
        
        Args:
            card: BeautifulSoup tag for the card container
            
        Returns:
            Employer text string or None
        """
        # Look for text containing "Humboldt County, CA"
        for elem in card.descendants:
            if hasattr(elem, 'string') and elem.string:
                text = elem.string.strip()
                if 'Humboldt County, CA' in text and len(text) < 200:
                    return text
        
        # Try finding in paragraph text
        for p in card.find_all('p'):
            text = p.get_text(strip=True)
            if 'Humboldt County, CA' in text:
                return text
        
        return None
    
    def _extract_salary(self, card) -> Optional[str]:
        """
        Extract salary text from the card.
        
        Args:
            card: BeautifulSoup tag for the card container
            
        Returns:
            Salary text string or None
        """
        card_text = card.get_text()
        
        # Look for salary patterns in the full text
        # Pattern: "$21.42 - $34.02 Per Hour" or "$51,171 - $103,148 Annually"
        salary_match = re.search(
            r'\$[\d,]+(?:\.\d{2})?\s*(?:-\s*\$[\d,]+(?:\.\d{2})?)?\s*(?:Per Hour|Hourly|Per Month|Monthly|Per Year|Annually|Daily)?',
            card_text,
            re.IGNORECASE
        )
        if salary_match:
            return salary_match.group(0).strip()
        
        # Check for daily rate like "$200 Daily"
        daily_match = re.search(r'\$\d+\s*Daily', card_text)
        if daily_match:
            return daily_match.group(0)
        
        # Check for "Pay dependent on experience"
        if 'Pay dependent on experience' in card_text:
            return "Pay dependent on experience"
        
        return None
    
    def _extract_deadline(self, card) -> Optional[datetime]:
        """
        Extract closing date from the card.
        
        Args:
            card: BeautifulSoup tag for the card container
            
        Returns:
            datetime object or None
        """
        card_text = card.get_text()
        
        # Look for deadline pattern
        deadline_match = re.search(r'Deadline:\s*(.+?)(?:\n|$)', card_text)
        if deadline_match:
            deadline_text = deadline_match.group(1).strip()
            if 'Until Filled' not in deadline_text:
                return self._parse_date(deadline_text)
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object.
        
        Args:
            date_str: Date string like "1/16/2026 12:00 am"
            
        Returns:
            datetime object or None
        """
        if not date_str:
            return None
        
        try:
            return date_parser.parse(date_str.strip())
        except (ValueError, TypeError):
            return None
