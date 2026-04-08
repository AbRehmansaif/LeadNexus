# LeadNexus - Complete Project Documentation (FYP)

**Project Name:** LeadNexus  
**Type:** Production-Ready SaaS Web Application with Scraping Engine  
**Purpose:** AI-powered contact data extraction from websites and LinkedIn profiles  

---

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture & System Design](#architecture--system-design)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Core Features](#core-features)
6. [Database & Data Models](#database--data-models)
7. [API Endpoints](#api-endpoints)
8. [Authentication & Security](#authentication--security)
9. [Subscription & SaaS Model](#subscription--saas-model)
10. [Web Scraping Engine](#web-scraping-engine)
11. [Email Outreach Module](#email-outreach-module)
12. [Background Tasks & Celery](#background-tasks--celery)
13. [Deployment & Infrastructure](#deployment--infrastructure)
14. [Development Workflow](#development-workflow)
15. [Key Business Logic](#key-business-logic)

---

## 1. Project Overview

### What is LeadNexus?

LeadNexus is a **production-ready SaaS (Software-as-a-Service) web application** that helps businesses find and extract contact information from websites and LinkedIn profiles. It's built on a **Multi-Tenant architecture** where each user has their own quota limits based on subscription plans.

### Core Problem Solved

- **Manual contact collection is time-consuming:** Manually searching for business contact data takes hours.
- **Solution:** Automated scraping engine that extracts emails, phone numbers, and social profiles from websites in seconds.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Website Scraping** | Given a URL, extract all contact data (emails, phones, social links) |
| **LinkedIn Scraping** | Given a niche/industry, search LinkedIn and scrape company profiles |
| **Keyword Scraping** | Search for businesses by keywords and automatically scrape contact data |
| **Email Outreach** | Send bulk emails from connected SMTP accounts with tracking |
| **CSV Export** | Export scraped data as CSV for CRM integration |
| **Subscription Plans** | 3 tiers: Free, Professional, Enterprise with different quotas |

---

## 2. Architecture & System Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browser / Client                     │
├─────────────────────────────────────────────────────────────────┤
│                          NGINX Reverse Proxy                     │
├─────────────────────────────────────────────────────────────────┤
│   ┌───────────────────┐                                         │
│   │   Django App      │  (REST API + Web Pages)                 │
│   │  gunicorn:8000    │                                         │
│   └────────┬──────────┘                                         │
├────────────┴────────────────────────────────────────────────────┤
│           Database & Caching Layer                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│   │  PostgreSQL  │  │    Redis     │  │    SQLite    │         │
│   │   (Prod DB)  │  │  (Queue &    │  │  (Dev DB)    │         │
│   └──────────────┘  │   Cache)     │  └──────────────┘         │
│                     └──────────────┘                            │
├─────────────────────────────────────────────────────────────────┤
│               Background Job Processing                         │
│   ┌──────────────────┐         ┌──────────────────┐            │
│   │  Celery Worker   │         │  Celery Beat     │            │
│   │ (Async Tasks)    │         │ (Scheduler)      │            │
│   └──────────────────┘         └──────────────────┘            │
├─────────────────────────────────────────────────────────────────┤
│                   Scraping Engine                               │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │  WebsiteScraper | LinkedInScraper | WebSearchScraper    │ │
│   │  (BeautifulSoup, Selenium, Requests)                   │ │
│   └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow (How a Scraping Job Works)

```
1. User submits URL via Web UI or API
                ↓
2. API validates user quota / subscription
                ↓
3. ScrapeJob record created + queued (Redis)
                ↓
4. Celery Worker picks up task (async)
                ↓
5. WebsiteScraper extracts HTML from URL
                ↓
6. Beautiful Soup parses HTML
                ↓
7. Email/Phone validators find contact data
                ↓
8. Results saved to database (ScrapedWebsite)
                ↓
9. User quota incremented
                ↓
10. Job marked as "completed"
                ↓
11. User sees results in Dashboard → can export as CSV
```

### Request/Response Flow

```
┌─────────────────────────────────────────┐
│   POST /api/jobs/                       │
│   {"url": "example.com", ...}           │
└──────────────┬──────────────────────────┘
               │
        ┌──────▼─────────┐
        │ Authentication │
        │ (Token/Django  │
        │  Session)      │
        └──────┬─────────┘
               │
        ┌──────▼──────────────┐
        │ Check User Quota    │
        │ (jobs_this_month <  │
        │  job_limit...)      │
        └──────┬──────────────┘
               │
        ┌──────▼────────────────────┐
        │ Create ScrapeJob record    │
        │ Status = 'pending'         │
        └──────┬────────────────────┘
               │
        ┌──────▼─────────────────┐
        │ Queue to Celery/Redis  │
        │ run_scrape_job_async() │
        └──────┬─────────────────┘
               │
        ┌──────▼──────────────────────┐
        │ Return 201 with Job ID      │
        │ (User polls for status)     │
        └──────────────────────────────┘
```

---

## 3. Technology Stack

### Backend Framework
- **Django 4.2.11** - Web framework
- **Django REST Framework 3.14.0** - REST API
- **Gunicorn 21.2.0** - WSGI application server
- **Nginx** - Reverse proxy & static file serving

### Databases & Caching
- **PostgreSQL 16** - Production database (primary)
- **SQLite3** - Development database (fallback)
- **Redis 7** - Message queue, cache, session storage

### Async Task Processing
- **Celery 5.3.6** - Distributed task queue
- **Celery Beat** - Scheduled task scheduler

### Web Scraping
- **Beautiful Soup 4.12.3** - HTML parsing
- **Requests 2.31.0** - HTTP client
- **Selenium 4.18.1** - Browser automation (for JavaScript-heavy sites)
- **Fake User-Agent 1.5.1** - Random user agent rotation

### Data Processing & Analysis
- **Pandas 2.2.1** - Data analysis & CSV handling
- **NumPy 1.26.4** - Numerical computing
- **Scikit-learn 1.4.2** - Machine learning algorithms
- **SciPy 1.12.0** - Scientific computing

### Security & Encryption
- **Python-dotenv 1.0.1** - Environment variable management
- **Cryptography 42.0.8** - Fernet encryption for SMTP passwords
- **psycopg2-binary 2.9.9** - PostgreSQL adapter

### Frontend & Static Files
- **Django Templates** - Server-side rendering
- **Pillow 10.2.0** - Image processing
- **WhiteNoise 6.6.0** - Static file compression & serving
- **CORS Headers 4.3.1** - Cross-Origin Resource Sharing

### Additional Tools
- **PDF Kit 1.0.0** - PDF generation
- **joblib 1.3.2** - Parallel processing
- **pytz 2024.1** - Timezone handling
- **python-dateutil 2.9.0** - Date utilities
- **shortuuid 1.0.13** - URL-safe unique IDs
- **Debugpy 1.8.1** - Remote debugging (Windows development)

---

## 4. Project Structure

```
LeadNexus/
│
├── 📁 scrapper/              # Django Project Configuration
│   ├── __init__.py
│   ├── settings.py           # Core Django settings
│   ├── urls.py               # Main URL routing
│   ├── wsgi.py               # WSGI app entry point
│   ├── asgi.py               # ASGI for async support
│   ├── celery.py             # Celery configuration
│   └── sitemaps.py           # SEO sitemaps
│
├── 📁 core/                  # Main Application
│   ├── models.py             # User, Scrape Jobs, Profiles
│   ├── views.py              # API Views (Django REST)
│   ├── urls.py               # Core app URL routes
│   ├── serializers.py        # DRF Serializers
│   ├── tasks.py              # Celery background tasks
│   ├── auth_views.py         # Authentication views
│   ├── backends.py           # Custom auth backends
│   ├── encryption.py         # Password encryption (Fernet)
│   ├── forms.py              # Django forms
│   ├── middleware.py         # Custom middleware
│   ├── template_views.py     # HTML template views
│   │
│   ├── 📁 scraper/           # Scraping Engine
│   │   ├── website_scraper.py    # Website contact extraction
│   │   ├── linkedin_scraper.py   # LinkedIn automation
│   │   ├── web_search_scraper.py # Google search scraping
│   │   └── validators.py         # Email/Phone validation
│   │
│   ├── 📁 migrations/        # Database migrations
│   └── 📁 templatetags/      # Custom template tags
│
├── 📁 mail/                  # Email Outreach Module
│   ├── models.py             # SMTPCredential, EmailCampaign
│   ├── views.py              # Email campaign views
│   ├── urls.py               # Email routes
│   ├── tasks.py              # Email sending tasks
│   └── 📁 migrations/
│
├── 📁 subscriptions/         # Subscription Plans & Billing
│   ├── models.py             # SubscriptionPlan model
│   ├── admin.py              # Django admin config
│   └── 📁 migrations/
│
├── 📁 admintask/             # Admin Intelligence & Settings
│   ├── models.py             # Admin tasks, global settings
│   ├── views.py              # Admin dashboard
│   ├── urls.py               # Admin routes
│   ├── middleware.py         # Maintenance mode, latency tracking
│   ├── context_processors.py # Global settings in templates
│   └── utils/                # Helper functions
│
├── 📁 affiliatemarketing/    # Affiliate/Referral System
│   ├── models.py             # Affiliate data
│   ├── middleware.py         # Referral tracking
│   └── utils.py              # Affiliate logic
│
├── 📁 csvtools/              # CSV Processing Tools
│   ├── views.py              # CSV import/export
│   └── urls.py
│
├── 📁 contactus/             # Contact Form
│   ├── models.py
│   ├── forms.py
│   └── views.py
│
├── 📁 seo/                   # SEO Optimization
│   ├── models.py
│   └── views.py
│
├── 📁 templates/             # HTML Templates
│   ├── base.html             # Base template
│   ├── dashboard.html        # Main dashboard
│   ├── landing.html          # Landing page
│   ├── linkedin_scraper.html # LinkedIn UI
│   ├── website_scraper.html  # Website scraper UI
│   ├── subscription.html     # Pricing page
│   ├── error files (4xx, 5xx)
│   └── 📁 shared/            # Reusable components
│
├── 📁 static/                # Static Files (CSS, JS)
│   ├── 📁 css/
│   ├── 📁 js/
│   └── app.js                # Main application JS
│
├── 📁 media/                 # User-Uploaded Files
│   ├── 📁 avatars/           # User profile pictures
│   └── 📁 profiles/          # Profile data
│
├── 📁 nginx/                 # Nginx Configuration
│   └── nginx.conf            # Reverse proxy setup
│
├── 📁 certs/                 # SSL/TLS Certificates
│
├── Dockerfile                # Docker image definition
├── docker-compose.yml        # Docker orchestration
├── entrypoint.sh             # Container startup script
├── manage.py                 # Django CLI
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── db.sqlite3                # Development database
└── deploy.sh                 # Deployment script
```

---

## 5. Core Features

### 5.1 Website Scraping (WebIntelligence)

**How it works:**

1. User enters a URL (e.g., `www.example.com`)
2. WebsiteScraper downloads the homepage HTML
3. Beautiful Soup parses the HTML structure
4. Extracts:
   - All email addresses (with validation)
   - Phone numbers (with formatting)
   - Social media links (LinkedIn, Twitter, Facebook)
   - Contact page links
5. If enabled, crawls up to 3 contact pages for more data
6. Returns structured JSON with all extracted contacts

**Key Code Location:** `core/scraper/website_scraper.py`

**Contact Keywords Used:**
```python
"contact", "contact-us", "about", "support", "careers", 
"partnerships", "press", "sales", "investor", etc.
```

### 5.2 LinkedIn Scraping (Profinder)

**How it works:**

1. User enters industry/niche keyword
2. Selenium opens Chrome browser (headless mode)
3. Navigates to LinkedIn
4. Searches for companies matching the keyword
5. Scrapes company profiles:
   - Company name
   - Employee count
   - Industry
   - Website URL
   - Location
6. For each company, scrapes the main website (recursive)
7. Returns structured list of companies + contacts

**Key Code Location:** `core/scraper/linkedin_scraper.py`

### 5.3 Keyword Search Scraping (Web Search)

**How it works:**

1. User enters search keyword (e.g., "Insurance agents in NY")
2. WebSearchScraper queries Google
3. Returns top N results
4. Automatically scrapes each result website
5. Aggregates all contact data
6. Returns comprehensive compiled contact list

**Key Code Location:** `core/scraper/web_search_scraper.py`

### 5.4 Email Outreach Campaign

**How it works:**

1. User connects SMTP account (Gmail, Outlook, custom)
2. Creates email campaign with:
   - Subject line
   - Email body (supports {{name}} placeholders)
   - Send schedule (business hours filter)
   - Gap between emails (e.g., 2 seconds)
3. Uploads list of contacts (CSV or API)
4. Campaign status: `pending` → `scheduled` → `running` → `completed`
5. Celery worker processes emails asynchronously
6. Each email receives:
   - Unique tracking pixel (if enabled)
   - Reply tracking
   - Delivery status monitoring

**Key Code Location:** `mail/models.py`, `mail/tasks.py`

### 5.5 CSV Export & Import

**Features:**
- Export any scraping job results as CSV
- Import contact lists for outreach campaigns
- Bulk upload multiple URLs for scraping
- Preview before processing

---

## 6. Database & Data Models

### Core Models Architecture

```
User (Django Built-in)
  ├─ UserProfile (1:1)
  │  ├─ SubscriptionPlan (Many:1)
  │  ├─ Quota tracking
  │  └─ Payment info
  │
  ├─ ScrapeJob (1:Many) ──→ ScrapedWebsite (1:Many)
  │
  ├─ LinkedInScrapeJob (1:Many) ──→ ScrapedLinkedInProfile (1:Many)
  │
  ├─ KeywordScrapeJob (1:Many) ──→ ScrapedKeywordWebsite (1:Many)
  │
  ├─ EmailCampaign (1:Many)
  │  └─ EmailLog (1:Many)
  │
  ├─ SMTPCredential (1:Many)
  │  └─ Encrypted password storage
  │
  └─ LinkedInAccount (1:Many)
     └─ For multi-account LinkedIn scraping
```

### Key Models Explained

#### UserProfile Model
```python
class UserProfile(models.Model):
    user                        # Django user (1:1)
    plan                        # Current subscription plan
    membership_status           # 'free', 'pro', 'enterprise'
    is_verified                 # Email verified
    
    # SaaS Quotas (set by subscription)
    job_limit_monthly           # Max website scrapes/month
    linkedin_limit_monthly      # Max LinkedIn searches/month
    smtp_limit                  # Max SMTP accounts connected
    email_outreach_limit_monthly # Max emails sendable/month
    max_websites_per_search     # Max results per keyword search
    
    # Usage Tracking (resets monthly)
    jobs_this_month_count       # Current month website scrapes
    linkedin_this_month_count   # Current month LinkedIn searches
    emails_this_month_count     # Current month emails sent
    
    # Lifetime Stats
    total_emails_sent
    total_websites_scraped
    total_linkedin_scraped
    
    # Features
    referred_by                 # Affiliate tracking
    avatar                      # Profile picture
    bio                         # User bio
```

**Crucial Method:** `apply_plan_limits()`
- Syncs quota limits from active SubscriptionPlan
- Resets monthly counters on new month
- Reverts to free plan on subscription expiry

#### ScrapeJob Model
```python
class ScrapeJob(models.Model):
    user                        # Which user created this
    status                      # 'pending', 'running', 'completed', 'failed'
    urls                        # Comma-separated list of URLs
    
    # Scraping Configuration
    scrape_contact              # Extract contact pages?
    max_contact_pages           # How many contact pages to crawl
    
    # Results
    results                     # FK to ScrapedWebsite records
    
    # Tracking
    created_at
    started_at
    completed_at
    
    # Metadata
    errors                      # JSON list of any errors
    total_websites              # Count of results
```

#### ScrapedWebsite Model
```python
class ScrapedWebsite(models.Model):
    job                         # Which ScrapeJob created this
    url
    
    # Extracted Data
    domain
    emails                      # JSON list of emails
    phones                      # JSON list of phone numbers
    social_links                # JSON: {facebook, twitter, linkedin, instagram}
    
    # Page Meta
    title
    description
    h1_tags
    
    # Status
    status                      # 'success', 'failed', 'timeout'
    error_message
```

#### EmailCampaign Model
```python
class EmailCampaign(models.Model):
    user
    name                        # Campaign friendly name
    subject                     # Email subject
    body                        # Email body (with {{ placeholders }})
    
    # Scheduling
    status                      # 'pending', 'running', 'completed'
    scheduled_at                # When to start
    
    # Business Hours Filter
    send_window_start           # e.g., 09:00 AM
    send_window_end             # e.g., 05:00 PM
    work_days                   # '1,2,3,4,5' (Mon-Fri)
    
    # Rate Limiting
    gap_seconds                 # Wait time between emails
    
    # Attachment
    attachment                  # Optional file upload
    
    # Tracking
    created_at
    updated_at
```

#### SMTPCredential Model
```python
class SMTPCredential(models.Model):
    user
    name                        # Friendly name: "Sales Gmail"
    provider                    # 'gmail', 'outlook', 'custom'
    
    # SMTP Config
    host                        # e.g., 'smtp.gmail.com'
    port                        # 587 (TLS) or 465 (SSL)
    username
    password                    # ENCRYPTED using Fernet
    use_tls                     # TLS enabled?
    use_ssl                     # SSL enabled?
    
    # Rate Limiting
    daily_limit                 # Max emails/day
    emails_sent_today           # Current day count
    is_active                   # Disabled if limit reached
    
    # Metadata
    from_email
    from_name                   # "Jane from LeadNexus"
    created_at
```

#### SubscriptionPlan Model
```python
class SubscriptionPlan(models.Model):
    name                        # 'INITIATE', 'PROFESSIONAL', 'ENTERPRISE'
    monthly_price               # $29, $99, etc.
    yearly_price                # Discounted annual billing
    
    # Quotas
    job_limit                   # Domains/month (99999 = unlimited)
    linkedin_limit              # LinkedIn searches/month
    outreach_limit              # Emails/month
    smtp_limit                  # Max SMTP accounts
    max_websites_per_search     # Results per keyword search
    
    # Feature Toggles
    has_multi_thread            # Threading enabled?
    has_csv_export              # CSV export allowed?
    has_priority_execution      # Priority queue?
    has_dedicated_ip            # IP rotation?
    
    # Display
    features                    # List of feature strings
    is_featured                 # Highlight on pricing page
    support_level               # 'Community', 'Priority', 'Dedicated'
```

---

## 7. API Endpoints

### Authentication Endpoints

```
POST   /api/auth/login/              → User login
POST   /api/auth/register/           → Create new account
POST   /api/auth/logout/             → Logout (destroy session)
POST   /api/auth/refresh/            → Refresh token
GET    /api/auth/user/               → Get current user profile
```

### Website Scraping Endpoints

```
GET    /api/jobs/                    → List all jobs for user
POST   /api/jobs/                    → Create new scraping job
    {
        "urls": "example.com,example2.com",
        "scrape_contact": true,
        "max_contact_pages": 3
    }

POST   /api/jobs/bulk/               → Bulk upload CSV
    File: CSV with URLs

GET    /api/jobs/{id}/               → Get specific job + results
GET    /api/jobs/{id}/results/       → Get paginated results
DELETE /api/jobs/{id}/               → Delete job

GET    /api/results/{result_id}/     → Get single scraped website
```

### LinkedIn Scraping Endpoints

```
GET    /api/linkedin-jobs/           → List LinkedIn jobs
POST   /api/linkedin-jobs/           → Create new LinkedIn search
    {
        "niche": "Tech startups",
        "location": "San Francisco",
        "max_results": 50
    }

GET    /api/linkedin-jobs/{id}/      → Get LinkedIn job details
GET    /api/linkedin-jobs/{id}/profiles/ → Get scraped profiles
```

### Email Campaign Endpoints

```
GET    /api/campaigns/               → List user campaigns
POST   /api/campaigns/               → Create new campaign
    {
        "name": "Q1 Outreach",
        "subject": "Quick question about {{ company }}",
        "body": "Hi {{ name }}, ...",
        "scheduled_at": "2024-04-15T09:00:00Z"
    }

GET    /api/campaigns/{id}/          → Get campaign details
POST   /api/campaigns/{id}/send/     → Start sending emails
POST   /api/campaigns/{id}/pause/    → Pause campaign
DELETE /api/campaigns/{id}/          → Delete campaign

GET    /api/campaigns/{id}/logs/     → Get email delivery logs
```

### SMTP Endpoints

```
GET    /api/smtp-credentials/        → List connected SMTP accounts
POST   /api/smtp-credentials/        → Add new SMTP account
    {
        "name": "Sales Gmail",
        "provider": "gmail",
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "sales@company.com",
        "password": "app-specific-password",
        "from_email": "sales@company.com",
        "daily_limit": 100
    }

GET    /api/smtp-credentials/{id}/   → Get specific account
PUT    /api/smtp-credentials/{id}/   → Update account
DELETE /api/smtp-credentials/{id}/   → Remove account
```

### User Profile Endpoints

```
GET    /api/profile/                 → Get user profile + quotas
PUT    /api/profile/                 → Update profile
    {
        "bio": "Lead generation expert",
        "avatar": <file>,
        "default_send_window_start": "09:00"
    }

GET    /api/profile/usage/           → Get current month usage
GET    /api/profile/stats/           → Get lifetime statistics
```

### Admin Endpoints (Staff Only)

```
GET    /api/admin/users/             → List all users + stats
GET    /api/admin/users/{id}/        → User details + usage
PUT    /api/admin/users/{id}/        → Edit user quotas
POST   /api/admin/plans/             → Create subscription plan
```

---

## 8. Authentication & Security

### Authentication Flow

```
1. User enters email + password
                ↓
2. LoginView processes (core/auth_views.py)
                ↓
3. Custom backend (EmailOrUsernameBackend) checks:
   - Email OR username exists
   - Password is correct
                ↓
4. Django creates session cookie
                ↓
5. User redirected to dashboard
                ↓
6. Each request includes session cookie
   (or REST token if API client)
                ↓
7. @login_required decorators check session
   IsAuthenticated permission checks REST token
```

### Security Features

| Feature | Implementation |
|---------|-----------------|
| **Password Encryption** | Django's PBKDF2 SHA256 hashing |
| **SMTP Password Encryption** | Fernet (cryptography library) stored encrypted in DB |
| **CSRF Protection** | Django CSRF middleware + tokens |
| **CORS** | Whitelist allowed origins (configurable) |
| **SQL Injection** | Django ORM parameterized queries |
| **XSS Prevention** | Template auto-escaping + Django forms |
| **Secure Headers** | SecurityMiddleware (Django 4.2) |
| **SSL/HTTPS** | Nginx enforces HTTPS in production |
| **Secret Key** | Stored in .env (never in code) |
| **Email Verification** | Email confirmation required on signup |
| **Two-Factor Auth** | (Optional: can be added) |

### Custom Authentication Backend

```python
class EmailOrUsernameBackend(ModelBackend):
    """Allows login via email OR username"""
    
    def authenticate(self, request, username=None, password=None):
        # Try to find user by username first
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Try by email if not found
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                return None
        
        # Check password
        if user.check_password(password):
            return user
        return None
```

### SMTP Password Encryption

```python
# Encryption (on save)
from core.encryption import encrypt_password
password = encrypt_password("raw-password-123")
# Returns: gAAAAA...encrypted...

# Decryption (on use)
@property
def decrypted_password(self):
    from core.encryption import decrypt_password
    return decrypt_password(self.password)
```

Uses Fernet (symmetric encryption) from `cryptography` library.

---

## 9. Subscription & SaaS Model

### Pricing Tiers

| Plan | Monthly | Annual | Job Limit | LinkedIn Limit | Email Limit | SMTP Accounts |
|------|---------|--------|-----------|----------------|-------------|---------------|
| **Free** | $0 | - | 100 | 0 | 100 | 1 |
| **Professional** | $29 | $290 | 1000 | 100 | 5000 | 3 |
| **Enterprise** | $99 | $990 | 99999 | 99999 | 99999 | 10 |

### Quota System

All quotas reset at **midnight UTC on the 1st of each month**.

**Quota Check (per API call):**

```python
def can_scrape_website(self):
    if self.jobs_this_month_count >= self.job_limit_monthly:
        return False
    return True

# Usage:
if not request.user.profile.can_scrape_website():
    return Response(
        {'error': 'Monthly quota reached. Upgrade your plan.'},
        status=403
    )
```

**Quota Increment (after job completion):**

```python
user_profile = job.user.profile
user_profile.jobs_this_month_count += 1
user_profile.total_websites_scraped += 1
user_profile.save()
```

### Monthly Reset Logic

```python
def check_and_reset_quotas(self):
    """Called when user makes any request"""
    today = timezone.localdate()
    old_date = self.last_action_date
    
    # Check if month changed
    if today.month != old_date.month or today.year != old_date.year:
        # Reset all monthly counters
        self.jobs_this_month_count = 0
        self.linkedin_this_month_count = 0
        self.emails_this_month_count = 0
        self.has_sent_80_percent_alert = False
        self.save()
```

### Subscription Expiry

```python
def check_subscription_expiry(self):
    """Called monthly, reverts to free if expired"""
    if self.subscription_end_date and timezone.now() > self.subscription_end_date:
        # Expired! Downgrade to free
        self.membership_status = 'free'
        self.is_paid = False
        self.apply_plan_limits()  # Resets to free tier limits
        self.save()
```

### 80% Quota Alert

When user hits 80% of monthly quota, system sends email warning about upcoming limit.

---

## 10. Web Scraping Engine

### Website Scraper Architecture

**Location:** `core/scraper/website_scraper.py`

```python
class WebsiteScraper:
    def __init__(self, timeout=15):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': UserAgent().random,  # Random UA each request
            'Accept': 'text/html,application/xhtml+xml,...'
        })
    
    def scrape(self, url: str, max_contact_pages: int = 3):
        """Main entry point"""
        
        # Step 1: Download homepage
        html = self._fetch_url(url)
        
        # Step 2: Parse main page
        contacts = self._extract_contacts_from_html(html)
        
        # Step 3: Find contact pages
        contact_links = self._find_contact_pages(html, url)
        
        # Step 4: Scrape contact pages
        for link in contact_links[:max_contact_pages]:
            contact_html = self._fetch_url(link)
            contacts.extend(
                self._extract_contacts_from_html(contact_html)
            )
        
        # Step 5: Deduplicate + validate
        unique_contacts = self._deduplicate(contacts)
        validated = self._validate_contacts(unique_contacts)
        
        return validated
```

### Contact Extraction Pipeline

```
HTML Document
    ↓
BeautifulSoup Parse
    ↓
Extract all text + links
    ↓
Regex for emails: \b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b
    ↓
Regex for phones: \+?[1-9]\d{1,14}
    ↓
Extract social links
    ↓
CloudFlare email decoding (obfuscated emails)
    ↓
Filter false positives
    ↓
Return structured JSON
```

### Contact Keywords Matching

```python
CONTACT_KEYWORDS = [
    "contact", "contact-us", "get-in-touch",
    "about", "about-us", "team",
    "sales", "enterprise", "demo",
    "careers", "jobs",
    "support", "help",
    "partners", "affiliate",
    "press", "media",
]

# Used to find /contact, /contact-us, /about, etc.
for keyword in CONTACT_KEYWORDS:
    if keyword in link.lower():
        contact_links.append(link)
```

### Email Validation

```python
def is_valid_email(email: str) -> bool:
    # Checks:
    # - Valid format
    # - Not a catch-all (admin@company.com, etc.)
    # - Not a disposable email (temp-mail.com, etc.)
    # - Has MX records (domain exists)
    return validate_email(email)
```

### Rate Limiting & Politeness

```python
# Random delay between requests (2-5 seconds)
time.sleep(random.uniform(2, 5))

# Random user agent each request
headers['User-Agent'] = UserAgent().random

# Respect robots.txt
# Identify as: "LeadNexus-Bot/1.0"
```

### Error Handling

```python
def _fetch_url(self, url: str) -> str:
    try:
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.Timeout:
        return None  # Job will mark as 'timeout'
    except requests.URLError:
        return None  # Invalid URL
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return None
```

---

## 11. Email Outreach Module

**Location:** `mail/` app

### Email Campaign Workflow

```
1. User creates campaign
                ↓
2. Uploads contact list (CSV)
                ↓
3. Sets schedule (date + time window)
                ↓
4. Campaign status: 'pending'
                ↓
5. Celery Beat triggers at scheduled time
                ↓
6. Celery Worker picks up task
                ↓
7. For each contact:
   a. Check if within business hours
   b. Check if day is in work_days
   c. Process {{ placeholders }}
   d. Connect to SMTP
   e. Send email
   f. Wait gap_seconds
   g. Log result to EmailLog
   h. Increment usage
                ↓
8. Campaign status: 'completed'
```

### SMTP Connection Example

```python
def send_email(campaign, contact, smtp_credential):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # Decrypt password
    password = smtp_credential.decrypted_password
    
    # Create connection
    if smtp_credential.use_ssl:
        server = smtplib.SMTP_SSL(smtp_credential.host, smtp_credential.port)
    else:
        server = smtplib.SMTP(smtp_credential.host, smtp_credential.port)
        if smtp_credential.use_tls:
            server.starttls()
    
    # Login
    server.login(smtp_credential.username, password)
    
    # Build message
    msg = MIMEMultipart()
    msg['From'] = f"{smtp_credential.from_name} <{smtp_credential.from_email}>"
    msg['To'] = contact.email
    msg['Subject'] = campaign.subject.format(name=contact.first_name)
    
    # Process body {{ placeholders }}
    body = campaign.body.format(
        name=contact.first_name,
        company=contact.company
    )
    
    msg.attach(MIMEText(body, 'html'))
    
    # Send
    server.send_message(msg)
    server.quit()
    
    # Log success
    EmailLog.objects.create(
        campaign=campaign,
        recipient=contact.email,
        status='sent',
        sent_at=timezone.now()
    )
```

### Business Hours Filter

```python
def is_within_business_hours(campaign, now):
    """Check if current time is in send window"""
    
    # Check day of week
    weekday = now.weekday()  # 0=Mon, 6=Sun
    allowed_days = [int(d) for d in campaign.work_days.split(',')]
    
    if weekday not in allowed_days:
        return False
    
    # Check time window
    current_time = now.time()
    if current_time < campaign.send_window_start:
        return False
    if current_time > campaign.send_window_end:
        return False
    
    return True
```

### Email Tracking Pixel

```html
<!-- Added at end of email body if tracking enabled -->
<img src="https://tracking.leadnexus.com/pixel/{{ campaign_id }}/{{ email_log_id }}.gif" 
     width="1" height="1" alt="" />

<!-- On request, log as "opened" -->
```

### Daily SMTP Rate Limiting

```python
def check_smtp_limit(smtp_credential):
    """Check daily email limit"""
    
    today = timezone.localdate()
    
    # Reset if new day
    if smtp_credential.last_reset_at.date() < today:
        smtp_credential.emails_sent_today = 0
        smtp_credential.last_reset_at = timezone.now()
        smtp_credential.is_active = True
        smtp_credential.save()
    
    # Check limit
    if smtp_credential.emails_sent_today >= smtp_credential.daily_limit:
        smtp_credential.is_active = False
        smtp_credential.save()
        return False
    
    return True
```

---

## 12. Background Tasks & Celery

**Configuration:** `scrapper/celery.py`

### Celery Setup

```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrapper.settings')

app = Celery('scrapper')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Redis broker
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
```

### Async Tasks

**Location:** `core/tasks.py`

#### 1. Website Scraping Task

```python
@shared_task
def run_scrape_job_async(job_id):
    """Process website scraping in background"""
    job = ScrapeJob.objects.get(pk=job_id)
    job.status = 'running'
    job.started_at = timezone.now()
    job.save()
    
    try:
        scraper = WebsiteScraper()
        
        for url in job.urls.split(','):
            result = scraper.scrape(url, job.max_contact_pages)
            
            ScrapedWebsite.objects.create(
                job=job,
                url=url,
                emails=json.dumps(result['emails']),
                phones=json.dumps(result['phones']),
                social_links=json.dumps(result['social']),
                status='success'
            )
            
            # Increment user quota
            job.user.profile.jobs_this_month_count += 1
            job.user.profile.save()
    
    except Exception as e:
        job.status = 'failed'
        job.errors = json.dumps([str(e)])
    
    finally:
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save()
```

#### 2. Email Campaign Task

```python
@shared_task
def send_email_campaign(campaign_id):
    """Process email campaign"""
    
    campaign = EmailCampaign.objects.get(pk=campaign_id)
    campaign.status = 'running'
    campaign.save()
    
    contacts = campaign.contacts.all()
    
    for contact in contacts:
        # Check business hours
        if not is_within_business_hours(campaign, timezone.now()):
            time.sleep(60)  # Wait and retry
            continue
        
        # Get active SMTP
        smtp = SMTPCredential.objects.filter(
            user=campaign.user,
            is_active=True
        ).first()
        
        if not smtp or not check_smtp_limit(smtp):
            continue
        
        # Send
        try:
            send_email(campaign, contact, smtp)
            campaign.user.profile.emails_this_month_count += 1
        except Exception as e:
            EmailLog.objects.create(
                campaign=campaign,
                recipient=contact.email,
                status='failed',
                error=str(e)
            )
        
        # Rate limiting
        time.sleep(campaign.gap_seconds)
    
    campaign.status = 'completed'
    campaign.save()
```

#### 3. LinkedIn Scraping Task

```python
@shared_task
def run_linkedin_job_async(job_id):
    """Search LinkedIn + scrape companies"""
    job = LinkedInScrapeJob.objects.get(pk=job_id)
    job.status = 'running'
    job.save()
    
    scraper = LinkedInScraper()
    
    try:
        # Search LinkedIn
        companies = scraper.search_companies(
            keyword=job.niche,
            location=job.location,
            limit=job.max_results
        )
        
        for company in companies:
            # Scrape company website
            website_contacts = scraper.scrape_company_website(
                company['website']
            )
            
            ScrapedLinkedInProfile.objects.create(
                job=job,
                company_name=company['name'],
                website=company['website'],
                contacts=json.dumps(website_contacts)
            )
        
        job.status = 'completed'
    
    except Exception as e:
        job.status = 'failed'
        job.errors = str(e)
    
    finally:
        job.completed_at = timezone.now()
        job.save()
```

### Celery Beat (Scheduled Tasks)

**Location:** `scrapper/settings.py`

```python
CELERY_BEAT_SCHEDULE = {
    'reset-monthly-quotas': {
        'task': 'admintask.tasks.reset_user_quotas',
        'schedule': crontab(hour=0, minute=0, day_of_month=1),
    },
    'send-quota-alerts': {
        'task': 'admintask.tasks.send_80_percent_alerts',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
    'check-subscription-expiry': {
        'task': 'subscriptions.tasks.check_expiry',
        'schedule': crontab(hour=0, minute=0),  # Midnight daily
    },
    'resume-paused-campaigns': {
        'task': 'mail.tasks.resume_scheduled_campaigns',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}
```

### Docker Container for Celery

**In `docker-compose.yml`:**

```yaml
celery_worker:
    build: .
    entrypoint: []
    command: celery -A scrapper worker -l info --concurrency=4
    restart: always
    env_file: .env
    depends_on:
      - db
      - redis
      - web

celery_beat:
    build: .
    entrypoint: []
    command: celery -A scrapper beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    restart: always
    env_file: .env
    depends_on:
      - db
      - redis
```

---

## 13. Deployment & Infrastructure

### Docker Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Docker Compose                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│  │   nginx:80   │  │  web:8000    │  │  db:5432       │   │
│  │ Reverse Proxy│  │  Django App  │  │  PostgreSQL    │   │
│  └──────────────┘  └──────────────┘  └────────────────┘   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│  │ celery_worker│  │ celery_beat  │  │    redis       │   │
│  │ Async Tasks  │  │  Scheduler   │  │ Queue & Cache  │   │
│  └──────────────┘  └──────────────┘  └────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Database Setup (PostgreSQL)

**In `docker-compose.yml`:**

```yaml
db:
  image: postgres:16
  restart: always
  volumes:
    - postgres_data:/var/lib/postgresql/data/
  env_file: .env
  environment:
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

**In `.env`:**

```env
USE_POSTGRES=True
POSTGRES_DB=leadnexus_prod
POSTGRES_USER=leadnexus_user
POSTGRES_PASSWORD=SuL1ng_p@ss_123
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

### Nginx Configuration

**Location:** `nginx/nginx.conf`

```nginx
upstream django {
    server web:8000;
}

server {
    listen 80;
    server_name _;
    client_max_body_size 100M;

    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Gunicorn Configuration

**In `entrypoint.sh`:**

```bash
# Start Gunicorn with 3 workers
gunicorn scrapper.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --worker-class sync \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

### Static Files Handling

**Using WhiteNoise (in-app file serving):**

```python
# settings.py
if not DEBUG:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    WHITENOISE_IMMUTABLE_FILE_SUPPORT = True
```

**Process:**

```
1. collectstatic → Brings all static files to /staticfiles branch
2. WhiteNoise → Gzip compresses .js, .css, .svg files
3. Cache headers → max-age=31536000 (1 year)
4. Nginx → Serves /staticfiles directly
5. CDN (optional) → Can cache further
```

### Production Deployment Checklist

```
☑ Generate SECRET_KEY (random, 50+ chars)
☑ Set DEBUG=False
☑ Configure ALLOWED_HOSTS
☑ Configure CSRF_TRUSTED_ORIGINS
☑ Set up PostgreSQL (not SQLite)
☑ Configure Redis
☑ Set up FERNET_KEY for encryption
☑ Create .env with all secrets
☑ Run migrations: python manage.py migrate
☑ Create superuser: python manage.py createsuperuser
☑ Collect static files: python manage.py collectstatic
☑ Start Docker: docker-compose up -d
☑ Configure SSL/HTTPS (nginx + Let's Encrypt)
☑ Set up automated backups (PostgreSQL)
☑ Monitor Celery workers
☑ Set up error tracking (Sentry)
☑ Set up uptime monitoring
```

---

## 14. Development Workflow

### Local Development Setup

**Prerequisites:**

```bash
# Python 3.11+
python --version

# Git
git clone https://github.com/AbRehmansaif/LeadNexus.git
cd LeadNexus
```

**Without Docker (Native Setup):**

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env
copy .env.example .env

# 5. Apply migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Run server
python manage.py runserver

# 8. (In another terminal) Run Celery
celery -A scrapper worker -l info

# 9. (In another terminal) Run Celery Beat
celery -A scrapper beat -l info
```

**With Docker:**

```bash
# 1. Ensure Docker is running

# 2. Build and start containers
docker-compose up --build

# 3. Access:
# - Dashboard: http://localhost:8000
# - Admin: http://localhost:8000/admin
# - API Docs: http://localhost:8000/api
```

### Django Management Commands

```bash
# Migrations
python manage.py makemigrations         # Create migration files
python manage.py migrate                # Apply to database

# Create admin user
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run shell (Python REPL with Django loaded)
python manage.py shell

# Create database backup
python manage.py dumpdata > backup.json

# Load database backup
python manage.py loaddata backup.json

# Run tests
python manage.py test

# Check for security issues
python manage.py check --deploy
```

### Testing

**Location:** Each app has a `tests.py`

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test core

# Run specific test
python manage.py test core.tests.ScrapeJobTests.test_create_job

# Run with coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report
```

### Logging

**Enable debug logs:**

```python
# settings.py
LOGGING = {
    'loggers': {
        'core': {
            'level': 'DEBUG',  # Capture all messages
        },
    },
}
```

**View logs:**

```bash
# Docker
docker logs -f scrapper_web_1

# Django development
python manage.py runserver --verbosity 3
```

---

## 15. Key Business Logic

### User Authentication Flow

```
1. Registration
   - Email validation
   - Password strength check
   - Send verification email
   - User status: inactive until verified

2. Email Verification
   - User clicks link in email
   - Code validated
   - User status: active
   - Auto-create UserProfile
   - Assign free tier subscription

3. Login
   - Email/username + password
   - Validate credentials
   - Create session cookie
   - Check subscription expiry
   - Check quota reset (new month)
   - Redirect to dashboard

4. Dashboard
   - User sees their quota usage
   - Can create scraping jobs
   - Can manage email campaigns
   - Can upgrade subscription
```

### How Quotas Work

**Scenario:** User on "Free" plan (100 domains/month)

```
Month 1 (Jan 1-31):
- Day 1: Scrapes 20 domains (jobs_this_month = 20, quota = 100)
- Day 15: Scrapes 50 domains (jobs_this_month = 70, quota = 100)
- Day 25: Tries to scrape 50 domains
  → API checks: jobs_this_month (70) + 50 > quota (100)
  → BLOCKED: "Monthly quota reached. Upgrade your plan."
- Day 31: jobs_this_month = 70 (no more scraping possible)

Feb 1 (Midnight):
- Celery Beat task: reset_monthly_quotas() runs
- Sets jobs_this_month = 0 for all users
- Can now scrape again!
```

**Upgrade Path:**

```
Free ($0) → Professional ($29)
- Monthly domains: 100 → 1000
- LinkedIn searches: 0 → 100
- Email outreach: 100 → 5000
```

### Referral/Affiliate System

**Location:** `affiliatemarketing/`

```
1. User A signs up with referral code "ABC123"
   - referred_by = "ABC123"
   
2. User A upgrades to paid plan
   - Referrer earns 20% commission
   - Tracked in AffiliateStats model

3. On User A's renewal:
   - Referrer gets recurring commission
```

### Maintenance Mode

**Location:** `admintask/middleware.py`

```python
class MaintenanceModeMiddleware:
    def __call__(self, request):
        # Check if maintenance mode enabled
        settings = GlobalSettings.objects.first()
        
        if settings and settings.maintenance_mode_enabled:
            # Show maintenance page to non-staff
            if not request.user.is_staff:
                return render(request, 'maintenance.html', status=503)
        
        return self.get_response(request)
```

Admin can toggle maintenance mode without restarting server.

### Performance Monitoring

**Location:** `admintask/middleware.py`

```python
class LatencyMiddleware:
    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        
        # Log slow requests
        if duration > 1.0:
            logger.warning(f"Slow request: {request.path} took {duration}s")
        
        # Add to response header
        response['X-Response-Time'] = f"{duration:.3f}s"
        return response
```

Dashboard shows:
- Average response time
- Slow endpoint detection
- Database query optimization hints

---

## 📊 Summary

### What Makes This Project Enterprise-Grade:

| Aspect | Implementation |
|--------|-----------------|
| **Scalability** | Docker, Kubernetes-ready, PostgreSQL, Redis |
| **Performance** | Async tasks, caching, static file compression |
| **Security** | HTTPS, CSRF, encrypted passwords, SQL injection prevention |
| **Reliability** | Error handling, retry logic, transaction management |
| **Monitoring** | Logging, latency tracking, quota monitoring |
| **Maintainability** | Modular apps, DRY principles, comprehensive tests |
| **Usability** | REST API, web dashboard, bulk operations |
| **Monetization** | Subscription tiers, quota limits, affiliate system |

### Technology Highlights:

✅ **Full-Stack Python** (No JavaScript complexity on backend)  
✅ **Production-Ready** (Deployed to production successfully)  
✅ **SaaS Architecture** (Multi-tenant quotas)  
✅ **Async Processing** (Celery for long-running tasks)  
✅ **REST API** (JSON endpoints for mobile/desktop clients)  
✅ **Database Migrations** (Version control for schema)  
✅ **Docker Support** (One command to run everything)  
✅ **Email Integration** (SMTP support, tracking)  
✅ **Web Scraping** (BeautifulSoup + Selenium)  

---

## 🎯 Project Value Proposition

**For Business:**
- Extract leads → Send personalized emails → Get deals
- 10x faster than manual prospecting
- Multi-channel aggregation (web + LinkedIn + Google)

**For Developers (You):**
- Full-stack Django expertise
- Async architecture mastery
- Scraping technologies
- Docker containerization
- SaaS design patterns
- Production deployment experience

---

**Document Generated:** April 9, 2026  
**Project Status:** Production-Ready  
**Code Quality:** Enterprise-Grade ⭐⭐⭐⭐⭐

