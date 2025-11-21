# Test Cases for TR Automation Scripts

## Squarespace to QuickBooks Integration Tests

### Test Case 1: Single Order Import
**Purpose**: Verify basic invoice generation for a single order

**Command**:
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 12821 --customers "" --email matt@thetanneryrow.com
```

**Expected Results**:
- Customer IIF file created with customer details
- Invoice IIF file created with line items
- Email sent with encrypted ZIP file
- Import log updated

**Validation**:
- Customer has billing and shipping addresses populated
- Invoice has correct date, amount, and line items
- Product mappings applied correctly

---

### Test Case 2: Multiple Orders Import
**Purpose**: Verify batch processing of multiple orders

**Command**:
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 12821,12891 --customers "" --email matt@thetanneryrow.com
```

**Expected Results**:
- Multiple customers in customer IIF file
- Multiple invoices in invoice IIF file
- New customers report generated
- All orders logged in import_log.csv

**Validation**:
- Each order processed independently
- No duplicate customer records
- Customer matching works correctly

---

### Test Case 3: Holiday Sale Mappings
**Purpose**: Verify holiday sale products map to correct QB items

**Command**:
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 12891 --customers "" --email matt@thetanneryrow.com
```

**Expected Results**:
- Products map to "2025 Holiday" items:
  - Horween Dublin → `2025 Holiday Horween Dublin FF`
  - Horween Chromexcel SHF → `2025 Holiday Horween Chrxl SHF`
  - Mystery Bundle 3.5-6 oz → `2025 Holiday Horween 6oz and under`

**Validation**:
- Check invoice IIF file for correct item names
- Holiday mappings take priority over regular mappings

---

### Test Case 4: Customer Matching
**Purpose**: Verify existing customer detection

**Command**:
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 12821 --customers examples/customers_backup.csv --email matt@thetanneryrow.com
```

**Expected Results**:
- Existing customers matched by email/phone/name
- Only truly new customers in customer IIF file
- Report shows matched vs new customers

**Validation**:
- Check new customers report
- Verify matched customers not duplicated

---

### Test Case 5: Email Delivery
**Purpose**: Verify OAuth2 email sending

**Script**: `tests/test_email.bat`

**Expected Results**:
- Email sent successfully
- ZIP file encrypted with random password
- Password displayed in output

**Validation**:
- Check inbox for email
- Verify ZIP file can be opened with password

---

### Test Case 6: IIF Format Validation
**Purpose**: Verify IIF files import into QuickBooks without errors

**Steps**:
1. Generate IIF files using test case 2
2. Open QuickBooks test file (fscpay)
3. Import customer IIF file: `File > Utilities > Import > IIF Files`
4. Import invoice IIF file

**Expected Results**:
- No import errors
- Customers created with addresses
- Invoices created with correct totals
- Sales tax properly applied based on ship-to state

**Validation**:
- Check customer records in QuickBooks
- Verify invoice line items and totals
- Confirm addresses populated correctly

---

## PayPal Integration Tests

### Test Case 7: PayPal Payment Fetch
**Script**: `tests/run_paypal.bat`

**Expected Results**:
- Payments fetched from PayPal API
- CSV file generated with payment details

---

## Test Data

### Test Orders
- **Order 12821**: Troy Nixon - 2 Dublin panels
- **Order 12891**: Trenton Hill - Holiday sale items (Dublin FF, Chrxl SHF, Mystery Bundle)

### Test Files Location
- Customer backup: `examples/customers_backup.csv`
- Holiday mappings: `examples/holiday_sale_mappings.csv`
- Product mappings: `sku_mapping.csv`
- QB item list: `examples/QB item list Oct 2025.xlsx - Sheet1.csv`

---

## Pre-Test Setup

### Required Environment Variables
```bash
SQUARESPACE_API_KEY=<your_key>
EMAIL_USER=matt@thetanneryrow.com
EMAIL_RECIPIENT=matt@thetanneryrow.com
```

### Required Files
- `config/gmail_credentials.json` - OAuth2 credentials
- `config/gmail_token.json` - OAuth2 token (auto-generated)
- `config/sku_mapping.csv` - Product mappings
- `examples/holiday_sale_mappings.csv` - Holiday sale mappings

---

## Post-Test Cleanup

**Clean up test outputs**:
```bash
rm -f squarespace_invoice_*.iif squarespace_invoice_*.txt squarespace_invoice_*.zip
echo "order_number,date_imported,iif_file" > config/import_log.csv
```

---

## Common Issues & Troubleshooting

### Issue: "INVITEMDESC is not a valid column name"
**Solution**: This was fixed - SPL header should only have minimal fields (no INVITEMDESC, no OTHER1)

### Issue: "SHIPTOADDR1 is not a valid column name"
**Solution**: Addresses belong in customer record (BADDR/SADDR), not in invoice TRNS

### Issue: "SalesRep must be formatted as Name:EntityType:Initials"
**Solution**: Leave REP field blank in TRNS line

### Issue: Holiday items not mapping correctly
**Solution**: Ensure `examples/holiday_sale_mappings.csv` exists and is loaded by default

### Issue: Customer addresses not populating
**Solution**: Verify BADDR1-3 and SADDR1-3 fields in customer IIF, with customer name on first line
