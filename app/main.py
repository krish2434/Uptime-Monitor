from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from .database import engine, get_db
from .models import Base, User, Website, CheckResult
from .routes import auth, websites, dashboard
from .worker import start_worker
from .auth import get_current_user, authenticate_user, create_access_token, hash_password

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Uptime Monitor",
    description="A simple uptime monitoring system",
    version="1.0.0"
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup Jinja2 templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Include API routers with /api prefix
app.include_router(auth.router, prefix="/api")
app.include_router(websites.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


# ============= WEB ROUTES (HTML PAGES) =============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Home page"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        current_user = None
    
    return templates.TemplateResponse("index.html", {"request": request, "current_user": current_user})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Handle login"""
    user = authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    
    access_token = create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle registration"""
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Passwords do not match"})
    
    # Check if user exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Email already registered"})
    
    # Create new user
    hashed_password = hash_password(password)
    new_user = User(email=email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    
    access_token = create_access_token(data={"sub": email})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@app.get("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    """Dashboard page"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    websites = db.query(Website).filter(Website.user_id == current_user.id).all()
    
    # Get website statuses based on last 3 checks
    for website in websites:
        # Get last 3 checks
        last_3_checks = db.query(CheckResult).filter(
            CheckResult.website_id == website.id
        ).order_by(desc(CheckResult.checked_at)).limit(3).all()
        
        if len(last_3_checks) == 0:
            website.last_status = None
            website.status_display = "UNKNOWN"
        elif len(last_3_checks) < 3:
            # If less than 3 checks, use what we have
            all_up = all(check.status.value == "UP" for check in last_3_checks)
            all_down = all(check.status.value == "DOWN" for check in last_3_checks)
            if all_up:
                website.last_status = last_3_checks[0].status
                website.status_display = "UP"
            elif all_down:
                website.last_status = last_3_checks[0].status
                website.status_display = "DOWN"
            else:
                website.last_status = last_3_checks[0].status
                website.status_display = "UNKNOWN"
        else:
            # Check last 3 results
            statuses = [check.status.value for check in last_3_checks]
            if all(status == "UP" for status in statuses):
                website.last_status = last_3_checks[0].status
                website.status_display = "UP"
            elif all(status == "DOWN" for status in statuses):
                website.last_status = last_3_checks[0].status
                website.status_display = "DOWN"
            else:
                website.last_status = last_3_checks[0].status
                website.status_display = "UNKNOWN"
    
    # Calculate metrics (ONLINE = last 3 UP, OFFLINE = last 3 DOWN)
    uptime_count = sum(1 for w in websites if w.status_display == "UP")
    downtime_count = sum(1 for w in websites if w.status_display == "DOWN")
    
    # Calculate average uptime percentage
    total_checks = db.query(CheckResult).filter(
        CheckResult.website_id.in_([w.id for w in websites])
    ).count()
    up_checks = db.query(CheckResult).filter(
        CheckResult.website_id.in_([w.id for w in websites]),
        CheckResult.status == "UP"
    ).count()
    average_uptime = (up_checks / total_checks * 100) if total_checks > 0 else 0
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": current_user,
        "websites": websites,
        "uptime_count": uptime_count,
        "downtime_count": downtime_count,
        "average_uptime": average_uptime
    })


@app.get("/website/{website_id}", response_class=HTMLResponse)
async def website_detail(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Website detail page"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    website = db.query(Website).filter(
        Website.id == website_id,
        Website.user_id == current_user.id
    ).first()
    
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    # Get last status
    last_check = db.query(CheckResult).filter(
        CheckResult.website_id == website_id
    ).order_by(desc(CheckResult.checked_at)).first()
    website.last_status = last_check.status if last_check else None
    
    # Calculate metrics
    total_checks = db.query(CheckResult).filter(CheckResult.website_id == website_id).count()
    up_checks = db.query(CheckResult).filter(
        CheckResult.website_id == website_id,
        CheckResult.status == "UP"
    ).count()
    uptime_percentage = (up_checks / total_checks * 100) if total_checks > 0 else 0
    
    # Get average response time
    avg_response = db.query(func.avg(CheckResult.response_time_ms)).filter(
        CheckResult.website_id == website_id
    ).scalar() or 0
    
    # Get recent checks
    recent_checks = db.query(CheckResult).filter(
        CheckResult.website_id == website_id
    ).order_by(desc(CheckResult.checked_at)).limit(10).all()
    
    # Get incidents count
    incidents_count = 0
    
    # Prepare chart data
    last_24h = datetime.utcnow() - timedelta(hours=24)
    checks = db.query(CheckResult).filter(
        CheckResult.website_id == website_id,
        CheckResult.checked_at >= last_24h
    ).order_by(CheckResult.checked_at).all()
    
    labels = [check.checked_at.strftime("%H:%M") for check in checks]
    response_times = [check.response_time_ms or 0 for check in checks]
    
    return templates.TemplateResponse("website_detail.html", {
        "request": request,
        "current_user": current_user,
        "website": website,
        "uptime_percentage": uptime_percentage,
        "avg_response_time": avg_response,
        "incidents_count": incidents_count,
        "recent_checks": recent_checks,
        "labels": labels,
        "response_times": response_times
    })


@app.get("/websites", response_class=HTMLResponse)
async def websites_page(request: Request, db: Session = Depends(get_db)):
    """Websites list page"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    websites = db.query(Website).filter(Website.user_id == current_user.id).all()
    
    # Get website statuses, latencies, and recent checks
    avg_latencies = {}
    for website in websites:
        last_check = db.query(CheckResult).filter(
            CheckResult.website_id == website.id
        ).order_by(desc(CheckResult.checked_at)).first()
        website.last_status = last_check.status if last_check else None
        
        # Calculate average latency
        avg_latency = db.query(func.avg(CheckResult.response_time_ms)).filter(
            CheckResult.website_id == website.id
        ).scalar()
        if avg_latency:
            avg_latencies[website.id] = f"{round(avg_latency)}ms"
        else:
            avg_latencies[website.id] = "N/A"
        
        # Get recent 30 checks for uptime blocks
        website.recent_checks = db.query(CheckResult).filter(
            CheckResult.website_id == website.id
        ).order_by(desc(CheckResult.checked_at)).limit(30).all()
        website.recent_checks.reverse()  # Reverse to show oldest first
    
    return templates.TemplateResponse("websites.html", {
        "request": request,
        "current_user": current_user,
        "websites": websites,
        "avg_latencies": avg_latencies
    })


@app.get("/add-website", response_class=HTMLResponse)
async def add_website_page(request: Request, db: Session = Depends(get_db)):
    """Add website page"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("add_website.html", {
        "request": request,
        "current_user": current_user
    })


