import asyncio
import httpx
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from .database import SessionLocal, engine
from .models import Base, Website, CheckResult, Incident, CheckResultStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_website_health(url: str) -> tuple[CheckResultStatus, float | None, str | None]:
    """
    Check the health of a website by making an HTTP request.
    
    Returns:
        tuple: (status, response_time_ms, error_message)
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            start_time = datetime.utcnow()
            response = await client.get(
                url, 
                follow_redirects=True,
                headers={"User-Agent": "Uptime-Monitor/1.0"}
            )
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # If server responds with any status code, it's UP
            # Only mark as DOWN if there's a connection error
            return CheckResultStatus.UP, elapsed, None
    except asyncio.TimeoutError:
        return CheckResultStatus.DOWN, None, "Request timeout"
    except httpx.ConnectError:
        return CheckResultStatus.DOWN, None, "Connection error"
    except httpx.RequestError as e:
        return CheckResultStatus.DOWN, None, str(e)
    except Exception as e:
        return CheckResultStatus.DOWN, None, f"Unexpected error: {str(e)}"


def detect_incident_changes(db: Session, website_id: int, new_status: CheckResultStatus):
    """
    Detect when status changes from UP to DOWN (start incident)
    or from DOWN to UP (end incident).
    """
    # Get the previous check result
    previous_check = db.query(CheckResult).filter(
        CheckResult.website_id == website_id
    ).order_by(CheckResult.checked_at.desc()).offset(1).first()
    
    if not previous_check:
        # No previous check, skip incident logic
        return
    
    previous_status = previous_check.status
    
    # UP -> DOWN: Start a new incident
    if previous_status == CheckResultStatus.UP and new_status == CheckResultStatus.DOWN:
        incident = Incident(
            website_id=website_id,
            start_time=datetime.utcnow()
        )
        db.add(incident)
        db.commit()
        logger.info(f"Incident started for website {website_id}: {previous_status} -> {new_status}")
    
    # DOWN -> UP: Close the ongoing incident
    elif previous_status == CheckResultStatus.DOWN and new_status == CheckResultStatus.UP:
        ongoing_incident = db.query(Incident).filter(
            Incident.website_id == website_id,
            Incident.end_time == None
        ).first()
        
        if ongoing_incident:
            ongoing_incident.end_time = datetime.utcnow()
            db.commit()
            duration = (ongoing_incident.end_time - ongoing_incident.start_time).total_seconds()
            logger.info(f"Incident ended for website {website_id}: {previous_status} -> {new_status} (duration: {duration}s)")


async def check_and_save_result(db: Session, website: Website):
    """Check a website and save the result to the database"""
    logger.info(f"Checking website {website.id}: {website.url}")
    
    status, response_time, error_message = await check_website_health(website.url)
    
    # Save check result
    check_result = CheckResult(
        website_id=website.id,
        status=status,
        response_time_ms=response_time,
        error_message=error_message,
        checked_at=datetime.utcnow()
    )
    db.add(check_result)
    db.commit()
    db.refresh(check_result)
    
    # Detect incident changes
    detect_incident_changes(db, website.id, status)
    
    # Update last_checked_at
    website.last_checked_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Website {website.id} check completed: {status} ({response_time}ms)" if response_time else f"Website {website.id} check completed: {status}")


async def worker_loop():
    """
    Main worker loop that continuously checks websites.
    Runs on a separate thread/task from FastAPI.
    """
    logger.info("Worker started")
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    while True:
        db = SessionLocal()
        try:
            # Get all active websites that need checking
            now = datetime.utcnow()
            websites = db.query(Website).filter(Website.is_active == True).all()
            
            for website in websites:
                # Check if enough time has passed since last check
                last_checked = website.last_checked_at
                if last_checked is None or (now - last_checked).total_seconds() >= website.check_interval:
                    await check_and_save_result(db, website)
            
            # Small delay to prevent CPU spinning
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Worker error: {str(e)}", exc_info=True)
            await asyncio.sleep(5)
        finally:
            db.close()


def start_worker():
    """
    Start the background worker.
    This is called during FastAPI startup.
    """
    import asyncio
    import threading
    
    def run_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(worker_loop())
    
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()
    logger.info("Worker thread started")
