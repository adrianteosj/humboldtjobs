"""
Category and Location Normalizer for standardizing job data across sources
"""
import re
from typing import Optional

from config import STANDARD_CATEGORIES


# Humboldt County cities for location normalization
HUMBOLDT_CITIES = {
    'eureka': 'Eureka, CA',
    'arcata': 'Arcata, CA',
    'fortuna': 'Fortuna, CA',
    'mckinleyville': 'McKinleyville, CA',
    'blue lake': 'Blue Lake, CA',
    'ferndale': 'Ferndale, CA',
    'rio dell': 'Rio Dell, CA',
    'trinidad': 'Trinidad, CA',
    'hoopa': 'Hoopa, CA',
    'willow creek': 'Willow Creek, CA',
    'garberville': 'Garberville, CA',
    'redway': 'Redway, CA',
    'miranda': 'Miranda, CA',
    'scotia': 'Scotia, CA',
    'fortuna': 'Fortuna, CA',
    'loleta': 'Loleta, CA',
    'fields landing': 'Fields Landing, CA',
    'samoa': 'Samoa, CA',
    'manila': 'Manila, CA',
    'cutten': 'Cutten, CA',
    'myrtletown': 'Myrtletown, CA',
    'kneeland': 'Kneeland, CA',
    'bridgeville': 'Bridgeville, CA',
    'petrolia': 'Petrolia, CA',
    'orleans': 'Orleans, CA',
    'weitchpec': 'Weitchpec, CA',
    'orick': 'Orick, CA',
    'klamath': 'Klamath, CA',
    'crescent city': 'Crescent City, CA',
    'smith river': 'Smith River, CA',
}

# Location aliases that map to standard city names
LOCATION_ALIASES = {
    'mck': 'McKinleyville, CA',
    'mckinleyville': 'McKinleyville, CA',
    'mc kinleyville': 'McKinleyville, CA',
    'e-ville': 'Eureka, CA',
    'main office': 'Eureka, CA',
    'humboldt': 'Humboldt County, CA',
    'all areas': 'Humboldt County, CA',
    'various': 'Humboldt County, CA',
    'multiple': 'Humboldt County, CA',
    'county-wide': 'Humboldt County, CA',
}


