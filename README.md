# TR-Automation-Scripts

A collection of scripts used to automate processes at The Tannery Row LLC

## Setup

### Prerequisites
- Python 3.7 or higher
- Required Python packages: `requests`, `stripe`

### Installation
```bash
pip install requests stripe
```

### API Keys
Set your API keys as environment variables:

**Windows:**
```cmd
set SQUARESPACE_API_KEY=your-squarespace-api-key-here
set STRIPE_API_KEY=sk_live_your_stripe_key_here
set PAYPAL_CLIENT_ID=your_paypal_client_id
set PAYPAL_CLIENT_SECRET=your_paypal_client_secret
```

**Mac/Linux:**
```bash
export SQUARESPACE_API_KEY=your-squarespace-api-key-here
export STRIPE_API_KEY=sk_live_your_stripe_key_here
export PAYPAL_CLIENT_ID=your_paypal_client_id
export PAYPAL_CLIENT_SECRET=your_paypal_client_secret
```

## Panel Count Script

**File:** `panel_count.py`

This script connects to the Squarespace API to count panel and swatch book products from pending orders. It provides detailed breakdowns by product type, variant specifications, and SKUs.

### Features
- **SKU-based counting** for precise product identification
- **Variant details** including sizes, weights, leather types (Dublin, Glove, etc.)
- **Separate tracking** of panels and swatch books
- **Detailed output** with product names, variant descriptions, and SKU references

### Usage

```bash
python panel_count.py
```

### Example Output

```
Panel counts:
  Horween Dublin Leather Panels (Size: 2′ Panel - Weight: 3-4 oz) [SKU: SQ5172253]: 1
Total panels: 1

Swatch book counts:
  Horween Swatch Books (Swatch Book: Dublin) [SKU: SQ6839957]: 1
  Horween Swatch Books (Swatch Book: Glove) [SKU: SQ0776396]: 1
Total swatch books: 2
```

### Configuration
- By default, fetches orders with "PENDING" fulfillment status
- Modify the script to change fulfillment status or add date filters if needed

## Migrate Sortly Inventory

This script is a POC of how we can use LLM intelligence in order to differentiate between multi-worded colors and materials. Purposed to migrate the current sortly inventory to any other chosen platform once Shopify is migrated to.

## Payment Fetch Script (EOM Billing Report)

**File:** `payment_fetch.py`

This script pulls transaction data from both Stripe and PayPal for end-of-month (EOM) billing reports. It provides comprehensive summaries with breakdowns by payment source and supports CSV export.

### Features
- **Multi-source support** - Fetches from Stripe and PayPal simultaneously
- **Read-only operations** - Cannot create, modify, or delete transactions
- **Detailed summaries** - Shows gross revenue, fees, net revenue, and fee rates
- **CSV export** - Save data for further analysis
- **Date range filtering** - Specify custom date ranges or use defaults

### Prerequisites
Set up your API keys as environment variables:

```bash
# Required for Stripe
export STRIPE_API_KEY=sk_live_your_stripe_key_here

# Required for PayPal
export PAYPAL_CLIENT_ID=your_paypal_client_id
export PAYPAL_CLIENT_SECRET=your_paypal_client_secret

# Optional: Set to 'sandbox' for PayPal testing (defaults to 'live')
export PAYPAL_MODE=live
```

### Usage

```bash
python payment_fetch.py [options]
```

### Options

```
--start-date START_DATE    Start date (YYYY-MM-DD). Default: 30 days ago
--end-date END_DATE        End date (YYYY-MM-DD). Default: today
--source {stripe,paypal,both}  Payment source to fetch. Default: both
--csv                      Export results to CSV file
```

### Example Usage

```bash
# Get last 30 days from both sources with CSV export
python payment_fetch.py --csv

# Get specific date range from Stripe only
python payment_fetch.py --start-date 2024-01-01 --end-date 2024-01-31 --source stripe

# Get PayPal transactions for last week
python payment_fetch.py --start-date 2024-01-15 --source paypal
```

### Example Output

```
============================================================
EOM BILLING SUMMARY
============================================================

Stripe:
  Transactions: XX
  Gross Revenue: $XXX.XX
  Processing Fees: $XX.XX
  Net Revenue: $XXX.XX
  Fee Rate: X.XX%

PayPal:
  Transactions: XX
  Gross Revenue: $XXX.XX
  Processing Fees: $XX.XX
  Net Revenue: $XXX.XX
  Fee Rate: X.XX%

==============================
COMBINED TOTAL:
  All Transactions: XX
  Total Gross: $XXX.XX
  Total Fees: $XX.XX
  Total Net: $XXX.XX
  Overall Fee Rate: X.XX%
```

### Troubleshooting
- **PayPal 403 Error**: Transaction Search API may be disabled. Call PayPal support at 1-888-221-1161 to enable
- **Missing transactions**: Verify API keys are set correctly
- **Date format**: Use YYYY-MM-DD format for dates
