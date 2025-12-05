# Squarespace to QuickBooks - Quick Reference

## Single Invoice
```cmd
python squarespace_to_quickbooks.py --order-numbers 1001
```
→ Creates: `squarespace_invoice_1001.iif`

## Multiple Specific Invoices
```cmd
python squarespace_to_quickbooks.py --order-numbers 1001,1002,1003
```
→ Creates: `squarespace_invoices_3_orders.iif`

## Batch - Last 30 Days
```cmd
python squarespace_to_quickbooks.py
```
→ Creates: `squarespace_invoices_[dates].iif`

## Batch - Custom Date Range
```cmd
python squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31
```
→ Creates: `squarespace_invoices_2025-01-01_to_2025-01-31.iif`

## With Customer Matching
```cmd
python squarespace_to_quickbooks.py --order-numbers 1001 --customers qb_customers.csv
```

---

## What Happens When You Import

### Existing Customers
✓ Invoice created immediately
✓ Uses existing customer record

### New Customers (Flagged in Report)
⚠ Customer created with full contact info
✓ THEN invoice created for that customer

---

## Files Created

1. **`.iif`** - Import this into QuickBooks
2. **`_NEW_CUSTOMERS.txt`** - Review this before importing

---

## Import to QuickBooks

1. File > Utilities > Import > IIF Files
2. Select the `.iif` file
3. Done!

QuickBooks automatically:
- Skips customers that already exist (by name)
- Creates new customers with full details
- Creates all invoices
