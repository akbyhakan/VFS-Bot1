"""Proxy models for VFS-Bot web application."""

from typing import Optional

from pydantic import BaseModel


class ProxyCreateRequest(BaseModel):
    """Proxy creation request model."""

    server: str
    port: int
    username: str
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "server": "gw.netnut.net",
                "port": 5959,
                "username": "ntnt_user",
                "password": "your_password",
            }
        }


class ProxyUpdateRequest(BaseModel):
    """Proxy update request model."""

    server: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class ProxyResponse(BaseModel):
    """Proxy response model (password excluded)."""

    id: int
    server: str
    port: int
    username: str
    is_active: bool
    failure_count: int
    last_used: Optional[str] = None
    created_at: str
    updated_at: str
