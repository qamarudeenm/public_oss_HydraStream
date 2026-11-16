"""Pydantic models for the control plane API."""

from uuid import UUID

from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    description: str = ""


class TenantUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class Tenant(TenantCreate):
    id: UUID
