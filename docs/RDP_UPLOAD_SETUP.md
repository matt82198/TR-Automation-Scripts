# RDP Upload Setup - Better than Email

**Save IIF files directly to your RDP/network location for easy import into QuickBooks**

## Why RDP Upload is Better

✅ No email credentials needed
✅ Files go directly where QuickBooks can access them
✅ Faster workflow - just open QB and import
✅ Keeps all files organized in one location
✅ No attachment limits or email issues

## Quick Setup

### 1. Choose Your Upload Location

Pick where QuickBooks can access files on your RDP:

**Option A: Network Share**
```
\\RDPSERVER\QuickBooks\Imports
```

**Option B: Mapped Network Drive**
```
Z:\QuickBooks\Imports
```

**Option C: Local RDP Path** (if running script ON the RDP)
```
C:\QuickBooks\Imports
```

### 2. Edit daily_automation_rdp.bat

```batch
set SQUARESPACE_API_KEY=your_squarespace_key
set QB_IMPORT_PATH=\\RDPSERVER\QuickBooks\Imports
```

### 3. Test It

Run manually to test:
```cmd
daily_automation_rdp.bat
```

Files will be saved to your RDP location:
```
\\RDPSERVER\QuickBooks\Imports\squarespace_fulfilled_2025-01-15.iif
\\RDPSERVER\QuickBooks\Imports\squarespace_fulfilled_2025-01-15_NEW_CUSTOMERS.txt
```

### 4. Schedule Daily (11 PM)

Use Windows Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task: "Squarespace Daily RDP Upload"
3. Trigger: Daily at 11:00 PM
4. Action: Start a program
   - Program: `C:\Windows\System32\cmd.exe`
   - Arguments: `/c "C:\Users\matt8\TRDev\TR-Automation-Scripts\daily_automation_rdp.bat"`

## Daily Workflow

**Automated (every night at 11 PM):**
1. Script fetches orders fulfilled that day
2. Generates IIF file
3. Saves to RDP location
4. Creates new customers report

**Manual (next morning):**
1. Open RDP
2. Open QuickBooks Desktop
3. File > Utilities > Import > IIF Files
4. Navigate to import folder
5. Select today's IIF file
6. Import (QB skips existing customers, creates new ones)

## File Naming

Files are automatically named with the date:
```
squarespace_fulfilled_2025-01-15.iif
squarespace_fulfilled_2025-01-15_NEW_CUSTOMERS.txt

squarespace_fulfilled_2025-01-16.iif
squarespace_fulfilled_2025-01-16_NEW_CUSTOMERS.txt
```

One file per day, easy to track and import.

## Network Path Troubleshooting

**"Path not found":**
- Verify network path is correct
- Check you have write permissions
- Test path in File Explorer first
- Try mapping as a drive letter

**Access denied:**
- Check Windows credentials for network share
- Run script with admin privileges
- Verify folder permissions

**Running script FROM the RDP:**
- Change QB_IMPORT_PATH to local path: `C:\QuickBooks\Imports`
- No network access needed

## Comparison: Email vs RDP

### Email Method
- ✓ Works from anywhere
- ✓ Email notification
- ✗ Needs email credentials
- ✗ Extra step (download attachments)
- ✗ Files scattered in email

### RDP Upload Method
- ✓ Direct to QuickBooks location
- ✓ No email setup needed
- ✓ Organized in one folder
- ✓ Faster import workflow
- ✗ Requires network/RDP access

## Advanced: Both Email AND RDP

You can do both if you want email notifications AND RDP upload:

```batch
REM Generate and save to RDP
python squarespace_to_quickbooks.py --fulfilled-today --output "%QB_IMPORT_PATH%\squarespace_fulfilled_%TODAY%.iif" --email matt@thetanneryrow.com
```

This will:
1. Save IIF to RDP
2. Email a copy to matt@thetanneryrow.com

## Manual Testing

Test specific date range and save to RDP:
```cmd
python squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31 --output "\\RDPSERVER\QuickBooks\Imports\january.iif"
```

## Logs

Add logging to track daily runs:
```batch
daily_automation_rdp.bat >> "\\RDPSERVER\QuickBooks\Imports\daily_log.txt" 2>&1
```

This keeps a history of each day's import.
