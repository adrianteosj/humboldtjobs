#!/usr/bin/env python3
"""
Static Site Generator for Humboldt Jobs
Generates static HTML files for deployment to Netlify or similar platforms.
"""
import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func

from db.database import get_session
from db.models import Job, Employer, ScrapeLog
from processing.normalizer import JobClassifier, CLASSIFICATION_RULES

# Configuration
OUTPUT_DIR = Path("dist")
PER_PAGE = 20


def active_jobs_filter():
    """Return filter conditions for active, non-quarantined jobs."""
    return (Job.is_active == True) & ((Job.is_quarantined == False) | (Job.is_quarantined == None))

# Pacific timezone (PST = UTC-8, PDT = UTC-7)
# For simplicity, using PST; for accurate DST handling, use pytz or zoneinfo
PACIFIC_OFFSET = timedelta(hours=-8)


def utc_to_pacific(dt):
    """Convert UTC datetime to Pacific time."""
    if dt is None:
        return None
    # Assume input is naive UTC, convert to Pacific
    return dt + PACIFIC_OFFSET


def slugify(text):
    """Convert text to URL-friendly slug."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def get_common_data(session):
    """Get sidebar data used across all pages."""
    total_all_jobs = session.query(Job).filter(active_jobs_filter()).count()
    last_updated_utc = session.query(func.max(Job.scraped_at)).filter(active_jobs_filter()).scalar()
    last_updated = utc_to_pacific(last_updated_utc)
    
    categories = (
        session.query(Job.category, func.count(Job.id))
        .filter(active_jobs_filter())
        .group_by(Job.category)
        .order_by(func.count(Job.id).desc())
        .all()
    )
    
    locations = (
        session.query(Job.location, func.count(Job.id))
        .filter(active_jobs_filter())
        .filter(Job.location != None)
        .filter(Job.location != '')
        .group_by(Job.location)
        .order_by(func.count(Job.id).desc())
        .limit(15)
        .all()
    )
    
    employers = (
        session.query(Employer)
        .filter(Employer.job_count > 0)
        .order_by(Employer.name.asc())
        .all()
    )
    
    # Get latest scrape log for "new jobs" info
    latest_scrape = (
        session.query(ScrapeLog)
        .order_by(ScrapeLog.scraped_at.desc())
        .first()
    )
    
    new_jobs_count = 0
    new_jobs_date = None
    new_job_urls = []
    if latest_scrape:
        new_jobs_count = latest_scrape.jobs_inserted
        new_jobs_date = utc_to_pacific(latest_scrape.scraped_at)
        # Parse new job URLs from JSON
        if latest_scrape.new_job_urls:
            try:
                new_job_urls = json.loads(latest_scrape.new_job_urls)
            except:
                new_job_urls = []
    
    return {
        'total_all_jobs': total_all_jobs,
        'last_updated': last_updated,
        'categories': categories,
        'locations': locations,
        'employers': employers,
        'new_jobs_count': new_jobs_count,
        'new_jobs_date': new_jobs_date,
        'new_job_urls': new_job_urls,
    }


def generate_pagination_links(current_page, total_pages, base_path="/"):
    """Generate pagination data for templates."""
    return {
        'page': current_page,
        'pages': total_pages,
        'base_path': base_path,
        'prev_url': f"{base_path}page/{current_page - 1}/" if current_page > 1 else None,
        'next_url': f"{base_path}page/{current_page + 1}/" if current_page < total_pages else None,
    }


def generate_index_pages(env, session, common_data):
    """Generate main index and paginated pages."""
    print("Generating index pages...")
    
    jobs = (
        session.query(Job)
        .filter(active_jobs_filter())
        .order_by(Job.scraped_at.desc())
        .all()
    )
    
    total = len(jobs)
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    
    template = env.get_template("static/index.html")
    
    for page in range(1, total_pages + 1):
        offset = (page - 1) * PER_PAGE
        page_jobs = jobs[offset:offset + PER_PAGE]
        
        context = {
            **common_data,
            'jobs': page_jobs,
            'total': total,
            'category_total': total,
            'page': page,
            'pages': total_pages,
            'page_title': 'Find Jobs in Humboldt County',
            'selected_category': None,
            'selected_location': None,
            'selected_employer': None,
            'selected_classification': None,
            'subcategories': [],  # No subcategories on main index
        }
        
        # Add pagination URLs
        context['prev_url'] = f"/page/{page - 1}/" if page > 1 else None
        context['next_url'] = f"/page/{page + 1}/" if page < total_pages else None
        context['base_path'] = "/"
        
        html = template.render(**context)
        
        if page == 1:
            output_path = OUTPUT_DIR / "index.html"
        else:
            output_dir = OUTPUT_DIR / "page" / str(page)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "index.html"
        
        output_path.write_text(html, encoding='utf-8')
        print(f"  Generated: {output_path}")


def generate_category_pages(env, session, common_data):
    """Generate category filter pages."""
    print("Generating category pages...")
    
    template = env.get_template("static/index.html")
    classifier = JobClassifier()
    
    for cat, count in common_data['categories']:
        cat_slug = slugify(cat)
        
        jobs = (
            session.query(Job)
            .filter(active_jobs_filter(), Job.category == cat)
            .order_by(Job.scraped_at.desc())
            .all()
        )
        
        category_total = len(jobs)
        total_pages = max(1, (category_total + PER_PAGE - 1) // PER_PAGE)
        
        # Calculate subcategory counts for this category
        subcategories = []
        subcat_jobs = {}  # Store jobs by classification for sub-category pages
        
        if cat in CLASSIFICATION_RULES:
            subcat_counts = {}
            for job in jobs:
                # Use stored classification or calculate on-the-fly
                classification = job.classification or classifier.classify(job.title, cat)
                if classification:
                    job.classification = classification  # Ensure it's set
                    subcat_counts[classification] = subcat_counts.get(classification, 0) + 1
                    if classification not in subcat_jobs:
                        subcat_jobs[classification] = []
                    subcat_jobs[classification].append(job)
            
            # Sort by count descending
            subcategories = sorted(subcat_counts.items(), key=lambda x: -x[1])
        
        # Generate main category pages (All)
        for page in range(1, total_pages + 1):
            offset = (page - 1) * PER_PAGE
            page_jobs = jobs[offset:offset + PER_PAGE]
            
            base_path = f"/category/{cat_slug}/"
            
            context = {
                **common_data,
                'jobs': page_jobs,
                'total': category_total,
                'category_total': category_total,
                'page': page,
                'pages': total_pages,
                'page_title': f'{cat} Jobs',
                'selected_category': cat,
                'selected_location': None,
                'selected_employer': None,
                'selected_classification': None,
                'base_path': base_path,
                'prev_url': f"{base_path}page/{page - 1}/" if page > 1 else None,
                'next_url': f"{base_path}page/{page + 1}/" if page < total_pages else None,
                'subcategories': subcategories,
            }
            
            html = template.render(**context)
            
            if page == 1:
                output_dir = OUTPUT_DIR / "category" / cat_slug
            else:
                output_dir = OUTPUT_DIR / "category" / cat_slug / "page" / str(page)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "index.html"
            output_path.write_text(html, encoding='utf-8')
        
        # Generate sub-category pages
        for subcat, subcat_count in subcategories:
            subcat_slug = slugify(subcat)
            subcat_job_list = subcat_jobs.get(subcat, [])
            subcat_total_pages = max(1, (len(subcat_job_list) + PER_PAGE - 1) // PER_PAGE)
            
            for page in range(1, subcat_total_pages + 1):
                offset = (page - 1) * PER_PAGE
                page_jobs = subcat_job_list[offset:offset + PER_PAGE]
                
                base_path = f"/category/{cat_slug}/"
                subcat_base_path = f"/category/{cat_slug}/{subcat_slug}/"
                
                context = {
                    **common_data,
                    'jobs': page_jobs,
                    'total': len(subcat_job_list),
                    'category_total': category_total,
                    'page': page,
                    'pages': subcat_total_pages,
                    'page_title': f'{subcat} - {cat} Jobs',
                    'selected_category': cat,
                    'selected_location': None,
                    'selected_employer': None,
                    'selected_classification': subcat,
                    'base_path': base_path,
                    'prev_url': f"{subcat_base_path}page/{page - 1}/" if page > 1 else None,
                    'next_url': f"{subcat_base_path}page/{page + 1}/" if page < subcat_total_pages else None,
                    'subcategories': subcategories,
                }
                
                html = template.render(**context)
                
                if page == 1:
                    output_dir = OUTPUT_DIR / "category" / cat_slug / subcat_slug
                else:
                    output_dir = OUTPUT_DIR / "category" / cat_slug / subcat_slug / "page" / str(page)
                
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / "index.html"
                output_path.write_text(html, encoding='utf-8')
        
        subcats_info = f", {len(subcategories)} subcats" if subcategories else ""
        print(f"  Generated: /category/{cat_slug}/ ({category_total} jobs, {total_pages} pages{subcats_info})")


def generate_location_pages(env, session, common_data):
    """Generate location filter pages."""
    print("Generating location pages...")
    
    template = env.get_template("static/index.html")
    
    for loc, count in common_data['locations']:
        loc_slug = slugify(loc)
        
        jobs = (
            session.query(Job)
            .filter(active_jobs_filter(), Job.location == loc)
            .order_by(Job.scraped_at.desc())
            .all()
        )
        
        total = len(jobs)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        
        for page in range(1, total_pages + 1):
            offset = (page - 1) * PER_PAGE
            page_jobs = jobs[offset:offset + PER_PAGE]
            
            base_path = f"/location/{loc_slug}/"
            
            context = {
                **common_data,
                'jobs': page_jobs,
                'total': total,
                'category_total': total,
                'page': page,
                'pages': total_pages,
                'page_title': f'Jobs in {loc}',
                'selected_category': None,
                'selected_location': loc,
                'selected_employer': None,
                'selected_classification': None,
                'base_path': base_path,
                'prev_url': f"{base_path}page/{page - 1}/" if page > 1 else None,
                'next_url': f"{base_path}page/{page + 1}/" if page < total_pages else None,
                'subcategories': [],  # No subcategories on location pages
            }
            
            html = template.render(**context)
            
            if page == 1:
                output_dir = OUTPUT_DIR / "location" / loc_slug
            else:
                output_dir = OUTPUT_DIR / "location" / loc_slug / "page" / str(page)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "index.html"
            output_path.write_text(html, encoding='utf-8')
        
        print(f"  Generated: /location/{loc_slug}/ ({total} jobs, {total_pages} pages)")


def generate_employer_pages(env, session, common_data):
    """Generate employer detail pages."""
    print("Generating employer pages...")
    
    template = env.get_template("static/employer.html")
    
    # Get all employers with jobs
    employers_with_jobs = (
        session.query(Employer)
        .filter(Employer.job_count > 0)
        .order_by(Employer.job_count.desc())
        .all()
    )
    
    for emp in employers_with_jobs:
        emp_slug = slugify(emp.name)
        
        jobs = (
            session.query(Job)
            .filter(active_jobs_filter(), Job.employer == emp.name)
            .order_by(Job.scraped_at.desc())
            .all()
        )
        
        total = len(jobs)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        
        for page in range(1, total_pages + 1):
            offset = (page - 1) * PER_PAGE
            page_jobs = jobs[offset:offset + PER_PAGE]
            
            base_path = f"/employer/{emp_slug}/"
            
            context = {
                **common_data,
                'jobs': page_jobs,
                'total': total,
                'page': page,
                'pages': total_pages,
                'employer': emp,
                'employer_name': emp.name,
                'selected_employer': emp.name,
                'selected_category': None,
                'selected_location': None,
                'base_path': base_path,
                'prev_url': f"{base_path}page/{page - 1}/" if page > 1 else None,
                'next_url': f"{base_path}page/{page + 1}/" if page < total_pages else None,
            }
            
            html = template.render(**context)
            
            if page == 1:
                output_dir = OUTPUT_DIR / "employer" / emp_slug
            else:
                output_dir = OUTPUT_DIR / "employer" / emp_slug / "page" / str(page)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "index.html"
            output_path.write_text(html, encoding='utf-8')
        
        print(f"  Generated: /employer/{emp_slug}/ ({total} jobs, {total_pages} pages)")


def generate_employers_directory(env):
    """Generate the employer career pages directory."""
    print("Generating employers directory page...")
    
    template = env.get_template("static/employers.html")
    
    # Define employer data by category
    employers_by_category = {
        "Government": [
            {"name": "County of Humboldt", "url": "https://www.governmentjobs.com/careers/humboldtcountyca"},
            {"name": "City of Eureka", "url": "https://www.governmentjobs.com/careers/eurekaca"},
            {"name": "City of Arcata", "url": "https://www.cityofarcata.org/Jobs.aspx"},
            {"name": "City of Fortuna", "url": "https://www.governmentjobs.com/careers/fortunaca"},
            {"name": "City of Rio Dell", "url": "https://www.cityofriodell.ca.gov/282/Employment"},
            {"name": "City of Blue Lake", "url": "https://bluelake.ca.gov/employment-opportunities/"},
            {"name": "City of Ferndale", "url": "https://ci.ferndale.ca.us/employment/"},
            {"name": "City of Trinidad", "url": "https://www.trinidad.ca.gov/employment-opportunities"},
            {"name": "Wiyot Tribe", "url": "https://www.wiyot.us/Jobs.aspx"},
            {"name": "Yurok Tribe", "url": "https://www.governmentjobs.com/careers/yuroktribe"},
        ],
        "Education": [
            {"name": "Cal Poly Humboldt", "url": "https://csucareers.calstate.edu/en-us/filter/?location=humboldt"},
            {"name": "College of the Redwoods", "url": "https://employment.redwoods.edu/postings/search"},
            {"name": "Humboldt County School Districts", "url": "https://edjoin.org/Home/Jobs?location=humboldt"},
        ],
        "Healthcare": [
            {"name": "Open Door Community Health", "url": "https://opendoorhealth.wd503.myworkdayjobs.com/ODCHC"},
            {"name": "Providence St. Joseph Hospital", "url": "https://providence.jobs/eureka/new-jobs/"},
            {"name": "Providence Redwood Memorial", "url": "https://providence.jobs/fortuna/new-jobs/"},
            {"name": "Mad River Community Hospital", "url": "https://www.madriverhospital.com/careers"},
            {"name": "United Indian Health Services", "url": "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=447f2bd0-2d4d-4f2a-9bae-3f5453ebc910"},
            {"name": "K'ima:w Medical Center", "url": "https://www.kimaw.org/jobs"},
            {"name": "Hospice of Humboldt", "url": "https://www.paycomonline.net/v4/ats/web.php/portal/C7DCD5CFA20B99C322370C9F9EEA00E2/career-page"},
            {"name": "Humboldt Senior Resource Center", "url": "https://www.paycomonline.net/v4/ats/web.php/portal/26A855BC71A6DA61564C6529E594B2E4/career-page"},
            {"name": "Redwood Community Action Agency", "url": "https://rcaa.org/employment-opportunities"},
            {"name": "SoHum Health", "url": "https://sohumhealth.org/careers/"},
            {"name": "Redwoods Rural Health Center", "url": "https://www.rrhc.org/job-opportunities"},
        ],
        "Nonprofit & Social Services": [
            {"name": "Food for People", "url": "https://www.foodforpeople.org/jobs"},
            {"name": "Boys & Girls Club of the Redwoods", "url": "https://bgcredwoods.org/careers/"},
            {"name": "Changing Tides Family Services", "url": "https://changingtidesfs.org/employment/"},
            {"name": "Two Feathers NAFS", "url": "https://twofeathers-nafs.org/about-us/employment-opportunities/"},
            {"name": "Arcata House Partnership", "url": "https://www.arcatahouse.org/join-our-team"},
        ],
        "Local Retail": [
            {"name": "North Coast Co-op", "url": "https://recruiting2.ultipro.com/NOR1050NCCOP/JobBoard/ec9e3a4a-afd4-4ee8-a6b5-4d3767816852/"},
            {"name": "Eureka Natural Foods", "url": "https://www.eurekanaturalfoods.com/employment-our-team"},
            {"name": "Murphy's Markets", "url": "https://www.murphysmarkets.net/employment"},
            {"name": "Pierson Building Center", "url": "https://www.thebighammer.com/jobs"},
            {"name": "C. Crane Company", "url": "https://ccrane.com/jobs/"},
        ],
        "National Retail": [
            {"name": "Walmart", "url": "https://careers.walmart.com/us/en/results?searchQuery=95501"},
            {"name": "Costco", "url": "https://careers.costco.com/jobs?stretchUnit=MILES&stretch=10&lat=40.87548845327257&lng=-124.09764277786618"},
            {"name": "Safeway/Albertsons", "url": "https://eofd.fa.us6.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?location=Eureka%2C+CA"},
            {"name": "Dollar General", "url": "https://careers.dollargeneral.com/jobs?keywords=&location=95521&stretch=50"},
            {"name": "Walgreens", "url": "https://jobs.walgreens.com/en/search-jobs/95521%2C%20Arcata%2C%20CA/1242/4/"},
            {"name": "TJ Maxx", "url": "https://jobs.tjx.com/global/en/search-results?keywords=&location=Eureka,%20CA,%20USA"},
            {"name": "CVS Health", "url": "https://jobs.cvshealth.com/us/en/search-results?keywords=&location=Eureka%2C%20CA"},
            {"name": "Rite Aid", "url": "https://careers.riteaid.com/jobs?location=Eureka%2C+CA&radius=50"},
            {"name": "Ace Hardware", "url": "https://careers.acehardware.com/job-search/?location=Eureka%2C+CA&radius=50"},
            {"name": "WinCo Foods", "url": "https://careers.wincofoods.com"},
            {"name": "Grocery Outlet", "url": "https://groceryoutlet.com/careers"},
            {"name": "Harbor Freight Tools", "url": "https://jobs.harborfreight.com/search-jobs/eureka%2C%20ca"},
        ],
        "Food & Agriculture": [
            {"name": "Humboldt Creamery", "url": "https://recruiting.paylocity.com/recruiting/jobs/All/249cf053-4850-4112-bc86-33c91f93332a/Crystal-Creamery"},
            {"name": "Cypress Grove Chevre", "url": "https://www.cypressgrovecheese.com/careers/"},
            {"name": "Alexandre Family Farm", "url": "https://alexandrefamilyfarm.com/pages/careers"},
            {"name": "Driscoll's", "url": "https://www.driscolls.com/about/careers"},
            {"name": "Pacific Seafood", "url": "https://careers.pacificseafood.com/search-result/?keyword=&city=95501&state=CA"},
        ],
        "Food & Beverage": [
            {"name": "Lost Coast Brewery", "url": "https://lostcoast.com/careers"},
            {"name": "Starbucks", "url": "https://www.starbucks.com/careers/find-a-job?location=Eureka%2C%20CA"},
        ],
        "Timber & Forestry": [
            {"name": "Humboldt Sawmill / Humboldt Redwood Company", "url": "https://careers-mfp.icims.com/jobs/search?ss=1&searchLocation=12781-12789-Scotia"},
            {"name": "Green Diamond Resource Company", "url": "https://secure3.entertimeonline.com/ta/6110531.careers?CareersSearch"},
            {"name": "Sierra Pacific Industries", "url": "https://spi-ind.com/CAREERS"},
            {"name": "Jones Family Tree Service", "url": "https://www.jonesfamilytreeservice.com/careers"},
        ],
        "Manufacturing": [
            {"name": "Kokatat", "url": "https://kokatat.com/careers"},
        ],
        "Construction & Engineering": [
            {"name": "Danco Group", "url": "https://www.danco-group.com/who-we-are/join-our-team"},
            {"name": "LACO Associates", "url": "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=98890d1f-2673-4416-b519-52f06ee8bb40"},
        ],
        "Energy & Utilities": [
            {"name": "Redwood Coast Energy Authority", "url": "https://redwoodenergy.org/about/employment/"},
            {"name": "Pacific Gas & Electric (PG&E)", "url": "https://jobs.pge.com/search/?searchby=location&q=&locationsearch=eureka"},
        ],
        "Transportation & Logistics": [
            {"name": "FedEx", "url": "https://careers.fedex.com/fedex/jobs?location=Eureka%2C%20CA&woe=7&stretch=50"},
            {"name": "UPS", "url": "https://www.jobs-ups.com/search-jobs/eureka%2C%20ca"},
        ],
        "Financial Services": [
            {"name": "Coast Central Credit Union", "url": "https://www.coastccu.org/community/careers/"},
            {"name": "Compass Community Credit Union", "url": "https://compassccu.org/career-opportunities/"},
            {"name": "Columbia Bank", "url": "https://columbiabank.wd108.myworkdayjobs.com/Columbia?locations=ca89c3dfc91010011a94de4a15710000"},
            {"name": "Redwood Capital Bank", "url": "https://www.redwoodcapitalbank.com/about-us/careers"},
            {"name": "Tri Counties Bank", "url": "https://recruiting.ultipro.com/TRI1013/JobBoard/4245b871-01e9-d361-c591-d813261dcc18/"},
        ],
        "Hospitality & Entertainment": [
            {"name": "Blue Lake Casino & Hotel", "url": "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=5e47fadf-5db6-4b69-91e1-34513c2b4a4b"},
            {"name": "Bear River Casino Resort", "url": "https://www.paycomonline.net/v4/ats/web.php/jobs?clientkey=CE0F26C6709C873C92555F8D0F5C7AAE"},
        ],
    }
    
    # Count total employers
    total_employers = sum(len(emp_list) for emp_list in employers_by_category.values())
    
    # Flatten for template
    all_employers = []
    for emp_list in employers_by_category.values():
        all_employers.extend(emp_list)
    
    context = {
        'employers_by_category': employers_by_category,
        'employers': all_employers,
    }
    
    html = template.render(**context)
    
    output_dir = OUTPUT_DIR / "employers"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(html, encoding='utf-8')
    
    print(f"  Generated: /employers/ ({total_employers} employers)")


def generate_new_jobs_page(env, session, common_data):
    """Generate the 'new jobs since last update' page."""
    print("Generating new jobs page...")
    
    new_job_urls = common_data.get('new_job_urls', [])
    
    if not new_job_urls:
        print("  No new job URLs found, skipping...")
        return
    
    # Get jobs by URL
    jobs = (
        session.query(Job)
        .filter(active_jobs_filter(), Job.url.in_(new_job_urls))
        .order_by(Job.scraped_at.desc())
        .all()
    )
    
    total = len(jobs)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    
    template = env.get_template("static/index.html")
    
    for page in range(1, total_pages + 1):
        offset = (page - 1) * PER_PAGE
        page_jobs = jobs[offset:offset + PER_PAGE]
        
        base_path = "/new/"
        new_jobs_date = common_data.get('new_jobs_date')
        date_str = new_jobs_date.strftime('%b %d, %Y') if new_jobs_date else 'recently'
        
        context = {
            **common_data,
            'jobs': page_jobs,
            'total': total,
            'category_total': total,
            'page': page,
            'pages': total_pages,
            'page_title': f'New Jobs Added {date_str}',
            'selected_category': None,
            'selected_location': None,
            'selected_employer': None,
            'selected_classification': None,
            'base_path': base_path,
            'prev_url': f"{base_path}page/{page - 1}/" if page > 1 else None,
            'next_url': f"{base_path}page/{page + 1}/" if page < total_pages else None,
            'subcategories': [],
            # Don't show new jobs badge on this page (we're already viewing new jobs)
            'new_jobs_count': 0,
        }
        
        html = template.render(**context)
        
        if page == 1:
            output_dir = OUTPUT_DIR / "new"
        else:
            output_dir = OUTPUT_DIR / "new" / "page" / str(page)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "index.html"
        output_path.write_text(html, encoding='utf-8')
    
    print(f"  Generated: /new/ ({total} jobs, {total_pages} pages)")


def generate_updates_page(env, session, common_data):
    """Generate the update history page."""
    print("Generating updates history page...")
    
    # Get all scrape logs, most recent first
    scrape_logs = (
        session.query(ScrapeLog)
        .order_by(ScrapeLog.scraped_at.desc())
        .limit(50)  # Show last 50 updates
        .all()
    )
    
    # Convert timestamps to Pacific time
    for log in scrape_logs:
        log.scraped_at = utc_to_pacific(log.scraped_at)
    
    template = env.get_template("static/updates.html")
    
    total_employers = session.query(Employer).filter(Employer.job_count > 0).count()
    
    context = {
        'scrape_logs': scrape_logs,
        'total_jobs': common_data['total_all_jobs'],
        'total_employers': total_employers,
    }
    
    html = template.render(**context)
    
    output_dir = OUTPUT_DIR / "updates"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(html, encoding='utf-8')
    
    print(f"  Generated: /updates/ ({len(scrape_logs)} logs)")


def copy_static_assets():
    """Copy static assets to output directory."""
    print("Copying static assets...")
    
    src = Path("web/static")
    dst = OUTPUT_DIR / "static"
    
    if dst.exists():
        shutil.rmtree(dst)
    
    shutil.copytree(src, dst)
    print(f"  Copied: {src} -> {dst}")


def generate_jobs_json(session):
    """Generate jobs.json for client-side search and AI context.
    
    This enriched JSON includes all available job data to enable
    smarter AI recommendations and better search filtering.
    """
    print("Generating jobs.json for search...")
    
    jobs = (
        session.query(Job)
        .filter(active_jobs_filter())
        .order_by(Job.scraped_at.desc())
        .all()
    )
    
    jobs_data = []
    for job in jobs:
        job_entry = {
            # Core fields
            'id': job.id,
            'title': job.title,
            'employer': job.employer,
            'category': job.category,
            'classification': job.classification or '',
            'location': job.location or '',
            'url': job.url,
            'slug': slugify(job.employer),
            
            # Salary data (text and parsed)
            'salary': job.salary_text or '',
            'salary_min': job.salary_min,
            'salary_max': job.salary_max,
            'salary_type': job.salary_type or '',
            
            # Job type and level
            'job_type': job.job_type or '',
            'experience_level': job.experience_level or '',
            'education_required': job.education_required or '',
            'is_remote': job.is_remote or False,
            'department': job.department or '',
            
            # Rich text (truncated to keep file size manageable)
            'description': (job.description or '')[:500],
            'requirements': (job.requirements or '')[:300],
            'benefits': (job.benefits or '')[:200],
            
            # Dates (ISO format for JS parsing)
            'posted_date': job.posted_date.isoformat() if job.posted_date else '',
            'closing_date': job.closing_date.isoformat() if job.closing_date else '',
        }
        jobs_data.append(job_entry)
    
    output_path = OUTPUT_DIR / "static" / "jobs.json"
    output_path.write_text(json.dumps(jobs_data, ensure_ascii=False), encoding='utf-8')
    print(f"  Generated: jobs.json ({len(jobs_data)} jobs with enriched data)")


def generate_sitemap(session):
    """Generate sitemap.xml for SEO."""
    print("Generating sitemap.xml...")
    
    base_url = "https://humboldtjobs.netlify.app"  # Update this with your actual domain
    
    urls = [base_url + "/"]
    
    # Add category pages
    categories = (
        session.query(Job.category)
        .filter(active_jobs_filter())
        .group_by(Job.category)
        .all()
    )
    for (cat,) in categories:
        urls.append(f"{base_url}/category/{slugify(cat)}/")
    
    # Add location pages
    locations = (
        session.query(Job.location)
        .filter(active_jobs_filter(), Job.location != None, Job.location != '')
        .group_by(Job.location)
        .limit(15)
        .all()
    )
    for (loc,) in locations:
        urls.append(f"{base_url}/location/{slugify(loc)}/")
    
    # Add employer pages
    employers = (
        session.query(Employer)
        .filter(Employer.job_count > 0)
        .all()
    )
    for emp in employers:
        urls.append(f"{base_url}/employer/{slugify(emp.name)}/")
    
    # Add employers directory page
    urls.append(f"{base_url}/employers/")
    
    # Add new jobs and updates pages
    urls.append(f"{base_url}/new/")
    urls.append(f"{base_url}/updates/")
    
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for url in urls:
        sitemap += f'  <url><loc>{url}</loc></url>\n'
    
    sitemap += '</urlset>'
    
    (OUTPUT_DIR / "sitemap.xml").write_text(sitemap, encoding='utf-8')
    print(f"  Generated: sitemap.xml ({len(urls)} URLs)")


def generate_robots_txt():
    """Generate robots.txt."""
    print("Generating robots.txt...")
    
    robots = """User-agent: *
