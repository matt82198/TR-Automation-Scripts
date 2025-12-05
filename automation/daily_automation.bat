@echo off
REM ============================================
REM Daily Squarespace Fulfilled Orders
REM Runs automatically and emails IIF to matt@thetanneryrow.com
REM ============================================

REM Set your credentials
set SQUARESPACE_API_KEY=your_api_key_here
set EMAIL_USER=your_email@gmail.com
set EMAIL_PASSWORD=your_app_password_here
set EMAIL_RECIPIENT=matt@thetanneryrow.com

REM Fetch orders fulfilled today and email the IIF file (with customer matching)
python scripts\squarespace_to_quickbooks.py --fulfilled-today --customers customers.csv

REM The script will:
REM 1. Fetch all orders fulfilled TODAY
REM 2. Generate IIF file
REM 3. Create new customers report
REM 4. Email both files to matt@thetanneryrow.com
