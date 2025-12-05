# Streamlit Cloud Deployment Setup Guide

This guide walks you through deploying the Tannery Row Internal Tools dashboard to Streamlit Cloud with Google Sign-In authentication.

## Prerequisites

- GitHub account (repo already exists)
- Google account with admin access to create projects
- ~1 hour for initial setup

---

## Step 1: Google Cloud Project Setup

### 1.1 Create Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown (top left) > "New Project"
3. Name: `TR-Automation-Tools`
4. Click "Create"
5. Make sure the new project is selected

### 1.2 Enable APIs

1. Go to **APIs & Services > Library**
2. Search for and enable:
   - "Google Sheets API"
   - "Gmail API" (if you want email notifications)

### 1.3 Configure OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**
2. Select **External** (unless you have Google Workspace, then Internal)
3. Fill in:
   - App name: `Tannery Row Internal Tools`
   - User support email: `matt@thetanneryrow.com`
   - Developer contact: `matt@thetanneryrow.com`
4. Click "Save and Continue"
5. **Scopes**: Click "Add or Remove Scopes"
   - Add: `openid`, `email`, `profile`
   - Click "Update" then "Save and Continue"
6. **Test users**: Add your email addresses for testing
7. Click "Save and Continue" then "Back to Dashboard"

### 1.4 Create OAuth 2.0 Client ID (for user login)

