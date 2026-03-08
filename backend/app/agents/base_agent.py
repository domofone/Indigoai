"""
Base agent interface and decorator.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentRequest:
    """Request to an agent."""
    query_id: str
    user_id: Optional[str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Response from an agent."""
    success: bool
    data: Dict[str, Any]
    confidence: float = 1.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: Optional[int] = None


class BaseAgent(ABC):
    """Base class for all agents."""
    
    agent_type: str = "base"
    dependencies: list = []  # Other agents this one depends on
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    @abstractmethod
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Execute the agent's task."""
        pass
    
    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """Validate input parameters. Override in subclasses."""
        return True
    
    def get_required_params(self) -> list:
        """List required parameters. Override in subclasses."""
        return []