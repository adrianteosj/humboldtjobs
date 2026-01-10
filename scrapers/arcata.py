"""
City of Arcata Job Scraper
https://www.cityofarcata.org/996/Part-Time-Job-Opportunities

City of Arcata uses their own website for job postings, not NEOGOV.
"""
import requests
import re
from typing import List, Optional
from bs4 import BeautifulSoup

from .base import BaseScraper, JobData
from config import USER_AGENT


class ArcataScraper(BaseScraper):
    """
    Scraper for City of Arcata job postings.
    """
    
    JOBS_URL = "https://www.cityofarcata.org/996/Part-Time-Job-Opportunities"
    BASE_URL = "https://www.cityofarcata.org"
    
    def __init__(self):
        super().__init__("arcata")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    
    def scrape(self) -> List[JobData]:
        """
        Scrape City of Arcata job postings.
        
        Returns:
            List of JobData objects
        """
        self.logger.info("Scraping City of Arcata...")
        
        all_jobs = []
        
        try:
            # Get the main jobs page
            response = self.session.get(self.JOBS_URL, timeout=30)
            
            if response.status_code != 200:
                self.logger.error(f"HTTP {response.status_code}")
                return []
            
            jobs = self._parse_html(response.text)
            all_jobs.extend(jobs)
            
            self.logger.info(f"  Found {len(jobs)} jobs from City of Arcata")
            
        except Exception as e:
            self.logger.error(f"Error scraping Arcata: {e}")
        
        return all_jobs
    
    def _parse_html(self, html: str) -> List[JobData]:
        """
        Parse the HTML page for job listings.
        
        Args:
            html: HTML content
            
        Returns:
            List of JobData objects
        """
        soup = BeautifulSoup(html, 'lxml')
        jobs = []
        
        # Find the job table
        table = soup.find('table')
        if not table:
            self.logger.warning("No job table found")
            return []
        
        # Find all rows (skip header)
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            try:
                job = self._parse_row(row)
                if job and self.validate_job(job):
                    jobs.append(job)
            except Exception as e:
                self.logger.warning(f"Error parsing row: {e}")
        
        return jobs
    
    def _parse_row(self, row) -> Optional[JobData]:
        """
        Parse a single table row.
        
        Args:
            row: BeautifulSoup table row element
            
        Returns:
            JobData object or None
        """
        cells = row.find_all('td')
        if len(cells) < 2:
            return None
        
        # First cell contains job title and description
        title_cell = cells[0]
        
        # Find the title (usually bold or in a strong tag)
        title_elem = title_cell.find(['strong', 'b'])
        if not title_elem:
            # Try to get first line as title
            title = title_cell.get_text().strip().split('\n')[0]
        else:
            title = title_elem.get_text().strip()
        
        if not title:
            return None
        
        # Clean up title
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Get description from the cell
        description = title_cell.get_text().strip()
        description = re.sub(r'\s+', ' ', description)
        
        # Find job flyer link in the last cell (Application Materials)
        url = self.JOBS_URL  # Default to the jobs page
        if len(cells) >= 3:
            links = cells[2].find_all('a')
            for link in links:
                href = link.get('href', '')
                if 'DocumentCenter' in href or 'Job' in href or 'Flyer' in link.get_text():
                    if href.startswith('/'):
                        url = f"{self.BASE_URL}{href}"
                    else:
                        url = href
                    break
        
        # If no document link, use the jobs page URL
        if url == self.JOBS_URL:
            # Create a unique URL by adding a fragment
            url = f"{self.JOBS_URL}#{title.replace(' ', '-').lower()}"
        
        # Extract closing date from second cell
        closing_date = None
        if len(cells) >= 2:
            date_text = cells[1].get_text().strip()
            # Most are "Open until filled" but check for actual dates
            if 'Open' not in date_text:
                from dateutil import parser as date_parser
                try:
                    closing_date = date_parser.parse(date_text)
                except:
                    pass
        
        # Generate a unique source ID
        source_id = re.sub(r'[^a-z0-9]', '_', title.lower())[:50]
        
        return JobData(
            source_id=f"arcata_{source_id}",
            source_name="arcata",
            title=title,
            url=url,
            employer="City of Arcata",
            category="Government",
            location="Arcata, CA",
            description=description[:500] if description else None,
            closing_date=closing_date,
        )