@app.post("/add-website", response_class=HTMLResponse)
async def add_website_post(
    request: Request,
    url: str = Form(...),
    check_interval: int = Form(...),
    name: str = Form(None),
    db: Session = Depends(get_db)
):
    """Handle add website"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    website = Website(
        user_id=current_user.id,
        url=url,
        check_interval=check_interval,
        is_active=True
    )
    db.add(website)
    db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/website/{website_id}/edit", response_class=HTMLResponse)
async def edit_website_page(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Edit website page"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    website = db.query(Website).filter(
        Website.id == website_id,
        Website.user_id == current_user.id
    ).first()
    
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    return templates.TemplateResponse("edit_website.html", {
        "request": request,
        "current_user": current_user,
        "website": website
    })


@app.post("/website/{website_id}/edit", response_class=HTMLResponse)
async def edit_website_post(
    website_id: int,
    request: Request,
    url: str = Form(...),
    check_interval: int = Form(...),
    is_active: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Handle edit website"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    website = db.query(Website).filter(
        Website.id == website_id,
        Website.user_id == current_user.id
    ).first()
    
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    website.url = url
    website.check_interval = check_interval
    website.is_active = is_active
    db.commit()
    
    return RedirectResponse(url=f"/website/{website_id}", status_code=302)


@app.post("/website/{website_id}/delete", response_class=HTMLResponse)
async def delete_website(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete website"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    website = db.query(Website).filter(
        Website.id == website_id,
        Website.user_id == current_user.id
    ).first()
    
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    db.delete(website)
    db.commit()
    
    return RedirectResponse(url="/websites", status_code=302)


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    """User profile page"""
    try:
        current_user = get_current_user(request=request, token=None, db=db)
    except:
        return RedirectResponse(url="/login", status_code=302)
    
    websites_count = db.query(Website).filter(Website.user_id == current_user.id).count()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "current_user": current_user,
        "websites_count": websites_count
    })


# ============= API ENDPOINTS =============

@app.get("/api/")
def api_home():
    """Root API endpoint"""
    return {
        "message": "Uptime Monitor API",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.on_event("startup")
async def startup_event():
    """Start background worker on app startup"""
    start_worker()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on app shutdown"""
    pass