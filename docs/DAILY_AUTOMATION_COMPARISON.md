# Daily Automation - Which Option?

## Option 1: Email (Simple)
**Files:** `daily_automation.bat` + `DAILY_AUTOMATION_SETUP.md`

### How it works:
- Runs at 11 PM daily
- Fetches orders fulfilled that day
- Emails IIF + report to matt@thetanneryrow.com
- You download attachments and import to QB

### Pros:
✅ Works from anywhere (local machine, laptop, etc.)
✅ Email notification when ready
✅ No network/RDP configuration needed

### Cons:
✗ Requires email credentials (Gmail app password)
✗ Extra step: download attachments
✗ Files scattered across emails by date

### Best for:
- Running script on local machine
- Want email notifications
- Don't have reliable RDP/network access

---

## Option 2: RDP Upload (Recommended)
**Files:** `daily_automation_rdp.bat` + `RDP_UPLOAD_SETUP.md`

### How it works:
- Runs at 11 PM daily
- Fetches orders fulfilled that day
- Saves IIF directly to RDP/network folder
- You open QB on RDP and import directly

### Pros:
✅ **Files go directly to QuickBooks location**
✅ **No email setup needed**
✅ Cleaner workflow - just import in QB
✅ All files organized in one folder
✅ Faster daily import

### Cons:
✗ Requires network/RDP path access
✗ No automatic notification (but you check daily anyway)

### Best for:
- **You use RDP for QuickBooks** (your use case!)
- Want the simplest daily workflow
- Files saved where QB can easily access them

---

## Option 3: Both Email + RDP
**Best of both worlds**

### How it works:
- Saves to RDP location
- Also emails a copy for notifications

### Setup:
Edit `daily_automation_rdp.bat`:
```batch
python squarespace_to_quickbooks.py --fulfilled-today --output "%QB_IMPORT_PATH%\squarespace_fulfilled_%TODAY%.iif" --email matt@thetanneryrow.com
```

Add email credentials:
```batch
set EMAIL_USER=your_email@gmail.com
set EMAIL_PASSWORD=your_app_password
```

---

## Recommendation for Your Workflow

Since you mentioned **"uploading to RDP"**, I recommend:

### **Use Option 2: RDP Upload**

**Setup (5 minutes):**
1. Edit `daily_automation_rdp.bat`
2. Set your RDP path: `\\RDPSERVER\QuickBooks\Imports`
3. Set Squarespace API key
4. Schedule in Task Scheduler (11 PM daily)

**Daily Workflow:**
1. Script runs automatically at 11 PM
2. Next morning: Open RDP
3. Open QuickBooks
4. Import today's IIF file from the import folder
5. Done!

**Files automatically named by date:**
```
squarespace_fulfilled_2025-01-15.iif
squarespace_fulfilled_2025-01-16.iif
squarespace_fulfilled_2025-01-17.iif
```

One import per day, all organized in one folder.

---

## Quick Setup Commands

### Email Option:
```cmd
# Edit daily_automation.bat with your credentials
# Then schedule:
daily_automation.bat
```

### RDP Option (Recommended):
```cmd
# Edit daily_automation_rdp.bat with your RDP path
# Then schedule:
daily_automation_rdp.bat
```

---

## Testing

Test before scheduling:

**Email:**
```cmd
set EMAIL_USER=test@gmail.com
set EMAIL_PASSWORD=app_password
python squarespace_to_quickbooks.py --fulfilled-today --email matt@thetanneryrow.com
```

**RDP:**
```cmd
python squarespace_to_quickbooks.py --fulfilled-today --output "\\RDPSERVER\QuickBooks\Imports\test.iif"
```
