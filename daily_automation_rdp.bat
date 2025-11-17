@echo off
REM ============================================
REM Daily Squarespace Fulfilled Orders - RDP Upload
REM Saves IIF files directly to RDP/network location
REM ============================================

REM Set your Squarespace API key
set SQUARESPACE_API_KEY=your_api_key_here

REM Set your business state for sales tax calculation
set SHIP_FROM_STATE=GA

REM Set your RDP/network path for QuickBooks
REM Examples:
REM   Network share: \\RDPSERVER\QuickBooks\Imports
REM   Mapped drive: Z:\QuickBooks\Imports
REM   Local RDP path: C:\QuickBooks\Imports
set QB_IMPORT_PATH=\\RDPSERVER\QuickBooks\Imports

REM Create output directory if it doesn't exist
if not exist "%QB_IMPORT_PATH%" mkdir "%QB_IMPORT_PATH%"

REM Generate today's filename
set TODAY=%date:~-4,4%-%date:~-10,2%-%date:~-7,2%
set OUTPUT_FILE=%QB_IMPORT_PATH%\squarespace_fulfilled_%TODAY%.iif

REM Fetch orders fulfilled today and save to RDP (with customer matching and product mapping)
python scripts\squarespace_to_quickbooks.py --fulfilled-today --output "%OUTPUT_FILE%" --customers customers.csv --product-mapping sku_mapping.csv

REM Copy the new customers report too
copy "squarespace_fulfilled_%TODAY%_NEW_CUSTOMERS.txt" "%QB_IMPORT_PATH%\" >nul 2>&1

echo.
echo ============================================
echo Files saved to RDP:
echo %OUTPUT_FILE%
echo %QB_IMPORT_PATH%\squarespace_fulfilled_%TODAY%_NEW_CUSTOMERS.txt
echo ============================================
echo.
echo On your RDP, open QuickBooks and import the IIF file
echo.
