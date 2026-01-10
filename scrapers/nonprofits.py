"""
Nonprofit and Social Services Scrapers

Scrapers for local nonprofit organizations:
- Redwoods Rural Health Center (RRHC) - Wix site
- Two Feathers Native American Family Services - Custom HTML
- Changing Tides Family Services - Custom HTML
"""
import re
import requests
from typing import List
from bs4 import BeautifulSoup

from .base import BaseScraper, JobData
from config import USER_AGENT


# URLs for nonprofit career pages
RRHC_URL = "https://www.rrhc.org/job-opportunities"
TWO_FEATHERS_URL = "https://twofeathers-nafs.org/about-us/employment-opportunities/"
CHANGING_TIDES_URL = "https://changingtidesfs.org/employment/"


class RRHCScraper(BaseScraper):
    """
    Scraper for Redwoods Rural Health Center (Wix-based site).
    Jobs are listed in h5 headings with descriptions in paragraphs.
    """
    
    def __init__(self):
        super().__init__("rrhc")
        self.url = RRHC_URL
        self.employer_name = "Redwoods Rural Health Center"
        self.category = "Healthcare"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(
                self.url,
                headers={'User-Agent': USER_AGENT},
                timeout=15
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find all h5 headings which contain job titles
            job_headings = soup.find_all('h5')
            
            for heading in job_headings:
                heading_text = heading.get_text(strip=True)
                
                # Skip non-job headings
                if not heading_text or len(heading_text) < 5:
                    continue
                    
                # Skip headings that don't look like job titles
                skip_keywords = ['responsibilities', 'qualifications', 'benefits', 
                                'knowledge', 'competencies', 'education', 'pay',
                                'application', 'general ledger', 'accounting operations',
                                'interpersonal', 'rdh responsibilities']
                if any(kw in heading_text.lower() for kw in skip_keywords):
                    continue
                
                # Extract job title
                title = heading_text
                
                # Clean up title - remove parenthetical items from start
                title = re.sub(r'^\([^)]+\)\s*', '', title)
                
                # Skip if title doesn't look like a job position
                if not re.search(r'(nurse|assistant|hygienist|accountant|director|manager|specialist|coordinator|technician|therapist|counselor|social worker)', title.lower()):
                    continue
                
                # Get description from following paragraphs
                description = ""
                next_elem = heading.find_next_sibling()
                while next_elem and next_elem.name != 'h5':
                    if next_elem.name == 'p':
                        p_text = next_elem.get_text(strip=True)
                        if p_text and len(p_text) > 20:
                            description = p_text[:500]
                            break
                    next_elem = next_elem.find_next_sibling()
                
                # Extract salary if present in description or following text
                salary_text = None
                salary_match = re.search(
                    r'\$[\d,]+(?:\.\d{2})?\s*(?:to|-)?\s*\$[\d,]+(?:\.\d{2})?\s*(?:per\s+(?:hour|year)|hourly|annually)?',
                    description,
                    re.IGNORECASE
                )
                if salary_match:
                    salary_text = salary_match.group(0)
                
                # Determine job type from title/description
                job_type = "Full-Time"  # Default for RRHC
                if 'part-time' in title.lower() or 'part-time' in description.lower():
                    job_type = "Part-Time"
                
                # Create unique source_id
                source_id = f"rrhc_{title.lower().replace(' ', '_')[:50]}"
                
                job = JobData(
                    source_id=source_id,
                    source_name="rrhc",
                    title=title,
                    url=self.url,
                    employer=self.employer_name,
                    category=self.category,
                    location="Redway, CA",
                    description=description,
                    salary_text=salary_text,
                    job_type=job_type,
                )
                
                if self.validate_job(job):
                    jobs.append(job)
            
            # Deduplicate by title (some headings may be duplicated)
            seen_titles = set()
            unique_jobs = []
            for job in jobs:
                if job.title not in seen_titles:
                    seen_titles.add(job.title)
                    unique_jobs.append(job)
            
            jobs = unique_jobs
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class TwoFeathersScraper(BaseScraper):
    """
    Scraper for Two Feathers Native American Family Services.
    Employment page lists benefits but not specific job openings.
    This scraper checks for any job listings that may be added.
    """
    
    def __init__(self):
        super().__init__("two_feathers")
        self.url = TWO_FEATHERS_URL
        self.employer_name = "Two Feathers Native American Family Services"
        self.category = "Social Services"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(
                self.url,
                headers={'User-Agent': USER_AGENT},
                timeout=15
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for job listings in various formats
            # Check for h2, h3, h4 headings that might contain job titles
            for heading_tag in ['h2', 'h3', 'h4', 'h5']:
                headings = soup.find_all(heading_tag)
                for heading in headings:
                    heading_text = heading.get_text(strip=True)
                    
                    # Skip common non-job headings
                    skip_phrases = ['employment opportunities', 'benefits include', 
                                   'join our team', 'about', 'contact', 'how to apply']
                    if any(phrase in heading_text.lower() for phrase in skip_phrases):
                        continue
                    
                    # Check if it looks like a job title
                    job_indicators = ['coordinator', 'specialist', 'therapist', 'counselor',
                                     'director', 'manager', 'assistant', 'worker', 'intern']
                    if any(ind in heading_text.lower() for ind in job_indicators):
                        job = JobData(
                            source_id=f"two_feathers_{heading_text.lower().replace(' ', '_')[:50]}",
                            source_name="two_feathers",
                            title=heading_text,
                            url=self.url,
                            employer=self.employer_name,
                            category=self.category,
                            location="McKinleyville, CA",
                        )
                        
                        if self.validate_job(job):
                            jobs.append(job)
            
            # Also check for links to job postings (PDF or other)
            job_links = soup.find_all('a', href=True)
            for link in job_links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True)
                
                # Skip non-job links
                if not link_text or len(link_text) < 5:
                    continue
                
                # Check if it's a job posting link
                if any(ext in href.lower() for ext in ['.pdf', 'job', 'position', 'opening']):
                    job_indicators = ['coordinator', 'specialist', 'therapist', 'counselor',
                                     'director', 'manager', 'assistant', 'worker']
                    if any(ind in link_text.lower() for ind in job_indicators):
                        # Use main employment page, not PDF links
                        job = JobData(
                            source_id=f"two_feathers_{link_text.lower().replace(' ', '_')[:50]}",
                            source_name="two_feathers",
                            title=link_text,
                            url=self.url,  # Use employment page, not PDF
                            employer=self.employer_name,
                            category=self.category,
                            location="McKinleyville, CA",
                        )
                        
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class ChangingTidesScraper(BaseScraper):
    """
    Scraper for Changing Tides Family Services.
    Jobs are listed with links to PDF job descriptions.
    """
    
    def __init__(self):
        super().__init__("changing_tides")
        self.url = CHANGING_TIDES_URL
        self.employer_name = "Changing Tides Family Services"
        self.category = "Social Services"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(
                self.url,
                headers={'User-Agent': USER_AGENT},
                timeout=15
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find job links - they link to PDFs with job descriptions
            job_links = soup.find_all('a', href=True)
            
            for link in job_links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True)
                
                # Skip non-PDF links or links without text
                if not link_text or '.pdf' not in href.lower():
                    continue
                
                # Skip non-job PDFs
                skip_pdfs = ['application', 'benefits']
                if any(skip in link_text.lower() for skip in skip_pdfs):
                    continue
                
                # Look for job-related PDFs
                job_indicators = ['specialist', 'worker', 'coordinator', 'therapist',
                                 'counselor', 'director', 'manager', 'assistant',
                                 'teacher', 'aide', 'support']
                if any(ind in link_text.lower() for ind in job_indicators):
                    title = link_text
                    
                    # Get description from nearby text
                    description = ""
                    parent = link.find_parent('div') or link.find_parent('p')
                    if parent:
                        next_elem = parent.find_next_sibling()
                        if next_elem:
                            desc_container = next_elem.find_all('p')
                            for p in desc_container[:2]:  # Get first 2 paragraphs
                                description += p.get_text(strip=True) + " "
                            description = description[:500].strip()
                    
                    # Extract salary from description
                    salary_text = None
                    salary_match = re.search(
                        r'\$[\d.]+(?:/hour|per\s+hour)?',
                        description,
                        re.IGNORECASE
                    )
                    if salary_match:
                        salary_text = salary_match.group(0)
                    
                    # Determine job type
                    job_type = "Part-Time"  # Most Changing Tides positions are part-time/intermittent
                    if 'full-time' in title.lower() or 'full-time' in description.lower():
                        job_type = "Full-Time"
                    elif 'intermittent' in description.lower():
                        job_type = "Intermittent"
                    
                    # Use main employment page, not PDF links
                    job = JobData(
                        source_id=f"changing_tides_{title.lower().replace(' ', '_')[:50]}",
                        source_name="changing_tides",
                        title=title,
                        url=self.url,  # Use employment page, not PDF
                        employer=self.employer_name,
                        category=self.category,
                        location="Eureka, CA",
                        description=description,
                        salary_text=salary_text,
                        job_type=job_type,
                    )
                    
                    if self.validate_job(job):
                        jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs
