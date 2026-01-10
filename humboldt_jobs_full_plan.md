# Humboldt County Local Jobs Aggregator - Complete Source Plan

**Date:** January 9, 2026  
**Project:** Python-based job aggregator with SQLite/PostgreSQL, modular scraper architecture  
**Goal:** Aggregate all local job postings for potential API/newsletter monetization

---

## Executive Summary

| Tier | Focus | Sources | Est. Jobs | Dev Time | Cost |
|------|-------|---------|-----------|----------|------|
| **Tier 1** | Government, Media, University | 10+ | 150-280 | 2-3 days | $0 |
| **Tier 2** | Healthcare Facilities | 25+ | 300-500 | 3-4 weeks | $0 |
| **Tier 3A** | Local Major Employers | 35+ | 100-250 | 1-2 weeks | $0 |
| **Tier 3B** | National Chains & Retail | 30+ | 100-200 | 1-2 weeks | $0 |
| **Total** | | **100+ employers** | **650-1,230** | **~8-9 weeks** | **$0** |

*Tier 3B can optionally use Google Jobs API at ~$0.003/request for easier aggregation

---

# TIER 1: CORE LOCAL SOURCES

## Government - NEOGOV RSS Feeds ⭐ PRIORITY

| Agency | RSS Feed URL | Est. Jobs |
|--------|--------------|-----------|
| County of Humboldt | `https://www.governmentjobs.com/careers/humboldtcountyca/rss` | 50-100 |
| City of Eureka | `https://www.governmentjobs.com/careers/eureka/rss` | 10-20 |
| City of Arcata | `https://www.governmentjobs.com/careers/arcataca/rss` | 5-15 |
| City of Fortuna | `https://www.governmentjobs.com/careers/fortunaca/rss` | 5-10 |
| Yurok Tribe | `https://www.governmentjobs.com/careers/yuroktribe/rss` | 10-20 |

**Method:** RSS parsing with `feedparser` — 4 hours development

## Other Government
| Source | Platform | Est. Jobs |
|--------|----------|-----------|
| Wiyot Tribe | RSS/HTML | 3-8 |
| Rio Dell | ProudCity | 1-5 |
| Humboldt County Office of Education | EdJoin | 20-40 |

## Local Media Job Boards
| Source | URL | Platform | Est. Jobs |
|--------|-----|----------|-----------|
| Lost Coast Outpost | lostcoastoutpost.com/jobs/ | WordPress | 5-15 |
| North Coast Journal | northcoastjournal.com/classifieds | Custom | 15-30 |

## Higher Education
| Source | Platform | Est. Jobs |
|--------|----------|-----------|
| Cal Poly Humboldt | PageUp | 100+ |
| College of the Redwoods | NEOGOV/Custom | 20-40 |

**Tier 1 Total: ~150-280 jobs, 2-3 days development**

---

# TIER 2: HEALTHCARE FACILITIES

## Hospitals
| # | Facility | Platform | Est. Jobs |
|---|----------|----------|-----------|
| 1 | Providence St. Joseph (Eureka) | TalentBrew | 50-100 |
| 2 | Mad River Community Hospital (Arcata) | WordPress/Indeed | 25-30 |
| 3 | Redwood Memorial (Fortuna) | TalentBrew | 15-25 |
| 4 | SoHum Health / Jerold Phelps (Garberville) | Paylocity | 10-20 |

## FQHCs (Federally Qualified Health Centers)
| # | Facility | Platform | Est. Jobs |
|---|----------|----------|-----------|
| 5 | Open Door Community Health | Workday CXS API | 50-80 |
| 6 | Redwoods Rural Health Center (Redway) | Wix | 10-15 |
| 7 | Southern Humboldt Community Clinic | Paylocity | 5-10 |

## Tribal Health
| # | Facility | Platform | Est. Jobs |
|---|----------|----------|-----------|
| 8 | United Indian Health Services | ADP | 30-50 |
| 9 | K'ima:w Medical Center (Hoopa) | Custom | 15-25 |
| 10 | Two Feathers Native American Family Services | Custom | 5-10 |

