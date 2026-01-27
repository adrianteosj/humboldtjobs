"""
AI-Powered Data Extraction Fallback

Uses Gemini AI to extract salary, description, and other job data
when regex-based extraction fails.

Token-efficient design:
- Only called as fallback when regex fails
- Batches multiple extractions per API call
- Uses focused prompts to minimize token usage
- Caches results to avoid duplicate calls
"""

import os
import json
import logging
import hashlib
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed - AI extraction unavailable")


@dataclass
class ExtractionResult:
    """Result from AI extraction"""
    salary_text: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_type: Optional[str] = None  # hourly, annual
    description: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    confidence: float = 0.0


# Simple in-memory cache to avoid duplicate API calls
_extraction_cache: Dict[str, ExtractionResult] = {}


def _get_cache_key(page_text: str) -> str:
    """Generate cache key from page text."""
    # Use hash of first 5000 chars to identify unique pages
    text_sample = page_text[:5000] if len(page_text) > 5000 else page_text
    return hashlib.md5(text_sample.encode()).hexdigest()


def is_ai_available() -> bool:
    """Check if AI extraction is available."""
    if not GEMINI_AVAILABLE:
        return False
    
    api_key = os.environ.get('GEMINI_API_KEY')
    return bool(api_key)


def extract_with_ai(
    page_text: str,
    job_title: str = "",
    extract_salary: bool = True,
    extract_description: bool = False,
    extract_location: bool = False
) -> Optional[ExtractionResult]:
    """
    Extract job data from page text using Gemini AI.
    
    This is a fallback method - only use when regex extraction fails.
    
    Args:
        page_text: Raw text from the job page
        job_title: Optional job title for context
        extract_salary: Whether to extract salary info
        extract_description: Whether to extract job description
        extract_location: Whether to extract location
        
    Returns:
        ExtractionResult or None if AI unavailable/fails
    """
    if not is_ai_available():
        logger.debug("AI extraction not available")
        return None
    
    # Check cache
    cache_key = _get_cache_key(page_text)
    if cache_key in _extraction_cache:
        logger.debug("Using cached AI extraction result")
        return _extraction_cache[cache_key]
    
    try:
        # Configure Gemini
        api_key = os.environ.get('GEMINI_API_KEY')
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Truncate text to save tokens (focus on first ~2000 chars which usually contains key info)
        truncated_text = page_text[:3000] if len(page_text) > 3000 else page_text
        
        # Build focused prompt
        fields_to_extract = []
        if extract_salary:
            fields_to_extract.append('"salary_text": "hourly or annual salary range as string",')
            fields_to_extract.append('"salary_min": number (hourly rate or annual if no hourly),')
            fields_to_extract.append('"salary_max": number,')
            fields_to_extract.append('"salary_type": "hourly" or "annual",')
        if extract_description:
            fields_to_extract.append('"description": "brief job description (max 200 chars)",')
        if extract_location:
            fields_to_extract.append('"location": "city, state format",')
        
        prompt = f"""Extract job information from this text. Return JSON only.

JOB TITLE: {job_title or "Unknown"}

TEXT:
{truncated_text}

Return ONLY valid JSON with these fields (use null if not found):
{{
{chr(10).join(fields_to_extract)}
"confidence": 0.0 to 1.0 how confident you are
}}

RULES:
- For salary, prefer hourly rates if available
- Convert "per hour" to hourly, "per year" to annual
- If salary shows "$XX.XX - $YY.YY" format, extract both min and max
- For single salary like "$16.90 per hour", set both min and max to same value
- Return null for any field you cannot find

JSON ONLY:"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse JSON response
        # Clean up response (remove markdown code blocks if present)
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        data = json.loads(response_text)
        
        result = ExtractionResult(
            salary_text=data.get('salary_text'),
            salary_min=data.get('salary_min'),
            salary_max=data.get('salary_max'),
            salary_type=data.get('salary_type'),
            description=data.get('description'),
            location=data.get('location'),
            job_type=data.get('job_type'),
            confidence=data.get('confidence', 0.5)
        )
        
        # Cache result
        _extraction_cache[cache_key] = result
        
        logger.debug(f"AI extraction result: salary={result.salary_text}, confidence={result.confidence}")
        return result
        
    except json.JSONDecodeError as e:
        logger.warning(f"AI extraction returned invalid JSON: {e}")
        return None
    except Exception as e:
        logger.warning(f"AI extraction failed: {e}")
        return None


def batch_extract_salaries(
    jobs: List[Dict[str, str]],
    max_batch_size: int = 5
) -> Dict[str, ExtractionResult]:
    """
    Extract salary information for multiple jobs in a single API call.
    
    This is more token-efficient than calling extract_with_ai for each job.
    
    Args:
        jobs: List of dicts with 'id', 'title', 'page_text' keys
        max_batch_size: Maximum jobs per API call (default 5)
        
    Returns:
        Dict mapping job id to ExtractionResult
    """
    if not is_ai_available() or not jobs:
        return {}
    
    results = {}
    
    # Process in batches
    for i in range(0, len(jobs), max_batch_size):
        batch = jobs[i:i + max_batch_size]
        batch_results = _batch_extract_impl(batch)
        results.update(batch_results)
    
    return results


def _batch_extract_impl(jobs: List[Dict[str, str]]) -> Dict[str, ExtractionResult]:
    """Implementation of batch extraction."""
    try:
        api_key = os.environ.get('GEMINI_API_KEY')
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Build batch prompt
        job_sections = []
        for job in jobs:
            # Truncate each job's text to ~500 chars to fit more in batch
            text_sample = job.get('page_text', '')[:800]
            job_sections.append(f"""
JOB ID: {job['id']}
TITLE: {job.get('title', 'Unknown')}
TEXT SAMPLE:
{text_sample}
---""")
        
        prompt = f"""Extract salary information from these job postings. Return JSON array.

{chr(10).join(job_sections)}

Return ONLY a JSON array with one object per job:
[
  {{"id": "job_id", "salary_text": "$X - $Y/hr", "salary_min": number, "salary_max": number, "salary_type": "hourly"/"annual"}},
  ...
]

Use null for fields you cannot find. JSON ONLY:"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up response
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        data = json.loads(response_text)
        
        results = {}
        for item in data:
            job_id = item.get('id')
            if job_id:
                results[job_id] = ExtractionResult(
                    salary_text=item.get('salary_text'),
                    salary_min=item.get('salary_min'),
                    salary_max=item.get('salary_max'),
                    salary_type=item.get('salary_type'),
                    confidence=0.8
                )
        
        return results
        
    except Exception as e:
        logger.warning(f"Batch AI extraction failed: {e}")
        return {}


def clear_cache():
    """Clear the extraction cache."""
    global _extraction_cache
    _extraction_cache = {}
    logger.debug("AI extraction cache cleared")
