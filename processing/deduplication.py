"""
Deduplication logic for job listings
"""
import re
from typing import List, Set, Tuple
from difflib import SequenceMatcher


def normalize_title(title: str) -> str:
    """
    Normalize a job title for comparison.
    
    Args:
        title: Original job title
        
    Returns:
        Normalized title string
    """
    # Convert to lowercase
    normalized = title.lower()
    # Remove punctuation
    normalized = re.sub(r'[^\w\s]', '', normalized)
    # Normalize whitespace
    normalized = ' '.join(normalized.split())
    return normalized


def normalize_employer(employer: str) -> str:
    """
    Normalize an employer name for comparison.
    
    Args:
        employer: Original employer name
        
    Returns:
        Normalized employer string
    """
    # Convert to lowercase
    normalized = employer.lower()
    # Remove common suffixes
    suffixes = ['inc', 'llc', 'corp', 'corporation', 'company', 'co']
    for suffix in suffixes:
        normalized = re.sub(rf'\b{suffix}\b\.?', '', normalized)
    # Remove punctuation
    normalized = re.sub(r'[^\w\s]', '', normalized)
    # Normalize whitespace
    normalized = ' '.join(normalized.split())
    return normalized


def generate_job_key(title: str, employer: str) -> Tuple[str, str]:
    """
    Generate a normalized key for deduplication.
    
    Args:
        title: Job title
        employer: Employer name
        
    Returns:
        Tuple of (normalized_title, normalized_employer)
    """
    return (normalize_title(title), normalize_employer(employer))


def is_similar(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """
    Check if two job titles are similar enough to be duplicates.
    
    Args:
        title1: First title
        title2: Second title
        threshold: Similarity threshold (0.0 to 1.0)
        
    Returns:
        True if titles are similar
    """
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    # Exact match after normalization
    if norm1 == norm2:
        return True
    
    # Use sequence matching for fuzzy comparison
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio >= threshold


def deduplicate_jobs(jobs: List, key_func=None) -> List:
    """
    Remove duplicate jobs from a list.
    
    Args:
        jobs: List of JobData objects
        key_func: Optional function to generate dedup key (default: title + employer)
        
    Returns:
        Deduplicated list of jobs
    """
    if key_func is None:
        key_func = lambda j: generate_job_key(j.title, j.employer)
    
    seen: Set[Tuple[str, str]] = set()
    unique_jobs = []
    
    for job in jobs:
        key = key_func(job)
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    return unique_jobs


def deduplicate_by_url(jobs: List) -> List:
    """
    Remove duplicate jobs by URL.
    
    Args:
        jobs: List of JobData objects
        
    Returns:
        Deduplicated list of jobs
    """
    seen_urls: Set[str] = set()
    unique_jobs = []
    
    for job in jobs:
        # Normalize URL for comparison
        url = job.url.lower().rstrip('/')
        if url not in seen_urls:
            seen_urls.add(url)
            unique_jobs.append(job)
    
    return unique_jobs
