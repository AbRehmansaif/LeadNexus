#!/bin/bash
# deploy.sh
# "One-click" deployment script for the Scrapper project.

# Ensure script is run with sudo if needed
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root or with sudo"
  exit
fi

echo "🚀 Starting Deployment Process..."

# 1. Update system and install Docker if not present
if ! [ -x "$(command -v docker)" ]; then
  echo "📦 Installing Docker..."
  apt-get update
  apt-get install -y apt-transport-https ca-certificates curl software-properties-common
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
  add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
  apt-get update
  apt-get install -y docker-ce
fi

if ! [ -x "$(command -v docker-compose)" ]; then
  echo "📦 Installing Docker Compose..."
  curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  chmod +x /usr/local/bin/docker-compose
fi

# 2. Configure SWAP (Essential for 2GB RAM VPS)
if [ ! -f /swapfile ]; then
    echo "🧠 Setting up 2GB Swap Memory for stability..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
    echo "✅ Swap setup complete."
fi

# 3. Handle .env file
if [ ! -f .env ]; then
    echo "📝 Creating default .env file..."
    cp .env.example .env 2>/dev/null || touch .env
    echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
    echo "DEBUG=False" >> .env
    echo "USE_POSTGRES=True" >> .env
    echo "POSTGRES_DB=scrapper_db" >> .env
    echo "POSTGRES_USER=scrapper_user" >> .env
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 12)" >> .env
    echo "POSTGRES_HOST=db" >> .env
    echo "POSTGRES_PORT=5432" >> .env
    echo "⚠️  NOTE: A default .env was created. Please edit it for your specific SMTP/LinkedIn credentials."
fi

# 4. Build and Run Containers
echo "🏗️  Building and starting containers (this may take a few minutes)..."
docker-compose up -d --build

# 5. Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT COMPLETE!"
echo "📍 Your app is now running on Port 80."
echo "🔐 Default Admin Credentials: admin / adminpass"
echo "⚠️  Important: Don't forget to update your .env with real credentials!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
