# Uptime Monitor - FastAPI Backend

A simple, production-ready uptime monitoring system built with FastAPI. Monitor websites, track response times, detect downtime incidents, and generate uptime reports.

## 🎯 Features

- **User Authentication**: JWT-based authentication with password hashing
- **Website Monitoring**: Add and manage websites to monitor
- **Health Checks**: Periodic HTTP requests to check website status
- **Incident Detection**: Automatic detection of downtime events (UP → DOWN, DOWN → UP)
- **Dashboard APIs**: Get uptime metrics, response time history, and incident reports
- **Simple Architecture**: Single background worker, database-backed queue, SQLite for development
- **No Over-Engineering**: No Celery, Redis, or microservices complexity

## 📋 Requirements

- Python 3.9+
- FastAPI 0.104+
- SQLAlchemy 2.0+
- Pydantic 2.5+

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
cd app
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

Access the interactive documentation at `http://localhost:8000/docs`

## 🏗️ Architecture

### Directory Structure

```
uptime-monitor/
├── app/
│   ├── main.py              # FastAPI app initialization
│   ├── database.py          # Database configuration
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── auth.py              # Authentication and JWT handling
│   ├── worker.py            # Background worker for health checks
│   └── routes/
│       ├── auth.py          # Authentication endpoints
│       ├── websites.py      # Website management endpoints
│       └── dashboard.py     # Dashboard/metrics endpoints
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

### Database Models

#### User
- `id`: Primary key
- `email`: Unique email address
- `hashed_password`: Bcrypt hashed password

#### Website
- `id`: Primary key
- `user_id`: Foreign key to User
- `url`: Website URL to monitor
- `check_interval`: Interval between checks (seconds)
- `is_active`: Whether monitoring is active
- `last_checked_at`: Timestamp of last check
- `created_at`: Timestamp of creation

#### CheckResult
- `id`: Primary key
- `website_id`: Foreign key to Website
- `status`: UP or DOWN
- `response_time_ms`: HTTP response time in milliseconds
- `checked_at`: Timestamp of the check
- `error_message`: Error details if check failed

#### Incident
- `id`: Primary key
- `website_id`: Foreign key to Website
- `start_time`: When the downtime started
- `end_time`: When the downtime ended (NULL if ongoing)

## 🔐 Authentication

All user-facing APIs require JWT authentication. The worker does not use authentication.

### Getting a Token

1. **Register**:
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'
```

2. **Login**:
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

3. **Use the token** in subsequent requests:
```bash
curl -X GET http://localhost:8000/websites \
  -H "Authorization: Bearer <your_token>"
```

## 📡 API Endpoints

### Authentication

- `POST /auth/register` - Register a new user
- `POST /auth/login` - Login and get JWT token

### Websites

- `POST /websites` - Add a new website to monitor
- `GET /websites` - List all websites for the current user
- `GET /websites/{id}` - Get details of a specific website
- `PUT /websites/{id}` - Update website settings
- `DELETE /websites/{id}` - Delete a website

### Dashboard

- `GET /dashboard/summary/{website_id}` - Get current status and uptime metrics
- `GET /dashboard/response-times/{website_id}?hours=24` - Get response time history
- `GET /dashboard/incidents/{website_id}?days=30` - Get downtime incidents history

## 👷 Background Worker

The worker runs automatically when the FastAPI app starts. It:

1. **Checks active websites** according to their `check_interval`
2. **Makes HTTP requests** to each website URL
3. **Measures response times** in milliseconds
4. **Records check results** in the database
5. **Detects incidents**:
   - UP → DOWN: Creates a new incident record
   - DOWN → UP: Closes the ongoing incident

### How It Works

- Single daemon thread running an async event loop
- Checks loop every 5 seconds for due websites
- Uses `httpx` for async HTTP requests with 10-second timeout
- Considers HTTP 2xx-3xx as UP, others as DOWN
- Logs all activities to stdout

## 🧪 Testing

### Add a Website

```bash
curl -X POST http://localhost:8000/websites \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "check_interval": 60
  }'
```

### Get Dashboard Summary

```bash
curl -X GET http://localhost:8000/dashboard/summary/1 \
  -H "Authorization: Bearer <token>"
```

Response:
```json
{
  "website_id": 1,
  "url": "https://example.com",
  "current_status": "UP",
  "last_checked_at": "2024-01-03T10:30:45.123456",
  "uptime_percentage": 99.5,
  "total_checks": 200,
  "failed_checks": 1,
  "ongoing_incident": null
}
```

### Get Response Time History

```bash
curl -X GET "http://localhost:8000/dashboard/response-times/1?hours=24" \
  -H "Authorization: Bearer <token>"
```

### Get Incidents

```bash
curl -X GET "http://localhost:8000/dashboard/incidents/1?days=30" \
  -H "Authorization: Bearer <token>"
```

## 📊 Database

The system uses SQLite for development. The database file (`uptime_monitor.db`) is created automatically in the `app` directory.

To reset the database, simply delete `uptime_monitor.db` and restart the application.

## 🔧 Configuration

Key settings in `auth.py`:
- `SECRET_KEY`: JWT signing key (change in production)
- `ALGORITHM`: JWT algorithm (HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration (1440 = 24 hours)

## 🚨 Important Notes

### Production Deployment

Before deploying to production:

1. **Change `SECRET_KEY`** in `auth.py`
2. **Use environment variables** for sensitive configuration
3. **Use a proper database** (PostgreSQL, MySQL) instead of SQLite
4. **Enable HTTPS** for all API calls
5. **Review CORS settings** in `main.py`
6. **Add rate limiting** to API endpoints
7. **Monitor worker logs** for health issues
8. **Use a process manager** (systemd, supervisor) to keep the app running

### Current Limitations

- Single-worker design doesn't scale to thousands of websites
- SQLite is single-threaded (not suitable for high concurrency)
- No built-in alerting or notifications
- No persistent event log
- Token refresh not implemented

### Future Enhancements

- PostgreSQL support with connection pooling
- Multiple workers with distributed scheduling
- Email/Slack alerts for downtime
- Webhook notifications
- Custom health check patterns (DNS, TCP, etc.)
- Response validation (check for specific content)
- API rate limiting and quota management
- Audit logging

## 📝 Code Philosophy

This codebase follows these principles:

- **Explicit over implicit**: Code is clear and readable
- **Simple over complex**: No unnecessary abstractions
- **Single responsibility**: Each module has one job
- **Easy to extend**: Add features without refactoring
- **Type hints**: Full type annotations for clarity
- **Minimal dependencies**: Only essential packages

## 📄 License

MIT
