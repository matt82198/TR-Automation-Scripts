@echo off
REM ============================================
REM Squarespace Invoice Import to QuickBooks
REM Import: SINGLE, MULTIPLE, or BATCH
REM ============================================

REM Set your Squarespace API key
set SQUARESPACE_API_KEY=your_api_key_here

REM ============================================
REM CHOOSE YOUR IMPORT MODE:
REM ============================================

REM SINGLE INVOICE - by order number
REM python squarespace_to_quickbooks.py --order-numbers 1001

REM MULTIPLE INVOICES - comma-separated order numbers
REM python squarespace_to_quickbooks.py --order-numbers 1001,1002,1003

REM BATCH - Last 30 days (default)
python squarespace_to_quickbooks.py

REM BATCH - Custom date range (any quantity)
REM python squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31

REM ============================================
REM ADVANCED - With customer matching:
REM ============================================
REM First export customers from QB:
REM   Reports > List > Customer Contact List
REM   Save as qb_customers.csv
REM
REM Then run with --customers flag:
REM python squarespace_to_quickbooks.py --order-numbers 1001 --customers qb_customers.csv
REM python squarespace_to_quickbooks.py --customers qb_customers.csv

pause
