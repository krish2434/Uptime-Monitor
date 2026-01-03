from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List

from ..database import get_db
from ..models import User, Website, CheckResult, Incident, CheckResultStatus
from ..schemas import DashboardSummary, ResponseTimeHistory, ResponseTimeMetric, IncidentHistory, IncidentResponse
from ..auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _verify_website_ownership(website_id: int, current_user: User, db: Session) -> Website:
    """Verify that the user owns the website"""
    website = db.query(Website).filter(
        Website.id == website_id,
        Website.user_id == current_user.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found"
        )
    
    return website


@router.get("/summary/{website_id}", response_model=DashboardSummary)
def get_summary(
    website_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard summary for a website"""
    website = _verify_website_ownership(website_id, current_user, db)
    
    # Get last check result
    last_check = db.query(CheckResult).filter(
        CheckResult.website_id == website_id
    ).order_by(desc(CheckResult.checked_at)).first()
    
    current_status = last_check.status if last_check else None
    
    # Calculate uptime percentage
    total_checks = db.query(CheckResult).filter(
        CheckResult.website_id == website_id
    ).count()
    
    failed_checks = db.query(CheckResult).filter(
        CheckResult.website_id == website_id,
        CheckResult.status == CheckResultStatus.DOWN
    ).count()
    
    uptime_percentage = (
        ((total_checks - failed_checks) / total_checks * 100)
        if total_checks > 0 else 100.0
    )
    
    # Get ongoing incident
    ongoing_incident = db.query(Incident).filter(
        Incident.website_id == website_id,
        Incident.end_time == None
    ).first()
    
    return DashboardSummary(
        website_id=website.id,
        url=website.url,
        current_status=current_status,
        last_checked_at=last_check.checked_at if last_check else None,
        uptime_percentage=round(uptime_percentage, 2),
        total_checks=total_checks,
        failed_checks=failed_checks,
        ongoing_incident=ongoing_incident
    )


@router.get("/response-times/{website_id}", response_model=ResponseTimeHistory)
def get_response_times(
    website_id: int,
    hours: int = 24,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get response time history for a website"""
    website = _verify_website_ownership(website_id, current_user, db)
    
    # Get check results from the last N hours
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    results = db.query(CheckResult).filter(
        CheckResult.website_id == website_id,
        CheckResult.checked_at >= cutoff_time
    ).order_by(CheckResult.checked_at).all()
    
    metrics = [
        ResponseTimeMetric(
            checked_at=result.checked_at,
            response_time_ms=result.response_time_ms,
            status=result.status
        )
        for result in results
    ]
    
    return ResponseTimeHistory(
        website_id=website.id,
        url=website.url,
        metrics=metrics
    )


@router.get("/incidents/{website_id}", response_model=IncidentHistory)
def get_incidents(
    website_id: int,
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get incident history for a website"""
    website = _verify_website_ownership(website_id, current_user, db)
    
    # Get incidents from the last N days
    cutoff_time = datetime.utcnow() - timedelta(days=days)
    incidents = db.query(Incident).filter(
        Incident.website_id == website_id,
        Incident.start_time >= cutoff_time
    ).order_by(desc(Incident.start_time)).all()
    
    return IncidentHistory(
        website_id=website.id,
        url=website.url,
        incidents=incidents
    )
