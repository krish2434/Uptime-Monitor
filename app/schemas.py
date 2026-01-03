from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from enum import Enum


class CheckResultStatus(str, Enum):
    """Status of a health check"""
    UP = "UP"
    DOWN = "DOWN"


# Auth Schemas
class UserRegister(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT Token response"""
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    """User response model"""
    id: int
    email: str

    class Config:
        from_attributes = True


# Website Schemas
class WebsiteCreate(BaseModel):
    """Schema for creating a website"""
    url: str
    check_interval: int = 60


class WebsiteUpdate(BaseModel):
    """Schema for updating a website"""
    url: Optional[str] = None
    check_interval: Optional[int] = None
    is_active: Optional[bool] = None


class WebsiteResponse(BaseModel):
    """Website response model"""
    id: int
    url: str
    check_interval: int
    is_active: bool
    last_checked_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Check Result Schemas
class CheckResultResponse(BaseModel):
    """Check result response model"""
    id: int
    website_id: int
    status: CheckResultStatus
    response_time_ms: Optional[float] = None
    checked_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# Incident Schemas
class IncidentResponse(BaseModel):
    """Incident response model"""
    id: int
    website_id: int
    start_time: datetime
    end_time: Optional[datetime] = None

    class Config:
        from_attributes = True


# Dashboard Schemas
class DashboardSummary(BaseModel):
    """Dashboard summary for a website"""
    website_id: int
    url: str
    current_status: CheckResultStatus
    last_checked_at: Optional[datetime]
    uptime_percentage: float
    total_checks: int
    failed_checks: int
    ongoing_incident: Optional[IncidentResponse] = None


class ResponseTimeMetric(BaseModel):
    """Response time metric"""
    checked_at: datetime
    response_time_ms: Optional[float]
    status: CheckResultStatus


class ResponseTimeHistory(BaseModel):
    """Response time history"""
    website_id: int
    url: str
    metrics: list[ResponseTimeMetric]


class IncidentHistory(BaseModel):
    """Incident history"""
    website_id: int
    url: str
    incidents: list[IncidentResponse]