## Other Healthcare
| # | Facility | Platform | Est. Jobs |
|---|----------|----------|-----------|
| 11 | Hospice of Humboldt | Custom | 10-15 |
| 12 | Humboldt Senior Resource Center | Custom | 15-20 |
| 13-15 | Skilled Nursing Facilities | Various | 25-50 |
| 16 | Fresenius Kidney Care | Corporate | 5-10 |
| 17 | RCAA (oral health, community) | Custom | 10-20 |
| 18+ | Private practices | Various | 15-30 |

**Tier 2 Total: ~300-500 jobs, 3-4 weeks development**

---

# TIER 3: MAJOR LOCAL EMPLOYERS & NATIONAL CHAINS

## 3A: LOCAL MAJOR EMPLOYERS (NOT YET COVERED)

### Timber & Forest Products ⭐ MAJOR INDUSTRY
| Employer | Description | Est. Employees | Est. Jobs | Platform |
|----------|-------------|----------------|-----------|----------|
| **Green Diamond Resource Co** | Largest private landowner (360,000+ acres), timber | 500+ | 10-25 | Custom/Workday |
| **Humboldt Redwood Company** | Major timberland (former Pacific Lumber) | 200+ | 5-15 | Custom |
| **Sierra Pacific Industries** | Largest US private landowner, lumber | 100+ local | 5-15 | Custom |
| **Schmidbauer Lumber / North Fork Lumber** | Local sawmill, Korbel | 100+ | 5-15 | Custom |
| **Humboldt Sawmill Company** | Scotia, biomass power | 100+ | 5-15 | Custom |

### Construction & Engineering
| Employer | Description | Est. Employees | Est. Jobs | Platform |
|----------|-------------|----------------|-----------|----------|
| **Mercer-Fraser Company** | Heavy civil contractor since 1870, Fortuna | 200+ | 10-20 | Custom |
| **LACO Associates** | Engineering, surveying, planning | 50+ | 3-8 | Custom |
| **Wahlund Construction** | General contractor | 50+ | 3-8 | Custom |
| **GR Sundberg** | Commercial construction | 30+ | 2-5 | Custom |

### Energy & Utilities
| Employer | Description | Est. Employees | Est. Jobs | Platform |
|----------|-------------|----------------|-----------|----------|
| **Redwood Coast Energy Authority** | Community Choice Energy | 50+ | 3-8 | Custom |
| **PG&E** | Grid maintenance, local operations | 50+ | 3-8 | Workday |
| **Renner Petroleum (Valley Pacific)** | Fuel distribution | 50+ | 2-5 | Custom |

### Casinos & Gaming 🎰
| Employer | Description | Est. Employees | Est. Jobs | Platform |
|----------|-------------|----------------|-----------|----------|
| **Blue Lake Casino & Hotel** | Blue Lake Rancheria | 300+ | 15-30 | Custom |
| **Bear River Casino Resort** | Bear River Band, Loleta | 250+ | 10-25 | Custom |
| **Cher-Ae Heights Casino** | Trinidad Rancheria | 100+ | 5-15 | Custom |

### Food, Agriculture & Dairy 🥛
| Employer | Description | Est. Employees | Est. Jobs | Platform |
|----------|-------------|----------------|-----------|----------|
| **Humboldt Creamery** | Dairy products, Fernbridge | 100+ | 3-8 | Custom |
| **Cypress Grove Chevre** | Humboldt Fog cheese | 75+ | 3-8 | Custom |
| **Alexandre Family Farm** | Organic dairy | 50+ | 2-5 | Custom |
| **Driscoll's** | Berry operations (leased land) | 50+ | 2-5 | Workday |

### Seafood & Fishing 🐟
| Employer | Description | Est. Employees | Est. Jobs | Platform |
|----------|-------------|----------------|-----------|----------|
| **Pacific Choice Seafood** | Seafood processing, Eureka | 100+ | 5-15 | Custom |
| **Caito Fisheries** | Commercial fishing | 30+ | 2-5 | Custom |

### Local Grocery & Retail
| Employer | Description | Locations | Est. Jobs | Platform |
|----------|-------------|-----------|-----------|----------|
| **North Coast Co-op** | Member-owned natural foods | Arcata, Eureka | 5-15 | Custom |
| **Eureka Natural Foods** | Natural/organic grocery | Eureka, McKinleyville | 5-10 | Custom |
| **Murphy's Markets** | Local grocery chain | Multiple | 5-10 | Custom |
| **Pierson Building Center** | Lumber/hardware | Eureka | 3-8 | Custom |
| **Shafer's Ace Hardware** | Hardware stores | Multiple | 3-8 | Custom |

