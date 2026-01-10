"""
REST API Routes for Humboldt Jobs
"""
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from db.database import get_session
from db.models import Job, Employer
from config import API_DEFAULT_PAGE_SIZE, API_MAX_PAGE_SIZE, STANDARD_CATEGORIES

router = APIRouter(tags=["jobs"])


# Pydantic models for API responses
class JobResponse(BaseModel):
    id: int
    title: str
    employer: str
    category: str
    location: Optional[str]
    url: str
    description: Optional[str]
    salary_text: Optional[str]
    job_type: Optional[str]
    posted_date: Optional[str]
    closing_date: Optional[str]
    source_name: str
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int
    pages: int


class EmployerResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    job_count: int
    
    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    name: str
    job_count: int


class StatsResponse(BaseModel):
    total_jobs: int
    total_employers: int
    jobs_by_category: List[CategoryResponse]
    jobs_by_source: List[dict]


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(API_DEFAULT_PAGE_SIZE, ge=1, le=API_MAX_PAGE_SIZE, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    employer: Optional[str] = Query(None, description="Filter by employer (partial match)"),
    search: Optional[str] = Query(None, description="Search in job title"),
    source: Optional[str] = Query(None, description="Filter by source"),
):
    """
    List all jobs with pagination and filtering.
    
    - **page**: Page number (starts at 1)
    - **per_page**: Items per page (max 100)
    - **category**: Filter by standardized category
    - **employer**: Filter by employer name (partial match)
    - **search**: Search in job title
    - **source**: Filter by source name
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
        if source:
            query = query.filter(Job.source_name.ilike(f"%{source}%"))
        
        # Get total count
        total = query.count()
        
        # Calculate pagination
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
        
        # Convert to response format
        job_responses = []
        for job in jobs:
            job_responses.append(JobResponse(
                id=job.id,
                title=job.title,
                employer=job.employer,
                category=job.category,
                location=job.location,
                url=job.url,
                description=job.description[:200] + "..." if job.description and len(job.description) > 200 else job.description,
                salary_text=job.salary_text,
                job_type=job.job_type,
                posted_date=job.posted_date.isoformat() if job.posted_date else None,
                closing_date=job.closing_date.isoformat() if job.closing_date else None,
                source_name=job.source_name,
            ))
        
        return JobListResponse(
            jobs=job_responses,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )
    
    finally:
        session.close()


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int):
    """Get a single job by ID."""
    session = get_session()
    
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobResponse(
            id=job.id,
            title=job.title,
            employer=job.employer,
            category=job.category,
            location=job.location,
            url=job.url,
            description=job.description,
            salary_text=job.salary_text,
            job_type=job.job_type,
            posted_date=job.posted_date.isoformat() if job.posted_date else None,
            closing_date=job.closing_date.isoformat() if job.closing_date else None,
            source_name=job.source_name,
        )
    
    finally:
        session.close()


@router.get("/employers", response_model=List[EmployerResponse])
async def list_employers(
    category: Optional[str] = Query(None, description="Filter by category"),
    min_jobs: int = Query(0, ge=0, description="Minimum job count"),
):
    """
    List all employers with job counts.
    
    - **category**: Filter employers by primary category
    - **min_jobs**: Only show employers with at least this many jobs
    """
    session = get_session()
    
    try:
        query = session.query(Employer).filter(Employer.job_count >= min_jobs)
        
        if category:
            query = query.filter(Employer.category == category)
        
        employers = query.order_by(Employer.job_count.desc()).all()
        
        return [
            EmployerResponse(
                id=emp.id,
                name=emp.name,
                category=emp.category,
                job_count=emp.job_count,
            )
            for emp in employers
        ]
    
    finally:
        session.close()


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories():
    """List all categories with job counts."""
    session = get_session()
    
    try:
        categories = (
            session.query(Job.category, func.count(Job.id))
            .filter(Job.is_active == True)
            .group_by(Job.category)
            .order_by(func.count(Job.id).desc())
            .all()
        )
        
        return [
            CategoryResponse(name=cat, job_count=count)
            for cat, count in categories
        ]
    
    finally:
        session.close()


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get aggregation statistics."""
    session = get_session()
    
    try:
        # Total jobs
        total_jobs = session.query(Job).filter(Job.is_active == True).count()
        
        # Total employers
        total_employers = session.query(Employer).count()
        
        # Jobs by category
        categories = (
            session.query(Job.category, func.count(Job.id))
            .filter(Job.is_active == True)
            .group_by(Job.category)
            .order_by(func.count(Job.id).desc())
            .all()
        )
        
        # Jobs by source
        sources = (
            session.query(Job.source_name, func.count(Job.id))
            .filter(Job.is_active == True)
            .group_by(Job.source_name)
            .order_by(func.count(Job.id).desc())
            .all()
        )
        
        return StatsResponse(
            total_jobs=total_jobs,
            total_employers=total_employers,
            jobs_by_category=[
                CategoryResponse(name=cat, job_count=count)
                for cat, count in categories
            ],
            jobs_by_source=[
                {"source": source, "job_count": count}
                for source, count in sources
            ],
        )
    
    finally:
        session.close()
