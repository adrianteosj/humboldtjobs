#!/usr/bin/env python3
"""
Static Site Generator for Humboldt Jobs
Generates static HTML files for deployment to Netlify or similar platforms.
"""
import os
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func

from db.database import get_session
from db.models import Job, Employer

# Configuration
OUTPUT_DIR = Path("dist")
PER_PAGE = 20

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
    total_all_jobs = session.query(Job).filter(Job.is_active == True).count()
    last_updated_utc = session.query(func.max(Job.scraped_at)).filter(Job.is_active == True).scalar()
    last_updated = utc_to_pacific(last_updated_utc)
    
    categories = (
        session.query(Job.category, func.count(Job.id))
        .filter(Job.is_active == True)
        .group_by(Job.category)
        .order_by(func.count(Job.id).desc())
        .all()
    )
    
    locations = (
        session.query(Job.location, func.count(Job.id))
        .filter(Job.is_active == True)
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
        .order_by(Employer.job_count.desc())
        .limit(15)
        .all()
    )
    
    return {
        'total_all_jobs': total_all_jobs,
        'last_updated': last_updated,
        'categories': categories,
        'locations': locations,
        'employers': employers,
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
        .filter(Job.is_active == True)
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
            'page': page,
            'pages': total_pages,
            'page_title': 'Find Jobs in Humboldt County',
            'selected_category': None,
            'selected_location': None,
            'selected_employer': None,
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
    
    for cat, count in common_data['categories']:
        cat_slug = slugify(cat)
        
        jobs = (
            session.query(Job)
            .filter(Job.is_active == True, Job.category == cat)
            .order_by(Job.scraped_at.desc())
            .all()
        )
        
        total = len(jobs)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        
        for page in range(1, total_pages + 1):
            offset = (page - 1) * PER_PAGE
            page_jobs = jobs[offset:offset + PER_PAGE]
            
            base_path = f"/category/{cat_slug}/"
            
            context = {
                **common_data,
                'jobs': page_jobs,
                'total': total,
                'page': page,
                'pages': total_pages,
                'page_title': f'{cat} Jobs',
                'selected_category': cat,
                'selected_location': None,
                'selected_employer': None,
                'base_path': base_path,
                'prev_url': f"{base_path}page/{page - 1}/" if page > 1 else None,
                'next_url': f"{base_path}page/{page + 1}/" if page < total_pages else None,
            }
            
            html = template.render(**context)
            
            if page == 1:
                output_dir = OUTPUT_DIR / "category" / cat_slug
            else:
                output_dir = OUTPUT_DIR / "category" / cat_slug / "page" / str(page)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "index.html"
            output_path.write_text(html, encoding='utf-8')
        
        print(f"  Generated: /category/{cat_slug}/ ({total} jobs, {total_pages} pages)")


def generate_location_pages(env, session, common_data):
    """Generate location filter pages."""
    print("Generating location pages...")
    
    template = env.get_template("static/index.html")
    
    for loc, count in common_data['locations']:
        loc_slug = slugify(loc)
        
        jobs = (
            session.query(Job)
            .filter(Job.is_active == True, Job.location == loc)
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
                'page': page,
                'pages': total_pages,
                'page_title': f'Jobs in {loc}',
                'selected_category': None,
                'selected_location': loc,
                'selected_employer': None,
                'base_path': base_path,
                'prev_url': f"{base_path}page/{page - 1}/" if page > 1 else None,
                'next_url': f"{base_path}page/{page + 1}/" if page < total_pages else None,
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
            .filter(Job.is_active == True, Job.employer == emp.name)
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


def copy_static_assets():
    """Copy static assets to output directory."""
    print("Copying static assets...")
    
    src = Path("web/static")
    dst = OUTPUT_DIR / "static"
    
    if dst.exists():
        shutil.rmtree(dst)
    
    shutil.copytree(src, dst)
    print(f"  Copied: {src} -> {dst}")


def generate_sitemap(session):
    """Generate sitemap.xml for SEO."""
    print("Generating sitemap.xml...")
    
    base_url = "https://humboldtjobs.netlify.app"  # Update this with your actual domain
    
    urls = [base_url + "/"]
    
    # Add category pages
    categories = (
        session.query(Job.category)
        .filter(Job.is_active == True)
        .group_by(Job.category)
        .all()
    )
    for (cat,) in categories:
        urls.append(f"{base_url}/category/{slugify(cat)}/")
    
    # Add location pages
    locations = (
        session.query(Job.location)
        .filter(Job.is_active == True, Job.location != None, Job.location != '')
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
        
        # Copy static assets
        copy_static_assets()
        
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