### Nonprofits & Social Services
| Employer | Description | Est. Employees | Est. Jobs | Platform |
|----------|-------------|----------------|-----------|----------|
| **Changing Tides Family Services** | Childcare, mental health | 100+ | 5-15 | Custom |
| **Boys & Girls Club of the Redwoods** | Youth services | 30+ | 2-5 | Custom |
| **Food for People** | Food bank | 30+ | 2-5 | Custom |
| **Arcata House Partnership** | Homeless services | 30+ | 2-5 | Custom |

### Manufacturing & Other
| Employer | Description | Est. Jobs | Platform |
|----------|-------------|-----------|----------|
| **C. Crane Company** | Electronics manufacturer | 2-5 | Custom |
| **Humboldt Moving & Storage** | Moving services | 2-5 | Custom |
| **Kokatat** | Paddlesports apparel, Arcata | 3-8 | Custom |
| **Lost Coast Brewery** | Craft brewery | 2-5 | Custom |

**Tier 3A Subtotal: ~100-250 jobs from 35+ local employers**

---

## 3B: NATIONAL CHAINS & RETAIL

## Grocery & Retail

| Employer | Location(s) | Platform | Est. Jobs |
|----------|-------------|----------|-----------|
| **Walmart** | Eureka (Bayshore Mall) | Workday | 15-30 |
| **Target** | Eureka | Workday | 10-20 |
| **Costco** | Eureka | Custom ATS | 10-20 |
| **Safeway/Albertsons** | Arcata, Eureka, Fortuna | Workday | 15-25 |
| **WinCo Foods** | Eureka | Custom | 5-15 |
| **Grocery Outlet** | McKinleyville, Eureka | Custom | 5-10 |
| **Dollar General/Tree** | Multiple | Corporate | 3-8 |

### Workday API Pattern (Walmart, Target, Safeway)
```python
# Walmart example - same pattern as Open Door
walmart = WorkdayScraper("wd5", "walmart", "WalmartExternal")
jobs = walmart.get_all_jobs()
# Filter by location contains "Eureka" or "Humboldt"
```

## Pharmacy
| Employer | Locations | Platform | Est. Jobs |
|----------|-----------|----------|-----------|
| **Walgreens** | Multiple | Workday | 3-8 |
| **CVS** | Multiple | Workday | 3-8 |
| **Rite Aid** | Multiple | Workday | 2-5 |

## Home Improvement
| Employer | Location | Platform | Est. Jobs |
|----------|----------|----------|-----------|
| **Lowe's** | Eureka | Workday | 5-15 |
| **Home Depot** | Eureka (if present) | Taleo | 5-15 |
| **Harbor Freight** | Eureka | Custom | 2-5 |

## Fast Food & Restaurants
| Employer | Locations | Platform | Est. Jobs |
|----------|-----------|----------|-----------|
| **Starbucks** | 5+ locations | Eightfold | 5-15 |
| **McDonald's** | Multiple | McHire | 5-10 |
| **Taco Bell** | Multiple | Workday | 3-8 |
| **Subway** | Multiple | Custom | 2-5 |
| **Denny's** | Eureka | Corporate | 2-5 |
| **Dutch Bros** | Multiple | Workday | 3-8 |

## Banks & Financial
| Employer | Locations | Platform | Est. Jobs |
|----------|-----------|----------|-----------|
| **Wells Fargo** | Multiple | Workday | 2-5 |
| **Bank of America** | Multiple | Workday | 2-5 |
| **US Bank** | Multiple | Workday | 1-3 |
| **Umpqua Bank** | Multiple | iCIMS | 1-3 |

## Hotels & Hospitality
| Employer | Location | Platform | Est. Jobs |
|----------|----------|----------|-----------|
| **Holiday Inn** | Eureka | IHG Careers | 2-5 |
| **Best Western** | Multiple | Corporate | 2-5 |
| **Red Lion** | Eureka | Corporate | 2-5 |
| **Hampton Inn** | Eureka | Hilton Careers | 2-5 |