1. Go to **APIs & Services > Credentials**
2. Click **"+ Create Credentials" > "OAuth client ID"**
3. Application type: **Web application**
4. Name: `Streamlit Cloud Login`
5. **Authorized redirect URIs**: Add:
   ```
   https://tr-internal-tools.streamlit.app/oauth2callback
   ```
   (You'll update this after deployment if the URL is different)
6. Click "Create"
7. **SAVE THE CLIENT ID AND CLIENT SECRET** - you'll need these!

### 1.5 Create Service Account (for Google Sheets)

1. Go to **APIs & Services > Credentials**
2. Click **"+ Create Credentials" > "Service account"**
3. Name: `streamlit-sheets`
4. Click "Create and Continue"
5. Skip the optional steps, click "Done"
6. Click on the service account you just created
7. Go to **Keys** tab > **Add Key > Create new key**
8. Choose **JSON** and click "Create"
9. **SAVE THE DOWNLOADED JSON FILE** - you'll need values from it!

---

## Step 2: Google Sheets Setup

### 2.1 Create the Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com/)
2. Create a new blank spreadsheet
3. Name it: `TR-Automation-Data`

### 2.2 Create Worksheets

Create 3 worksheet tabs (click + at bottom):

**Tab 1: `import_log`**
Add headers in row 1:
```
order_number | date_imported | iif_file
```

**Tab 2: `missing_inventory`**
Add headers in row 1:
```
unique_id | date_marked
```

**Tab 3: `leather_coefficients`**
Add headers in row 1:
```
leather_name | coefficient | sample_weight | sample_sqft | last_updated | notes
```

### 2.3 Share with Service Account

1. Open the service account JSON file you downloaded
2. Find the `client_email` field (looks like `streamlit-sheets@tr-automation-tools.iam.gserviceaccount.com`)
3. In Google Sheets, click **Share**
4. Paste the service account email
5. Give it **Editor** access
6. Uncheck "Notify people"
7. Click "Share"

### 2.4 Get the Spreadsheet URL

Copy the URL - it looks like:
```
https://docs.google.com/spreadsheets/d/1ABC123xyz.../edit
```

---

## Step 3: Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select app: **Mail**
5. Select device: **Other** (enter "Streamlit")
6. Click "Generate"
7. **SAVE THE 16-CHARACTER PASSWORD** - you'll need this!

---

## Step 4: Prepare Secrets

### 4.1 Create Local Secrets File (for testing)

Copy the example file:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

### 4.2 Fill in Your Values

Edit `.streamlit/secrets.toml` with your actual values:

```toml
# Google OAuth (from Step 1.4)
[auth]
redirect_uri = "https://tr-internal-tools.streamlit.app/oauth2callback"
cookie_secret = "GENERATE_RANDOM_STRING_32_CHARS"
client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
client_secret = "YOUR_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

# API Keys (from your existing environment)
SQUARESPACE_API_KEY = "YOUR_SQUARESPACE_KEY"
STRIPE_API_KEY = "sk_live_YOUR_STRIPE_KEY"
PAYPAL_CLIENT_ID = "YOUR_PAYPAL_CLIENT_ID"
PAYPAL_CLIENT_SECRET = "YOUR_PAYPAL_SECRET"
PAYPAL_MODE = "live"

# Email (from Step 3)
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = "587"
EMAIL_USER = "matt@thetanneryrow.com"
EMAIL_PASSWORD = "YOUR_16_CHAR_APP_PASSWORD"
EMAIL_RECIPIENT = "matt@thetanneryrow.com"

# Business
SHIP_FROM_STATE = "GA"

# Authorized Users
[authorized_users]
emails = [
    "matt@thetanneryrow.com",
    "sueeyles@thetanneryrow.com"
]

# Google Sheets (from Step 1.5 JSON file and Step 2.4)
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit"
worksheet = "0"
type = "service_account"
project_id = "tr-automation-tools"
private_key_id = "FROM_JSON_FILE"
private_key = "-----BEGIN PRIVATE KEY-----\nFROM_JSON_FILE\n-----END PRIVATE KEY-----\n"
client_email = "streamlit-sheets@tr-automation-tools.iam.gserviceaccount.com"
client_id = "FROM_JSON_FILE"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "FROM_JSON_FILE"
```

### 4.3 Generate Cookie Secret

Run this to generate a random cookie secret:
```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

---

## Step 5: Push to GitHub

```bash
cd C:\Users\matt8\TRDev\TR-Automation-Scripts
git add .
git commit -m "Add Streamlit Cloud deployment with Google OAuth"
git push origin master
```

---

## Step 6: Deploy to Streamlit Cloud

1. Go to [Streamlit Cloud](https://share.streamlit.io/)
2. Sign in with GitHub
3. Click **"New app"**
4. Select:
   - Repository: `TR-Automation-Scripts`
   - Branch: `master`
   - Main file path: `app.py`
5. Click **"Advanced settings"**
6. In the **Secrets** section, paste your entire `secrets.toml` content
7. Click **"Deploy!"**

---

## Step 7: Update OAuth Redirect URI

After deployment:

1. Note your actual app URL (e.g., `https://tr-internal-tools.streamlit.app`)
2. Go back to [Google Cloud Console > Credentials](https://console.cloud.google.com/apis/credentials)
3. Click on your OAuth 2.0 Client ID
4. Update the **Authorized redirect URIs** to match:
   ```
   https://YOUR-ACTUAL-APP-URL.streamlit.app/oauth2callback
   ```
5. Also update the `redirect_uri` in your Streamlit Cloud secrets

---

## Step 8: Test

1. Visit your app URL
2. You should see a login page
3. Click "Sign in with Google"
4. Sign in with an authorized email
5. You should see the dashboard!

---

## Troubleshooting

### "Access Denied" after login
- Check that your email is in `[authorized_users]` or ends with `@thetanneryrow.com`

### "redirect_uri_mismatch" error
- The redirect URI in Google Cloud must EXACTLY match the one in secrets
- Make sure it ends with `/oauth2callback`

### Google Sheets not working
- Verify the service account email has Editor access to the sheet
- Check that the spreadsheet URL is correct in secrets
- Ensure worksheet names match exactly: `import_log`, `missing_inventory`, `leather_coefficients`

### App crashes on startup
- Check Streamlit Cloud logs for errors
- Verify all required secrets are present

---

## Local Development

The app still works locally! Just run:
```bash
streamlit run app.py
```

It will:
- Skip authentication (not on cloud)
- Use local CSV files instead of Google Sheets
- Use environment variables for API keys

---

## Adding New Users

To authorize new employees:

1. Go to Streamlit Cloud > Your App > Settings > Secrets
2. Add their email to the `[authorized_users]` section:
   ```toml
   [authorized_users]
   emails = [
       "matt@thetanneryrow.com",
       "sueeyles@thetanneryrow.com",
       "newemployee@thetanneryrow.com"
   ]
   ```
3. Click "Save"
4. The app will automatically reload

Note: Anyone with `@thetanneryrow.com` email is automatically authorized!
