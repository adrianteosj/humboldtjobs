"""
Database models for Humboldt Jobs Aggregator
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Index, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Job(Base):
    """Job listing model with standardized fields"""
    __tablename__ = 'jobs'
    
    id = Column(Integer, primary_key=True)
    source_id = Column(String(255), nullable=False)  # External ID from source
    source_name = Column(String(100), nullable=False)  # e.g., 'neogov_humboldt_county'
    
    title = Column(String(500), nullable=False)
    employer = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)  # Standardized category
    classification = Column(String(100))  # Sub-category (Teaching, Support Staff, etc.)
    original_category = Column(String(255))  # Preserved from source
    
    location = Column(String(255))
    url = Column(String(1000), nullable=False, unique=True)
    description = Column(Text)
    
    salary_text = Column(String(255))  # Original salary string
    job_type = Column(String(100))  # Full-time, Part-time, etc.
    
    posted_date = Column(DateTime)
    closing_date = Column(DateTime)
    
    scraped_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_source', 'source_name'),
        Index('idx_category', 'category'),
        Index('idx_employer', 'employer'),
        Index('idx_posted', 'posted_date'),
        Index('idx_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title[:40]}...', employer='{self.employer}')>"
    
    def to_dict(self):
        """Convert job to dictionary for API responses"""
        return {
            'id': self.id,
            'title': self.title,
            'employer': self.employer,
            'category': self.category,
            'location': self.location,
            'url': self.url,
            'description': self.description[:200] + '...' if self.description and len(self.description) > 200 else self.description,
            'salary_text': self.salary_text,
            'job_type': self.job_type,
            'posted_date': self.posted_date.isoformat() if self.posted_date else None,
            'closing_date': self.closing_date.isoformat() if self.closing_date else None,
            'source_name': self.source_name,
        }


class Employer(Base):
    """Employer model for grouping jobs"""
    __tablename__ = 'employers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    category = Column(String(100))  # Primary category for this employer
    job_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<Employer(id={self.id}, name='{self.name}', jobs={self.job_count})>"
    
    def to_dict(self):
        """Convert employer to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'job_count': self.job_count,
        }


class ScrapeLog(Base):
    """Log of each scrape run for tracking new jobs"""
    __tablename__ = 'scrape_logs'
    
    id = Column(Integer, primary_key=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    jobs_inserted = Column(Integer, default=0)  # New jobs added
    jobs_updated = Column(Integer, default=0)   # Existing jobs refreshed
    jobs_total = Column(Integer, default=0)     # Total active jobs after scrape
    jobs_deactivated = Column(Integer, default=0)  # Jobs marked inactive (stale)
    duration_seconds = Column(Integer)          # How long the scrape took
    new_job_urls = Column(Text)                 # JSON list of URLs for new jobs
    source_errors = Column(Text)                # JSON dict of source -> error message
    
    __table_args__ = (
        Index('idx_scrape_date', 'scraped_at'),
    )
    
    def __repr__(self):
        return f"<ScrapeLog(id={self.id}, date={self.scraped_at}, new={self.jobs_inserted})>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None,
            'jobs_inserted': self.jobs_inserted,
            'jobs_updated': self.jobs_updated,
            'jobs_total': self.jobs_total,
            'duration_seconds': self.duration_seconds,
        }