## Auto & Gas
| Employer | Locations | Platform | Est. Jobs |
|----------|-----------|----------|-----------|
| **O'Reilly Auto** | Multiple | Workday | 2-5 |
| **AutoZone** | Multiple | Custom | 2-5 |
| **Chevron/Shell/76** | Multiple | Various | 2-5 |

## Other National Chains
| Employer | Category | Est. Jobs |
|----------|----------|-----------|
| **FedEx/UPS** | Shipping | 3-8 |
| **Amazon (DSP)** | Delivery | 5-10 |
| **AT&T/Verizon** | Telecom | 2-5 |
| **Staples** | Office | 2-5 |

**Tier 3 Total: ~100-200 jobs, 1-2 weeks development**

---

# TIER 3 SCRAPING STRATEGIES

## Tier 3A: Local Employers Strategy

Most local employers have simple websites. Strategy by type:

### Timber Companies
Most timber companies have minimal web presence. Check:
- `greendiamond.com/careers` 
- `spi-ind.com/careers` (Sierra Pacific)
- Contact HR directly for job feeds

### Casinos (Priority - High Volume)
Tribal casinos are significant employers with dedicated career pages:
```python
# Blue Lake Casino
# Check: bluelakecasino.com/careers or similar
# Bear River Casino  
# Check: bearrivercasino.com/careers
```

### Construction/Engineering
- Mercer-Fraser: mercerfraserco.com (check for careers section)
- LACO Associates: lacoassociates.com/careers

### Food/Agriculture
Many use Indeed or simple contact forms. Consider:
- Direct scraping of career pages
- Indeed location-filtered search as fallback

### Local Retail
Small employers often post to:
- Lost Coast Outpost jobs board
- North Coast Journal classifieds
- Their own websites (simple HTML)

---

## Tier 3B: National Chains Strategy

## Option A: Google Jobs API (Recommended for Tier 3)

The Google Jobs API aggregates most national chains automatically. Filter by location.

```python
# Conceptual - actual implementation varies
from serpapi import GoogleSearch

params = {
    "engine": "google_jobs",
    "q": "jobs",
    "location": "Eureka, California",
    "chips": "date_posted:week"
}
search = GoogleSearch(params)
results = search.get_dict()
```

**Pros:** 
- One API covers 30+ chains
- Pre-aggregated, deduplicated
- Fresh data

**Cons:**
- Cost: ~$0.003/request (SerpAPI) or free tier limits
- Less control over sources

## Option B: Workday API Pattern (DIY)

Many chains use Workday. Same pattern as Open Door:

| Chain | Tenant | DC | Site Code |
|-------|--------|-----|-----------|
| Walmart | walmart | wd5 | WalmartExternal |
| Target | target | wd5 | targetcareers |
| Safeway | albertsons | wd5 | AlbertsonsCompanies |
| Walgreens | wba | wd5 | External |
| CVS | cvshealth | wd1 | CVSHealth |
| Starbucks | starbucks | wd5 | StarbucksExternal |
| Lowe's | lowes | wd5 | LOWES |

**Process:**
1. Query corporate endpoint
2. Filter results by location (Eureka, Arcata, Humboldt, 95501, 95521, etc.)
3. Store locally, dedupe

## Option C: Indeed/LinkedIn Scraping (Not Recommended)

- Terms of Service issues
- Rate limiting
- Data quality concerns
- Better to use official APIs or direct employer sites

---

# PLATFORM SUMMARY (ALL TIERS)

| Platform | Count | Method | Difficulty |
|----------|-------|--------|------------|
| NEOGOV | 6 | RSS feeds | Very Easy |
| WordPress/Custom HTML | 35+ | BeautifulSoup | Easy |
| Wix | 1 | HTML parsing | Very Easy |
| PageUp | 1 | API/HTML | Moderate |
| Workday | 15+ | CXS API | Moderate |
| ADP | 1 | API/HTML | Moderate |
| Paylocity | 2 | API investigation | Moderate |
| TalentBrew | 2 | JSON-LD | Moderate |
| Taleo | 2 | HTML/Playwright | Moderate |
| iCIMS | 2 | API | Moderate |
| Tribal Custom | 3 | HTML parsing | Easy-Moderate |
| Other Corporate | 15+ | Various | Varies |