# Comprehensive employer-to-category mapping (based on EMPLOYER_DIRECTORY.md)
# This is the PRIMARY categorization method - employer determines category
EMPLOYER_CATEGORY_MAP = {
    # Government
    'County of Humboldt': 'Government',
    'City of Eureka': 'Government',
    'City of Arcata': 'Government',
    'City of Fortuna': 'Government',
    'City of Rio Dell': 'Government',
    'City of Blue Lake': 'Government',
    'City of Ferndale': 'Government',
    'City of Trinidad': 'Government',
    'Wiyot Tribe': 'Government',
    
    # Education
    'Cal Poly Humboldt': 'Education',
    'College of the Redwoods': 'Education',
    # EdJoin school districts will be mapped via partial match
    
    # Healthcare
    'Open Door Community Health': 'Healthcare',
    'Providence St. Joseph Hospital': 'Healthcare',
    'Providence Redwood Memorial': 'Healthcare',
    'Providence': 'Healthcare',
    'Mad River Community Hospital': 'Healthcare',
    'United Indian Health Services': 'Healthcare',
    "K'ima:w Medical Center": 'Healthcare',
    'Hospice of Humboldt': 'Healthcare',
    'Humboldt Senior Resource Center': 'Healthcare',
    'Redwood Community Action Agency': 'Healthcare',
    'SoHum Health': 'Healthcare',
    'Redwoods Rural Health Center': 'Healthcare',
    
    # Tribal Organizations
    'Yurok Tribe': 'Tribal Organizations',
    'Two Feathers NAFS': 'Tribal Organizations',
    'Two Feathers': 'Tribal Organizations',
    
    # Nonprofit & Social Services
    'Food for People': 'Nonprofit & Social Services',
    'Boys & Girls Club of the Redwoods': 'Nonprofit & Social Services',
    'Changing Tides Family Services': 'Nonprofit & Social Services',
    'Arcata House Partnership': 'Nonprofit & Social Services',
    'RCAA': 'Nonprofit & Social Services',
    
    # Local Retail
    'North Coast Co-op': 'Local Retail',
    'Eureka Natural Foods': 'Local Retail',
    "Murphy's Markets": 'Local Retail',
    'Pierson Building Center': 'Local Retail',
    'C. Crane Company': 'Local Retail',
    
    # National Retail
    'Walmart': 'National Retail',
    'Costco': 'National Retail',
    'Safeway': 'National Retail',
    'Albertsons': 'National Retail',
    'Dollar General': 'National Retail',
    'Walgreens': 'National Retail',
    'TJ Maxx': 'National Retail',
    'CVS Health': 'National Retail',
    'CVS': 'National Retail',
    'Rite Aid': 'National Retail',
    'Ace Hardware': 'National Retail',
    'WinCo Foods': 'National Retail',
    'Grocery Outlet': 'National Retail',
    'Harbor Freight Tools': 'National Retail',
    'Harbor Freight': 'National Retail',
    
    # Food & Agriculture
    'Humboldt Creamery': 'Food & Agriculture',
    'Crystal Creamery': 'Food & Agriculture',
    'Cypress Grove Chevre': 'Food & Agriculture',
    'Cypress Grove': 'Food & Agriculture',
    'Alexandre Family Farm': 'Food & Agriculture',
    "Driscoll's": 'Food & Agriculture',
    'Driscolls': 'Food & Agriculture',
    'Pacific Seafood': 'Food & Agriculture',
    'Pacific Choice Seafood': 'Food & Agriculture',
    
    # Food & Beverage
    'Lost Coast Brewery': 'Food & Beverage',
    'Starbucks': 'Food & Beverage',
    
    # Timber & Forestry
    'Humboldt Sawmill': 'Timber & Forestry',
    'Humboldt Redwood Company': 'Timber & Forestry',
    'Green Diamond Resource Company': 'Timber & Forestry',
    'Green Diamond': 'Timber & Forestry',
    'Sierra Pacific Industries': 'Timber & Forestry',
    'Jones Family Tree Service': 'Timber & Forestry',
    'Jones Tree': 'Timber & Forestry',
    
    # Manufacturing
    'Kokatat': 'Manufacturing',
    
    # Construction & Engineering
    'Danco Group': 'Construction & Engineering',
    'LACO Associates': 'Construction & Engineering',
    
    # Energy & Utilities
    'Redwood Coast Energy Authority': 'Energy & Utilities',
    'RCEA': 'Energy & Utilities',
    'Pacific Gas & Electric': 'Energy & Utilities',
    'PG&E': 'Energy & Utilities',
    
    # Transportation & Logistics
    'FedEx': 'Transportation & Logistics',
    'UPS': 'Transportation & Logistics',
    
    # Financial Services
    'Coast Central Credit Union': 'Financial Services',
    'Compass Community Credit Union': 'Financial Services',
    'Columbia Bank': 'Financial Services',
    'Redwood Capital Bank': 'Financial Services',
    'Tri Counties Bank': 'Financial Services',
    
    # Hospitality & Entertainment
    'Blue Lake Casino': 'Hospitality & Entertainment',
    'Blue Lake Casino & Hotel': 'Hospitality & Entertainment',
    'Bear River Casino': 'Hospitality & Entertainment',
    'Bear River Casino Resort': 'Hospitality & Entertainment',
}

# Partial match patterns for employers (for EdJoin school districts, etc.)
EMPLOYER_CATEGORY_PATTERNS = {
    'Education': [
        'school', 'district', 'unified', 'elementary', 'high school',
        'college', 'university', 'hcoe', 'county office of education',
    ],
    'Government': [
        'city of', 'county of', 'tribe', 'tribal',
    ],
}

# Fallback keyword mappings (only used if employer mapping doesn't match)
CATEGORY_KEYWORDS = {
    'Healthcare': [
        'nurse', 'nursing', 'medical', 'health', 'clinical', 'therapist',
        'physician', 'doctor', 'pharmacy', 'pharmacist', 'dental',
        'mental health', 'counselor', 'psychologist', 'social worker',
        'behavioral', 'patient', 'healthcare', 'rn', 'lpn', 'cna',
    ],
}


class CategoryNormalizer:
    """
    Normalizes job categories based on employer type (from EMPLOYER_DIRECTORY.md).
    Employer-based categorization is the PRIMARY method.
    """
    
    def __init__(self):
        self.employer_map = EMPLOYER_CATEGORY_MAP
        self.employer_patterns = EMPLOYER_CATEGORY_PATTERNS
        self.keywords = CATEGORY_KEYWORDS
        # Compile keyword patterns for efficiency
        self._compiled_patterns = {}
        for category, keywords in self.keywords.items():
            pattern = '|'.join(re.escape(kw) for kw in keywords)
            self._compiled_patterns[category] = re.compile(pattern, re.IGNORECASE)
    
    def _get_employer_category(self, employer: Optional[str]) -> Optional[str]:
        """Get category based on employer name."""
        if not employer:
            return None
        
        # Direct match first
        if employer in self.employer_map:
            return self.employer_map[employer]
        
        # Partial match - check if employer contains a known key
        employer_lower = employer.lower()
        for known_employer, category in self.employer_map.items():
            if known_employer.lower() in employer_lower or employer_lower in known_employer.lower():
                return category
        
        # Pattern-based matching (for school districts, etc.)
        for category, patterns in self.employer_patterns.items():
            for pattern in patterns:
                if pattern in employer_lower:
                    return category
        
        return None
    
    def normalize(self, title: str, original_category: Optional[str] = None, 
                  employer: Optional[str] = None) -> str:
        """
        Normalize a job to a standard category.
        
        PRIMARY method: Employer-based categorization
        FALLBACK: Keyword matching on title
        
        Args:
            title: Job title
            original_category: Original category from source (if any)
            employer: Employer name (PRIMARY categorization method)
            
        Returns:
            Standard category string
        """
        # PRIMARY: Employer-based categorization
        employer_category = self._get_employer_category(employer)
        if employer_category:
            return employer_category
        
        # FALLBACK: Keyword matching on title
        for category, pattern in self._compiled_patterns.items():
            if pattern.search(title):
                return category
        
        # Check original category directly if it matches a standard category
        if original_category:
            original_lower = original_category.lower()
            for std_cat in STANDARD_CATEGORIES:
                if std_cat.lower() in original_lower:
                    return std_cat
        
        # Ultimate fallback
        return 'Other'
    
    def normalize_job(self, job) -> str:
        """
        Normalize a JobData object's category.
        
        Args:
            job: JobData object with title, original_category, employer
            
        Returns:
            Standard category string
        """
        return self.normalize(
            title=job.title,
            original_category=job.original_category,
            employer=job.employer
        )


def normalize_category(title: str, original_category: Optional[str] = None,
                       employer: Optional[str] = None) -> str:
    """
    Convenience function for one-off category normalization.
    
    Args:
        title: Job title
        original_category: Original category from source
        employer: Employer name
        
    Returns:
        Standard category string
    """
    normalizer = CategoryNormalizer()
    return normalizer.normalize(title, original_category, employer)


