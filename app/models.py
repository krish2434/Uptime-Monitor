from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .database import Base


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    websites = relationship("Website", back_populates="owner", cascade="all, delete-orphan")


class Website(Base):
    """Website to monitor"""
    __tablename__ = "websites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    url = Column(String, nullable=False)
    check_interval = Column(Integer, default=60)  # seconds
    is_active = Column(Boolean, default=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="websites")
    check_results = relationship("CheckResult", back_populates="website", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="website", cascade="all, delete-orphan")


class CheckResultStatus(str, enum.Enum):
    """Status of a health check"""
    UP = "UP"
    DOWN = "DOWN"


class CheckResult(Base):
    """Individual health check result"""
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    status = Column(SQLEnum(CheckResultStatus), nullable=False)
    response_time_ms = Column(Float, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(String, nullable=True)

    website = relationship("Website", back_populates="check_results")


class Incident(Base):
    """Downtime incident"""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    website = relationship("Website", back_populates="incidents")
