@echo off
echo ========================================
echo LinkedIn Data Scraper - Setup Script
echo ========================================
@REM echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/4] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo [4/4] Creating configuration file...
if not exist config.json (
    copy config.example.json config.json
    echo Created config.json from example
) else (
    echo config.json already exists, skipping...
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit config.json with your settings
echo 2. Run: venv\Scripts\activate
echo 3. Run: python main.py --niche "your niche" --max-profiles 50
echo.
echo For help: python main.py --help
echo.
pause
