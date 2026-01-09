# Self-Hosting Setup Guide

Deploy TR Internal Tools to your own server with custom domain **tanneryrowtools.com**.

## Architecture

```
Internet → Caddy (SSL/Reverse Proxy) → Streamlit App
              ↓
        Auto HTTPS via Let's Encrypt
```

---

## Prerequisites

- VPS with Ubuntu 22.04+ (DigitalOcean, Linode, AWS, etc.)
- Domain: tanneryrowtools.com with DNS access
- SSH access to server

---

## Step 1: Provision VPS

### Recommended Specs
- **CPU:** 1-2 vCPU
- **RAM:** 2-4 GB
- **Storage:** 25 GB SSD
- **Cost:** ~$10-20/month

### Providers
- [DigitalOcean](https://www.digitalocean.com/) - $12/mo (2GB)
- [Linode](https://www.linode.com/) - $12/mo (2GB)
- [Vultr](https://www.vultr.com/) - $12/mo (2GB)
- [Hetzner](https://www.hetzner.com/) - $5/mo (2GB, EU)

---

## Step 2: Point DNS

Add these DNS records for **tanneryrowtools.com**:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_SERVER_IP | 300 |
| A | www | YOUR_SERVER_IP | 300 |

Wait 5-30 minutes for DNS propagation.

Verify:
```bash
nslookup tanneryrowtools.com
```

---

## Step 3: Server Setup

SSH into your server:
```bash
ssh root@YOUR_SERVER_IP
```

### Install Docker
```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt install docker-compose-plugin -y

# Verify
docker --version
docker compose version
```

### Create app user (optional but recommended)
```bash
adduser --disabled-password --gecos "" trtools
usermod -aG docker trtools
su - trtools
```

---

## Step 4: Deploy Application

### Clone repository
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/TR-Automation-Scripts.git
cd TR-Automation-Scripts
```

### Create secrets file
```bash
mkdir -p .streamlit
nano .streamlit/secrets.toml
```

Paste your secrets (copy from local `.streamlit/secrets.toml`):
```toml
[auth]
redirect_uri = "https://tanneryrowtools.com/oauth2callback"
cookie_secret = "YOUR_32_CHAR_SECRET"
client_id = "YOUR_GOOGLE_CLIENT_ID"
client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

SQUARESPACE_API_KEY = "YOUR_KEY"
STRIPE_API_KEY = "YOUR_KEY"
PAYPAL_CLIENT_ID = "YOUR_KEY"
PAYPAL_CLIENT_SECRET = "YOUR_KEY"
PAYPAL_MODE = "live"
SHIP_FROM_STATE = "GA"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = "587"
EMAIL_USER = "matt@thetanneryrow.com"
EMAIL_PASSWORD = "YOUR_APP_PASSWORD"
EMAIL_RECIPIENT = "matt@thetanneryrow.com"

[authorized_users]
emails = [
    "matt@thetanneryrow.com",
    "sueeyles@thetanneryrow.com"
]

[connections.gsheets]
spreadsheet = "YOUR_SHEET_URL"
# ... rest of service account config
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Set permissions
```bash
chmod 600 .streamlit/secrets.toml
```

### Start the application
```bash
docker compose up -d --build
```

### Check logs
```bash
docker compose logs -f
```

---

## Step 5: Update Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Edit your OAuth 2.0 Client ID
3. Update **Authorized redirect URIs**:
   ```
   https://tanneryrowtools.com/oauth2callback
   ```
4. Save

---

## Step 6: Verify

1. Visit https://tanneryrowtools.com
2. You should see the login page with valid SSL
3. Sign in with Google
4. Verify all tools work

---

## Management Commands

### View logs
```bash
docker compose logs -f streamlit
docker compose logs -f caddy
```

### Restart services
```bash
docker compose restart
```

### Update application
```bash
git pull
docker compose up -d --build
```

### Stop everything
```bash
docker compose down
```

### Full rebuild
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## Troubleshooting

### SSL not working
- Ensure DNS is pointing to server (check with `nslookup`)
- Check Caddy logs: `docker compose logs caddy`
- Verify ports 80/443 are open in firewall

### App not loading
```bash
# Check if containers are running
docker compose ps

# Check app logs
docker compose logs streamlit

# Test internal connectivity
docker compose exec caddy curl http://streamlit:8501
```

### Firewall (if using UFW)
```bash
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp
ufw enable
```

### Google OAuth error
- Verify redirect_uri matches EXACTLY in:
  - Google Cloud Console
  - .streamlit/secrets.toml
  - Should be: `https://tanneryrowtools.com/oauth2callback`

---

## Backups

### Backup config
```bash
tar -czf tr-backup-$(date +%Y%m%d).tar.gz \
    .streamlit/secrets.toml \
    config/ \
    examples/customers_backup.csv
```

### Automated daily backup (optional)
```bash
crontab -e
# Add:
0 2 * * * cd ~/TR-Automation-Scripts && tar -czf ~/backups/tr-$(date +\%Y\%m\%d).tar.gz .streamlit/secrets.toml config/
```

---

## Security Checklist

- [ ] Firewall enabled (only 22, 80, 443 open)
- [ ] SSH key authentication (disable password auth)
- [ ] secrets.toml has 600 permissions
- [ ] Regular system updates
- [ ] Backups configured

---

## Cost Summary

| Item | Monthly Cost |
|------|--------------|
| VPS (2GB) | ~$12 |
| Domain renewal | ~$1 (yearly/12) |
| **Total** | **~$13/month** |

vs. Streamlit Cloud Teams: ~$250/month
