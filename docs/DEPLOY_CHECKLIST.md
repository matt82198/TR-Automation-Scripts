# Streamlit Cloud Deployment Checklist

Quick reference for deploying TR Internal Tools to the cloud.
Full guide: `docs/STREAMLIT_CLOUD_SETUP.md`

---

## Pre-Deployment (Do Once)

### Google Cloud Console (https://console.cloud.google.com)

- [ ] Create project "TR-Automation-Tools"
- [ ] Enable Google Sheets API
- [ ] Configure OAuth consent screen (External)
- [ ] Create OAuth 2.0 Client ID (Web application)
  - Redirect URI: `https://YOUR-APP.streamlit.app/oauth2callback`
  - **Save Client ID**: `_________________________________`
  - **Save Client Secret**: `_________________________________`
- [ ] Create Service Account for Sheets
  - Download JSON key file
  - **Save client_email**: `_________________________________`

### Google Sheets (https://sheets.google.com)

- [ ] Create spreadsheet "TR-Automation-Data"
- [ ] Create tab: `import_log` (columns: order_number, date_imported, iif_file)
- [ ] Create tab: `missing_inventory` (columns: unique_id, date_marked)
- [ ] Create tab: `leather_coefficients` (columns: leather_name, coefficient, sample_weight, sample_sqft, last_updated, notes)
- [ ] Share sheet with service account email (Editor access)
- [ ] **Save Spreadsheet URL**: `_________________________________`

### Gmail App Password (https://myaccount.google.com/apppasswords)

- [ ] Generate app password
- [ ] **Save 16-char password**: `_________________________________`

---

## Deployment

### Push Code
```bash
git add .
git commit -m "Add Streamlit Cloud deployment"
git push
```

### Streamlit Cloud (https://share.streamlit.io)

- [ ] New app > Select repo > Branch: master > File: app.py
- [ ] Advanced settings > Paste secrets (see secrets.toml.example)
- [ ] Deploy!
- [ ] Note app URL: `_________________________________`
- [ ] Update Google OAuth redirect URI to match actual URL

---

## Secrets Template (fill in and paste to Streamlit Cloud)

```toml
[auth]
redirect_uri = "https://YOUR-APP.streamlit.app/oauth2callback"
cookie_secret = "RANDOM_32_CHAR_STRING"
client_id = "GOOGLE_CLIENT_ID"
client_secret = "GOOGLE_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

SQUARESPACE_API_KEY = ""
STRIPE_API_KEY = ""
PAYPAL_CLIENT_ID = ""
PAYPAL_CLIENT_SECRET = ""
PAYPAL_MODE = "live"
SHIP_FROM_STATE = "GA"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = "587"
EMAIL_USER = "matt@thetanneryrow.com"
EMAIL_PASSWORD = "GMAIL_APP_PASSWORD"
EMAIL_RECIPIENT = "matt@thetanneryrow.com"

[authorized_users]
emails = [
    "matt@thetanneryrow.com",
    "sueeyles@thetanneryrow.com"
]

[connections.gsheets]
spreadsheet = "GOOGLE_SHEET_URL"
worksheet = "0"
type = "service_account"
project_id = "FROM_JSON"
private_key_id = "FROM_JSON"
private_key = "FROM_JSON"
client_email = "FROM_JSON"
client_id = "FROM_JSON"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "FROM_JSON"
```

---

## Your Existing API Keys (copy from environment)

Run this to see your current keys:
```bash
echo SQUARESPACE: %SQUARESPACE_API_KEY%
echo STRIPE: %STRIPE_API_KEY%
echo PAYPAL_ID: %PAYPAL_CLIENT_ID%
echo PAYPAL_SECRET: %PAYPAL_CLIENT_SECRET%
```

---

## Test

1. Visit app URL
2. Sign in with Google
3. Verify tools work
4. Check Google Sheet has data after using tools
