"""
SQLAlchemy models for the database.
"""
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    """User model for authentication and profile."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    locale = Column(String, default="ru")
    timezone = Column(String, default="Europe/Moscow")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Session(Base):
    """Session model for grouping queries."""
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    context = Column(JSON, nullable=True)  # Flexible context storage
    status = Column(String(20), default="active")  # active, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Query(Base):
    """Query model for storing user requests and results."""
    __tablename__ = "queries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    original_text = Column(String, nullable=False)
    processed_text = Column(String, nullable=True)
    intent = Column(String(100), nullable=True, index=True)
    status = Column(String(20), default="pending", index=True)  # pending, processing, completed, failed
    result = Column(JSON, nullable=True)  # Final aggregated result
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)


class AgentExecution(Base):
    """Track execution of individual agents for a query."""
    __tablename__ = "agent_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False, index=True)
    sequence_order = Column(Integer, nullable=False)
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")  # pending, running, success, failed
    confidence = Column(Float, nullable=True)
    error = Column(String, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    api_calls = Column(JSON, nullable=True)  # Details of external API calls
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class APICache(Base):
    """Cache for external API responses."""
    __tablename__ = "api_cache"
    
    id = Column(Integer, primary_key=True)
    api_name = Column(String(50), nullable=False, index=True)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    response_data = Column(JSON, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)