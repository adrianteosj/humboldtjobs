"""
Base Agent Class

All specialized agents inherit from this base class.
Provides common functionality for Gemini API interaction.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent role identifiers"""
    QA = "qa_agent"
    ENGINEER = "engineer_agent"
    ANALYST = "analyst_agent"
    ORCHESTRATOR = "orchestrator"


class ActionType(Enum):
    """Types of actions agents can recommend"""
    APPROVE = "approve"
    QUARANTINE = "quarantine"
    FLAG_REVIEW = "flag_for_review"
    FIX_REQUIRED = "fix_required"
    MONITOR = "monitor"
    NO_ACTION = "no_action"


@dataclass
class AgentResponse:
    """Standardized response from any agent"""
    agent: AgentRole
    success: bool
    action: ActionType
    confidence: float  # 0.0 to 1.0
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent.value,
            "success": self.success,
            "action": self.action.value,
            "confidence": self.confidence,
            "summary": self.summary,
            "details": self.details,
            "recommendations": self.recommendations
        }


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents.
    
    Each agent has:
    - A specific role and system prompt
    - Access to Gemini API
    - Standardized input/output format
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        
        self._model = None
        self._client = None
    
    @property
    @abstractmethod
    def role(self) -> AgentRole:
        """Return the agent's role identifier"""
        pass
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the agent's system prompt defining its role and behavior"""
        pass
    
    @property
    def model_name(self) -> str:
        """Gemini model to use"""
        return "gemini-2.0-flash"
    
    def _get_client(self):
        """Lazy load Gemini client"""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai
                self._model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=self.system_prompt
                )
            except ImportError:
                raise ImportError("google-generativeai package required. Install with: pip install google-generativeai")
        return self._model
    
    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """
        Make a call to Gemini API.
        
        Args:
            prompt: The user prompt to send
            temperature: Controls randomness (lower = more focused)
            
        Returns:
            The model's text response
        """
        model = self._get_client()
        
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": 2048,
                }
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error in {self.role.value}: {e}")
            raise
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling markdown code blocks and edge cases.
        """
        original_response = response
        
        # Try to extract JSON from markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                response = response[start:end].strip()
        
        # Try direct parsing first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON array or object in response
        for start_char, end_char in [('[', ']'), ('{', '}')]:
            start_idx = response.find(start_char)
            if start_idx != -1:
                # Find matching closing bracket
                depth = 0
                for i, char in enumerate(response[start_idx:], start_idx):
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(response[start_idx:i+1])
                            except json.JSONDecodeError:
                                break
        
        # Try to fix common JSON issues
        cleaned = response.strip()
        # Remove trailing commas before ] or }
        import re
        cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
        # Try parsing cleaned version
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            return {"raw": original_response[:500], "parse_error": str(e)}
    
    @abstractmethod
    def process(self, data: Any) -> AgentResponse:
        """
        Process input data and return a response.
        
        Each agent implements this with their specific logic.
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} role={self.role.value}>"
