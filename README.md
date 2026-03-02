## Project Overview

This is a **production-ready Django project** with:

* Django backend + REST API (`djangorestframework`)
* Scraper module (`requests`, `beautifulsoup4`, `fake-useragent`)
* PostgreSQL database
* Gunicorn WSGI server
* Nginx reverse proxy for static/media files
* Fully Dockerized setup
* Secure remote access via **SSH tunnel** or **VPN**

Project structure:

```
project/
│
├── apps/                   # Django apps
├── scrapper/               # Django config (settings.py, urls.py, wsgi.py)
├── static/
├── media/
├── templates/
├── Dockerfile
├── docker-compose.yml
├── nginx/
│   └── nginx.conf
├── requirements.txt
├── entrypoint.sh
└── .env
```

---

## ⚙️ Frontend Laptop Setup (Host)

This laptop **runs the full project**, including database, scraper, Gunicorn, and Nginx.

### 1️⃣ Install prerequisites

* **Docker & Docker Compose** (recommended)

  * [Docker Desktop](https://www.docker.com/products/docker-desktop/) for Windows/Mac
  * Linux: `sudo apt install docker.io docker-compose`

> **Optional**: If you cannot use Docker, see the “Native Python Setup” section below.

---

### 2️⃣ Clone the project

```bash
git clone https://github.com/AbRehmansaif/Scrapper.git
cd yourproject
```

---

### 3️⃣ Configure `.env` (Production-ready)

Create a `.env` file at project root:

```text
# Django
SECRET_KEY=super-secret-production-key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# PostgreSQL
POSTGRES_DB=yourdb
POSTGRES_USER=youruser
POSTGRES_PASSWORD=StrongPass123
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Superuser
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=StrongPass123

# CORS
CORS_ALLOW_ALL=False
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

---

### 4️⃣ Build and start Docker containers

```bash
docker-compose up --build -d
```

* Containers started:

  * `db` → PostgreSQL
  * `web` → Django + Gunicorn + scraper
  * `nginx` → serves static/media files

**Automatically done by `entrypoint.sh`:**

* Migrations applied
* Superuser created
* Static files collected

---

### 5️⃣ Check running containers

```bash
docker-compose ps
```

### 6️⃣ Logs

```bash
docker-compose logs -f web
```

---

### 7️⃣ Optional: Native Python Setup (No Docker)

1. Install Python 3.13+ and virtualenv
2. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate    # Linux/macOS
.\venv\Scripts\activate     # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install PostgreSQL locally
5. Apply migrations:

```bash
python scrapper/manage.py migrate
```

6. Create superuser:

```bash
python scrapper/manage.py createsuperuser
```

7. Collect static files:

```bash
python scrapper/manage.py collectstatic
```

8. Run Django server:

```bash
python scrapper/manage.py runserver 0.0.0.0:8000
```

> **Note:** For production, you still need Gunicorn + Nginx manually. Docker automates this.

---

## 🌐 Remote Laptop Setup (Client)

This laptop **accesses the frontend laptop** securely. It does **not need Docker or project code**.

---

### 1️⃣ Install SSH client

* Linux / macOS → pre-installed
* Windows → OpenSSH in PowerShell or [PuTTY](https://www.putty.org/)

---

### 2️⃣ Find `yourusername` (frontend laptop)

* Linux/macOS:

```bash
whoami
```

* Windows (PowerShell):

```powershell
echo %USERNAME%
```

> Example output: `devanony` → this is `yourusername`

---

### 3️⃣ Find `FRONTEND_PUBLIC_IP` (frontend laptop IP)

* **Local network:**

  * Linux/macOS: `ip addr show` → look for `inet` of active interface
  * Windows: `ipconfig` → IPv4 address

* **Remote over internet:**

  * Go to [whatismyipaddress.com](https://whatismyipaddress.com) → copy public IP

> Example: `203.45.67.89` → this is `FRONTEND_PUBLIC_IP`

---

### 4️⃣ Optional: SSH Key Setup (Passwordless)

On remote laptop:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
ssh-copy-id yourusername@FRONTEND_PUBLIC_IP
```

* You can now SSH **without typing a password**.

---

### 5️⃣ Access Django via SSH tunnel

```bash
ssh -L 8000:localhost:80 yourusername@FRONTEND_PUBLIC_IP
```

* Forward remote laptop’s `localhost:8000` → frontend laptop’s Nginx (port 80)
* Open browser → `http://localhost:8000` → full Django app accessible

---

### 6️⃣ Optional: VPN / Tailscale

* Install [Tailscale](https://tailscale.com/) on both laptops
* Create a private network
* Use Tailscale IP instead of public IP → more secure, no port forwarding needed

---

## ⚡ Daily Workflow

**Frontend Laptop:**

* Start containers: `docker-compose up -d`
* Check logs: `docker-compose logs -f web`
* Stop containers (optional): `docker-compose down`

**Remote Laptop:**

* Connect via SSH tunnel: `ssh -L 8000:localhost:80 yourusername@FRONTEND_PUBLIC_IP`
* Open browser: `http://localhost:8000`

---

## 🔐 Security Notes

* Never use Django dev server (`runserver`) for production
* Always keep `DEBUG=False` in `.env`
* Use **strong passwords** or SSH keys
* Only open necessary ports (SSH 22, optionally HTTP/HTTPS via Nginx)
* Update OS, Docker, and dependencies regularly

---

## 📌 Summary

* **Frontend laptop** → full project, Dockerized, runs scraper + database + Gunicorn + Nginx
* **Remote laptop** → just SSH + browser, securely access Django app
* `.env` → production-ready settings
* Docker → fully automates migrations, superuser, static files

---

This README makes it **fully reproducible**:

* Anyone can clone the repo
* Install Docker (or Python/venv)
* Configure `.env`
* Run the app
* Access from anywhere securely
