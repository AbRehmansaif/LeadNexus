# LeadNexus - Executive Summary for FYP Evaluation

## 🎯 Project in 60 Seconds

**LeadNexus** is a production-ready **SaaS (Software-as-a-Service) web platform** that automates the process of finding and extracting business contact information from websites and LinkedIn profiles.

**Problem It Solves:**
- Manual lead generation takes hours
- Businesses need contact data but scraping is tedious
- No centralized platform for multi-source contact aggregation

**Solution:**
- Enter a URL → Extract emails, phones, social profiles automatically
- Search LinkedIn → Get company insights + contacts
- Upload contact list → Send personalized bulk emails
- Pay-as-you-go via subscription tiers

**Real-World Usage:** Sales teams, recruiters, marketers use it to build targeted contact lists for cold outreach.

---

## 📊 Project Statistics

| Metric | Value |
|--------|-------|
| **Total Python Files** | 40+ |
| **Total Lines of Code** | ~5,000+ |
| **Django Apps** | 7 major apps |
| **Database Models** | 15+ models |
| **API Endpoints** | 30+ REST endpoints |
| **External Dependencies** | 35+ packages |
| **Development Time** | Months of production development |
| **Status** | Live production system |

---

## 🏗️ Architecture at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                  User Browser                           │
│  (Dashboard, Scraper UI, Email Campaign Manager)       │
└───────────────┬─────────────────────────────────────────┘
                │ HTTPS
                ↓
        ┌───────────────────┐
        │ Nginx Reverse     │ (Load balancing, static files)
        │ Proxy :80/:443    │
        └────────┬──────────┘
                 │
    ┌────────────┴───────────────┐
    ↓                            ↓
┌──────────────┐      ┌──────────────────────────┐
│  Django App  │      │  Static/Media Files      │
│  Gunicorn    │      │  (CSS, JS, Images)      │
│  :8000       │      │  WhiteNoise Compressed   │
└──────┬───────┘      └──────────────────────────┘
       │                    
       ├─▶ PostgreSQL DB        (Data storage)
       ├─▶ Redis Queue          (Task scheduling)
       └─▶ Celery Workers       (Background processing)
       
       └─▶ WebsiteScraper       (HTML extraction)
           LinkedInScraper      (LinkedIn automation)
           EmailSender          (SMTP integration)
```

---

## 🔑 Core Components

### 1. **User Management & Authentication**
- Email/password registration
- Email verification
- Session-based authentication
- Support for both email and username login

### 2. **Website Scraping Engine**
**What:** Extracts contact data from any website
**How:**
- Downloads HTML via Requests library
- Parses with BeautifulSoup
- Regex finds emails, phones, social links
- Crawls up to 3 contact pages
- Validates extracted data

**Output:** JSON with emails, phones, company info

### 3. **LinkedIn Integration**
**What:** Search LinkedIn for companies + scrape their websites
**How:**
- Uses Selenium (headless Chrome)
- Automates LinkedIn search
- Extracts company profiles
- Recursively scrapes each company website
- Returns comprehensive company + contact data

### 4. **Email Outreach Module**
**What:** Send personalized bulk emails with tracking
**How:**
- Connect multiple SMTP accounts
- Create email templates with {{placeholders}}
- Set business hours filter (09:00-17:00, Mon-Fri)
- Send emails asynchronously (avoid email blocking)
- Track opens via pixel
- Log all delivery status

### 5. **Subscription & Quotas**
**What:** SaaS billing model with 3 tiers
**Tiers:**
- **Free:** 100 domains/month, 100 emails/month
- **Professional:** 1,000 domains/month, 5,000 emails/month, $29/month
- **Enterprise:** Unlimited, additional features, $99/month

**Features:**
- Monthly quota reset
- Quota enforcement per API call
- Upgrade/downgrade anytime
- Usage tracking (lifetime + monthly)
- 80% quota alert notifications

### 6. **Background Task Processing**
**What:** Async job execution (Celery + Redis)
**Jobs:**
- Website scraping (long-running)
- LinkedIn searches (long-running)
- Email campaign sending (batched)
- Monthly quota resets (scheduled)
- Subscription expiry checks (scheduled)

**Benefit:** UI never blocks, users see real-time progress

### 7. **Admin Dashboard**
**What:** System administration & monitoring
**Features:**
- View all user statistics
- Manually adjust user quotas
- Toggle maintenance mode
- Monitor system performance
- View email delivery logs
- Manage subscription plans

---

## 🛠️ Technology Stack (Production-Grade)

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.11 |
| **Web Framework** | Django 4.2 |
| **API** | Django REST Framework |
| **Database** | PostgreSQL (prod) / SQLite (dev) |
| **Cache/Queue** | Redis |
| **Async Jobs** | Celery |
| **Web Server** | Gunicorn |
| **Reverse Proxy** | Nginx |
| **HTML Parser** | BeautifulSoup 4 |
| **HTTP Client** | Requests + Selenium |
| **Containerization** | Docker + Docker Compose |
| **Encryption** | Cryptography (Fernet) |
| **Static Files** | WhiteNoise |

**Why These Choices:**
- Django: mature, batteries-included framework
- PostgreSQL: reliable ACID database
- Celery: standard for async tasks in Python
- Docker: easily deploy anywhere
- Nginx: proven, fast, lightweight

---

## 📁 Project Structure Breakdown

```
LeadNexus/
├── scrapper/
│   ├── settings.py      ← Django configuration
│   ├── urls.py          ← Main URL routes
│   ├── celery.py        ← Celery configuration
│   └── wsgi.py          ← WSGI application entry
│
├── core/
│   ├── models.py        ← Core database models (ScrapeJob, UserProfile)
│   ├── views.py         ← REST API endpoints
│   ├── serializers.py   ← JSON serialization
│   ├── tasks.py         ← Celery background tasks
│   ├── auth_views.py    ← Authentication/Login views
│   └── scraper/         ← Scraping engines
│       ├── website_scraper.py
│       ├── linkedin_scraper.py
│       └── web_search_scraper.py
│
├── mail/
│   ├── models.py        ← EmailCampaign, SMTPCredential
│   ├── views.py         ← Email UI
│   ├── tasks.py         ← Email sending task
│   └── urls.py          ← Email routes
│
├── subscriptions/
│   ├── models.py        ← SubscriptionPlan model
│   └── admin.py         ← Admin interface
│
├── admintask/
│   ├── models.py        ← AdminSettings
│   ├── views.py         ← Admin dashboard
│   ├── middleware.py    ← Maintenance mode, performance tracking
│   └── context_processors.py ← Global template variables
│
├── templates/           ← HTML pages
│   ├── base.html        ← Master template
│   ├── dashboard.html   ← Main dashboard
│   ├── login.html
│   ├── registration.html
│   └── ... (15+ templates)
│
├── static/
│   ├── css/             ← Stylesheets
│   └── js/
│       └── app.js       ← Frontend logic
│
├── Dockerfile           ← Container definition
├── docker-compose.yml   ← Orchestration config
├── entrypoint.sh        ← Container startup script
├── nginx/nginx.conf     ← Reverse proxy config
└── requirements.txt     ← Python dependencies
```

---

## 🔄 Data Flow: User Scrapes a Website

```
1. User enters URL "amazon.com" in web UI
   ↓
