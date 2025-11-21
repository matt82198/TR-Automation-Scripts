# Data Directory

This directory contains data files used by the automation scripts.

## Files

### Customer Data
- **`customers.csv`** - Exported customer list from QuickBooks
  - **Status**: Optional (for customer matching)
  - **Committed**: NO (in .gitignore - contains PII)
  - **Source**: Exported from QuickBooks
  - **Purpose**: Enables smart customer matching to prevent duplicates
  - **Format**: QuickBooks customer export CSV

## Usage

### Exporting Customer Data from QuickBooks

1. Open QuickBooks Desktop
2. Go to **Lists > Customers**
3. Click **Excel** button > **Export Customer List**
4. Save as `data/customers.csv`

### Using Customer Data

The Squarespace to QuickBooks script can use this file for smart customer matching:

```bash
python scripts/squarespace_to_quickbooks.py \
  --customers data/customers.csv \
  --order-numbers 12345
```

By default, the script uses `examples/customers_backup.csv` which is a sanitized example.

## Notes

- **Privacy**: This file may contain PII (names, emails, addresses)
- **Security**: File is gitignored and will not be committed
- **Backup**: Keep a backup of this file outside the repository
- **Updates**: Re-export periodically to keep customer data current
