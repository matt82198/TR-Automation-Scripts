# Email Setup Guide - OAuth2 (Sign in with Google)

## Setting up Gmail OAuth2 for Encrypted IIF File Delivery

The script uses **OAuth2 "Sign in with Google"** to send encrypted IIF files via email. This is more secure than app passwords and provides a better user experience.

### Quick Start

**One-time setup required. After setup, the script will remember your credentials.**

---

## Step 1: Create Google Cloud Project

1. Go to **Google Cloud Console**: https://console.cloud.google.com/
2. Click **"Select a project"** → **"New Project"**
3. Project name: `QuickBooks IIF Integration` (or any name)
4. Click **"Create"**

---

## Step 2: Enable Gmail API

1. In the Cloud Console, go to **"APIs & Services"** → **"Library"**
2. Search for **"Gmail API"**
3. Click **Gmail API** → Click **"Enable"**

---

## Step 3: Configure OAuth Consent Screen

1. Go to **"APIs & Services"** → **"OAuth consent screen"**
2. Select **"External"** (unless you have Google Workspace)
3. Click **"Create"**
4. Fill in required fields:
   - **App name**: `QuickBooks IIF Mailer`
   - **User support email**: Your Gmail address
   - **Developer contact email**: Your Gmail address
5. Click **"Save and Continue"**
6. **Scopes**: Click **"Add or Remove Scopes"**
   - Search for `gmail.send`
   - Check the box for `https://www.googleapis.com/auth/gmail.send`
   - Click **"Update"** → **"Save and Continue"**
7. **Test users**: Click **"Add Users"**
   - Add your Gmail address
   - Click **"Save and Continue"**
8. Click **"Back to Dashboard"**

---

## Step 4: Create OAuth 2.0 Client ID

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"Create Credentials"** → **"OAuth client ID"**
3. Application type: **"Desktop app"**
4. Name: `QuickBooks Desktop Client`
5. Click **"Create"**
6. A dialog appears with your Client ID and Secret
7. Click **"Download JSON"**
8. **IMPORTANT**: Rename the downloaded file to `gmail_credentials.json`
9. **Move it to**: `C:\Users\matt8\TRDev\TR-Automation-Scripts\gmail_credentials.json`

---

## Step 5: Set Your Email Address (Optional)

Set environment variable so you don't have to type your email each time:

**PowerShell:**
```powershell
$env:EMAIL_USER = "your-email@gmail.com"
```

**To make it permanent:**
```powershell
[System.Environment]::SetEnvironmentVariable('EMAIL_USER', 'your-email@gmail.com', 'User')
```

---

## Step 6: First-Time Authentication

Run the script with `--email` flag:

```bash
python scripts/squarespace_to_quickbooks.py --order-number 12821 --email matt@thetanneryrow.com
```

**What happens:**
1. Script checks for `gmail_credentials.json` ✓
2. Opens your **default web browser**
3. Shows Google Sign-In page
4. Click **"Sign in with Google"**
5. Choose your Gmail account
6. **Warning screen**: "Google hasn't verified this app"
   - Click **"Advanced"**
   - Click **"Go to QuickBooks IIF Mailer (unsafe)"**
7. Review permissions → Click **"Allow"**
8. Browser shows: **"The authentication flow has completed"**
9. Script saves token to `gmail_token.json`
10. Sends the email!

**Future runs**: Token is saved, no browser authentication needed (unless token expires)

---

## How It Works

1. **Script creates IIF files** (invoices + customers + reports)
2. **Generates random 16-character password** using secure random generation
3. **Creates encrypted ZIP** with AES-256 encryption containing all files
4. **Authenticates with Google** using OAuth2 (browser opens first time only)
5. **Sends email** via Gmail API with ZIP attached
6. **Displays password** in terminal (you must share this separately)

---

## Security Notes

- ✓ Uses **OAuth2** (modern, secure, Google-recommended)
- ✓ No password storage - only refresh tokens
- ✓ ZIP files use **AES-256 encryption** (military-grade)
- ✓ Password is **randomly generated** each time (16 characters)
- ✓ Password appears in terminal and email body
- ✓ **Best practice**: Share password via different channel (text, phone, Signal)
- ✓ Tokens stored in `gmail_token.json` (local file, gitignored)

---

## Files Created

After setup, you'll have:
- `gmail_credentials.json` - OAuth2 client credentials (keep private!)
- `gmail_token.json` - Refresh token (created automatically, keep private!)

**Important**: Both files are gitignored by default. Never commit these to version control.

---

## Email Contents

The recipient will receive:
- **Subject**: "QuickBooks IIF Files - [date]"
- **Body**: List of files, order count, ZIP password, import instructions
- **Attachment**: Encrypted ZIP file containing:
  - `*_INVOICES.iif`
  - `*_NEW_CUSTOMERS.iif`
  - `*_NEW_CUSTOMERS.txt` (report)

---

## Example Usage

**Single order:**
```bash
python scripts/squarespace_to_quickbooks.py --order-number 12821 --email matt@thetanneryrow.com
```

**Multiple orders:**
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 12821,12822,12823 --email matt@thetanneryrow.com
```

**Date range:**
```bash
python scripts/squarespace_to_quickbooks.py --start-date 2025-11-01 --end-date 2025-11-15 --email matt@thetanneryrow.com
```

---

## Troubleshooting

### "gmail_credentials.json not found"
**Solution**: Complete Steps 1-4 above to create and download OAuth credentials

### "Google hasn't verified this app"
**Normal!** This warning appears because you created the app yourself.
- Click **"Advanced"** → **"Go to QuickBooks IIF Mailer (unsafe)"**
- This is safe because it's YOUR app accessing YOUR email

### Token expired or invalid
**Solution**: Delete `gmail_token.json` and run script again
- Browser will open for re-authentication
- New token will be saved

### Email not arriving
- Check **spam/junk folder**
- Verify recipient email address
- Check **Gmail Sent folder** to confirm it was sent

### Permission denied errors
**Solution**: Make sure you added the `gmail.send` scope in Step 3

### Port already in use during OAuth
**Solution**: The script will try different ports automatically
- Or close any other application using port 8080

---

## Recipient Instructions

When someone receives the encrypted ZIP:

1. **Download the ZIP** attachment from the email
2. **Get the password** (sent separately via text/phone/etc.)
3. **Extract the ZIP**:
   - Windows: Right-click → Extract All → Enter password
   - Mac: Double-click → Enter password
4. **Import into QuickBooks**:
   - File → Utilities → Import → IIF Files
   - Import `*_NEW_CUSTOMERS.iif` FIRST
   - Import `*_INVOICES.iif` SECOND

---

## Security Best Practices

1. **Never share `gmail_credentials.json` or `gmail_token.json`**
2. **Share ZIP password via separate channel** (not in same email)
3. **Delete old encrypted ZIPs** after successful import
4. **Revoke access** if you stop using the script:
   - Go to: https://myaccount.google.com/permissions
   - Find "QuickBooks IIF Mailer" → Remove access

---

## Video Tutorial (Coming Soon)

For visual learners, we'll create a screen recording showing the entire setup process.

---

## Support

If you encounter issues:
1. Check this guide first
2. Verify all steps completed
3. Check Google Cloud Console for API quota issues
4. Review script error messages for specific guidance
