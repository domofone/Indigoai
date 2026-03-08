"""
Pydantic schemas for request/response validation.
These correspond to the API contracts with the Android client.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============ Auth Schemas ============

class GoogleAuthRequest(BaseModel):
    """Request for Google OAuth authentication."""
    id_token: str
    access_token: Optional[str] = None


class AuthResponse(BaseModel):
    """Response with authentication tokens."""
    user_id: str
    access_token: str
    refresh_token: str
    expires_in: int


# ============ Query Schemas ============

class ContextDto(BaseModel):
    """Additional context for a query."""
    location: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    budget: Optional[float] = None
    date: Optional[str] = None
    time: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class QueryRequest(BaseModel):
    """Incoming query from client."""
    text: str
    context: Optional[ContextDto] = None
    session_id: Optional[str] = None


class AgentStageDto(BaseModel):
    """Result from a single agent."""
    agent: str
    title: str
    data: Dict[str, Any]
    confidence: float
    display_order: int = 0


class FinalResultDto(BaseModel):
    """Aggregated result from all agents."""
    summary: str
    stages: List[AgentStageDto] = []
    suggestions: List[str] = []
    estimated_budget: Optional[float] = None


class PartialUpdateDto(BaseModel):
    """Partial update during processing."""
    agent: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response to a query (can be streaming or final)."""
    query_id: str
    status: str  # "processing", "completed", "failed"
    partial_updates: List[PartialUpdateDto] = []
    final_result: Optional[FinalResultDto] = None


# ============ History Schemas ============

class QueryHistoryItemDto(BaseModel):
    """Compact query history item."""
    id: str
    text: str
    created_at: str
    summary: Optional[str] = None
    agents_used: List[str] = []


class QueryHistoryResponse(BaseModel):
    """Paginated history response."""
    queries: List[QueryHistoryItemDto]


# ============ Feedback Schemas ============

class FeedbackRequest(BaseModel):
    """User feedback on a query."""
    query_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


# ============ Internal Models (for ORM) ============

class QueryResult(BaseModel):
    """Complete query result (stored in DB)."""
    summary: str
    stages: List[AgentStageDto] = []
    suggestions: List[str] = []
    estimated_budget: Optional[float] = None
    visual_data: Optional[Dict[str, Any]] = None


class AgentExecutionRecord(BaseModel):
    """Record of agent execution."""
    agent_type: str
    title: str
    data: Dict[str, Any]
    confidence: float
    display_order: int = 0