**Key Local Employer Platforms:**
- Most timber companies: Minimal web presence, may need manual monitoring
- Casinos: Custom career pages, HTML scraping
- Construction: Simple HTML career pages
- Local retail: Often post to local job boards (LCO, NCJ)

---

# IMPLEMENTATION TIMELINE

| Week | Phase | Focus | Sources Added | Cumulative Jobs |
|------|-------|-------|---------------|-----------------|
| 1 | Tier 1 | Government, Media, University | 10 | 150-280 |
| 2 | Tier 2A | Easy Healthcare (HTML sites) | 8 | 235-405 |
| 3 | Tier 2B | API Healthcare (Workday, ADP) | 5 | 330-560 |
| 4 | Tier 2C | Complex Healthcare | 7 | 410-720 |
| 5 | Tier 3A | Local Major Employers | 20 | 510-970 |
| 6 | Tier 3A cont. | Casinos, Timber, Construction | 15 | 560-1,050 |
| 7 | Tier 3B | Major Retail (Workday chains) | 15 | 620-1,150 |
| 8 | Tier 3B cont. | Remaining National Chains | 15 | 650-1,230 |
| 9 | Polish | Deduplication, monitoring | — | 650-1,230 |

---

# WORKDAY SCRAPER (Reusable for Tiers 2 & 3)

```python
import requests
import time
from typing import List, Dict

class WorkdayScraper:
    """Generic Workday CXS API scraper - works for ANY Workday employer"""
    
    def __init__(self, tenant: str, dc: str, site_code: str, 
                 location_filter: List[str] = None):
        self.base = f"https://{tenant}.wd{dc}.myworkdayjobs.com"
        self.api = f"/wday/cxs/{tenant}/{site_code}"
        self.location_filter = location_filter or []
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def get_all_jobs(self) -> List[Dict]:
        all_jobs = []
        offset = 0
        
        while True:
            url = f"{self.base}{self.api}/jobs"
            payload = {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""}
            data = self.session.post(url, json=payload).json()
            
            jobs = data.get('jobPostings', [])
            
            # Filter by location if specified
            if self.location_filter:
                jobs = [j for j in jobs if any(
                    loc.lower() in j.get('locationsText', '').lower() 
                    for loc in self.location_filter
                )]
            
            all_jobs.extend(jobs)
            
            if offset + 20 >= data.get('total', 0):
                break
            offset += 20
            time.sleep(0.5)
        
        return all_jobs


# Humboldt County location filters
HUMBOLDT_LOCATIONS = [
    'eureka', 'arcata', 'fortuna', 'mckinleyville', 
    'humboldt', '95501', '95521', '95540', '95519'
]

# Usage examples
scrapers = {
    'open_door': WorkdayScraper('opendoorhealth', '503', 'ODCHC'),
    'walmart': WorkdayScraper('walmart', '5', 'WalmartExternal', HUMBOLDT_LOCATIONS),
    'target': WorkdayScraper('target', '5', 'targetcareers', HUMBOLDT_LOCATIONS),
    'safeway': WorkdayScraper('albertsons', '5', 'AlbertsonsCompanies', HUMBOLDT_LOCATIONS),
    'starbucks': WorkdayScraper('starbucks', '5', 'StarbucksExternal', HUMBOLDT_LOCATIONS),
    'lowes': WorkdayScraper('lowes', '5', 'LOWES', HUMBOLDT_LOCATIONS),
}

# Run all scrapers
all_jobs = []
for name, scraper in scrapers.items():
    jobs = scraper.get_all_jobs()
    for job in jobs:
        job['source'] = name
    all_jobs.extend(jobs)
    print(f"{name}: {len(jobs)} jobs")
```

---

# DATABASE SCHEMA

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_tier INTEGER,              -- 1, 2, or 3
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    url TEXT NOT NULL UNIQUE,
    description TEXT,
    salary_min REAL,
    salary_max REAL,
    job_type TEXT,
    category TEXT,
    posted_date DATE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_jobs_source ON jobs(source_name);
