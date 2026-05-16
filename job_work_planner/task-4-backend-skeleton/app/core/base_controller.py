"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: base_controller.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from typing import Type, TypeVar, Generic, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Base
from app.core.tenant_context import tenant_id_context
from fastapi import HTTPException, status

T = TypeVar("T", bound=Base)

class BaseController(Generic[T]):
    def __init__(self, model: Type[T], db: AsyncSession):
        self.model = model
        self.db = db

    def _get_tenant_id(self) -> str:
        tenant_id = tenant_id_context.get()
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant context missing"
            )
        return tenant_id

    async def get_by_id(self, id: Any) -> T | None:
        tenant_id = self._get_tenant_id()
        # Assume primary key is the first column for simplicity in this base, 
        # or use a more specific pk check
        pk_attr = self.model.__mapper__.primary_key[0]
        query = select(self.model).where(
            pk_attr == id,
            self.model.tenant_id == tenant_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_all(self):
        tenant_id = self._get_tenant_id()
        query = select(self.model).where(self.model.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create(self, **kwargs) -> T:
        tenant_id = self._get_tenant_id()
        instance = self.model(tenant_id=tenant_id, **kwargs)
        self.db.add(instance)
        await self.db.flush() # Flush to get ID if needed
        return instance

    def scoped_query(self):
        """Returns a query object pre-filtered by tenant_id."""
        tenant_id = self._get_tenant_id()
        return select(self.model).where(self.model.tenant_id == tenant_id)