class LocationNormalizer:
    """
    Normalizes job locations to consistent "City, CA" format.
    Handles various input formats and typos.
    """
    
    def __init__(self):
        self.cities = HUMBOLDT_CITIES
        self.aliases = LOCATION_ALIASES
    
    def normalize(self, location: Optional[str]) -> str:
        """
        Normalize a location string to "City, CA" format.
        
        Args:
            location: Raw location string from scraper
            
        Returns:
            Normalized location string
        """
        if not location:
            return "Humboldt County, CA"
        
        # Clean up the location string
        location = location.strip()
        original = location
        location_lower = location.lower()
        
        # Check aliases first (but only exact matches for generic terms)
        for alias, normalized in self.aliases.items():
            if location_lower == alias or location_lower.startswith(alias + ' '):
                return normalized
        
        # First, try to extract city from common formats BEFORE removing parts
        # Handle "City, Humboldt County, CA" format
        match = re.match(r'^([A-Za-z\s]+),\s*Humboldt\s+County,?\s*(CA|California)?', location, re.IGNORECASE)
        if match:
            city_name = match.group(1).strip()
            city_key = city_name.lower().replace(' ', ' ')
            # Check if it's a known city
            for known_city, normalized in self.cities.items():
                if known_city in city_key or city_key in known_city:
                    return normalized
            # If city name looks valid, use it
            if len(city_name) > 2 and city_name.replace(' ', '').isalpha():
                return f"{city_name.title()}, CA"
        
        # Handle "Location Name - City, CA ZIP" format (e.g., "Main Office - Eureka, CA 95503")
        match = re.match(r'^.+[-–—]\s*([A-Za-z\s]+),\s*(CA|California)\s*\d*', location, re.IGNORECASE)
        if match:
            city_name = match.group(1).strip()
            city_key = city_name.lower()
            for known_city, normalized in self.cities.items():
                if known_city in city_key or city_key in known_city:
                    return normalized
            if len(city_name) > 2:
                return f"{city_name.title()}, CA"
        
        # Handle "ECHC Eureka Community Health Center" type locations
        for city_key, city_normalized in self.cities.items():
            if city_key in location_lower:
                return city_normalized
        
        # Clean up remaining formats
        location = re.sub(r'\s+\d{5}(-\d{4})?$', '', location)  # Remove ZIP codes
        location = re.sub(r',?\s*(US|USA|United States)$', '', location, flags=re.IGNORECASE)
        location = location.strip(' ,')
        
        location_lower = location.lower()
        
        # Handle "City, California" or "City, CA" format
        match = re.match(r'^([A-Za-z\s]+),?\s*(California|CA)$', location, re.IGNORECASE)
        if match:
            city_name = match.group(1).strip().title()
            city_key = city_name.lower()
            if city_key in self.cities:
                return self.cities[city_key]
            # Handle McKinleyville capitalization
            if city_key == 'mckinleyville':
                return 'McKinleyville, CA'
            return f"{city_name}, CA"
        
        # Handle just city name
        for city_key, city_normalized in self.cities.items():
            if location_lower == city_key:
                return city_normalized
        
        # If location looks like a city name (single word or two words), standardize it
        if re.match(r'^[A-Za-z]+(\s+[A-Za-z]+)?$', location):
            city_name = location.title()
            # Handle McKinleyville capitalization
            if city_name.lower() == 'mckinleyville':
                return 'McKinleyville, CA'
            return f"{city_name}, CA"
        
        # If nothing matches, check if original had a recognizable city
        for city_key, city_normalized in self.cities.items():
            if city_key in original.lower():
                return city_normalized
        
        # Default fallback
        return "Humboldt County, CA"


def normalize_location(location: Optional[str]) -> str:
    """
    Convenience function for one-off location normalization.
    
    Args:
        location: Raw location string
        
    Returns:
        Normalized location string in "City, CA" format
    """
    normalizer = LocationNormalizer()
    return normalizer.normalize(location)


# Job Classification System (sub-categories within main categories)
# These allow users to filter within a category (e.g., Education -> Teaching vs Support Staff)

