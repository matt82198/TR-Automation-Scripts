# Tannery Row Tools

Internal automation toolbox for The Tannery Row LLC. A Streamlit-based dashboard providing tools for payment processing, order management, inventory tracking, and QuickBooks integration. Written entirely using .MD for instruction and Claude Code, for fun.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dashboard
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## Tools

| Tool | Description |
|------|-------------|
| **Payment Fetch** | Pull EOM billing reports from Stripe and PayPal |
| **Order Payment Matcher** | Match Squarespace orders to payment transactions |
| **Pending Order Count** | Count pending panel and swatch book orders |
| **Mystery Bundle Counter** | Track mystery bundle inventory and orders |
| **Leather Weight Calculator** | Calculate leather weight using calibrated coefficients |
| **Swatch Book Generator** | Generate swatch book page layouts |
| **Material Bank Leads** | Import Material Bank leads to Method CRM |

## CLI Scripts

Scripts can also be run directly from command line:

```bash
# Squarespace to QuickBooks import
python scripts/squarespace_to_quickbooks.py --order-numbers 1001,1002,1003

# Payment fetch with CSV export
python scripts/payment_fetch.py --start-date 2025-01-01 --end-date 2025-01-31 --csv

# Pending order count
python scripts/pending_order_count.py
```

## Configuration

### Environment Variables

Set these in your environment or `.streamlit/secrets.toml`:

```bash
SQUARESPACE_API_KEY=your_key
STRIPE_API_KEY=sk_live_xxx
PAYPAL_CLIENT_ID=your_id
PAYPAL_CLIENT_SECRET=your_secret
PAYPAL_MODE=live
SHIP_FROM_STATE=GA
```

### Product Mapping

Edit `config/sku_mapping.csv` to map Squarespace products to QuickBooks items:

```csv
SquarespaceProductName,QuickBooksItem
Horween Dublin Leather Panels,Premium Leather Hide
Leather Panel - Horween Predator - Steel - 5-6 oz,Predator Steel 5-6 oz
```

## Project Structure

```
TR-Automation-Scripts/
├── app.py                 # Streamlit dashboard (main entry point)
├── requirements.txt       # Python dependencies
├── scripts/               # Core automation scripts
├── utils/                 # Shared utilities (auth, storage)
├── config/                # Configuration files
├── docs/                  # Documentation
├── output/                # Generated files (gitignored)
└── examples/              # Reference files
```

## Deployment

### Streamlit Cloud

1. Push to GitHub
2. Connect repo at share.streamlit.io
3. Configure secrets in dashboard settings
4. See `docs/STREAMLIT_CLOUD_SETUP.md` for full guide

### Cloudflare Tunnel (Local Network)

For local network access via Cloudflare:

```bash
# Install cloudflared
# Run dashboard on local network
streamlit run app.py --server.address 0.0.0.0 --server.port 8501

# Create tunnel
cloudflared tunnel --url http://localhost:8501
```

## Documentation

- `docs/DEPLOY_CHECKLIST.md` - Quick deployment reference
- `docs/STREAMLIT_CLOUD_SETUP.md` - Cloud deployment guide
- `docs/PRODUCT_MAPPING_GUIDE.md` - SKU mapping setup
- `docs/QUICK_REFERENCE.md` - Command quick reference
