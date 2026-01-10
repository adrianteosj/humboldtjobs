"""
Web Routes for serving HTML pages
"""
from typing import Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from pathlib import Path

from db.database import get_session
from db.models import Job, Employer
from config import STANDARD_CATEGORIES, API_DEFAULT_PAGE_SIZE

# Setup templates
templates_dir = Path(__file__).parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    page: int = Query(1, ge=1),
    category: Optional[str] = Query(None),
    employer: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
):
    """
    Main jobs listing page.
    """
    session = get_session()
    
    try:
        query = session.query(Job).filter(Job.is_active == True)
        
        # Apply filters
        if category:
            query = query.filter(Job.category == category)
        if employer:
            query = query.filter(Job.employer.ilike(f"%{employer}%"))
        if search:
            query = query.filter(Job.title.ilike(f"%{search}%"))
        if location:
            query = query.filter(Job.location.ilike(f"%{location}%"))
        
        # Get total count
        total = query.count()
        
        # Pagination
        per_page = API_DEFAULT_PAGE_SIZE
        pages = (total + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # Get jobs
        jobs = (
            query
            .order_by(Job.scraped_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        
        # Get total count of ALL active jobs (unfiltered)
        total_all_jobs = session.query(Job).filter(Job.is_active == True).count()
        
        # Get the last updated time (most recent scraped_at)
        last_updated = session.query(func.max(Job.scraped_at)).filter(Job.is_active == True).scalar()
        
        # Get categories with counts
        categories = (
            session.query(Job.category, func.count(Job.id))
            .filter(Job.is_active == True)
            .group_by(Job.category)
            .order_by(func.count(Job.id).desc())
            .all()
        )
        
        # Get locations with counts (filter out None/empty)
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
        
        # Get top employers
        employers = (
            session.query(Employer)
            .filter(Employer.job_count > 0)
            .order_by(Employer.job_count.desc())
            .limit(15)
            .all()
        )
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "jobs": jobs,
                "total": total,
                "total_all_jobs": total_all_jobs,
                "last_updated": last_updated,
                "page": page,
                "pages": pages,
                "per_page": per_page,
                "categories": categories,
                "locations": locations,
                "employers": employers,
                "selected_category": category,
                "selected_employer": employer,
                "selected_location": location,
                "search_query": search,
            }
        )
    
    finally:
        session.close()


@router.get("/employer/{employer_name}", response_class=HTMLResponse)
async def employer_detail(
    request: Request,
    employer_name: str,
    page: int = Query(1, ge=1),
):
    """
    Show all jobs from a specific employer.
    """
    session = get_session()
    
    try:
        # Get employer
        employer = session.query(Employer).filter(Employer.name == employer_name).first()
        
        if not employer:
            # Try partial match
            employer = session.query(Employer).filter(Employer.name.ilike(f"%{employer_name}%")).first()
        
        # Get jobs for this employer
        query = session.query(Job).filter(
            Job.is_active == True,
            Job.employer.ilike(f"%{employer_name}%")
        )
        
        total = query.count()
        per_page = API_DEFAULT_PAGE_SIZE
        pages = (total + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        jobs = (
            query
            .order_by(Job.scraped_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        
        # Get sidebar data (same as index page)
        total_all_jobs = session.query(Job).filter(Job.is_active == True).count()
        last_updated = session.query(func.max(Job.scraped_at)).filter(Job.is_active == True).scalar()
        
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
        
        employers_list = (
            session.query(Employer)
            .filter(Employer.job_count > 0)
            .order_by(Employer.job_count.desc())
            .limit(15)
            .all()
        )
        
        return templates.TemplateResponse(
            "employer.html",
            {
                "request": request,
                "employer": employer,
                "employer_name": employer_name,
                "jobs": jobs,
                "total": total,
                "total_all_jobs": total_all_jobs,
                "last_updated": last_updated,
                "page": page,
                "pages": pages,
                "categories": categories,
                "locations": locations,
                "employers": employers_list,
                "selected_employer": employer_name,
            }
        )
    
    finally:
        session.close()


@router.get("/category/{category_name}", response_class=HTMLResponse)
async def category_detail(
    request: Request,
    category_name: str,
    page: int = Query(1, ge=1),
):
    """
    Show all jobs in a specific category.
    """
    session = get_session()
    
    try:
        query = session.query(Job).filter(
            Job.is_active == True,
            Job.category == category_name
        )
        
        total = query.count()
        per_page = API_DEFAULT_PAGE_SIZE
        pages = (total + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        jobs = (
            query
            .order_by(Job.scraped_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        
        # Get employers in this category
        employers = (
            session.query(Job.employer, func.count(Job.id))
            .filter(Job.is_active == True, Job.category == category_name)
            .group_by(Job.employer)
            .order_by(func.count(Job.id).desc())
            .limit(10)
            .all()
        )
        
        return templates.TemplateResponse(
            "category.html",
            {
                "request": request,
                "category_name": category_name,
                "jobs": jobs,
                "total": total,
                "page": page,
                "pages": pages,
                "top_employers": employers,
            }
        )
    
    finally:
        session.close()