Allow: /

Sitemap: https://humboldtjobs.netlify.app/sitemap.xml
"""
    
    (OUTPUT_DIR / "robots.txt").write_text(robots, encoding='utf-8')
    print("  Generated: robots.txt")


def main():
    """Main entry point for static site generation."""
    print("=" * 60)
    print("Humboldt Jobs - Static Site Generator")
    print("=" * 60)
    print()
    
    # Clean output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    
    # Setup Jinja2 environment
    env = Environment(
        loader=FileSystemLoader("web/templates"),
        autoescape=True,
    )
    
    # Add custom filters
    env.filters['slugify'] = slugify
    
    session = get_session()
    
    try:
        # Get common sidebar data
        common_data = get_common_data(session)
        
        print(f"Total jobs: {common_data['total_all_jobs']}")
        print(f"Categories: {len(common_data['categories'])}")
        print(f"Locations: {len(common_data['locations'])}")
        print(f"Employers: {len(common_data['employers'])}")
        print()
        
        # Generate pages
        generate_index_pages(env, session, common_data)
        generate_category_pages(env, session, common_data)
        generate_location_pages(env, session, common_data)
        generate_employer_pages(env, session, common_data)
        generate_employers_directory(env)
        generate_new_jobs_page(env, session, common_data)
        generate_updates_page(env, session, common_data)
        
        # Copy static assets
        copy_static_assets()
        
        # Generate search data
        generate_jobs_json(session)
        
        # Generate SEO files
        generate_sitemap(session)
        generate_robots_txt()
        
        print()
        print("=" * 60)
        print("Static site generated successfully!")
        print(f"Output directory: {OUTPUT_DIR.absolute()}")
        print()
        print("To preview locally:")
        print(f"  cd {OUTPUT_DIR} && python -m http.server 8080")
        print()
        print("To deploy to Netlify:")
        print("  1. Push the 'dist' folder to GitHub")
        print("  2. Connect the repo to Netlify")
        print("  3. Set publish directory to 'dist'")
        print("=" * 60)
        
    finally:
        session.close()


if __name__ == "__main__":
    main()
