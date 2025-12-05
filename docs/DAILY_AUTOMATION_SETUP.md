# Daily Automation Setup

Automatically email IIF files for orders fulfilled each day to matt@thetanneryrow.com

## Quick Setup

### 1. Set Up Email Credentials

You need an email account to send from (Gmail recommended).

**For Gmail:**
1. Go to Google Account > Security
2. Enable 2-Step Verification
3. Go to App Passwords: https://myaccount.google.com/apppasswords
4. Create an app password for "Mail"
5. Copy the 16-character password

### 2. Configure Environment Variables

**Option A: Edit daily_automation.bat**
```batch
set SQUARESPACE_API_KEY=your_squarespace_key
set EMAIL_USER=your_email@gmail.com
set EMAIL_PASSWORD=your_16_char_app_password
set EMAIL_RECIPIENT=matt@thetanneryrow.com
```

**Option B: Set permanently in Windows**
```cmd
setx SQUARESPACE_API_KEY "your_squarespace_key"
setx EMAIL_USER "your_email@gmail.com"
setx EMAIL_PASSWORD "your_16_char_app_password"
setx EMAIL_RECIPIENT "matt@thetanneryrow.com"
```

### 3. Test Manually

Run the batch file to test:
```cmd
daily_automation.bat
```

It will:
- Fetch orders fulfilled TODAY
- Generate IIF file
- Create new customers report
- Email both files to matt@thetanneryrow.com

### 4. Schedule with Windows Task Scheduler

**Create the scheduled task:**

1. Open Task Scheduler (search in Start menu)

2. Click "Create Basic Task"

3. Name: "Squarespace Daily Export"

4. Trigger: **Daily** at **11:00 PM** (end of day)

5. Action: **Start a program**
   - Program: `C:\Windows\System32\cmd.exe`
   - Arguments: `/c "C:\Users\matt8\TRDev\TR-Automation-Scripts\daily_automation.bat"`
   - Start in: `C:\Users\matt8\TRDev\TR-Automation-Scripts`

6. Finish and test:
   - Right-click the task > Run

**Advanced Settings:**
- Run whether user is logged on or not
- Run with highest privileges
- Configure for Windows 10/11

## What Gets Emailed

**Every day at 11 PM**, you'll receive an email with:

**Subject:** Daily Squarespace Invoices - X invoice(s)

**Attachments:**
1. `squarespace_fulfilled_YYYY-MM-DD.iif` - Import into QuickBooks
2. `squarespace_fulfilled_YYYY-MM-DD_NEW_CUSTOMERS.txt` - Review new customers

**Email Body:**
- Number of invoices
- Number of new customers
- Instructions for importing into QuickBooks

## Manual Testing

Test orders fulfilled today:
```cmd
python squarespace_to_quickbooks.py --fulfilled-today
```

Test with email:
```cmd
python squarespace_to_quickbooks.py --fulfilled-today --email matt@thetanneryrow.com
```

## Troubleshooting

**No email received:**
- Check spam folder
- Verify EMAIL_USER and EMAIL_PASSWORD are set correctly
- Test Gmail app password is working
- Check script output for errors

**No orders found:**
- Normal if no orders were fulfilled today
- Check Squarespace to verify fulfillment dates
- Email will still be sent (with 0 invoices)

**Authentication errors:**
- Verify SQUARESPACE_API_KEY is correct
- Check API key hasn't expired
- Ensure Commerce Advanced plan is active

## Email Settings

**Default settings (Gmail):**
- Host: smtp.gmail.com
- Port: 587
- Encryption: TLS

**Custom SMTP server:**
```cmd
set EMAIL_HOST=smtp.office365.com
set EMAIL_PORT=587
```

## Alternative: Run Without Scheduling

You can also run this manually at end of day:
```cmd
daily_automation.bat
```

Or add to your Windows startup if you want it to run when you log in.

## Logs

Check the console output or redirect to a log file:
```batch
python squarespace_to_quickbooks.py --fulfilled-today >> daily_log.txt 2>&1
```

Add this to daily_automation.bat to keep a log of each run.