CREATE INDEX idx_jobs_tier ON jobs(source_tier);
CREATE INDEX idx_jobs_category ON jobs(category);
CREATE INDEX idx_jobs_posted ON jobs(posted_date);
```

---

# COST ANALYSIS

| Item | Option A (DIY) | Option B (w/ Google Jobs API) |
|------|----------------|-------------------------------|
| Tier 1 Development | $0 | $0 |
| Tier 2 Development | $0 | $0 |
| Tier 3 Development | $0 | $0 |
| Google Jobs API | — | ~$50-100/mo (1000-3000 req/day) |
| Hosting | ~$5-20/mo | ~$5-20/mo |
| **Total Monthly** | **$5-20** | **$55-120** |

**Recommendation:** Start with DIY (Option A) for all tiers. Consider Google Jobs API later if Tier 3 maintenance becomes burdensome.

---

# NEXT STEPS

1. **Week 1:** Build Tier 1 scrapers (NEOGOV RSS, local media, university)
2. **Week 2:** Begin Tier 2A easy healthcare sources
3. **Week 3:** Implement Workday API scraper (Open Door + chain template)
4. **Week 4:** Complete Tier 2 healthcare
5. **Week 5-6:** Roll out Tier 3 using Workday pattern
6. **Week 7:** Deduplication, monitoring, alerting

---

# LOCAL EMPLOYERS - FUTURE PHASES

Consider adding these smaller employers in future phases:

- **Cannabis Industry:** Licensed dispensaries, cultivators, manufacturers
- **Professional Services:** Law firms, accounting firms, real estate brokerages
- **Tourism/Hospitality:** Tour operators, smaller hotels/B&Bs, fishing charters
- **Education (Private):** Private schools, tutoring centers
- **Auto Dealers:** Local car dealerships
- **Media:** Local radio stations (KHUM, KMUD), newspapers
- **Veterinary:** Animal hospitals, vet clinics
- **Dental:** Private dental practices (large employers in aggregate)

---

# APPENDIX: COMPLETE EMPLOYER DIRECTORY WITH CAREERS URLS

This is a comprehensive list of all employers covered in this plan with their careers/job openings pages.

## TIER 1: GOVERNMENT, MEDIA & EDUCATION

### Government Agencies (NEOGOV)
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| County of Humboldt | https://www.governmentjobs.com/careers/humboldtcountyca | NEOGOV |
| City of Eureka | https://www.governmentjobs.com/careers/eureka | NEOGOV |
| City of Arcata | https://www.governmentjobs.com/careers/arcataca | NEOGOV |
| City of Fortuna | https://www.governmentjobs.com/careers/fortunaca | NEOGOV |
| Yurok Tribe | https://www.governmentjobs.com/careers/yuroktribe | NEOGOV |
| Wiyot Tribe | https://www.wiyot.us/jobs | Custom |
| City of Rio Dell | https://cityofriodell.ca.gov/jobs | ProudCity |
| Humboldt County Office of Education | https://www.edjoin.org (search Humboldt) | EdJoin |

### Higher Education
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Cal Poly Humboldt | https://www.humboldt.edu/jobs | PageUp |
| College of the Redwoods | https://www.redwoods.edu/hr/employment | Custom |

### Local Media Job Boards
| Source | URL | Notes |
|--------|-----|-------|
| Lost Coast Outpost | https://lostcoastoutpost.com/jobs/ | WordPress |
| North Coast Journal | https://www.northcoastjournal.com/humboldt/EventSearch?narrowByDate=all-events&eventCategory=1087656 | Custom |

---

## TIER 2: HEALTHCARE

### Hospitals
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Providence St. Joseph Hospital | https://www.providence.jobs/eureka/new-jobs/ | TalentBrew |
| Mad River Community Hospital | https://www.madriverhospital.com/careers | WordPress |
| Redwood Memorial Hospital | https://www.providence.jobs/fortuna/new-jobs/ | TalentBrew |
| SoHum Health / Jerold Phelps Hospital | https://sohumhealth.org/careers/ | Paylocity |

### FQHCs (Federally Qualified Health Centers)
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Open Door Community Health Centers | https://opendoorhealth.wd503.myworkdayjobs.com/ODCHC | Workday |
| Redwoods Rural Health Center | https://rrhc.org/job-opportunities/ | Wix |
| Southern Humboldt Community Clinic | https://sohumhealth.org/careers/ | Paylocity |

### Tribal Health
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| United Indian Health Services | https://unitedindianhealthservices.org/jobs/ | ADP |
| K'ima:w Medical Center | https://www.kimaw.org/jobs | Custom |
| Two Feathers Native American Family Services | https://www.twofeathers-nafs.org/careers | Custom |

### Senior Care & Hospice
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Hospice of Humboldt | https://hospiceofhumboldt.org/join-our-team/ | Custom |
| Humboldt Senior Resource Center | https://humsenior.org/about/employment/ | Custom |
| Seaview Rehabilitation & Wellness | Indeed (search location) | Corporate |
| Eureka Rehabilitation & Wellness | Indeed (search location) | Corporate |

### Community Health & Nonprofits
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| RCAA (Redwood Community Action Agency) | https://rcaa.org/employment-opportunities/ | Custom |
| Changing Tides Family Services | https://changingtidesfs.org/careers/ | Custom |

---

## TIER 3A: LOCAL MAJOR EMPLOYERS

### Timber & Forest Products
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Green Diamond Resource Company | https://www.greendiamond.com/people/career-opportunities | Custom |
| Humboldt Redwood Company | https://hrcllc.com/careers/ | Custom |
| Sierra Pacific Industries | https://www.spi-ind.com/Careers | Custom |
| Schmidbauer Lumber / North Fork Lumber | Contact directly | N/A |
| Humboldt Sawmill Company | Contact directly | N/A |

### Construction & Engineering
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Mercer-Fraser Company | https://www.mercerfraserco.com/careers/ | Custom |
| LACO Associates | https://lacoassociates.com/careers/ | Custom |
| Wahlund Construction | Contact directly | N/A |
| GR Sundberg | Contact directly | N/A |

### Energy & Utilities
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Redwood Coast Energy Authority | https://redwoodenergy.org/about/careers/ | Custom |
| PG&E (local) | https://jobs.pge.com/ (filter by location) | Workday |
| Renner Petroleum (Valley Pacific) | https://valleypacific.com/careers/ | Custom |

### Casinos & Gaming
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Blue Lake Casino & Hotel | https://www.bluelakecasino.com/careers/ | Custom |
| Bear River Casino Resort | https://bearrivercasino.com/careers/ | Custom |
| Cher-Ae Heights Casino | https://cheraeheightscasino.com/careers/ | Custom |

### Food, Agriculture & Dairy
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Humboldt Creamery | Contact directly | N/A |
| Cypress Grove Chevre | https://www.cypressgrovecheese.com/about-us/careers/ | Custom |
| Alexandre Family Farm | Contact directly | N/A |
| Driscoll's | https://www.driscolls.com/careers | Workday |
| Pacific Choice Seafood | Contact directly | N/A |

### Local Grocery & Retail
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| North Coast Co-op | https://www.northcoast.coop/about_us/careers/ | Custom |
| Eureka Natural Foods | https://www.eurekanatural.com/careers/ | Custom |
| Murphy's Markets | Contact directly | N/A |
| Pierson Building Center | https://piersonbuildingcenter.com/employment/ | Custom |

### Nonprofits & Social Services
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Boys & Girls Club of the Redwoods | https://www.bgcredwoods.org/join-our-team | Custom |
| Food for People | https://foodforpeople.org/about-us/employment/ | Custom |
| Arcata House Partnership | https://arcatahouse.org/employment/ | Custom |

### Other Local
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Kokatat | https://kokatat.com/pages/careers | Custom |
| Lost Coast Brewery | Contact directly | N/A |
| C. Crane Company | Contact directly | N/A |

---

## TIER 3B: NATIONAL CHAINS

### Grocery & Retail (Workday)
| Employer | Careers URL | Platform | Workday Tenant |
|----------|-------------|----------|----------------|
| Walmart | https://careers.walmart.com/ | Workday | walmart.wd5 |
| Target | https://jobs.target.com/ | Workday | target.wd5 |
| Costco | https://www.costco.com/jobs.html | Custom | N/A |
| Safeway/Albertsons | https://www.albertsonscompanies.com/careers/ | Workday | albertsons.wd5 |
| WinCo Foods | https://www.wincofoods.com/careers | Custom | N/A |
| Grocery Outlet | https://groceryoutlet.com/careers | Custom | N/A |

### Pharmacy
| Employer | Careers URL | Platform | Workday Tenant |
|----------|-------------|----------|----------------|
| Walgreens | https://jobs.walgreens.com/ | Workday | wba.wd5 |
| CVS | https://jobs.cvshealth.com/ | Workday | cvshealth.wd1 |
| Rite Aid | https://careers.riteaid.com/ | Workday | riteaid.wd5 |

### Home Improvement
| Employer | Careers URL | Platform | Workday Tenant |
|----------|-------------|----------|----------------|
| Lowe's | https://corporate.lowes.com/careers | Workday | lowes.wd5 |
| Home Depot | https://careers.homedepot.com/ | Taleo | N/A |
| Harbor Freight | https://careers.harborfreight.com/ | Custom | N/A |

### Fast Food & Restaurants
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Starbucks | https://www.starbucks.com/careers/ | Eightfold |
| McDonald's | https://careers.mcdonalds.com/ | McHire |
| Taco Bell | https://www.tacobell.com/careers | Workday |
| Subway | https://www.subway.com/en-US/Careers | Custom |
| Dutch Bros | https://careers.dutchbros.com/ | Workday |
| Denny's | https://careers.dennys.com/ | Custom |

### Banks & Financial
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Wells Fargo | https://www.wellsfargojobs.com/ | Workday |
| Bank of America | https://careers.bankofamerica.com/ | Workday |
| US Bank | https://careers.usbank.com/ | Workday |
| Umpqua Bank | https://www.umpquabank.com/careers/ | iCIMS |

### Hotels & Hospitality
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| Holiday Inn (IHG) | https://careers.ihg.com/ | Workday |
| Best Western | https://www.bestwestern.com/en_US/about/careers.html | Custom |
| Hampton Inn (Hilton) | https://jobs.hilton.com/ | Workday |
| Red Lion | https://www.redlion.com/careers | Custom |

### Auto & Gas
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| O'Reilly Auto Parts | https://corporate.oreillyauto.com/careers | Workday |
| AutoZone | https://careers.autozone.com/ | Custom |
| NAPA Auto Parts | https://www.napaonline.com/en/careers | Custom |

### Shipping & Delivery
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| FedEx | https://careers.fedex.com/ | Workday |
| UPS | https://www.jobs-ups.com/ | Custom |
| Amazon (DSP) | https://www.amazondelivers.jobs/ | Custom |

### Other National
| Employer | Careers URL | Platform |
|----------|-------------|----------|
| AT&T | https://www.att.jobs/ | Workday |
| Verizon | https://www.verizon.com/about/careers | Workday |
| Staples | https://careers.staples.com/ | Workday |

---

## QUICK REFERENCE: WORKDAY API ENDPOINTS

For employers using Workday, use this pattern:
```
POST https://{tenant}.wd{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site-code}/jobs
```

| Employer | Full API URL |
|----------|--------------|
| Open Door Health | https://opendoorhealth.wd503.myworkdayjobs.com/wday/cxs/opendoorhealth/ODCHC/jobs |
| Walmart | https://walmart.wd5.myworkdayjobs.com/wday/cxs/walmart/WalmartExternal/jobs |
| Target | https://target.wd5.myworkdayjobs.com/wday/cxs/target/targetcareers/jobs |
| Safeway | https://albertsons.wd5.myworkdayjobs.com/wday/cxs/albertsons/AlbertsonsCompanies/jobs |
| Starbucks | https://starbucks.wd5.myworkdayjobs.com/wday/cxs/starbucks/StarbucksExternal/jobs |
| Lowe's | https://lowes.wd5.myworkdayjobs.com/wday/cxs/lowes/LOWES/jobs |
| CVS | https://cvshealth.wd1.myworkdayjobs.com/wday/cxs/cvshealth/CVSHealth/jobs |
| Walgreens | https://wba.wd5.myworkdayjobs.com/wday/cxs/wba/External/jobs |

---

## NOTES ON CAREERS PAGES

1. **"Contact directly"** means the employer doesn't have a public careers page — check Indeed/local job boards or contact HR
2. **Workday employers** can be scraped via the CXS API pattern shown above
3. **Filter by location** for national chains using zip codes: 95501 (Eureka), 95521 (Arcata), 95540 (Fortuna), 95519 (McKinleyville)
4. **Indeed fallback**: For any employer without a careers page, search `site:indeed.com "{employer name}" Humboldt County`
5. **Local job boards** (Lost Coast Outpost, North Coast Journal) aggregate many smaller employers

---

*Last updated: January 9, 2026*
