"""
PDF Scraper Module

Downloads and extracts structured data from PDF job postings.
"""

import re
import io
import logging
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    pdfplumber = None

from .salary_parser import parse_salary
from .experience_detector import detect_experience

logger = logging.getLogger(__name__)


@dataclass
class PDFJobData:
    """Extracted job data from PDF"""
    title: Optional[str] = None
    employer: Optional[str] = None
    location: Optional[str] = None
    salary_text: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_type: Optional[str] = None
    job_type: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    education: Optional[str] = None
    experience_level: Optional[str] = None
    department: Optional[str] = None
    closing_date: Optional[str] = None
    raw_text: str = ""


class PDFScraper:
    """Download and extract job data from PDF files"""
    
    # Common section headers in job posting PDFs
    SECTION_PATTERNS = {
        'title': [
            r'(?:position|job)\s*(?:title)?[:]\s*(.+?)(?:\n|$)',
            r'^([A-Z][A-Z\s]+)$',  # All caps title at top
        ],
        'salary': [
            r'(?:salary|wage|pay|compensation)[\s:]*\$?([\d,.\s\-/]+(?:per\s+(?:hour|year|month|annum))?[^\n]*)',
            r'\$\s*([\d,]+(?:\.\d{2})?)\s*(?:-|to)\s*\$?\s*([\d,]+(?:\.\d{2})?)',
            r'(?:hourly|annual|monthly)\s*(?:rate|salary)?[\s:]*\$?([\d,.\s\-]+)',
        ],
        'location': [
            r'(?:location|work\s*location|job\s*location)[\s:]*(.+?)(?:\n|$)',
            r'(?:city|address)[\s:]*(.+?)(?:\n|$)',
        ],
        'department': [
            r'(?:department|division|unit)[\s:]*(.+?)(?:\n|$)',
        ],
        'job_type': [
            r'(?:employment\s*type|job\s*type|status)[\s:]*(.+?)(?:\n|$)',
            r'\b(full[\s-]?time|part[\s-]?time|temporary|seasonal|permanent)\b',
        ],
        'closing_date': [
            r'(?:closing|deadline|apply\s*by|applications?\s*due)[\s:]*(.+?)(?:\n|$)',
            r'(?:close[sd]?|ends?)[\s:]*(.+?)(?:\n|$)',
        ],
        'requirements': [
            r'(?:requirements?|qualifications?|minimum\s*qualifications?)[\s:]*\n((?:.+\n?)+?)(?=\n\s*\n|\Z)',
            r'(?:required|must\s*have)[\s:]*\n((?:.+\n?)+?)(?=\n\s*\n|\Z)',
        ],
        'benefits': [
            r'(?:benefits?|perks?)[\s:]*\n((?:.+\n?)+?)(?=\n\s*\n|\Z)',
        ],
        'description': [
            r'(?:description|summary|overview|about\s*(?:the|this)\s*(?:position|role|job))[\s:]*\n((?:.+\n?)+?)(?=\n\s*\n|\Z)',
            r'(?:duties|responsibilities)[\s:]*\n((?:.+\n?)+?)(?=\n\s*\n|\Z)',
        ],
    }
    
    # Headers to look for
    USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) HumboldtJobs/1.0'
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        if not PDF_AVAILABLE:
            logger.warning("pdfplumber not installed. PDF scraping will be disabled.")
    
    def scrape_pdf(self, url: str) -> Optional[PDFJobData]:
        """
        Download and extract job data from a PDF URL.
        
        Args:
            url: URL to PDF file
            
        Returns:
            PDFJobData with extracted information or None on failure
        """
        if not PDF_AVAILABLE:
            logger.error("pdfplumber not installed. Run: pip install pdfplumber")
            return None
        
        try:
            # Download PDF
            pdf_content = self._download_pdf(url)
            if not pdf_content:
                return None
            
            # Extract text
            text = self._extract_text(pdf_content)
            if not text:
                logger.warning(f"No text extracted from PDF: {url}")
                return None
            
            # Parse structured data
            return self._parse_text(text)
            
        except Exception as e:
            logger.error(f"Error scraping PDF {url}: {e}")
            return None
    
    def scrape_pdf_bytes(self, pdf_bytes: bytes) -> Optional[PDFJobData]:
        """
        Extract job data from PDF bytes directly.
        
        Args:
            pdf_bytes: Raw PDF content
            
        Returns:
            PDFJobData with extracted information
        """
        if not PDF_AVAILABLE:
            logger.error("pdfplumber not installed")
            return None
        
        try:
            text = self._extract_text(pdf_bytes)
            if not text:
                return None
            return self._parse_text(text)
        except Exception as e:
            logger.error(f"Error parsing PDF bytes: {e}")
            return None
    
    def _download_pdf(self, url: str) -> Optional[bytes]:
        """Download PDF from URL"""
        try:
            response = requests.get(
                url,
                headers={'User-Agent': self.USER_AGENT},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Verify it's a PDF
            content_type = response.headers.get('content-type', '')
            if 'pdf' not in content_type.lower() and not url.lower().endswith('.pdf'):
                logger.warning(f"URL may not be a PDF: {url} (content-type: {content_type})")
            
            return response.content
            
        except requests.RequestException as e:
            logger.error(f"Failed to download PDF from {url}: {e}")
            return None
    
    def _extract_text(self, pdf_content: bytes) -> Optional[str]:
        """Extract text from PDF content"""
        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                return '\n'.join(text_parts)
                
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return None
    
    def _parse_text(self, text: str) -> PDFJobData:
        """Parse extracted text into structured data"""
        result = PDFJobData(raw_text=text)
        
        # Extract each field using patterns
        for field, patterns in self.SECTION_PATTERNS.items():
            value = self._extract_field(text, patterns)
            if value:
                if field == 'salary':
                    result.salary_text = value
                    # Parse salary into structured data
                    parsed = parse_salary(value)
                    result.salary_min = parsed.min_annual
                    result.salary_max = parsed.max_annual
                    result.salary_type = parsed.salary_type
                elif hasattr(result, field):
                    setattr(result, field, value)
        
        # Detect experience level from title and requirements
        if result.title or result.requirements:
            exp_info = detect_experience(
                result.title or '',
                result.description,
                result.requirements
            )
            result.experience_level = exp_info.level
            if exp_info.education:
                result.education = exp_info.education
        
        # Try to extract title from first line if not found
        if not result.title:
            lines = text.strip().split('\n')
            for line in lines[:5]:  # Check first 5 lines
                line = line.strip()
                # Title is usually short and may be in caps
                if line and len(line) < 100 and len(line) > 3:
                    if line.isupper() or line[0].isupper():
                        result.title = line
                        break
        
        return result
    
    def _extract_field(self, text: str, patterns: list) -> Optional[str]:
        """Extract a field value using patterns"""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
                value = value.strip()
                # Clean up common issues
                value = re.sub(r'\s+', ' ', value)  # Normalize whitespace
                if value and len(value) > 2:
                    return value
        return None


# Module-level instance for convenience
_scraper = PDFScraper()


def scrape_pdf(url: str) -> Optional[PDFJobData]:
    """
    Download and extract job data from a PDF URL.
    
    Args:
        url: URL to PDF file
        
    Returns:
        PDFJobData with extracted information or None
    """
    return _scraper.scrape_pdf(url)


def scrape_pdf_bytes(pdf_bytes: bytes) -> Optional[PDFJobData]:
    """
    Extract job data from PDF bytes.
    
    Args:
        pdf_bytes: Raw PDF content
        
    Returns:
        PDFJobData with extracted information or None
    """
    return _scraper.scrape_pdf_bytes(pdf_bytes)


def is_pdf_available() -> bool:
    """Check if PDF scraping is available (pdfplumber installed)"""
    return PDF_AVAILABLE
