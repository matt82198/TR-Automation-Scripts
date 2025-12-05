# Squarespace Invoice Import to QuickBooks Desktop

**Import ANY quantity: Single invoice, multiple specific invoices, or batch by date range.**

## What It Does

- Fetches orders from Squarespace (1 invoice or 1000+ invoices)
- **Smart customer matching** - matches by email, phone, last name to avoid duplicates
- **Automatically creates new customers** only when no match found (with full contact info)
- **Flags new customers** in a separate report so you know who will be created
- Maps essential fields: **Price, Quantity, Product Name**
- Generates IIF file for one-click import into QuickBooks

## Quick Start

### 1. Get API Key

1. Squarespace > **Settings > Advanced > Developer API Keys**
2. Click **Generate Key**
3. Copy it (you only see it once!)

### 2. Run Script

**Import ANY quantity - you choose:**

```cmd
set SQUARESPACE_API_KEY=your_key_here

# SINGLE invoice by order number
python squarespace_to_quickbooks.py --order-numbers 1001

# MULTIPLE specific invoices (comma-separated)
python squarespace_to_quickbooks.py --order-numbers 1001,1002,1003,1004

# BATCH - all invoices in date range (any quantity)
python squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31

# BATCH - last 30 days (default)
python squarespace_to_quickbooks.py
```

**Advanced - with customer matching:**
```cmd
# Export customers from QB first (Reports > List > Customer Contact List)
python squarespace_to_quickbooks.py --order-numbers 1001,1002 --customers qb_customers.csv
```

### 3. Review New Customers Report

The script creates a `_NEW_CUSTOMERS.txt` report showing:
- Which customers will be created (flagged)
- Full contact details for each new customer
- Count of existing vs. new customers

### 4. Import to QuickBooks

1. QuickBooks > **File > Utilities > Import > IIF Files**
2. Select the `.iif` file
3. QuickBooks will:
   - **Existing customers** → Create invoices immediately
   - **New customers** → Create customer THEN create invoice
   - Skip any customers that already exist (matches by name)

## What Gets Imported

### Invoices
| Field | Source | Notes |
|-------|--------|-------|
| **Invoice #** | Squarespace order number | |
| **Date** | Order creation date | |
| **Quantity** | Line item quantity | Per product |
| **Price** | Unit price paid | Per product |
| **Product** | Product name + variant | |
| **Shipping** | Shipping total | If present |
| **Tax** | Sales tax total | If present |

### New Customers (Flagged)
| Field | Source | Notes |
|-------|--------|-------|
| **Name** | Billing name or email | Sanitized for QB |
| **Email** | Customer email | |
| **Phone** | Billing phone | |
| **Address** | Full billing address | Multi-line format |

**New customers are flagged in a separate report file** so you know exactly who will be created.

## Output Files

The script creates two files:

1. **`.iif` file** - Contains invoices and customer records for QuickBooks import
2. **`_NEW_CUSTOMERS.txt`** - Report flagging which customers will be created

Example:
```
squarespace_invoices_2025-01-01_to_2025-01-31.iif
squarespace_invoices_2025-01-01_to_2025-01-31_NEW_CUSTOMERS.txt
```

## Import Options - Flexible Quantity

### Single Invoice
```bash
python squarespace_to_quickbooks.py --order-numbers 1001
```
Output: `squarespace_invoice_1001.iif`

### Multiple Specific Invoices
```bash
python squarespace_to_quickbooks.py --order-numbers 1001,1002,1003,1004,1005
```
Output: `squarespace_invoices_5_orders.iif`

### Batch by Date Range (Any Quantity)
```bash
# Last 30 days (default)
python squarespace_to_quickbooks.py

# Specific date range
python squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31

# Just January orders
python squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31
```

### With Customer Matching
```bash
# Single invoice with matching
python squarespace_to_quickbooks.py --order-numbers 1001 --customers qb_customers.csv

# Multiple invoices with matching
python squarespace_to_quickbooks.py --order-numbers 1001,1002,1003 --customers qb_customers.csv

# Batch with matching
python squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31 --customers qb_customers.csv
```

### Other Options
```bash
# Custom QuickBooks account names
python squarespace_to_quickbooks.py --order-numbers 1001 --ar-account "A/R" --income-account "Product Sales"

# Custom output file
python squarespace_to_quickbooks.py --order-numbers 1001 --output my_invoice.iif
```

## Requirements

- Python 3.6+
- `requests` library: `pip install requests`
- Squarespace Commerce Advanced plan
- QuickBooks Desktop (any version)

## QuickBooks Setup

Just make sure these accounts exist (they usually do):
- **Accounts Receivable** - for invoices
- **Sales** or similar income account - for revenue

The script will tell you which account names it's using.

## How Customer Matching Works

### Without --customers flag (Simple Mode)

The IIF file includes customer records with:
- Name (from billing info or email)
- Email address
- Phone number
- Full billing address

When you import, **QuickBooks automatically**:
- Skips customers if the **name already exists** (exact match)
- Creates new customers with full contact details
- This works even if you don't have access to customer export!

### With --customers flag (Advanced Mode)

If you provide a customer export CSV, the script does **smarter matching**:

**Matching Priority:**
1. **Email** (exact match) - most reliable
2. **Phone number** (normalized) - removes spaces/dashes
3. **Last name only** - if unique
4. **Last name + First name** - if multiple people with same last name

**Benefits:**
- Matches even if name is slightly different in QB vs Squarespace
- Shows you which customers were matched vs. new
- Better handling of duplicate last names

**When to use --customers flag:**
- You have many customers with similar names
- Email/phone in Squarespace might match differently-named QB customers
- You want to see a detailed match report before importing

## Troubleshooting

**"Authentication failed"**
- Check your API key is correct

**"Access denied. Ensure you have Commerce Advanced plan"**
- Orders API requires Commerce Advanced subscription

**"No orders found"**
- Check date range
- Verify orders exist in Squarespace
- Canceled orders are skipped automatically

**Duplicate customers being created**
- Check if customer names in Squarespace match QB exactly
- QuickBooks matches by name only (case-sensitive sometimes)
- For smarter matching, export customer list and use `--customers qb_customers.csv`
- Example: "John Smith" in QB won't match "John A Smith" in Squarespace

**Import fails in QuickBooks**
- Make sure account names match your Chart of Accounts
- Use `--ar-account` and `--income-account` flags to customize

## Daily Automation

Want IIF files automatically generated every day for fulfilled orders?

### Option 1: RDP Upload (Recommended)
Files saved directly to your RDP/network location daily at 11 PM
- See: `RDP_UPLOAD_SETUP.md`
- File: `daily_automation_rdp.bat`

### Option 2: Email
IIF files emailed to matt@thetanneryrow.com daily at 11 PM
- See: `DAILY_AUTOMATION_SETUP.md`
- File: `daily_automation.bat`

**Comparison:** See `DAILY_AUTOMATION_COMPARISON.md` to choose the best option for your workflow.

## Technical Notes

- Customers are sanitized (41 char limit, no special chars)
- Product names limited to 31 characters
- Canceled orders automatically excluded
- IIF format uses standard QB invoice structure
