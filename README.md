# TR-Automation-Scripts

A collection of scripts used to automate processes at The Tannery Row LLC

## Setup

### Prerequisites
- Python 3.7 or higher
- Required Python packages: `requests`

### Installation
```bash
pip install requests
```

### API Keys
Set your API keys as environment variables:

**Windows:**
```cmd
set SQUARESPACE_API_KEY=your-squarespace-api-key-here
```

**Mac/Linux:**
```bash
export SQUARESPACE_API_KEY=your-squarespace-api-key-here
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

## Pull Squarespace Invoice Date Range Info + Summary

This script will pull down a list of payments given any date range passed in as a parameter. This will also return the following details in summary of the date range:

### Summary
- Total Gross Revenue
- Total Processing Fees  
- Total Net Revenue
- Average Fee Rate
- Number of Transactions
- Average Transaction

### Usage

```bash
stripe_invoices.py [-h] [--start-date START_DATE] [--end-date END_DATE] [--csv]
```

### Options

```
-h, --help            show this help message and exit
--start-date START_DATE
                      Start date (YYYY-MM-DD). Default: 30 days ago
--end-date END_DATE   End date (YYYY-MM-DD). Default: today
--csv                 Export results to CSV file
```

### Example Usage

```bash
python stripe_invoices.py --csv
```

When executed, this will return all data for the last 30 days by default and export to CSV.
