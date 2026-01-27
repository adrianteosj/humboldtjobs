from .normalizer import CategoryNormalizer, normalize_category
from .deduplication import deduplicate_jobs, deduplicate_by_url
from .anomaly_detector import AnomalyDetector, AnomalyType, Anomaly, run_anomaly_check
from .salary_parser import parse_salary, extract_salary_range, ParsedSalary, SalaryParser
from .experience_detector import detect_experience, get_experience_level, get_education_level, ExperienceInfo
from .ai_extractor import extract_with_ai, batch_extract_salaries, is_ai_available, ExtractionResult

# AI Agents (lazy import to avoid loading Gemini unless needed)
def get_orchestrator(api_key=None):
    """Get the AI agent orchestrator (lazy load)."""
    from .agents import Orchestrator
    return Orchestrator(api_key)

def get_qa_agent(api_key=None):
    """Get the QA agent (lazy load)."""
    from .agents import QAAgent
    return QAAgent(api_key)

def get_engineer_agent(api_key=None):
    """Get the Engineer agent (lazy load)."""
    from .agents import EngineerAgent
    return EngineerAgent(api_key)

def get_analyst_agent(api_key=None):
    """Get the Analyst agent (lazy load)."""
    from .agents import AnalystAgent
    return AnalystAgent(api_key)

__all__ = [
    'CategoryNormalizer', 
    'normalize_category', 
    'deduplicate_jobs', 
    'deduplicate_by_url',
    'AnomalyDetector',
    'AnomalyType',
    'Anomaly',
    'run_anomaly_check',
    # Salary parsing
    'parse_salary',
    'extract_salary_range',
    'ParsedSalary',
    'SalaryParser',
    # Experience detection
    'detect_experience',
    'get_experience_level',
    'get_education_level',
    'ExperienceInfo',
    # AI extraction fallback
    'extract_with_ai',
    'batch_extract_salaries',
    'is_ai_available',
    'ExtractionResult',
    # AI Agents
    'get_orchestrator',
    'get_qa_agent',
    'get_engineer_agent',
    'get_analyst_agent',
]