2. JavaScript sends: POST /api/jobs/
   ├─ Payload: {"urls": "amazon.com", "scrape_contact": true}
   ↓
3. Django API validates:
   ├─ Is user authenticated? ✓
   ├─ Has quota remaining? ✓ (95/100 domains used)
   ├─ Create ScrapeJob record
   └─ Queue: run_scrape_job_async(job_id=123)
   ↓
4. Returns: {"id": 123, "status": "pending", "created_at": "..."}
   ↓
5. User polls: GET /api/jobs/123/ (every 2 sec)
   ├─ Returns: status="pending" (still processing)
   ↓
6. Meanwhile... Celery Worker processes task:
   ├─ WebsiteScraper.scrape("amazon.com")
   │  ├─ GET https://amazon.com → HTML
   │  ├─ Beautiful Soup parses HTML
   │  ├─ Regex finds: contact@amazon.com, +1-206-266-1000
   │  ├─ Finds /contact page
   │  ├─ Scrapes /contact → finds 5 more emails
   │  └─ Returns: {emails: [...], phones: [...], social: {...}}
   │
   ├─ Save to database: ScrapedWebsite
   ├─ Increment quota: user.jobs_this_month_count = 96
   └─ Set status = "completed"
   ↓
7. Next poll: GET /api/jobs/123/
   ├─ Returns: status="completed", results=[{
   │     "url": "amazon.com",
   │     "emails": ["contact@amazon.com", ...],
   │     "phones": ["+1-206-266-1000", ...],
   │     "social": {...}
   │  }]
   ↓
8. Frontend shows results
   User can:
   ├─ View extracted data
   ├─ Export as CSV
   ├─ Create email campaign
   └─ Share results
```

---

## 💰 SaaS Business Model

### Pricing Strategy

| Feature | Free | Professional | Enterprise |
|---------|------|--------------|-----------|
| Price/Month | $0 | $29 | $99 |
| Website Scrapes | 100 | 1,000 | ∞ |
| LinkedIn Searches | 0 | 100 | ∞ |
| Email Outreach | 100 | 5,000 | ∞ |
| SMTP Accounts | 1 | 3 | 10 |
| Support | Community | Email | Dedicated |

### Revenue Model
- Customers subscribe monthly or annually
- All quotas reset on 1st of month
- Users can upgrade/downgrade anytime
- Affiliate referral commission (20% of revenue)

### Quota Enforcement
```python
# Every API call checks:
if user.jobs_this_month_count >= user.job_limit_monthly:
    return error_403("Quota exceeded")
```

---

## 🔐 Security Features

| Feature | Implementation |
|---------|-----------------|
| Password Security | PBKDF2-SHA256 hashing (Django default) |
| SMTP Password | Encrypted with Fernet (cryptography library) |
| CSRF Protection | Django CSRF middleware + tokens |
| XSS Prevention | Template auto-escaping |
| SQL Injection | Django ORM parameterized queries |
| HTTPS/SSL | Nginx enforces HTTPS in production |
| Session Security | Secure + httponly cookie flags |
| API Authentication | Token authentication (optional) |
| Rate Limiting | Redis-backed rate limits per IP |
| Email Verification | Required on signup |

---

## 🚀 Deployment

### Local Development
```bash
# With Docker (Recommended)
docker-compose up --build

# Without Docker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
celery -A scrapper worker -l info
```

### Production Deployment
```bash
# 1. Set environment variables in .env
SECRET_KEY=<generated>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
POSTGRES_DB=leadnexus_prod
POSTGRES_PASSWORD=<strong-password>

# 2. Deploy
docker-compose -f docker-compose.yml up -d

# 3. Containers start automatically:
# - Web (Gunicorn)
# - Database (PostgreSQL)
# - Cache (Redis)
# - Celery Worker
# - Celery Beat
# - Nginx
```

---

## 📈 Key Achievements

✅ **Full-stack application** - Frontend + Backend + Database + Async jobs  
✅ **Production-ready** - Currently running live  
✅ **Scalable architecture** - Docker, PostgreSQL, Redis, Celery  
✅ **REST API** - 30+ endpoints for frontend/mobile clients  
✅ **SaaS monetization** - Subscription tiers with quota enforcement  
✅ **Web scraping at scale** - Handles thousands of websites  
✅ **Email automation** - Bulk outreach with tracking  
✅ **Security best practices** - Encryption, CSRF, XSS prevention  
✅ **Async processing** - Background jobs don't block UI  
✅ **Admin dashboard** - System management & analytics  

---

## 🎓 Why This is a Strong FYP Project

1. **Complexity:** ~5,000+ lines of code across 7 Django apps
2. **Real-world relevance:** Addresses actual business need (lead generation)
3. **Technical depth:**
   - Database design (models, migrations, relationships)
   - REST API development
   - Background task processing (Celery)
   - Web scraping (Beautiful Soup, Selenium)
   - Authentication & authorization
   - SaaS subscription model
4. **DevOps:** Docker, Nginx, PostgreSQL, Redis
5. **Production quality:** Error handling, logging, monitoring
6. **Full lifecycle:** Design → Development → Testing → Deployment

---

## 📊 Database Schema Overview

```
User
├─ UserProfile (1:1)
│  ├─ jobs_this_month_count
│  ├─ linkedin_this_month_count
│  ├─ emails_this_month_count
│  └─ subscription_end_date
│
├─ ScrapeJob (1:Many)
│  └─ ScrapedWebsite (1:Many)
│     ├─ emails (JSON)
│     ├─ phones (JSON)
│     └─ social_links (JSON)
│
├─ EmailCampaign (1:Many)
│  └─ EmailLog (1:Many)
│     ├─ recipient (email)
│     ├─ status (sent/failed)
│     └─ opened_at (tracking)
│
└─ SMTPCredential (1:Many)
   └─ password (encrypted)
```

---

## 🎯 Next Steps for Evaluation

**What to Demonstrate:**
1. Live scraping of a website (fast extraction)
2. Email campaign creation + sending
3. Subscription quota enforcement
4. Admin dashboard analytics
5. REST API endpoints
6. Docker deployment

**Key Files to Review:**
- `PROJECT_DOCUMENTATION.md` - Complete A-Z guide
- `TECHNICAL_ARCHITECTURE.md` - Component breakdown
- `core/models.py` - Database schema
- `core/views.py` - REST API logic
- `core/scraper/website_scraper.py` - Scraping engine
- `mail/tasks.py` - Email task processing
- `docker-compose.yml` - Deployment config

---

## 💡 Conclusion

LeadNexus is a **production-grade SaaS platform** demonstrating:
- Advanced Django development
- Distributed systems (Celery + Redis)
- Web scraping at scale
- REST API design
- Database architecture
- Security best practices
- containerization (Docker)
- Professional code quality

**Status:** ✅ Ready for FYP submission and live customer use.

---

**Project Repository:** https://github.com/AbRehmansaif/LeadNexus  
**Documentation:** See PROJECT_DOCUMENTATION.md and TECHNICAL_ARCHITECTURE.md  
**Deployment:** Docker Compose (one command to run)

