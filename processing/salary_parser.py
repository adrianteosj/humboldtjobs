"""
Salary Parser Module

Parses salary strings into structured data with min/max values normalized to annual amounts.
"""

import re
from typing import Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class ParsedSalary:
    """Structured salary data"""
    min_annual: Optional[int] = None  # Minimum salary as annual amount
    max_annual: Optional[int] = None  # Maximum salary as annual amount
    salary_type: Optional[str] = None  # hourly, monthly, annual, daily
    original_text: str = ""


class SalaryParser:
    """Parse salary text strings into structured data"""
    
    # Hours per year for hourly to annual conversion (40hr/wk * 52 weeks)
    HOURS_PER_YEAR = 2080
    # Months per year
    MONTHS_PER_YEAR = 12
    # Work days per year (approx)
    DAYS_PER_YEAR = 260
    
    # Common DOE/DOQ patterns (Depends on Experience/Qualifications)
    DOE_PATTERNS = [
        r'\bDOE\b', r'\bDOQ\b', r'\bD\.O\.E\b', r'\bD\.O\.Q\b',
        r'depends?\s+on\s+(experience|qualifications)',
        r'commensurate\s+with\s+experience',
        r'negotiable', r'competitive'
    ]
    
    # Patterns indicating per-hour rates
    HOURLY_INDICATORS = [
        r'/\s*hr\b', r'/\s*hour', r'per\s+hour', r'hourly',
        r'/\s*h\b', r'an\s+hour'
    ]
    
    # Patterns indicating monthly rates
    MONTHLY_INDICATORS = [
        r'/\s*mo\b', r'/\s*month', r'per\s+month', r'monthly',
        r'/\s*mon\b'
    ]
    
    # Patterns indicating annual rates
    ANNUAL_INDICATORS = [
        r'/\s*yr\b', r'/\s*year', r'per\s+year', r'annually',
        r'annual', r'/\s*annum', r'p\.a\.'
    ]
    
    # Patterns indicating daily rates
    DAILY_INDICATORS = [
        r'/\s*day', r'per\s+day', r'daily', r'/\s*diem'
    ]
    
    def parse(self, salary_text: Optional[str]) -> ParsedSalary:
        """
        Parse a salary string into structured data.
        
        Args:
            salary_text: Raw salary string (e.g., "$25.50 - $32.00/hr")
            
        Returns:
            ParsedSalary with min/max annual values and type
        """
        result = ParsedSalary(original_text=salary_text or "")
        
        if not salary_text:
            return result
        
        text = salary_text.lower().strip()
        
        # Check for DOE/DOQ patterns - return empty if salary is negotiable
        for pattern in self.DOE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return result
        
        # Detect salary type
        salary_type = self._detect_salary_type(text)
        result.salary_type = salary_type
        
        # Extract numeric values
        min_val, max_val = self._extract_values(text)
        
        if min_val is None:
            return result
        
        # Normalize to annual
        if salary_type == 'hourly':
            result.min_annual = int(min_val * self.HOURS_PER_YEAR)
            result.max_annual = int(max_val * self.HOURS_PER_YEAR) if max_val else result.min_annual
        elif salary_type == 'monthly':
            result.min_annual = int(min_val * self.MONTHS_PER_YEAR)
            result.max_annual = int(max_val * self.MONTHS_PER_YEAR) if max_val else result.min_annual
        elif salary_type == 'daily':
            result.min_annual = int(min_val * self.DAYS_PER_YEAR)
            result.max_annual = int(max_val * self.DAYS_PER_YEAR) if max_val else result.min_annual
        else:  # annual or unknown (assume annual for large numbers)
            result.min_annual = int(min_val)
            result.max_annual = int(max_val) if max_val else result.min_annual
            if result.salary_type is None:
                result.salary_type = 'annual'
        
        return result
    
    def _detect_salary_type(self, text: str) -> Optional[str]:
        """Detect the salary type (hourly, monthly, annual, daily)"""
        for pattern in self.HOURLY_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                return 'hourly'
        
        for pattern in self.MONTHLY_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                return 'monthly'
        
        for pattern in self.ANNUAL_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                return 'annual'
        
        for pattern in self.DAILY_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                return 'daily'
        
        return None
    
    def _extract_values(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract numeric salary values from text.
        
        Returns:
            Tuple of (min_value, max_value) or (single_value, None)
        """
        # Remove dollar signs and commas, keeping decimals
        clean_text = text.replace('$', '').replace(',', '')
        
        # Pattern for numbers (with optional decimals)
        number_pattern = r'(\d+(?:\.\d+)?)'
        
        # Find all numbers
        numbers = re.findall(number_pattern, clean_text)
        
        if not numbers:
            return None, None
        
        # Convert to floats
        values = [float(n) for n in numbers]
        
        # Filter out unreasonably small numbers (likely not salaries)
        # and very large numbers (likely not salaries either)
        values = [v for v in values if v >= 7 or v >= 1000]  # Min wage or annual salary
        
        if not values:
            return None, None
        
        # If we have a range pattern, look for "to", "-", "through"
        range_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:-|to|through)\s*(\d+(?:,\d{3})*(?:\.\d+)?)', clean_text)
        if range_match:
            min_val = float(range_match.group(1).replace(',', ''))
            max_val = float(range_match.group(2).replace(',', ''))
            return min_val, max_val
        
        # If only one value, return it
        if len(values) == 1:
            return values[0], None
        
        # If two values, assume min and max
        if len(values) == 2:
            return min(values), max(values)
        
        # If more values, take the reasonable range
        # (excluding very small numbers that might be hours or other metadata)
        salary_values = [v for v in values if v >= 10]
        if len(salary_values) >= 2:
            return min(salary_values), max(salary_values)
        elif salary_values:
            return salary_values[0], None
        
        return values[0], None
    
    def normalize_to_annual(self, value: float, salary_type: str) -> int:
        """
        Convert a salary value to annual equivalent.
        
        Args:
            value: The salary value
            salary_type: Type of salary (hourly, monthly, annual, daily)
            
        Returns:
            Annual salary as integer
        """
        if salary_type == 'hourly':
            return int(value * self.HOURS_PER_YEAR)
        elif salary_type == 'monthly':
            return int(value * self.MONTHS_PER_YEAR)
        elif salary_type == 'daily':
            return int(value * self.DAYS_PER_YEAR)
        else:
            return int(value)


# Module-level instance for convenience
_parser = SalaryParser()


def parse_salary(salary_text: Optional[str]) -> ParsedSalary:
    """
    Parse a salary string into structured data.
    
    Args:
        salary_text: Raw salary string
        
    Returns:
        ParsedSalary object with min/max annual values
    """
    return _parser.parse(salary_text)


def extract_salary_range(salary_text: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Extract salary range from text as a tuple.
    
    Args:
        salary_text: Raw salary string
        
    Returns:
        Tuple of (min_annual, max_annual, salary_type)
    """
    result = _parser.parse(salary_text)
    return result.min_annual, result.max_annual, result.salary_type