CLASSIFICATION_RULES = {
    'Education': {
        'Teaching': [
            'teacher', 'instructor', 'professor', 'faculty', 'lecturer',
            'teaching', 'tutor', 'coach', 'substitute', 'certificated',
            'english', 'math', 'science', 'history', 'art', 'music', 'pe ',
            'special education', 'sped', 'credential',
        ],
        'Support Staff': [
            'custodian', 'janitor', 'cook', 'food service', 'bus driver',
            'driver', 'aide', 'paraprofessional', 'para ',
            'secretary', 'clerk', 'office', 'receptionist', 'attendance',
            'maintenance', 'groundskeeper', 'custodial', 'cafeteria',
            'nutrition', 'transportation', 'classified',
        ],
        'Administration': [
            'principal', 'superintendent', 'director', 'coordinator',
            'administrator', 'manager', 'dean', 'vice principal',
            'assistant superintendent', 'cabinet', 'executive', 'chief',
        ],
        'Student Employment': [
            'student assistant', 'instructional student assistant',
            'teaching associate', 'graduate assistant', 'student worker',
            'work-study', 'work study', 'student aide', 'student tutor',
        ],
    },
    'Healthcare': {
        'Clinical': [
            'nurse', 'rn', 'lpn', 'cna', 'physician', 'doctor', 'md',
            'therapist', 'clinical', 'medical assistant', 'ma ',
            'phlebotomist', 'lab', 'radiology', 'x-ray', 'technician',
            'dental', 'dentist', 'hygienist', 'pharmacist', 'pharmacy',
            'patient care', 'caregiver', 'behavioral health', 'counselor',
            'psychologist', 'psychiatrist', 'social worker', 'lcsw', 'mft',
        ],
        'Administrative': [
            'billing', 'coder', 'medical records', 'registration',
            'receptionist', 'front desk', 'scheduler', 'authorization',
            'insurance', 'revenue', 'collections', 'hr ', 'human resources',
            'payroll', 'accounting', 'finance', 'administrative',
        ],
        'Support': [
            'housekeeper', 'environmental', 'food service', 'dietary',
            'maintenance', 'facilities', 'security', 'transport',
            'warehouse', 'supply', 'it ', 'information technology',
        ],
    },
    'Government': {
        'Public Safety': [
            'police', 'officer', 'sheriff', 'deputy', 'fire', 'firefighter',
            'emt', 'paramedic', 'dispatcher', '911', 'corrections',
            'probation', 'animal control', 'code enforcement',
        ],
        'Administrative': [
            'clerk', 'secretary', 'administrative', 'assistant',
            'receptionist', 'office', 'coordinator', 'specialist',
            'analyst', 'accountant', 'hr ', 'human resources',
        ],
        'Technical': [
            'engineer', 'planner', 'surveyor', 'gis', 'it ', 'programmer',
            'developer', 'technician', 'inspector', 'environmental',
        ],
        'Maintenance': [
            'maintenance', 'mechanic', 'equipment', 'operator',
            'groundskeeper', 'custodian', 'facilities', 'utility',
        ],
    },
    'National Retail': {
        'Store Operations': [
            'cashier', 'sales', 'associate', 'team member', 'customer service',
            'stocker', 'merchandiser', 'retail', 'floor', 'department',
        ],
        'Management': [
            'manager', 'supervisor', 'lead', 'assistant manager', 'team lead',
            'shift lead', 'department manager', 'store manager',
        ],
        'Warehouse': [
            'warehouse', 'forklift', 'shipping', 'receiving', 'inventory',
            'loader', 'unloader', 'distribution', 'logistics',
        ],
    },
    'Local Retail': {
        'Store Operations': [
            'cashier', 'sales', 'associate', 'team member', 'customer service',
            'stocker', 'merchandiser', 'retail', 'floor', 'department',
            'deli', 'bakery', 'produce', 'meat', 'grocery',
        ],
        'Management': [
            'manager', 'supervisor', 'lead', 'assistant manager', 'team lead',
        ],
    },
}


class JobClassifier:
    """
    Classifies jobs into sub-categories within their main category.
    E.g., Education jobs -> Teaching, Support Staff, or Administration
    """
    
    def __init__(self):
        self.rules = CLASSIFICATION_RULES
        # Pre-compile patterns for efficiency
        self._compiled = {}
        for category, subcats in self.rules.items():
            self._compiled[category] = {}
            for subcat, keywords in subcats.items():
                pattern = '|'.join(re.escape(kw) for kw in keywords)
                self._compiled[category][subcat] = re.compile(pattern, re.IGNORECASE)
    
    def classify(self, title: str, category: str) -> Optional[str]:
        """
        Classify a job title into a sub-category.
        
        Args:
            title: Job title
            category: Main category (e.g., "Education")
            
        Returns:
            Sub-category string (e.g., "Teaching") or None if no match
        """
        if category not in self._compiled:
            return None
        
        title_lower = title.lower()
        
        # Priority order for sub-categories (check these first)
        # Student Employment should be checked before Teaching because
        # "Instructional Student Assistant" contains "instructor"
        priority_order = ['Student Employment', 'Administration', 'Management']
        
        # Check priority sub-categories first
        for subcat in priority_order:
            if subcat in self._compiled[category]:
                if self._compiled[category][subcat].search(title_lower):
                    return subcat
        
        # Check remaining sub-categories
        for subcat, pattern in self._compiled[category].items():
            if subcat in priority_order:
                continue  # Already checked
            if pattern.search(title_lower):
                return subcat
        
        return None
    
    def get_subcategories(self, category: str) -> list:
        """
        Get list of available sub-categories for a main category.
        
        Args:
            category: Main category name
            
        Returns:
            List of sub-category names
        """
        return list(self.rules.get(category, {}).keys())


def classify_job(title: str, category: str) -> Optional[str]:
    """
    Convenience function for one-off job classification.
    
    Args:
        title: Job title
        category: Main category
        
    Returns:
        Sub-category string or None
    """
    classifier = JobClassifier()
    return classifier.classify(title, category)
