@echo off
REM LinkedIn Data Scraper - Quick Run Scripts
REM This file contains common scraping scenarios

echo ========================================
echo LinkedIn Data Scraper - Quick Run
echo ========================================
echo.
echo Select a scraping scenario:
echo.
echo 1. Software Developers (50 profiles)
echo 2. Digital Marketers (50 profiles)
echo 3. Sales Professionals (50 profiles)
echo 4. Data Scientists (50 profiles)
echo 5. Custom niche
echo 6. Exit
echo.

set /p choice="Enter your choice (1-6): "

REM Activate virtual environment
call venv\Scripts\activate.bat

if "%choice%"=="1" (
    echo.
    echo Scraping Software Developers...
    python main.py --niche "software developer" --max-profiles 50
    goto end
)

if "%choice%"=="2" (
    echo.
    echo Scraping Digital Marketers...
    python main.py --niche "digital marketing" --max-profiles 50
    goto end
)

if "%choice%"=="3" (
    echo.
    echo Scraping Sales Professionals...
    python main.py --niche "sales professional" --max-profiles 50
    goto end
)

if "%choice%"=="4" (
    echo.
    echo Scraping Data Scientists...
    python main.py --niche "data scientist" --max-profiles 50
    goto end
)

if "%choice%"=="5" (
    echo.
    set /p custom_niche="Enter your niche: "
    set /p max_profiles="Enter max profiles (default 50): "
    if "%max_profiles%"=="" set max_profiles=50
    echo.
    echo Scraping %custom_niche%...
    python main.py --niche "%custom_niche%" --max-profiles %max_profiles%
    goto end
)

if "%choice%"=="6" (
    echo Exiting...
    exit /b 0
)

echo Invalid choice!

:end
echo.
echo ========================================
echo Scraping Complete!
echo ========================================
echo.
echo Check the 'data' folder for results.
echo.
pause
