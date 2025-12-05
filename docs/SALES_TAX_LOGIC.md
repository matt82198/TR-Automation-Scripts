# Sales Tax Logic - Location-Based

**Taxable status is determined by customer location (ship-to address), not by item type**

## How It Works

### In-State Orders → Taxable
If customer ships to the same state as your business:
- All line items marked as **Taxable (Y)**
- QuickBooks will calculate sales tax

### Out-of-State Orders → Non-Taxable
If customer ships to a different state:
- All line items marked as **Non-Taxable (N)**
- No sales tax charged

## Configuration

Set your business state (where you ship from):

**Environment Variable:**
```cmd
set SHIP_FROM_STATE=GA
```

**Default:** Georgia (GA)

Common state codes:
- GA = Georgia
- NY = New York
- CA = California
- TX = Texas
- FL = Florida
- etc.

## Logic Details

The script compares:
- **Ship-To State** (from order shipping address)
- **Ship-From State** (your business location)

If they match → Taxable (Y)
If they don't match → Non-Taxable (N)

### Address Priority

1. **Shipping Address** - Used first if available
2. **Billing Address** - Fallback if no shipping address

## Examples

### Example 1: In-State Order (Taxable)

**Your Business:** Georgia (GA)
**Customer Ships To:** Atlanta, GA

**Result:**
```
All items: Taxable = Y
QuickBooks will calculate GA sales tax
```

### Example 2: Out-of-State Order (Non-Taxable)

**Your Business:** Georgia (GA)
**Customer Ships To:** New York, NY

**Result:**
```
All items: Taxable = N
No sales tax charged
```

### Example 3: Mixed Order

**Your Business:** Georgia (GA)
**Order Line Items:**
- Premium Leather Hide
- Brass Buckle Set
- Waxed Thread

**Customer Ships To:** Texas, TX

**Result:**
```
ALL items: Taxable = N
(Tax is based on customer, not item)
```

## IIF Output

### In-State Order
```
SPL    INVOICE    01/15/2025    Sales    John Smith    -120.00    2    60.00    Leather Hide    Y    2
SPL    INVOICE    01/15/2025    Sales    John Smith    -18.00     1    18.00    Brass Buckles   Y    12
SPL    INVOICE    01/15/2025    Sales    John Smith    -15.00     3    5.00     Waxed Thread    Y    3
```
All items marked as **Y** (taxable)

### Out-of-State Order
```
SPL    INVOICE    01/15/2025    Sales    John Smith    -120.00    2    60.00    Leather Hide    N    2
SPL    INVOICE    01/15/2025    Sales    John Smith    -18.00     1    18.00    Brass Buckles   N    12
SPL    INVOICE    01/15/2025    Sales    John Smith    -15.00     3    5.00     Waxed Thread    N    3
```
All items marked as **N** (non-taxable)

## Console Output

When running the script, you'll see:

```
SALES TAX CALCULATION:
  Ship from state: GA
  In-state orders → Taxable (Y)
  Out-of-state orders → Non-taxable (N)
```

## Daily Automation

For daily automation, set the state in your batch file:

**daily_automation_rdp.bat:**
```batch
set SHIP_FROM_STATE=GA
set SQUARESPACE_API_KEY=your_key_here
python squarespace_to_quickbooks.py --fulfilled-today --output "%OUTPUT_FILE%" --sku-mapping sku_mapping.csv
```

## What Changed

### Before (Incorrect):
- Taxable status was per-item in SKU mapping
- Could mark leather as taxable, thread as non-taxable
- ❌ Not correct for sales tax rules

### Now (Correct):
- Taxable status is per-customer based on location
- All items in an order have same tax status
- ✅ Follows proper sales tax rules

## QuickBooks Behavior

### When Taxable = Y
- QuickBooks will apply sales tax based on:
  - Your tax settings
  - Customer's tax status
  - Tax code assigned

### When Taxable = N
- QuickBooks will NOT apply any sales tax
- Correct for out-of-state sales

## Troubleshooting

**All orders showing as taxable:**
- Check SHIP_FROM_STATE is set correctly
- Verify shipping addresses in Squarespace have state codes
- Check console output for "Ship from state"

**All orders showing as non-taxable:**
- Verify your SHIP_FROM_STATE matches your actual state
- Check if Squarespace is using state abbreviations (GA, NY) or full names

**Some orders have no tax status:**
- Check if shipping address exists in order
- Script will fall back to billing address
- If neither has state, defaults may vary

## State Code Reference

Use 2-letter state abbreviations:
- AL, AK, AZ, AR, CA, CO, CT, DE, FL, GA, HI, ID, IL, IN, IA, KS, KY, LA, ME, MD, MA, MI, MN, MS, MO, MT, NE, NV, NH, NJ, NM, NY, NC, ND, OH, OK, OR, PA, RI, SC, SD, TN, TX, UT, VT, VA, WA, WV, WI, WY

Match the format Squarespace uses in shipping addresses.
