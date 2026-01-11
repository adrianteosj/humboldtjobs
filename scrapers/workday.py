"""
Workday CXS API Scraper - Generic scraper for Workday-powered career sites.
Works for Open Door Community Health and many national chains.
"""
import requests
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper, JobData
from config import USER_AGENT


class WorkdayScraper(BaseScraper):
    """
    Generic Workday CXS API scraper.
    Works for any employer using Workday's job posting system.
    """
    
    def __init__(
        self, 
        name: str,
        tenant: str, 
        dc: str, 
        site_code: str,
        employer_name: str,
        location_filter: Optional[List[str]] = None,
        default_location: str = "Humboldt County, CA",
        fetch_details: bool = False
    ):
        super().__init__(name)
        self.tenant = tenant
        self.dc = dc
        self.site_code = site_code
        self.employer_name = employer_name
        self.location_filter = location_filter
        self.default_location = default_location
        self.fetch_details = fetch_details  # Whether to fetch individual job details for salary
        
        self.base_url = f"https://{tenant}.wd{dc}.myworkdayjobs.com"
        self.api_path = f"/wday/cxs/{tenant}/{site_code}"
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': USER_AGENT
        })
    
    def scrape(self) -> List[JobData]:
        """Scrape all jobs from Workday API"""
        self.logger.info(f"Scraping {self.employer_name} via Workday API...")
        
        all_jobs = []
        offset = 0
        limit = 20  # Workday default page size
        
        while True:
            try:
                jobs_batch, total = self._fetch_jobs_page(offset, limit)
                
                if not jobs_batch:
                    break
                
                # Filter by location if specified
                if self.location_filter:
                    jobs_batch = self._filter_by_location(jobs_batch)
                
                all_jobs.extend(jobs_batch)
                self.logger.info(f"  Fetched {len(jobs_batch)} jobs (offset {offset})")
                
                # Check if we've fetched all jobs
                if offset + limit >= total:
                    break
                
                offset += limit
                self.delay()
                
            except Exception as e:
                self.logger.error(f"Error fetching jobs at offset {offset}: {e}")
                break
        
        # Convert to JobData objects
        job_data_list = []
        for job in all_jobs:
            job_data = self._parse_job(job)
            if job_data and self.validate_job(job_data):
                job_data_list.append(job_data)
        
        self.logger.info(f"  Found {len(job_data_list)} jobs from {self.employer_name}")
        return job_data_list
    
    def _fetch_jobs_page(self, offset: int, limit: int) -> tuple:
        """Fetch a page of jobs from Workday API"""
        url = f"{self.base_url}{self.api_path}/jobs"
        
        payload = {
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": ""
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        jobs = data.get('jobPostings', [])
        total = data.get('total', 0)
        
        return jobs, total
    
    def _fetch_job_details(self, external_path: str) -> Optional[Dict]:
        """Fetch individual job details to get salary and description"""
        try:
            url = f"{self.base_url}{self.api_path}{external_path}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json().get('jobPostingInfo', {})
        except Exception as e:
            self.logger.warning(f"Error fetching job details: {e}")
            return None
    
    def _extract_salary_from_description(self, description_html: str) -> Optional[str]:
        """
        Extract salary/compensation from job description HTML.
        
        Handles multiple formats including:
        - Simple range: "Compensation Range: $27.00-$31.35"
        - Role-based ranges: "MA I - $27.00 to $31.35", "Physician: $234,635.20 - $294,891.20"
        - Single base wages: "RN I: $42.00"
        - Year-based: "1st year $98,420.40; 2nd year $113,823.84"
        - Multi-line: "Physician:" on one line, "$X - $Y" on the next
        """
        if not description_html:
            return None
        
        soup = BeautifulSoup(description_html, 'html.parser')
        text = soup.get_text(separator='\n')
        
        # ============================================================
        # 1. First, try to find "Compensation Range:" pattern (simplest)
        # ============================================================
        range_match = re.search(
            r'(?:compensation\s+range|salary\s+range|pay\s+range)\s*:\s*\$?([\d,]+(?:\.\d{2})?)\s*[-–]\s*\$?([\d,]+(?:\.\d{2})?)',
            text, re.IGNORECASE
        )
        if range_match:
            low, high = range_match.groups()
            # Filter out $0.00 salaries
            try:
                low_val = float(low.replace(',', ''))
                high_val = float(high.replace(',', ''))
                if low_val == 0 and high_val == 0:
                    pass  # Skip and continue to other patterns
                elif low_val < 500:  # Likely hourly
                    return f"${low} - ${high}/hr"
                else:
                    return f"${low} - ${high}/yr"
            except:
                return f"${low} - ${high}"
        
        # ============================================================
        # 2. Look for year-based salaries (for residents)
        # "1st year $98,420.40; 2nd year $113,823.84"
        # ============================================================
        year_match = re.search(
            r'(?:1st|first)\s+year\s+\$?([\d,]+(?:\.\d{2})?)\s*;?\s*(?:2nd|second)\s+year\s+\$?([\d,]+(?:\.\d{2})?)',
            text, re.IGNORECASE
        )
        if year_match:
            year1, year2 = year_match.groups()
            return f"Year 1: ${year1} | Year 2: ${year2}"
        
        # ============================================================
        # 3. Extract role-based salary lines
        # ============================================================
        salary_entries = []
        lines = text.split('\n')
        
        # Track pending role (for multi-line patterns like "Physician:" on one line, salary on next)
        pending_role = None
        in_compensation_section = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) > 100:  # Skip empty or very long lines
                continue
            
            # Check if we're entering compensation section
            if 'compensation' in line.lower():
                in_compensation_section = True
            
            # Check if we're leaving compensation section
            if in_compensation_section and ('essential duties' in line.lower() or 'responsibilities' in line.lower()):
                in_compensation_section = False
                break
            
            # Pattern: "Role Name - $X to $Y" (MA Trainee - $24.00 to $27.87)
            role_range_to = re.match(
                r'^([A-Za-z\s]+(?:I{1,3}|Trainee)?)\s*[-–]\s*\$([\d,]+(?:\.\d{2})?)\s+to\s+\$([\d,]+(?:\.\d{2})?)',
                line, re.IGNORECASE
            )
            if role_range_to:
                role, low, high = role_range_to.groups()
                role = role.strip()
                # Skip if role is too generic or salary is $0
                if role.lower() not in ['compensation', 'salary', 'pay']:
                    try:
                        if float(low.replace(',', '')) > 0:
                            salary_entries.append({
                                'role': role,
                                'low': low,
                                'high': high,
                                'type': 'range'
                            })
                    except:
                        pass
                pending_role = None
                continue
            
            # Pattern: "Role Name: $X - $Y" or "Role Name: $X to $Y" (Physician: $234,635.20 - $294,891.20, APC: $X - $Y)
            role_range_dash = re.match(
                r'^([A-Za-z/\s]+(?:I{1,3})?)\s*:\s*\$([\d,]+(?:\.\d{2})?)\s*(?:[-–]|to)\s*\$([\d,]+(?:\.\d{2})?)',
                line, re.IGNORECASE
            )
            if role_range_dash:
                role, low, high = role_range_dash.groups()
                role = role.strip()
                # Skip if role is just "Compensation" or similar, or salary is $0
                if role.lower() not in ['compensation', 'compensation range', 'salary', 'pay', 'salary range']:
                    try:
                        if float(low.replace(',', '')) > 0:
                            salary_entries.append({
                                'role': role,
                                'low': low,
                                'high': high,
                                'type': 'range'
                            })
                    except:
                        pass
                pending_role = None
                continue
            
            # Pattern: "Role Name:" alone on a line (pending for next line's salary)
            role_alone = re.match(r'^([A-Za-z/\s]+(?:I{1,3})?)\s*:?\s*$', line)
            if role_alone and in_compensation_section:
                potential_role = role_alone.group(1).strip()
                if potential_role.lower() not in ['compensation', 'salary', 'pay', '']:
                    pending_role = potential_role
                continue
            
            # Pattern: Salary range alone "$X - $Y" or "$X to $Y" (following a role on previous line)
            salary_alone = re.match(r'^\$([\d,]+(?:\.\d{2})?)\s*(?:[-–]|to)\s*\$([\d,]+(?:\.\d{2})?)$', line)
            if salary_alone:
                low, high = salary_alone.groups()
                try:
                    if float(low.replace(',', '')) > 0:
                        if pending_role:
                            salary_entries.append({
                                'role': pending_role,
                                'low': low,
                                'high': high,
                                'type': 'range'
                            })
                        elif in_compensation_section and not salary_entries:
                            # First salary after COMPENSATION: without explicit role
                            salary_entries.append({
                                'role': None,
                                'low': low,
                                'high': high,
                                'type': 'range'
                            })
                except:
                    pass
                pending_role = None
                continue
            
            # Pattern: "Role Name: $X" single wage (RN I: $42.00)
            single_wage = re.match(
                r'^([A-Za-z\s]+(?:I{1,3})?)\s*:\s*\$([\d,]+(?:\.\d{2})?)$',
                line, re.IGNORECASE
            )
            if single_wage:
                role, wage = single_wage.groups()
                role = role.strip()
                try:
                    wage_val = float(wage.replace(',', ''))
                    # Only capture if it looks like a reasonable wage
                    if 15 <= wage_val <= 500:
                        salary_entries.append({
                            'role': role,
                            'wage': wage,
                            'type': 'single'
                        })
                except:
                    pass
                pending_role = None
                continue
            
            # Reset pending role if line doesn't match any pattern
            if not line.startswith('$'):
                pending_role = None
        
        # ============================================================
        # 4. Format salary entries for display
        # ============================================================
        if salary_entries:
            # Limit to 3 most relevant entries to keep display manageable
            entries_to_show = salary_entries[:3]
            
            formatted = []
            for entry in entries_to_show:
                role_prefix = f"{entry['role']}: " if entry.get('role') else ""
                
                if entry['type'] == 'range':
                    try:
                        low_val = float(entry['low'].replace(',', ''))
                        # Determine if hourly or annual
                        if low_val < 500:
                            formatted.append(f"{role_prefix}${entry['low']} - ${entry['high']}/hr")
                        else:
                            formatted.append(f"{role_prefix}${entry['low']} - ${entry['high']}/yr")
                    except:
                        formatted.append(f"{role_prefix}${entry['low']} - ${entry['high']}")
                else:  # single
                    formatted.append(f"{role_prefix}${entry['wage']}/hr")
            
            if formatted:
                return ' | '.join(formatted)
        
        # ============================================================
        # 5. Fallback: Simple compensation match
        # ============================================================
        simple_match = re.search(
            r'(?:compensation|salary)[:\s]*\$?([\d,]+(?:\.\d{2})?)\s*(?:to|-)\s*\$?([\d,]+(?:\.\d{2})?)',
            text, re.IGNORECASE
        )
        if simple_match:
            low, high = simple_match.groups()
            try:
                low_val = float(low.replace(',', ''))
                high_val = float(high.replace(',', ''))
                if low_val == 0 and high_val == 0:
                    return None  # Skip $0 salaries
                if low_val < 500:
                    return f"${low} - ${high}/hr"
                else:
                    return f"${low} - ${high}/yr"
            except:
                return f"${low} - ${high}"
        
        return None
    
    def _filter_by_location(self, jobs: List[Dict]) -> List[Dict]:
        """Filter jobs by location keywords"""
        filtered = []
        for job in jobs:
            location_text = job.get('locationsText', '').lower()
            # Check if any location filter matches
            if any(loc.lower() in location_text for loc in self.location_filter):
                filtered.append(job)
        return filtered
    
    def _parse_job(self, job_data: Dict[str, Any]) -> Optional[JobData]:
        """Parse Workday job posting into JobData"""
        try:
            title = job_data.get('title', '').strip()
            if not title:
                return None
            
            # Build job URL - use public path, not API path
            external_path = job_data.get('externalPath', '')
            # Public URL format: https://tenant.wdXXX.myworkdayjobs.com/en-US/site_code/job/path
            url = f"{self.base_url}/en-US/{self.site_code}{external_path}"
            
            # Extract job ID from path
            job_id = job_data.get('bulletFields', [{}])[0] if job_data.get('bulletFields') else ''
            if not job_id:
                # Try to extract from external path
                match = re.search(r'/job/([^/]+)', external_path)
                job_id = match.group(1) if match else external_path
            
            # Location
            location = job_data.get('locationsText', self.default_location)
            
            # Posted date
            posted_date = None
            posted_on = job_data.get('postedOn')
            if posted_on:
                try:
                    posted_date = date_parser.parse(posted_on)
                except:
                    pass
            
            # Job type - try from list data first, then from details
            job_type = job_data.get('timeType')  # Often available in list
            if not job_type:
                bullet_fields = job_data.get('bulletFields', [])
                for field in bullet_fields:
                    if isinstance(field, str):
                        if 'full' in field.lower() and 'time' in field.lower():
                            job_type = "Full-time"
                        elif 'part' in field.lower() and 'time' in field.lower():
                            job_type = "Part-time"
                        elif 'temporary' in field.lower():
                            job_type = "Temporary"
            
            # Category inference from title
            category = self._infer_category(title)
            
            # Fetch job details to get salary and description
            salary_text = None
            description = None
            
            if self.fetch_details:
                job_details = self._fetch_job_details(external_path)
                if job_details:
                    # Get job description
                    description_html = job_details.get('jobDescription', '')
                    if description_html:
                        # Extract salary from description
                        salary_text = self._extract_salary_from_description(description_html)
                        
                        # Clean description for storage (first 500 chars)
                        soup = BeautifulSoup(description_html, 'html.parser')
                        description = soup.get_text()[:500].strip()
                    
                    # Use timeType from details if not already set
                    if not job_type and job_details.get('timeType'):
                        job_type = job_details.get('timeType')
                    
                    # Small delay to be polite (brief, since we make many requests)
                    import time
                    time.sleep(0.2)
            
            return JobData(
                source_id=f"workday_{self.name}_{job_id}",
                source_name=f"workday_{self.name}",
                title=title,
                url=url,
                employer=self.employer_name,
                category=category,
                location=location,
                job_type=job_type,
                posted_date=posted_date,
                salary_text=salary_text,
                description=description,
            )
            
        except Exception as e:
            self.logger.warning(f"Error parsing job: {e}")
            return None
    
    def _infer_category(self, title: str) -> str:
        """Infer job category from title"""
        title_lower = title.lower()
        
        if any(kw in title_lower for kw in ['nurse', 'rn', 'lpn', 'medical', 'clinical', 'doctor', 'physician', 'dentist', 'dental', 'health', 'therapist', 'pharmacy', 'pharmacist']):
            return "Healthcare"
        elif any(kw in title_lower for kw in ['admin', 'assistant', 'clerk', 'receptionist', 'office', 'secretary']):
            return "Administrative"
        elif any(kw in title_lower for kw in ['it ', 'software', 'developer', 'engineer', 'tech', 'analyst']):
            return "Technical"
        elif any(kw in title_lower for kw in ['maintenance', 'custodian', 'facilities', 'janitor', 'groundskeeper']):
            return "Maintenance"
        elif any(kw in title_lower for kw in ['teacher', 'instructor', 'professor', 'education']):
            return "Education"
        
        return "Healthcare"  # Default for healthcare employers


class OpenDoorHealthScraper(WorkdayScraper):
    """Scraper for Open Door Community Health Centers"""
    
    def __init__(self):
        super().__init__(
            name="open_door",
            tenant="opendoorhealth",
            dc="503",
            site_code="ODCHC",
            employer_name="Open Door Community Health",
            location_filter=None,  # All jobs are local
            default_location="Humboldt County, CA",
            fetch_details=True  # Fetch details to get salary info
        )


# Humboldt County location filters for national chains
HUMBOLDT_LOCATIONS = [
    'eureka', 'arcata', 'fortuna', 'mckinleyville', 
    'humboldt', '95501', '95521', '95540', '95519'
]
