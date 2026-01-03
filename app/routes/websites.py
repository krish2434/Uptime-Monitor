from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import User, Website
from ..schemas import WebsiteCreate, WebsiteResponse, WebsiteUpdate
from ..auth import get_current_user

router = APIRouter(prefix="/websites", tags=["websites"])


@router.post("", response_model=WebsiteResponse)
def create_website(
    website_data: WebsiteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new website to monitor"""
    db_website = Website(
        user_id=current_user.id,
        url=website_data.url,
        check_interval=website_data.check_interval
    )
    db.add(db_website)
    db.commit()
    db.refresh(db_website)
    return db_website


@router.get("", response_model=List[WebsiteResponse])
def list_websites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all websites for the current user"""
    websites = db.query(Website).filter(Website.user_id == current_user.id).all()
    return websites


@router.get("/{website_id}", response_model=WebsiteResponse)
def get_website(
    website_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific website"""
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


@router.put("/{website_id}", response_model=WebsiteResponse)
def update_website(
    website_id: int,
    website_data: WebsiteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a website"""
    website = db.query(Website).filter(
        Website.id == website_id,
        Website.user_id == current_user.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found"
        )
    
    # Update only provided fields
    if website_data.url is not None:
        website.url = website_data.url
    if website_data.check_interval is not None:
        website.check_interval = website_data.check_interval
    if website_data.is_active is not None:
        website.is_active = website_data.is_active
    
    db.commit()
    db.refresh(website)
    return website


@router.delete("/{website_id}")
def delete_website(
    website_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a website"""
    website = db.query(Website).filter(
        Website.id == website_id,
        Website.user_id == current_user.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found"
        )
    
    db.delete(website)
    db.commit()
    
    return {"message": "Website deleted successfully"}
