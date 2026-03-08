"""
CRUD operations for Query model.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from typing import Optional, List
import uuid
from datetime import datetime

from app.models.models import Query as QueryModel
from app.schemas.schemas import QueryRequest, FinalResultDto, AgentStageDto


class QueryCRUD:
    """CRUD operations for queries."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_query(
        self,
        text: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        intent: Optional[str] = None
    ) -> QueryModel:
        """Create a new query record."""
        query = QueryModel(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id) if user_id else None,
            session_id=uuid.UUID(session_id) if session_id else None,
            original_text=text,
            intent=intent,
            status="pending"
        )
        self.session.add(query)
        await self.session.flush()
        return query
    
    async def get_query(self, query_id: str) -> Optional[QueryModel]:
        """Get query by ID."""
        result = await self.session.execute(
            select(QueryModel).where(QueryModel.id == uuid.UUID(query_id))
        )
        return result.scalar_one_or_none()
    
    async def get_queries_by_user(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[QueryModel]:
        """Get queries for a user with pagination."""
        result = await self.session.execute(
            select(QueryModel)
            .where(QueryModel.user_id == uuid.UUID(user_id))
            .order_by(QueryModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
    
    async def update_query_status(
        self,
        query_id: str,
        status: str,
        result: Optional[FinalResultDto] = None,
        error: Optional[str] = None
    ) -> Optional[QueryModel]:
        """Update query status and optionally result."""
        query = await self.get_query(query_id)
        if not query:
            return None
        
        query.status = status
        if result:
            query.result = result.model_dump()
        if error:
            query.error = error
        
        if status in ["completed", "failed"]:
            query.completed_at = datetime.utcnow()
        
        await self.session.merge(query)
        await self.session.flush()
        return query
    
    async def delete_query(self, query_id: str) -> bool:
        """Delete a query."""
        query = await self.get_query(query_id)
        if not query:
            return False
        
        await self.session.delete(query)
        await self.session.flush()
        return True
    
    async def clear_user_history(self, user_id: str) -> int:
        """Delete all queries for a user. Returns count of deleted rows."""
        stmt = delete(QueryModel).where(QueryModel.user_id == uuid.UUID(user_id))
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount