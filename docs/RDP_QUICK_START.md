# RDP Daily Automation - Quick Start

**5-minute setup for automatic daily IIF files uploaded to your RDP**

## What You Get

Every day at 11 PM:
- ✅ Script fetches orders fulfilled that day
- ✅ Generates IIF file
- ✅ Saves directly to your RDP/QuickBooks folder
- ✅ Ready to import in the morning

## Step 1: Edit the Batch File

Open `daily_automation_rdp.bat` and set:

```batch
# Your Squarespace API key
set SQUARESPACE_API_KEY=your_key_from_squarespace

# Your RDP/network path where QuickBooks can access files
set QB_IMPORT_PATH=\\RDPSERVER\QuickBooks\Imports
```

**RDP Path Examples:**
- Network share: `\\RDPSERVER\QuickBooks\Imports`
- Mapped drive: `Z:\QuickBooks\Imports`
- Local (if running ON the RDP): `C:\QuickBooks\Imports`

## Step 2: Test It

Run once manually to test:
```cmd
cd C:\Users\matt8\TRDev\TR-Automation-Scripts
daily_automation_rdp.bat
```

Check that files appear in your RDP location:
```
squarespace_fulfilled_2025-01-15.iif
squarespace_fulfilled_2025-01-15_NEW_CUSTOMERS.txt
```

## Step 3: Schedule It (11 PM Daily)

1. Press Windows Key, type **Task Scheduler**, open it

2. Click **Create Basic Task**

3. Name: `Squarespace Daily RDP Upload`

4. Trigger: **Daily** at **11:00 PM**

5. Action: **Start a program**
   - Program: `C:\Windows\System32\cmd.exe`
   - Arguments: `/c "C:\Users\matt8\TRDev\TR-Automation-Scripts\daily_automation_rdp.bat"`
   - Start in: `C:\Users\matt8\TRDev\TR-Automation-Scripts`

6. Click **Finish**

7. Right-click the task > **Run** to test immediately

## Done!

That's it. Every morning you'll have yesterday's fulfilled orders waiting in your RDP folder.

## Daily Workflow

**Morning routine:**
1. Open RDP
2. Open QuickBooks Desktop
3. File > Utilities > Import > IIF Files
4. Select: `squarespace_fulfilled_[today].iif`
5. Import (QB handles customer matching automatically)

**Files are named by date, one per day:**
```
Monday:    squarespace_fulfilled_2025-01-13.iif
Tuesday:   squarespace_fulfilled_2025-01-14.iif
Wednesday: squarespace_fulfilled_2025-01-15.iif
```

## What Happens

### Orders Fulfilled Today
- Fetches all orders with `fulfilledOn` = today's date
- Only FULFILLED orders (not pending or canceled)

### Customer Handling
- ✓ Existing customers → Invoice created
- ⚠️ New customers → Created with full contact info, then invoice created
- Report shows which customers are new

### If No Orders Today
- Script runs, creates empty/minimal file
- Normal - not every day has fulfillments

## Troubleshooting

**Path not found:**
- Test path in File Explorer first
- Check spelling and permissions
- Try mapping network share as drive letter

**No files created:**
- Check console output for errors
- Verify Squarespace API key is set correctly
- Check script ran (look in Task Scheduler history)

**Orders missing:**
- Check they were actually FULFILLED today (not just ordered)
- Verify in Squarespace > Orders > Fulfillment status

## Need Help?

See full docs:
- `RDP_UPLOAD_SETUP.md` - Complete setup guide
- `DAILY_AUTOMATION_COMPARISON.md` - Email vs RDP comparison
- `SQUARESPACE_SETUP.md` - Main documentation
