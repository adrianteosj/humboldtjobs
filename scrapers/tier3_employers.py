"""
Tier 3 Additional Employers Scrapers

Scrapers for additional local and regional employers in Humboldt County.
These include:
- Energy/Utilities: RCEA, PG&E
- Food/Agriculture: Humboldt Creamery, Cypress Grove, Murphy's Markets, etc.
- Manufacturing: Kokatat, Lost Coast Brewery
- Nonprofits: Boys & Girls Club, Food for People
- Retail: Ace Hardware, WinCo, Grocery Outlet, Harbor Freight
- Major Chains: CVS, Rite Aid, Starbucks, FedEx, UPS
"""
import re
import requests
from typing import List, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .base import BaseScraper, JobData
from config import USER_AGENT


class RCEAScraper(BaseScraper):
    """Scraper for Redwood Coast Energy Authority"""
    
    def __init__(self):
        super().__init__("rcea")
        self.url = "https://redwoodenergy.org/about/employment/"
        self.employer_name = "Redwood Coast Energy Authority"
        self.category = "Energy/Utilities"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for job listings after "Available Positions" heading
            content = soup.find('main') or soup.find('article')
            if content:
                text = content.get_text()
                # Check if there are positions
                if "no open positions" in text.lower():
                    self.logger.info("  No current openings")
                else:
                    # Look for job titles in headings
                    for heading in content.find_all(['h2', 'h3', 'h4']):
                        title = heading.get_text(strip=True)
                        # Skip section headings
                        skip_words = ['available positions', 'join our team', 'equal opportunity',
                                     'employee compensation', 'contact us', 'application']
                        if any(w in title.lower() for w in skip_words):
                            continue
                        if len(title) > 10 and len(title) < 100:
                            job = JobData(
                                source_id=f"rcea_{title.lower().replace(' ', '_')[:50]}",
                                source_name="rcea",
                                title=title,
                                url=self.url,
                                employer=self.employer_name,
                                category=self.category,
                                location="Eureka, CA",
                            )
                            if self.validate_job(job):
                                jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class FoodForPeopleScraper(BaseScraper):
    """Scraper for Food for People (Food Bank)"""
    
    def __init__(self):
        super().__init__("food_for_people")
        self.url = "https://www.foodforpeople.org/jobs"
        self.employer_name = "Food for People"
        self.category = "Nonprofit"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find job listings - they appear as h2 headings with job titles
            main_content = soup.find('main') or soup.find('article')
            if main_content:
                for heading in main_content.find_all('h2'):
                    title = heading.get_text(strip=True)
                    
                    # Skip page title and non-job headings
                    skip_words = ['jobs at', 'subscribe', 'newsletter', 'contact']
                    if any(w in title.lower() for w in skip_words):
                        continue
                    
                    if len(title) > 5 and len(title) < 100:
                        # Get description from following paragraphs
                        description = ""
                        salary_text = None
                        job_type = None
                        
                        next_elem = heading.find_next_sibling()
                        while next_elem and next_elem.name not in ['h2', 'h3']:
                            if next_elem.name == 'p':
                                p_text = next_elem.get_text(strip=True)
                                if not description and len(p_text) > 50:
                                    description = p_text[:500]
                                
                                # Extract salary
                                salary_match = re.search(r'\$[\d.]+\s*(?:per\s+hour|/hour)?', p_text)
                                if salary_match:
                                    salary_text = salary_match.group(0)
                                
                                # Extract hours/job type
                                hours_match = re.search(r'(\d+)\s*hours?(?:/week)?', p_text, re.IGNORECASE)
                                if hours_match:
                                    hours = int(hours_match.group(1))
                                    job_type = "Full-Time" if hours >= 35 else "Part-Time"
                            
                            next_elem = next_elem.find_next_sibling()
                        
                        job = JobData(
                            source_id=f"ffp_{title.lower().replace(' ', '_')[:50]}",
                            source_name="food_for_people",
                            title=title,
                            url=self.url,
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
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class BGCRedwoodsScraper(BaseScraper):
    """Scraper for Boys & Girls Club of the Redwoods"""
    
    def __init__(self):
        super().__init__("bgc_redwoods")
        self.url = "https://bgcredwoods.org/careers/"
        self.employer_name = "Boys & Girls Club of the Redwoods"
        self.category = "Nonprofit"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for specific job titles in headings or links
            content = soup.find('article') or soup.find('main')
            if content:
                # Check for job links (often to PDFs)
                for link in content.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # Skip generic links
                    if 'application' in href.lower() and 'employment' in href.lower():
                        continue
                    
                    # Look for job-specific PDFs or pages
                    job_keywords = ['coordinator', 'director', 'specialist', 'counselor', 
                                   'mentor', 'leader', 'instructor']
                    if any(kw in text.lower() for kw in job_keywords):
                        full_url = href if href.startswith('http') else f"https://bgcredwoods.org{href}"
                        job = JobData(
                            source_id=f"bgcr_{text.lower().replace(' ', '_')[:50]}",
                            source_name="bgc_redwoods",
                            title=text,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Eureka, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class KokatatScraper(BaseScraper):
    """Scraper for Kokatat (outdoor apparel manufacturer)"""
    
    def __init__(self):
        super().__init__("kokatat")
        self.url = "https://kokatat.com/careers"
        self.employer_name = "Kokatat"
        self.category = "Manufacturing"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            main_content = soup.find('main')
            if main_content:
                text = main_content.get_text()
                
                # Check for "no current job openings"
                if "no current job openings" in text.lower():
                    self.logger.info("  No current openings")
                else:
                    # Look for job titles after "Current Job Openings"
                    for heading in main_content.find_all(['h3', 'h4', 'h5']):
                        title = heading.get_text(strip=True)
                        
                        # Skip section headers
                        skip_words = ['current job', 'application', 'kokatat culture', 
                                     'completed applications', 'need help']
                        if any(w in title.lower() for w in skip_words):
                            continue
                        
                        if len(title) > 5 and len(title) < 100:
                            job = JobData(
                                source_id=f"kokatat_{title.lower().replace(' ', '_')[:50]}",
                                source_name="kokatat",
                                title=title,
                                url=self.url,
                                employer=self.employer_name,
                                category=self.category,
                                location="Arcata, CA",
                            )
                            if self.validate_job(job):
                                jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class LostCoastBreweryScraper(BaseScraper):
    """Scraper for Lost Coast Brewery"""
    
    def __init__(self):
        super().__init__("lost_coast_brewery")
        self.url = "https://lostcoast.com/careers"
        self.employer_name = "Lost Coast Brewery"
        self.category = "Food/Beverage"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            main_content = soup.find('main')
            if main_content:
                # Look for job listings - often in list items or headings
                for elem in main_content.find_all(['h2', 'h3', 'h4', 'li']):
                    text = elem.get_text(strip=True)
                    
                    # Skip generic content
                    skip_words = ['come join us', 'download', 'brewery', 'restaurant',
                                 'lost coast brewery', 'send your']
                    if any(w in text.lower() for w in skip_words):
                        continue
                    
                    # Check for job titles
                    job_keywords = ['manager', 'server', 'bartender', 'cook', 'brewer',
                                   'assistant', 'position', 'specialist']
                    if any(kw in text.lower() for kw in job_keywords) and len(text) < 80:
                        job = JobData(
                            source_id=f"lcb_{text.lower().replace(' ', '_')[:50]}",
                            source_name="lost_coast_brewery",
                            title=text,
                            url=self.url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Eureka, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class MurphysMarketsScraper(BaseScraper):
    """Scraper for Murphy's Markets"""
    
    def __init__(self):
        super().__init__("murphys_markets")
        self.url = "https://www.murphysmarkets.net/employment"
        self.employer_name = "Murphy's Markets"
        self.category = "Retail"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Murphy's primarily has an application form, but check for specific openings
            main_content = soup.find('main') or soup.find('article')
            if main_content:
                # Look for specific position announcements
                for heading in main_content.find_all(['h2', 'h3', 'h4']):
                    text = heading.get_text(strip=True)
                    
                    # Skip form headers
                    skip_words = ['join our team', 'employment', 'application']
                    if any(w in text.lower() for w in skip_words):
                        continue
                    
                    job_keywords = ['cashier', 'stocker', 'deli', 'produce', 'meat',
                                   'manager', 'clerk', 'bakery']
                    if any(kw in text.lower() for kw in job_keywords):
                        job = JobData(
                            source_id=f"murphys_{text.lower().replace(' ', '_')[:50]}",
                            source_name="murphys_markets",
                            title=text,
                            url=self.url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Humboldt County, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class CypressGroveScraper(BaseScraper):
    """Scraper for Cypress Grove Chevre"""
    
    def __init__(self):
        super().__init__("cypress_grove")
        self.url = "https://www.cypressgrovecheese.com/careers/"
        self.employer_name = "Cypress Grove Chevre"
        self.category = "Food/Agriculture"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                # Look for job listings
                for heading in main_content.find_all(['h2', 'h3', 'h4']):
                    text = heading.get_text(strip=True)
                    
                    # Skip generic headings
                    skip_words = ['careers', 'join', 'about', 'our team', 'benefits']
                    if any(w in text.lower() for w in skip_words) and len(text) < 30:
                        continue
                    
                    # Check for job titles
                    job_keywords = ['production', 'packaging', 'quality', 'supervisor',
                                   'technician', 'operator', 'manager', 'specialist']
                    if any(kw in text.lower() for kw in job_keywords):
                        job = JobData(
                            source_id=f"cypress_{text.lower().replace(' ', '_')[:50]}",
                            source_name="cypress_grove",
                            title=text,
                            url=self.url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Arcata, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class DriscollsScraper(BaseScraper):
    """Scraper for Driscoll's (berry company)"""
    
    def __init__(self):
        super().__init__("driscolls")
        self.url = "https://www.driscolls.com/about/careers"
        self.employer_name = "Driscoll's"
        self.category = "Food/Agriculture"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            # Driscoll's may use an ATS - try Playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(3000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for job listings or iframes to job boards
            job_links = soup.find_all('a', href=True)
            for link in job_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Check for job board links or job titles
                if 'workday' in href.lower() or 'careers' in href.lower():
                    # This is likely a link to their ATS
                    self.logger.info(f"  Found ATS link: {href}")
                    continue
                
                job_keywords = ['position', 'job', 'opening', 'manager', 'specialist',
                               'coordinator', 'technician']
                if any(kw in text.lower() for kw in job_keywords) and len(text) < 100:
                    full_url = href if href.startswith('http') else f"https://www.driscolls.com{href}"
                    job = JobData(
                        source_id=f"driscolls_{text.lower().replace(' ', '_')[:50]}",
                        source_name="driscolls",
                        title=text,
                        url=full_url,
                        employer=self.employer_name,
                        category=self.category,
                        location="Watsonville, CA",  # HQ, may have Humboldt positions
                    )
                    if self.validate_job(job):
                        jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class WinCoFoodsScraper(BaseScraper):
    """Scraper for WinCo Foods"""
    
    def __init__(self):
        super().__init__("winco")
        self.url = "https://careers.wincofoods.com"
        self.search_url = "https://careers.wincofoods.com/search-jobs/eureka/10030/1/6252001-5332921-5565500-5564154/40x8018/-124x16376/50/2"
        self.employer_name = "WinCo Foods"
        self.category = "Retail"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(3000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for job listings
            job_cards = soup.find_all('li', class_=re.compile(r'job-'))
            if not job_cards:
                job_cards = soup.find_all('div', class_=re.compile(r'job-'))
            
            for card in job_cards:
                title_elem = card.find('a') or card.find('h2') or card.find('h3')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get('href', '') if title_elem.name == 'a' else ''
                    
                    if title and len(title) > 3:
                        full_url = href if href.startswith('http') else f"{self.url}{href}"
                        
                        # Try to find location
                        location = "Eureka, CA"
                        loc_elem = card.find(class_=re.compile(r'location|city'))
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)
                        
                        job = JobData(
                            source_id=f"winco_{title.lower().replace(' ', '_')[:50]}",
                            source_name="winco",
                            title=title,
                            url=full_url if href else self.search_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class GroceryOutletScraper(BaseScraper):
    """Scraper for Grocery Outlet"""
    
    def __init__(self):
        super().__init__("grocery_outlet")
        self.url = "https://groceryoutlet.com/careers"
        self.employer_name = "Grocery Outlet"
        self.category = "Retail"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(3000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Check for ATS iframe or external job links
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                if 'workday' in src.lower() or 'icims' in src.lower():
                    self.logger.info(f"  Found ATS iframe: {src}")
            
            # Look for direct job links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if 'job' in href.lower() or 'career' in href.lower():
                    job_keywords = ['manager', 'clerk', 'cashier', 'associate', 'stocker']
                    if any(kw in text.lower() for kw in job_keywords):
                        full_url = href if href.startswith('http') else f"https://groceryoutlet.com{href}"
                        job = JobData(
                            source_id=f"go_{text.lower().replace(' ', '_')[:50]}",
                            source_name="grocery_outlet",
                            title=text,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Humboldt County, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class HarborFreightScraper(BaseScraper):
    """Scraper for Harbor Freight Tools"""
    
    def __init__(self):
        super().__init__("harbor_freight")
        self.base_url = "https://jobs.harborfreight.com"
        self.search_url = "https://jobs.harborfreight.com/search-jobs/eureka%2C%20ca/10032/1/6252001-5332921-5565500-5564154/40x8018/-124x16376/50/2"
        self.employer_name = "Harbor Freight Tools"
        self.category = "Retail"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(3000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for job listings in search results
            job_items = soup.select('li[class*="job"]') or soup.select('div[class*="job-item"]')
            
            for item in job_items:
                link = item.find('a', href=True)
                if link:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    if title and len(title) > 3:
                        full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                        
                        # Get location
                        location = "Eureka, CA"
                        loc_elem = item.select_one('[class*="location"]')
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)
                        
                        job = JobData(
                            source_id=f"hf_{title.lower().replace(' ', '_')[:50]}",
                            source_name="harbor_freight",
                            title=title,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class AceHardwareScraper(BaseScraper):
    """Scraper for Ace Hardware (Humboldt County locations)"""
    
    def __init__(self):
        super().__init__("ace_hardware")
        self.base_url = "https://careers.acehardware.com"
        self.search_url = "https://careers.acehardware.com/job-search/?location=Eureka%2C+CA&radius=50"
        self.employer_name = "Ace Hardware"
        self.category = "Retail"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(4000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for job cards
            job_cards = soup.select('div[class*="job"]') or soup.select('li[class*="job"]')
            
            for card in job_cards:
                title_elem = card.find(['a', 'h2', 'h3', 'h4'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get('href', '') if title_elem.name == 'a' else ''
                    
                    # Skip empty or too short titles
                    if not title or len(title) < 3:
                        continue
                    
                    full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    
                    # Get location
                    location = "Humboldt County, CA"
                    loc_elem = card.select_one('[class*="location"]')
                    if loc_elem:
                        location = loc_elem.get_text(strip=True)
                    
                    job = JobData(
                        source_id=f"ace_{title.lower().replace(' ', '_')[:50]}",
                        source_name="ace_hardware",
                        title=title,
                        url=full_url if href else self.search_url,
                        employer=self.employer_name,
                        category=self.category,
                        location=location,
                    )
                    if self.validate_job(job):
                        jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class SierraPacificScraper(BaseScraper):
    """Scraper for Sierra Pacific Industries (timber)"""
    
    def __init__(self):
        super().__init__("sierra_pacific")
        self.url = "https://spi-ind.com/CAREERS"
        self.employer_name = "Sierra Pacific Industries"
        self.category = "Timber/Forestry"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for job listings
            main_content = soup.find('main') or soup.find('body')
            if main_content:
                # Check for job links
                for link in main_content.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # Filter for job-related links
                    job_keywords = ['operator', 'technician', 'driver', 'mechanic',
                                   'forester', 'manager', 'supervisor', 'millwright']
                    
                    if any(kw in text.lower() for kw in job_keywords) and len(text) < 100:
                        full_url = href if href.startswith('http') else f"https://spi-ind.com{href}"
                        job = JobData(
                            source_id=f"spi_{text.lower().replace(' ', '_')[:50]}",
                            source_name="sierra_pacific",
                            title=text,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Northern California",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


# Major chain scrapers using Workday or similar ATS


class CVSHealthScraper(BaseScraper):
    """Scraper for CVS Health"""
    
    def __init__(self):
        super().__init__("cvs")
        self.base_url = "https://jobs.cvshealth.com"
        self.search_url = "https://jobs.cvshealth.com/us/en/search-results?keywords=&location=Eureka%2C%20CA%2C%20United%20States&latitude=40.8020712&longitude=-124.1636729&radius=50"
        self.employer_name = "CVS Health"
        self.category = "Healthcare/Retail"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # CVS uses Phenom/similar ATS
            job_cards = soup.select('[class*="job-card"]') or soup.select('[class*="JobCard"]')
            
            for card in job_cards:
                title_elem = card.find(['a', 'h2', 'h3'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get('href', '')
                    
                    if title and len(title) > 3:
                        full_url = f"{self.base_url}{href}" if href.startswith('/') else (href or self.search_url)
                        
                        location = "Humboldt County, CA"
                        loc_elem = card.select_one('[class*="location"]')
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)
                        
                        job = JobData(
                            source_id=f"cvs_{title.lower().replace(' ', '_')[:50]}",
                            source_name="cvs",
                            title=title,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class RiteAidScraper(BaseScraper):
    """Scraper for Rite Aid"""
    
    def __init__(self):
        super().__init__("rite_aid")
        self.base_url = "https://careers.riteaid.com"
        self.search_url = "https://careers.riteaid.com/jobs?location=Eureka%2C+CA&radius=50"
        self.employer_name = "Rite Aid"
        self.category = "Healthcare/Retail"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for job cards
            job_cards = soup.select('[class*="job"]') or soup.select('[data-job-id]')
            
            for card in job_cards[:20]:  # Limit to avoid too many
                title_elem = card.find(['a', 'h2', 'h3', 'h4'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get('href', '')
                    
                    if title and len(title) > 3 and len(title) < 150:
                        full_url = f"{self.base_url}{href}" if href.startswith('/') else (href or self.search_url)
                        
                        location = "Humboldt County, CA"
                        loc_elem = card.select_one('[class*="location"]')
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)
                        
                        job = JobData(
                            source_id=f"riteaid_{title.lower().replace(' ', '_')[:50]}",
                            source_name="rite_aid",
                            title=title,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class StarbucksScraper(BaseScraper):
    """Scraper for Starbucks"""
    
    def __init__(self):
        super().__init__("starbucks")
        self.base_url = "https://www.starbucks.com/careers"
        # Starbucks typically uses Workday
        self.search_url = "https://www.starbucks.com/careers/find-a-job?location=Eureka%2C%20CA"
        self.employer_name = "Starbucks"
        self.category = "Food/Beverage"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for job listings
            job_cards = soup.select('[class*="job"]') or soup.select('[class*="Job"]')
            
            for card in job_cards[:20]:
                title_elem = card.find(['a', 'h2', 'h3', 'h4'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get('href', '')
                    
                    if title and len(title) > 3 and len(title) < 150:
                        full_url = href if href.startswith('http') else f"https://www.starbucks.com{href}"
                        
                        location = "Humboldt County, CA"
                        loc_elem = card.select_one('[class*="location"]')
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)
                        
                        job = JobData(
                            source_id=f"sbux_{title.lower().replace(' ', '_')[:50]}",
                            source_name="starbucks",
                            title=title,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class FedExScraper(BaseScraper):
    """Scraper for FedEx"""
    
    def __init__(self):
        super().__init__("fedex")
        self.base_url = "https://careers.fedex.com"
        self.search_url = "https://careers.fedex.com/fedex/jobs?location=Eureka%2C%20CA&woe=7&stretch=50"
        self.employer_name = "FedEx"
        self.category = "Transportation/Logistics"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # FedEx uses Phenom
            job_cards = soup.select('[class*="job-tile"]') or soup.select('[class*="JobCard"]')
            
            for card in job_cards[:20]:
                title_elem = card.find(['a', 'h2', 'h3', 'h4'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get('href', '')
                    
                    if title and len(title) > 3 and len(title) < 150:
                        full_url = f"{self.base_url}{href}" if href.startswith('/') else (href or self.search_url)
                        
                        location = "Humboldt County, CA"
                        loc_elem = card.select_one('[class*="location"]')
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)
                        
                        job = JobData(
                            source_id=f"fedex_{title.lower().replace(' ', '_')[:50]}",
                            source_name="fedex",
                            title=title,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class UPSScraper(BaseScraper):
    """Scraper for UPS"""
    
    def __init__(self):
        super().__init__("ups")
        self.base_url = "https://www.jobs-ups.com"
        self.search_url = "https://www.jobs-ups.com/global/en/search-results?p=ChIJk29QFCL-01QRSYzCXxae3oU&location=Eureka%2C%20CA%2095501%2C%20USA"
        self.employer_name = "UPS"
        self.category = "Transportation/Logistics"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        # Skip patterns - navigation items and non-job text
        skip_patterns = [
            'saved jobs', 'your job cart', 'job alert', 'search jobs',
            'sign in', 'create account', 'my profile', 'applications',
            'follow us', 'privacy', 'terms', 'cookie'
        ]
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # UPS uses TalentBrew - look for job list items in search results section
            # Target the actual job search results, not navigation
            search_results = soup.select_one('#search-results-list') or soup.select_one('[class*="search-results"]')
            
            if search_results:
                job_items = search_results.select('li')
            else:
                # Fallback but filter more strictly
                job_items = soup.select('ul.job-list li') or soup.select('section[id*="search"] li')
            
            for item in job_items[:20]:
                link = item.find('a', href=True)
                if link:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Skip navigation items and non-job links
                    title_lower = title.lower()
                    if any(skip in title_lower for skip in skip_patterns):
                        continue
                    
                    # Must be a job detail page URL (contains /job/)
                    if '/job/' not in href and '/jobs/' not in href:
                        continue
                    
                    if title and len(title) > 3 and len(title) < 150:
                        full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                        
                        location = "Humboldt County, CA"
                        loc_elem = item.select_one('[class*="location"], span.job-location')
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)
                        
                        job = JobData(
                            source_id=f"ups_{title.lower().replace(' ', '_')[:50]}",
                            source_name="ups",
                            title=title,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class PGEScraper(BaseScraper):
    """Scraper for PG&E (Pacific Gas & Electric)"""
    
    def __init__(self):
        super().__init__("pge")
        self.base_url = "https://jobs.pge.com"
        self.search_url = "https://jobs.pge.com/search/?searchby=location&q=&locationsearch=eureka"
        self.employer_name = "Pacific Gas & Electric (PG&E)"
        self.category = "Energy/Utilities"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # PG&E uses SuccessFactors
            job_rows = soup.select('tr[class*="job"]') or soup.select('[class*="jobResult"]')
            
            for row in job_rows[:20]:
                link = row.find('a', href=True)
                if link:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    if title and len(title) > 3 and len(title) < 150:
                        full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                        
                        location = "Northern California"
                        loc_elem = row.select_one('[class*="location"]') or row.find('td', class_='location')
                        if loc_elem:
                            location = loc_elem.get_text(strip=True)
                        
                        job = JobData(
                            source_id=f"pge_{title.lower().replace(' ', '_')[:50]}",
                            source_name="pge",
                            title=title,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class HumboldtSawmillScraper(BaseScraper):
    """Scraper for Humboldt Sawmill Company / Humboldt Redwood Company (iCIMS)"""
    
    def __init__(self):
        super().__init__("humboldt_sawmill")
        self.base_url = "https://careers-mfp.icims.com"
        self.search_url = "https://careers-mfp.icims.com/jobs/search?ss=1&searchLocation=12781-12789-Scotia"
        self.employer_name = "Humboldt Sawmill Company"
        self.category = "Timber/Forestry"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # iCIMS job listings
            job_rows = soup.select('.iCIMS_JobsTable tr') or soup.select('[class*="job"]')
            
            for row in job_rows:
                link = row.find('a', href=True)
                if link:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Skip headers and non-job rows
                    if not title or len(title) < 3 or 'job title' in title.lower():
                        continue
                    
                    full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                    
                    location = "Scotia, CA"
                    loc_elem = row.select_one('[class*="location"]') or row.find('td', class_=re.compile(r'location'))
                    if loc_elem:
                        loc_text = loc_elem.get_text(strip=True)
                        if loc_text:
                            location = loc_text
                    
                    job = JobData(
                        source_id=f"humboldt_sawmill_{title.lower().replace(' ', '_')[:50]}",
                        source_name="humboldt_sawmill",
                        title=title,
                        url=full_url,
                        employer=self.employer_name,
                        category=self.category,
                        location=location,
                    )
                    if self.validate_job(job):
                        jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class HumboldtCreameryScraper(BaseScraper):
    """Scraper for Humboldt Creamery / Crystal Creamery (Paylocity)"""
    
    def __init__(self):
        super().__init__("humboldt_creamery")
        self.base_url = "https://recruiting.paylocity.com"
        self.search_url = "https://recruiting.paylocity.com/recruiting/jobs/All/249cf053-4850-4112-bc86-33c91f93332a/Crystal-Creamery"
        self.employer_name = "Humboldt Creamery"
        self.category = "Food/Agriculture"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Paylocity job listings
            job_cards = soup.select('[class*="job"]') or soup.select('[class*="posting"]')
            
            for card in job_cards[:20]:
                title_elem = card.find(['a', 'h2', 'h3', 'h4'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get('href', '') if title_elem.name == 'a' else ''
                    
                    if title and len(title) > 3 and len(title) < 150:
                        full_url = f"{self.base_url}{href}" if href.startswith('/') else (href or self.search_url)
                        
                        # Filter for Humboldt/Ferndale location
                        location = "Ferndale, CA"
                        loc_elem = card.select_one('[class*="location"]')
                        if loc_elem:
                            loc_text = loc_elem.get_text(strip=True)
                            # Only include jobs in Humboldt area
                            if 'ferndale' in loc_text.lower() or 'humboldt' in loc_text.lower() or 'eureka' in loc_text.lower():
                                location = loc_text
                            else:
                                continue  # Skip non-Humboldt jobs
                        
                        job = JobData(
                            source_id=f"humboldt_creamery_{title.lower().replace(' ', '_')[:50]}",
                            source_name="humboldt_creamery",
                            title=title,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location=location,
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class AlexandreFamilyFarmScraper(BaseScraper):
    """Scraper for Alexandre Family Farm (Shopify)"""
    
    def __init__(self):
        super().__init__("alexandre_farm")
        self.url = "https://alexandrefamilyfarm.com/pages/careers"
        self.employer_name = "Alexandre Family Farm"
        self.category = "Food/Agriculture"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Check page content
            page_text = soup.get_text().lower()
            
            if "no open roles" in page_text or "no open positions" in page_text:
                self.logger.info("  No current openings")
            else:
                # Look for job listings
                main_content = soup.find('main') or soup.find('article') or soup.find('body')
                if main_content:
                    for heading in main_content.find_all(['h2', 'h3', 'h4']):
                        title = heading.get_text(strip=True)
                        
                        # Skip generic headings
                        skip_words = ['careers', 'open roles', 'contact', 'benefits']
                        if any(w in title.lower() for w in skip_words):
                            continue
                        
                        if len(title) > 5 and len(title) < 100:
                            job = JobData(
                                source_id=f"alexandre_{title.lower().replace(' ', '_')[:50]}",
                                source_name="alexandre_farm",
                                title=title,
                                url=self.url,
                                employer=self.employer_name,
                                category=self.category,
                                location="Crescent City, CA",
                            )
                            if self.validate_job(job):
                                jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class PacificSeafoodScraper(BaseScraper):
    """Scraper for Pacific Choice Seafood / Pacific Seafood"""
    
    def __init__(self):
        super().__init__("pacific_seafood")
        self.base_url = "https://careers.pacificseafood.com"
        self.search_url = "https://careers.pacificseafood.com/search-result/?keyword=&city=95501&state=CA"
        self.employer_name = "Pacific Seafood"
        self.category = "Food/Agriculture"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.search_url, wait_until='domcontentloaded', timeout=25000)
                page.wait_for_timeout(5000)
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Check for "No jobs found"
            if "no jobs found" in soup.get_text().lower():
                self.logger.info("  No jobs in Humboldt area")
            else:
                # Look for job listings
                job_cards = soup.select('[class*="job"]') or soup.select('[class*="position"]')
                
                for card in job_cards[:20]:
                    title_elem = card.find(['a', 'h2', 'h3', 'h4'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        href = title_elem.get('href', '') if title_elem.name == 'a' else ''
                        
                        if title and len(title) > 3 and len(title) < 150:
                            full_url = f"{self.base_url}{href}" if href.startswith('/') else (href or self.search_url)
                            
                            location = "Eureka, CA"
                            loc_elem = card.select_one('[class*="location"]')
                            if loc_elem:
                                location = loc_elem.get_text(strip=True)
                            
                            job = JobData(
                                source_id=f"pacific_seafood_{title.lower().replace(' ', '_')[:50]}",
                                source_name="pacific_seafood",
                                title=title,
                                url=full_url,
                                employer=self.employer_name,
                                category=self.category,
                                location=location,
                            )
                            if self.validate_job(job):
                                jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class ArcataHouseScraper(BaseScraper):
    """Scraper for Arcata House Partnership"""
    
    def __init__(self):
        super().__init__("arcata_house")
        self.url = "https://www.arcatahouse.org/join-our-team"
        self.employer_name = "Arcata House Partnership"
        self.category = "Nonprofit"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for job listings or specific positions
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                # Check for job links (often PDFs)
                for link in main_content.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # Skip application downloads and generic links
                    if 'application' in text.lower() and 'download' in text.lower():
                        continue
                    
                    job_keywords = ['coordinator', 'specialist', 'manager', 'case worker',
                                   'counselor', 'advocate', 'director', 'supervisor']
                    if any(kw in text.lower() for kw in job_keywords) and len(text) < 100:
                        full_url = href if href.startswith('http') else f"https://www.arcatahouse.org{href}"
                        job = JobData(
                            source_id=f"arcata_house_{text.lower().replace(' ', '_')[:50]}",
                            source_name="arcata_house",
                            title=text,
                            url=full_url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Arcata, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
                
                # Also check for job headings
                for heading in main_content.find_all(['h2', 'h3', 'h4']):
                    title = heading.get_text(strip=True)
                    
                    skip_words = ['join our team', 'benefits', 'core values', 'our', 
                                 'compassion', 'dignity', 'empowerment', 'contact']
                    if any(w in title.lower() for w in skip_words):
                        continue
                    
                    job_keywords = ['coordinator', 'specialist', 'manager', 'case worker',
                                   'counselor', 'advocate', 'director', 'supervisor']
                    if any(kw in title.lower() for kw in job_keywords):
                        job = JobData(
                            source_id=f"arcata_house_{title.lower().replace(' ', '_')[:50]}",
                            source_name="arcata_house",
                            title=title,
                            url=self.url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Arcata, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class PiersonBuildingScraper(BaseScraper):
    """Scraper for Pierson Building Center (The Big Hammer)"""
    
    def __init__(self):
        super().__init__("pierson_building")
        self.url = "https://www.thebighammer.com/jobs"
        self.employer_name = "Pierson Building Center"
        self.category = "Retail"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for specific job postings
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                # Check for job titles in headings
                for heading in main_content.find_all(['h2', 'h3', 'h4', 'h5', 'h6']):
                    title = heading.get_text(strip=True)
                    
                    skip_words = ['career opportunities', 'work at', 'pierson']
                    if any(w in title.lower() for w in skip_words) and len(title) < 30:
                        continue
                    
                    job_keywords = ['clerk', 'cashier', 'associate', 'driver', 'yard',
                                   'manager', 'specialist', 'sales']
                    if any(kw in title.lower() for kw in job_keywords):
                        job = JobData(
                            source_id=f"pierson_{title.lower().replace(' ', '_')[:50]}",
                            source_name="pierson_building",
                            title=title,
                            url=self.url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Eureka, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class CCraneScraper(BaseScraper):
    """Scraper for C. Crane Company"""
    
    def __init__(self):
        super().__init__("c_crane")
        self.url = "https://ccrane.com/jobs/"
        self.employer_name = "C. Crane Company"
        self.category = "Retail/Electronics"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            response = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # C. Crane lists jobs in a table
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        cell_text = cells[0].get_text(strip=True)
                        
                        # Skip headers and non-job content
                        if not cell_text or 'job opportunities' in cell_text.lower():
                            continue
                        
                        # Check for job-related content
                        job_keywords = ['technician', 'sales', 'customer service', 'warehouse',
                                       'shipping', 'associate', 'position', 'representative']
                        
                        # Look for job titles or descriptions
                        if any(kw in cell_text.lower() for kw in job_keywords):
                            # Extract just the job title from the cell
                            lines = cell_text.split('\n')
                            for line in lines:
                                line = line.strip()
                                if any(kw in line.lower() for kw in job_keywords) and len(line) < 100:
                                    job = JobData(
                                        source_id=f"ccrane_{line.lower().replace(' ', '_')[:50]}",
                                        source_name="c_crane",
                                        title=line,
                                        url=self.url,
                                        employer=self.employer_name,
                                        category=self.category,
                                        location="Fortuna, CA",
                                    )
                                    if self.validate_job(job):
                                        jobs.append(job)
                                    break
            
            # Also check for job listings outside tables
            main_content = soup.find('main') or soup.find('body')
            if main_content and not jobs:
                for heading in main_content.find_all(['h2', 'h3', 'h4']):
                    title = heading.get_text(strip=True)
                    
                    job_keywords = ['technician', 'sales', 'customer service', 'warehouse',
                                   'shipping', 'associate', 'position']
                    if any(kw in title.lower() for kw in job_keywords):
                        job = JobData(
                            source_id=f"ccrane_{title.lower().replace(' ', '_')[:50]}",
                            source_name="c_crane",
                            title=title,
                            url=self.url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Fortuna, CA",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs


class JonesFamilyTreeServiceScraper(BaseScraper):
    """Scraper for Jones Family Tree Service"""
    
    def __init__(self):
        super().__init__("jones_tree")
        self.url = "https://www.jonesfamilytreeservice.com/careers"
        self.employer_name = "Jones Family Tree Service"
        self.category = "Skilled Trades"
    
    def scrape(self) -> List[JobData]:
        self.logger.info(f"Scraping {self.employer_name}...")
        jobs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(3000)  # Wait for dynamic content
                
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for job titles - they appear as headings with salary info
            # Pattern: "Job Title: $XX-XX/hr"
            job_patterns = [
                (r'Seasonal Swamper', r'\$18-24/hr'),
                (r'Seasonal Sawyer', r'\$24-28/hr'),
                (r'Estimator\s*/\s*Manager', r'\$38\.5-50/hr'),
            ]
            
            page_text = soup.get_text()
            
            for title_pattern, salary_pattern in job_patterns:
                if re.search(title_pattern, page_text, re.IGNORECASE):
                    # Extract salary
                    salary_match = re.search(salary_pattern, page_text)
                    salary = salary_match.group(0) if salary_match else None
                    
                    # Clean up title
                    title_match = re.search(title_pattern, page_text, re.IGNORECASE)
                    title = title_match.group(0).replace('\\s*', ' ').strip() if title_match else None
                    
                    if title:
                        # Normalize title
                        title = re.sub(r'\s+', ' ', title)
                        if 'Estimator' in title:
                            title = "Estimator / Manager"
                        
                        # Create unique URL with anchor for deduplication
                        job_anchor = title.lower().replace(' ', '-').replace('/', '-')
                        job_url = f"{self.url}#{job_anchor}"
                        
                        job = JobData(
                            source_id=f"jones_tree_{title.lower().replace(' ', '_').replace('/', '_')}",
                            source_name="jones_tree",
                            title=title,
                            url=job_url,
                            employer=self.employer_name,
                            category=self.category,
                            location="Salyer, CA",  # Based in Salyer and Eureka
                            salary_text=salary,
                            job_type="Seasonal" if "Seasonal" in title else "Full-time",
                        )
                        if self.validate_job(job):
                            jobs.append(job)
            
            # If pattern matching didn't work, try finding job sections
            if not jobs:
                # Look for "Now Hiring" section and job listings
                for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                    text = heading.get_text(strip=True)
                    
                    # Check for job titles with salary
                    salary_match = re.search(r'\$[\d\.\-]+/hr', text)
                    if salary_match:
                        # Extract title (everything before the salary)
                        title = re.sub(r'\$[\d\.\-]+/hr', '', text).strip().rstrip(':')
                        if title and len(title) > 3:
                            # Create unique URL with anchor
                            job_anchor = title.lower().replace(' ', '-')[:50]
                            job_url = f"{self.url}#{job_anchor}"
                            
                            job = JobData(
                                source_id=f"jones_tree_{title.lower().replace(' ', '_')[:50]}",
                                source_name="jones_tree",
                                title=title,
                                url=job_url,
                                employer=self.employer_name,
                                category=self.category,
                                location="Salyer, CA",
                                salary_text=salary_match.group(0),
                                job_type="Seasonal" if "Seasonal" in title else "Full-time",
                            )
                            if self.validate_job(job):
                                jobs.append(job)
            
        except Exception as e:
            self.logger.error(f"Error fetching {self.employer_name}: {e}")
        
        # Enrich jobs with parsed salary and experience
        self.enrich_jobs(jobs)
        
        self.logger.info(f"  Found {len(jobs)} jobs from {self.employer_name}")
        return jobs
