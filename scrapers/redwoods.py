"""
College of the Redwoods Job Scraper
https://employment.redwoods.edu/postings/search

Custom job board with pagination.
"""
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from dateutil import parser as date_parser

from .base import BaseScraper, JobData
from config import USER_AGENT


class RedwoodsScraper(BaseScraper):
    """
    Scraper for College of the Redwoods jobs.
    """
    
    def __init__(self):
        super().__init__("redwoods")
        self.base_url = "https://employment.redwoods.edu"
        self.search_url = "https://employment.redwoods.edu/postings/search"
    
    def scrape(self) -> List[JobData]:
        self.logger.info("Scraping College of the Redwoods jobs...")
        
        all_jobs = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            
            try:
                page_num = 1
                max_pages = 5
                
                while page_num <= max_pages:
                    if page_num == 1:
                        url = self.search_url
                    else:
                        url = f"{self.search_url}?page={page_num}"
                    
                    self.logger.info(f"  Fetching page {page_num}...")
                    page.goto(url, wait_until='networkidle', timeout=30000)
                    page.wait_for_timeout(1500)
                    
                    html = page.content()
                    jobs = self._parse_html(html)
                    
                    if not jobs:
                        break
                    
                    all_jobs.extend(jobs)
                    self.logger.info(f"    Page {page_num}: {len(jobs)} jobs")
                    
                    # Check for next page
                    next_link = page.query_selector('a:has-text("Next")')
                    if not next_link or not next_link.is_visible():
                        break
                    
                    page_num += 1
                    self.delay()
                
                self.logger.info(f"  Found {len(all_jobs)} jobs from College of the Redwoods")
                
            except Exception as e:
                self.logger.error(f"  Error scraping College of the Redwoods: {e}")
            
            browser.close()
        
        return all_jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Job listings are in table rows or divs with job info
        # Look for job title links
        job_rows = soup.find_all('tr', class_=re.compile(r'job-item|posting'))
        
        if not job_rows:
            # Try finding by link pattern
            job_links = soup.find_all('a', href=re.compile(r'/postings/\d+'))
            
            for link in job_links:
                try:
                    title = link.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    
                    href = link.get('href', '')
                    url = f"{self.base_url}{href}" if href.startswith('/') else href
                    
                    # Extract posting ID
                    id_match = re.search(r'/postings/(\d+)', url)
                    posting_id = id_match.group(1) if id_match else url
                    
                    # Get parent row for more details
                    row = link.find_parent('tr')
                    
                    department = None
                    position_type = None
                    closing_date = None
                    
                    if row:
                        cells = row.find_all('td')
                        # Typical structure: Title | Posting# | Department | Type | Close Date
                        if len(cells) >= 4:
                            department = cells[2].get_text(strip=True) if len(cells) > 2 else None
                            position_type = cells[3].get_text(strip=True) if len(cells) > 3 else None
                            if len(cells) > 4:
                                date_text = cells[4].get_text(strip=True)
                                closing_date = self._parse_date(date_text)
                    
                    # Determine category based on position type and title
                    category = self._determine_category(title, position_type)
                    
                    job = JobData(
                        source_id=f"redwoods_{posting_id}",
                        source_name="redwoods",
                        title=title,
                        url=url,
                        employer="College of the Redwoods",
                        category=category,
                        original_category=position_type,
                        location="Eureka, CA",
                        job_type=position_type,
                        closing_date=closing_date,
                    )
                    
                    if self.validate_job(job):
                        jobs.append(job)
                        
                except Exception as e:
                    self.logger.warning(f"Error parsing Redwoods job: {e}")
        
        return jobs
    
    def _determine_category(self, title: str, position_type: Optional[str]) -> str:
        """Determine job category based on title and position type."""
        title_lower = title.lower()
        
        if position_type:
            if 'Faculty' in position_type:
                return "Education"
            if 'Staff' in position_type:
                return "Administrative"
        
        if any(kw in title_lower for kw in ['instructor', 'teacher', 'professor', 'lecturer', 'faculty']):
            return "Education"
        if any(kw in title_lower for kw in ['counselor', 'advisor']):
            return "Education"
        if any(kw in title_lower for kw in ['police', 'safety', 'security']):
            return "Public Safety"
        if any(kw in title_lower for kw in ['maintenance', 'custodian', 'grounds']):
            return "Maintenance"
        if any(kw in title_lower for kw in ['nurse', 'health', 'dental', 'medical']):
            return "Healthcare"
        
        return "Education"  # Default for college jobs
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str or 'Open' in date_str:
            return None
        try:
            return date_parser.parse(date_str)
        except:
            return None
