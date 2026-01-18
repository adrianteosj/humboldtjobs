"""
Multi-Agent System for Data Quality & Engineering

Specialized AI agents with clear roles:
- QAAgent: Validates data quality, scores sources, approves/quarantines jobs
- EngineerAgent: Debugs scrapers, analyzes HTML, suggests fixes
- AnalystAgent: Identifies trends, anomalies, generates insights
- Orchestrator: Coordinates agents, manages workflows
"""

from .base import BaseAgent, AgentResponse
from .orchestrator import Orchestrator
from .qa_agent import QAAgent
from .engineer_agent import EngineerAgent
from .analyst_agent import AnalystAgent

__all__ = [
    'BaseAgent',
    'AgentResponse', 
    'Orchestrator',
    'QAAgent',
    'EngineerAgent',
    'AnalystAgent'
]
