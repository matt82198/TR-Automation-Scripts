# Automation Directory

This directory contains automated batch scripts for scheduled/recurring tasks.

## Files

### Daily Automation Scripts
- **`daily_automation.bat`** - Main daily automation script
  - Runs batch imports for previous day's orders
  - Sends automated email reports
  - Can be scheduled via Windows Task Scheduler

- **`daily_automation_rdp.bat`** - RDP-friendly version
  - Same functionality as `daily_automation.bat`
  - Optimized for running in Remote Desktop sessions
  - Handles RDP-specific quirks and session management

## Usage

### Manual Execution
```cmd
cd automation
daily_automation.bat
```

### Scheduled Execution

**Windows Task Scheduler**:
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., Daily at 9:00 AM)
4. Set action: Start a program
5. Program: `C:\Users\...\TR-Automation-Scripts\automation\daily_automation.bat`
6. Start in: `C:\Users\...\TR-Automation-Scripts`

**For RDP Users**:
- Use `daily_automation_rdp.bat` instead
- Ensures proper execution in RDP sessions

## Script Behavior

### What Gets Automated
- Fetches previous day's Squarespace orders
- Generates QuickBooks IIF files
- Sends encrypted email with files
- Logs all imports to prevent duplicates

### Error Handling
- Scripts log errors to console
- Failed imports do not block other orders
- Email sent even if some orders fail

## Environment Variables

Required environment variables (set in Windows or in script):
```cmd
SQUARESPACE_API_KEY=your_api_key_here
EMAIL_USER=sender@domain.com
EMAIL_RECIPIENT=recipient@domain.com
```

## Notes

- Scripts assume working directory is repository root
- Requires all dependencies installed (see main README.md)
- Check config/import_log.csv for import history
- Generated files saved to repository root
