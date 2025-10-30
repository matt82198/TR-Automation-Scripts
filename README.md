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

## Pending Order Count Script

**File:** `pending_order_count.py`

This script connects to the Squarespace API to count panel and swatch book products from pending orders. It provides detailed breakdowns by product type, variant specifications, and SKUs.

### Features
- **SKU-based counting** for precise product identification
- **Variant details** including sizes, weights, leather types (Dublin, Glove, etc.)
- **Separate tracking** of panels and swatch books
- **Detailed output** with product names, variant descriptions, and SKU references

### Usage

```bash
python scripts/pending_order_count.py
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
python scripts/payment_fetch.py [options]
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
python scripts/payment_fetch.py --csv

# Get specific date range from Stripe only
python scripts/payment_fetch.py --start-date 2024-01-01 --end-date 2024-01-31 --source stripe

# Get PayPal transactions for last week
python scripts/payment_fetch.py --start-date 2024-01-15 --source paypal
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

## Squarespace to QuickBooks Integration

**File:** `scripts/squarespace_to_quickbooks.py`

Automatically import Squarespace orders as QuickBooks Desktop invoices with product mapping, customer matching, and location-based tax calculation.

### What It Does

✅ Fetches orders from Squarespace (single, multiple, or batch)
✅ **Maps products by name** to QuickBooks items (no SKUs needed!)
✅ **NEW: Variant mapping** - Maps products with attributes (tannage, color, weight)
✅ **Extracts pieces** from order customizations/variants
✅ **Captures all fields**: Item, Description, Quantity, Pieces, Price
✅ **Location-based tax** (in-state vs out-of-state)
✅ Smart customer matching (email/phone/name) to avoid duplicates
✅ Auto-creates new customers with full contact info
✅ Flags new customers in separate report
✅ **REP = "SHOP"** and **SHIP VIA = "UPS"** (hardcoded)
✅ QuickBooks auto-generates invoice numbers
✅ **Daily automation** - saves to RDP or emails files

### Quick Start

**1. Set Environment Variables:**
```cmd
set SQUARESPACE_API_KEY=your_api_key_here
set SHIP_FROM_STATE=GA
```

**2. Create Product Mapping** (optional - edit `sku_mapping.csv`):
```csv
SquarespaceProductName,QuickBooksItem
Horween Dublin Leather Panels,Premium Leather Hide
Brass Hardware Set,Brass Buckle Set
Leather Panel - Horween Predator - Steel - 5-6 oz,Predator Steel 5-6 oz
Leather Panel - Italian Nubuck - French Navy - 3.5-4 oz,Italian Nubuck French Navy
```
**Note:** Supports both simple product mappings and variant-specific mappings (tannage, color, weight)

**3. Run Import:**
```cmd
# Orders fulfilled today
python scripts\squarespace_to_quickbooks.py --fulfilled-today

# Specific order(s)
python scripts\squarespace_to_quickbooks.py --order-numbers 1001
python scripts\squarespace_to_quickbooks.py --order-numbers 1001,1002,1003

# Date range
python scripts\squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31
```

**4. Import to QuickBooks:**
- File > Utilities > Import > IIF Files
- Select the generated `.iif` file
- QuickBooks will auto-assign invoice numbers

### Key Features

- **Product Name Mapping**: Map Squarespace products to QB items (no SKU required)
- **Variant Mapping**: Map products with multiple attributes (tannage, color, weight) to specific QB items
- **Unmapped Products Tracking**: Auto-generates report of products without mappings
- **Pieces Extraction**: From customizations/variants in Squarespace API
- **Location-Based Tax**: Compare ship-to vs ship-from state
- **Customer Matching**: Smart duplicate detection by email/phone/name
- **Daily Automation**: Auto-generate IIF files for fulfilled orders
- **Flexible Import**: Single, multiple, or batch by date range
- **REP & SHIP VIA**: Automatically set to "SHOP" and "UPS"

### Field Mapping

| QuickBooks | Squarespace | Notes |
|------------|-------------|-------|
| Date | `createdOn` | Invoice date |
| Invoice # | *(auto)* | QB generates sequential numbers |
| Customer | `billingAddress` | Smart duplicate detection |
| Ship To | `shippingAddress` | Full address |
| Ship Date | `fulfilledOn` | Fulfillment date |
| Ship Via | *(hardcoded)* | Always "UPS" |
| REP | *(hardcoded)* | Always "SHOP" |
| Item | `productName` → mapped | Via `sku_mapping.csv` |
| Description | `productName` + `variantOptions` | Full description |
| Quantity | `quantity` | Normal integers |
| Pieces | `customizations` or `variantOptions` | Extracted from API |
| Price | `unitPricePaid.value` | Unit price |
| Taxable | Ship-to vs Ship-from state | Y/N based on location |

### Generated Reports

After each import, the script generates helpful reports:

📄 **`*_NEW_CUSTOMERS.txt`** (always generated)
- Lists all new customers that will be created in QuickBooks
- Includes contact info for verification

📄 **`*_UNMAPPED_PRODUCTS.txt`** (if any unmapped products found)
- Lists products without mappings in `sku_mapping.csv`
- Shows what QB item names will be auto-created
- Provides suggested mapping entries to add
- **⚠️ Review this before importing to avoid unwanted QB items!**

### Action Items

**Required:**
- [ ] Get Squarespace API key (Settings > Advanced > Developer API Keys)
- [ ] Set `SQUARESPACE_API_KEY` and `SHIP_FROM_STATE` environment variables
- [ ] Create `sku_mapping.csv` with your product mappings
- [ ] Test with one order: `python squarespace_to_quickbooks.py --order-numbers 1001`
- [ ] **Review `_UNMAPPED_PRODUCTS.txt` report (if generated)**
- [ ] Import to QuickBooks and verify

**Optional:**
- [ ] Export QB customer list for smart duplicate detection
- [ ] Set up daily automation (email or RDP upload)
- [ ] Configure Windows Task Scheduler for daily imports

### Documentation

See these files for complete documentation:
- `docs/PRODUCT_MAPPING_GUIDE.md` - How to map products by name (no SKU!)
- `docs/FIELDS_CAPTURED.md` - Complete field mapping details
- `docs/SALES_TAX_LOGIC.md` - Location-based tax rules
- `docs/RDP_QUICK_START.md` - 5-minute daily automation setup
- `docs/DAILY_AUTOMATION_SETUP.md` - Email automation guide

### Daily Automation

**Option 1: RDP Upload (Recommended)**
```cmd
# Edit daily_automation_rdp.bat, set your RDP path, then schedule in Task Scheduler
daily_automation_rdp.bat
```

**Option 2: Email**
```cmd
# Set email environment variables, then schedule in Task Scheduler
set EMAIL_USER=your_email@gmail.com
set EMAIL_PASSWORD=your_app_password
python scripts\squarespace_to_quickbooks.py --fulfilled-today --email matt@thetanneryrow.com
```

See `RDP_QUICK_START.md` or `DAILY_AUTOMATION_SETUP.md` for setup instructions.
