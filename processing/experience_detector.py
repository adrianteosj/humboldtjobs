"""
Experience Level Detector Module

Detects experience level from job titles and requirements text.
"""

import re
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass 
class ExperienceInfo:
    """Detected experience information"""
    level: Optional[str] = None  # Entry, Mid, Senior
    years_min: Optional[int] = None  # Minimum years if specified
    years_max: Optional[int] = None  # Maximum years if specified
    education: Optional[str] = None  # Detected education requirement
    confidence: float = 0.0  # Confidence score 0-1


class ExperienceDetector:
    """Detect experience level from job information"""
    
    # Entry-level indicators (with confidence weights)
    ENTRY_PATTERNS = [
        (r'\bentry[\s-]?level\b', 1.0),
        (r'\bentry\b', 0.8),
        (r'\bjunior\b', 0.9),
        (r'\bjr\.?\b', 0.8),
        (r'\btrainee\b', 1.0),
        (r'\bintern\b', 1.0),
        (r'\binternship\b', 1.0),
        (r'\bapprentice\b', 1.0),
        (r'\bassociate\s+(?!director|dean|professor)', 0.6),
        (r'\bassistant\s+(?!director|dean|professor|manager|superintendent)', 0.5),
        (r'\bno\s+experience\s+(?:required|necessary|needed)\b', 1.0),
        (r'\b0[\s-]+(?:to[\s-]+)?[12]\s+years?\b', 0.9),
        (r'\blevel\s+[i1]\b', 0.9),
        (r'\bgrade\s+[i1]\b', 0.8),
        (r'\bI\b(?:\s|$)', 0.6),  # Roman numeral I at word boundary
        (r'\baide\b', 0.7),
        (r'\bclerk\b', 0.5),
    ]
    
    # Mid-level indicators
    MID_PATTERNS = [
        (r'\bmid[\s-]?level\b', 1.0),
        (r'\bintermediate\b', 0.9),
        (r'\blevel\s+(?:2|ii)\b', 0.9),
        (r'\bgrade\s+(?:2|ii)\b', 0.8),
        (r'\bII\b', 0.7),  # Roman numeral II
        (r'\b[2-4]\s*(?:-|to)\s*[3-6]\s+years?\b', 0.8),
        (r'\b(?:2|3|4)\s*\+?\s+years?\s+(?:of\s+)?experience\b', 0.8),
        (r'\bexperienced\b', 0.5),
        (r'\bspecialist\b', 0.5),
        (r'\bcoordinator\b', 0.4),
        (r'\banalyst\b', 0.4),
    ]
    
    # Senior-level indicators
    SENIOR_PATTERNS = [
        (r'\bsenior\b', 1.0),
        (r'\bsr\.?\b', 0.9),
        (r'\blead\b', 0.8),
        (r'\bprincipal\b', 0.9),
        (r'\bmanager\b', 0.7),
        (r'\bdirector\b', 0.9),
        (r'\bsupervisor\b', 0.7),
        (r'\bsuperintendent\b', 0.9),
        (r'\bexecutive\b', 0.9),
        (r'\bchief\b', 1.0),
        (r'\bhead\s+of\b', 0.9),
        (r'\bvp\b', 1.0),
        (r'\bvice\s+president\b', 1.0),
        (r'\blevel\s+(?:3|iii|iv|4)\b', 0.9),
        (r'\bgrade\s+(?:3|iii|iv|4)\b', 0.8),
        (r'\bIII\b', 0.8),  # Roman numeral III
        (r'\bIV\b', 0.8),  # Roman numeral IV
        (r'\b(?:5|6|7|8|9|10)\s*\+?\s+years?\s+(?:of\s+)?experience\b', 0.9),
        (r'\b[5-9]\s*(?:-|to)\s*(?:10|\d{2})\s+years?\b', 0.9),
    ]
    
    # Education patterns with levels
    EDUCATION_PATTERNS = [
        (r'\bhigh\s+school\b', 'High School'),
        (r'\bhs\s+diploma\b', 'High School'),
        (r'\bged\b', 'High School'),
        (r'\bassociate\'?s?\s+degree\b', 'Associate'),
        (r'\baa\s+degree\b', 'Associate'),
        (r'\bas\s+degree\b', 'Associate'),
        (r'\b2[\s-]year\s+degree\b', 'Associate'),
        (r'\bbachelor\'?s?\b', 'Bachelor'),
        (r'\bb\.?a\.?\b(?:\s+degree)?', 'Bachelor'),
        (r'\bb\.?s\.?\b(?:\s+degree)?', 'Bachelor'),
        (r'\bundergraduate\s+degree\b', 'Bachelor'),
        (r'\b4[\s-]year\s+degree\b', 'Bachelor'),
        (r'\bmaster\'?s?\b', 'Master'),
        (r'\bm\.?a\.?\b(?:\s+degree)?', 'Master'),
        (r'\bm\.?s\.?\b(?:\s+degree)?', 'Master'),
        (r'\bmba\b', 'Master'),
        (r'\bgraduate\s+degree\b', 'Master'),
        (r'\bdoctorate\b', 'Doctorate'),
        (r'\bph\.?d\.?\b', 'Doctorate'),
        (r'\bed\.?d\.?\b', 'Doctorate'),
        (r'\bm\.?d\.?\b', 'Doctorate'),
        (r'\bj\.?d\.?\b', 'Doctorate'),
    ]
    
    # Years of experience extraction patterns
    YEARS_PATTERNS = [
        r'(\d+)\s*(?:-|to)\s*(\d+)\s+years?',  # Range: "3-5 years"
        r'(\d+)\s*\+\s+years?',  # Minimum: "5+ years"
        r'(?:minimum|at\s+least)\s+(\d+)\s+years?',  # Minimum explicit
        r'(\d+)\s+years?\s+(?:of\s+)?(?:experience|exp)',  # "5 years experience"
    ]
    
    def detect(self, title: str, description: Optional[str] = None, 
               requirements: Optional[str] = None) -> ExperienceInfo:
        """
        Detect experience level from job information.
        
        Args:
            title: Job title
            description: Job description (optional)
            requirements: Job requirements text (optional)
            
        Returns:
            ExperienceInfo with detected level and confidence
        """
        result = ExperienceInfo()
        
        # Combine text for analysis
        full_text = title.lower()
        if description:
            full_text += " " + description.lower()
        if requirements:
            full_text += " " + requirements.lower()
        
        # Title gets more weight
        title_lower = title.lower()
        
        # Calculate scores for each level
        entry_score = self._calculate_score(title_lower, full_text, self.ENTRY_PATTERNS)
        mid_score = self._calculate_score(title_lower, full_text, self.MID_PATTERNS)
        senior_score = self._calculate_score(title_lower, full_text, self.SENIOR_PATTERNS)
        
        # Determine level based on highest score
        scores = {
            'Entry': entry_score,
            'Mid': mid_score,
            'Senior': senior_score
        }
        
        max_score = max(scores.values())
        if max_score > 0:
            result.level = max(scores, key=scores.get)
            result.confidence = min(max_score, 1.0)
        
        # Extract years of experience
        years_min, years_max = self._extract_years(full_text)
        result.years_min = years_min
        result.years_max = years_max
        
        # If we have years but no level, infer level
        if result.level is None and years_min is not None:
            if years_min == 0 or (years_max and years_max <= 2):
                result.level = 'Entry'
                result.confidence = 0.6
            elif years_min >= 5:
                result.level = 'Senior'
                result.confidence = 0.7
            else:
                result.level = 'Mid'
                result.confidence = 0.6
        
        # Detect education requirements
        result.education = self._detect_education(full_text)
        
        return result
    
    def _calculate_score(self, title: str, full_text: str, 
                         patterns: list) -> float:
        """Calculate experience level score based on patterns"""
        score = 0.0
        
        for pattern, weight in patterns:
            # Title matches get 2x weight
            if re.search(pattern, title, re.IGNORECASE):
                score += weight * 2.0
            elif re.search(pattern, full_text, re.IGNORECASE):
                score += weight
        
        return score
    
    def _extract_years(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract years of experience from text"""
        for pattern in self.YEARS_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2 and groups[1]:
                    # Range pattern
                    return int(groups[0]), int(groups[1])
                elif len(groups) >= 1:
                    # Single value (minimum)
                    return int(groups[0]), None
        
        return None, None
    
    def _detect_education(self, text: str) -> Optional[str]:
        """Detect highest education requirement mentioned"""
        education_order = ['High School', 'Associate', 'Bachelor', 'Master', 'Doctorate']
        detected = []
        
        for pattern, education in self.EDUCATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(education)
        
        if not detected:
            return None
        
        # Return highest education mentioned
        for edu in reversed(education_order):
            if edu in detected:
                return edu
        
        return detected[0] if detected else None


# Module-level instance for convenience
_detector = ExperienceDetector()


def detect_experience(title: str, description: Optional[str] = None,
                      requirements: Optional[str] = None) -> ExperienceInfo:
    """
    Detect experience level from job information.
    
    Args:
        title: Job title
        description: Job description (optional)
        requirements: Job requirements text (optional)
        
    Returns:
        ExperienceInfo with detected level and confidence
    """
    return _detector.detect(title, description, requirements)


def get_experience_level(title: str, description: Optional[str] = None,
                         requirements: Optional[str] = None) -> Optional[str]:
    """
    Get just the experience level string.
    
    Args:
        title: Job title
        description: Job description (optional)
        requirements: Job requirements text (optional)
        
    Returns:
        Experience level string ('Entry', 'Mid', 'Senior') or None
    """
    result = _detector.detect(title, description, requirements)
    return result.level if result.confidence >= 0.4 else None


def get_education_level(title: str, description: Optional[str] = None,
                        requirements: Optional[str] = None) -> Optional[str]:
    """
    Get detected education requirement.
    
    Args:
        title: Job title  
        description: Job description (optional)
        requirements: Job requirements text (optional)
        
    Returns:
        Education level string or None
    """
    result = _detector.detect(title, description, requirements)
    return result.education
