# TR-Automation-Scripts

A collection of scripts used to automate processes at The Tannery Row LLC

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
