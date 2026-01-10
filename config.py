"""
Humboldt Jobs Aggregator - Configuration
"""
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
DATABASE_PATH = BASE_DIR / "humboldt_jobs.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Scraping settings
REQUEST_DELAY = 1.0  # seconds between requests
USER_AGENT = "HumboldtJobsAggregator/1.0 (Local Job Board)"

# NEOGOV RSS Feeds - Government Jobs
NEOGOV_SOURCES = {
    'humboldt_county': {
        'name': 'County of Humboldt',
        'rss_url': 'https://www.governmentjobs.com/careers/humboldtcountyca/rss',
    },
    'eureka': {
        'name': 'City of Eureka',
        'rss_url': 'https://www.governmentjobs.com/careers/eureka/rss',
    },
    'arcata': {
        'name': 'City of Arcata',
        'rss_url': 'https://www.governmentjobs.com/careers/arcataca/rss',
    },
    'fortuna': {
        'name': 'City of Fortuna',
        'rss_url': 'https://www.governmentjobs.com/careers/fortunaca/rss',
    },
    'yurok_tribe': {
        'name': 'Yurok Tribe',
        'rss_url': 'https://www.governmentjobs.com/careers/yuroktribe/rss',
    },
}

# CSU Careers - Cal Poly Humboldt
CSU_CAREERS_BASE_URL = "https://csucareers.calstate.edu"
CSU_CAREERS_FILTER_URL = "https://csucareers.calstate.edu/en-us/filter/"
CSU_CAREERS_LOCATION = "humboldt"

# EdJoin - Education Jobs
EDJOIN_BASE_URL = "https://edjoin.org/Home/Jobs"
EDJOIN_LOCATION = "humboldt"

# Standardized Categories (matching EMPLOYER_DIRECTORY.md)
STANDARD_CATEGORIES = [
    'Government',
    'Education', 
    'Healthcare',
    'Tribal Organizations',
    'Nonprofit & Social Services',
    'Local Retail',
    'National Retail',
    'Food & Agriculture',
    'Food & Beverage',
    'Timber & Forestry',
    'Manufacturing',
    'Construction & Engineering',
    'Energy & Utilities',
    'Transportation & Logistics',
    'Financial Services',
    'Hospitality & Entertainment',
    'Other'
]

# Tier 3 - Local Employers

# Casinos (ADP WorkforceNow & Paycom)
BLUE_LAKE_CASINO_ADP_URL = "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=5e47fadf-5db6-4b69-91e1-34513c2b4a4b&ccId=19000101_000001&type=MP&lang=en_US"
BEAR_RIVER_CASINO_PAYCOM_URL = "https://www.paycomonline.net/v4/ats/web.php/jobs?clientkey=CE0F26C6709C873C92555F8D0F5C7AAE&fromClientSide=true"

# Construction/Engineering (ADP WorkforceNow)
LACO_ASSOCIATES_ADP_URL = "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=98890d1f-2673-4416-b519-52f06ee8bb40&ccId=19000101_000001&type=JS&lang=en_US&selectedMenuKey=CareerCenter"

# Construction (Danco Group - Custom HTML)
DANCO_GROUP_URL = "https://www.danco-group.com/who-we-are/join-our-team"

# Local Retail (Eureka Natural Foods - Custom HTML)
EUREKA_NATURAL_FOODS_URL = "https://www.eurekanaturalfoods.com/employment-our-team"

# Timber (enterTimeOnline)
GREEN_DIAMOND_ATS_URL = "https://secure3.entertimeonline.com/ta/6110531.careers?CareersSearch"

# Local Retail (UltiPro/UKG)
NORTH_COAST_COOP_UKG_URL = "https://recruiting2.ultipro.com/NOR1050NCCOP/JobBoard/ec9e3a4a-afd4-4ee8-a6b5-4d3767816852/?q=&o=postedDateDesc"

# Tier 3B - National Retailers
DOLLAR_GENERAL_API_URL = "https://careers.dollargeneral.com/api/jobs"
DOLLAR_GENERAL_LOCATION = "95521"  # Arcata ZIP code
DOLLAR_GENERAL_RADIUS = 50  # miles

WALGREENS_SEARCH_URL = "https://jobs.walgreens.com/en/search-jobs/95521%2C%20Arcata%2C%20CA/1242/4/6252001-5332921-5565500-5558953/40x8742/-124x0765/50/2"

TJ_MAXX_SEARCH_URL = "https://jobs.tjx.com/global/en/search-results?keywords=&p=ChIJp07_5oP_01QRlQYpuGYHhio&location=Eureka,%20CA,%20USA"

COSTCO_SEARCH_URL = "https://careers.costco.com/jobs?stretchUnit=MILES&stretch=10&lat=40.87548845327257&lng=-124.09764277786618"

SAFEWAY_EUREKA_URL = "https://eofd.fa.us6.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?location=Eureka%2C+CA%2C+United+States&locationId=300000002779854&locationLevel=city&mode=location&radius=25&radiusUnit=MI"
SAFEWAY_ARCATA_URL = "https://eofd.fa.us6.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?location=Arcata%2C+CA%2C+United+States&locationId=300000002779847&locationLevel=city&mode=location&radius=50&radiusUnit=MI"

# Walmart
WALMART_SEARCH_URL = "https://careers.walmart.com/us/en/results?searchQuery=95501"

# Tier 3B - Banks and Financial Institutions
REDWOOD_CAPITAL_BANK_URL = "https://www.redwoodcapitalbank.com/about-us/careers"
TRI_COUNTIES_BANK_UKG_URL = "https://recruiting.ultipro.com/TRI1013/JobBoard/4245b871-01e9-d361-c591-d813261dcc18/?q=&o=postedDateDesc"
COAST_CENTRAL_CU_URL = "https://www.coastccu.org/community/careers/"
COMPASS_CCU_URL = "https://compassccu.org/career-opportunities/"
COLUMBIA_BANK_WORKDAY_URL = "https://columbiabank.wd108.myworkdayjobs.com/Columbia?locations=ca89c3dfc91010011a94de4a15710000"
US_BANK_CAREERS_URL = "https://careers.usbank.com/global/en/search-results?keywords=california"

# API Settings
API_HOST = "0.0.0.0"
API_PORT = 8000
API_DEFAULT_PAGE_SIZE = 20
API_MAX_PAGE_SIZE = 100
