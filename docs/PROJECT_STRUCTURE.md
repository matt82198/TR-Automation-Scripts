# Project Structure

```
TR-Automation-Scripts/
├── README.md                      # Main documentation
├── .gitignore                     # Git ignore rules
│
├── config/                        # Configuration & credentials
│   ├── README.md                  # Config directory documentation
│   ├── sku_mapping.csv            # Product mapping (Squarespace → QB)
│   ├── import_log.csv             # Import tracking log (auto-generated)
│   ├── gmail_credentials.json     # Gmail OAuth2 credentials (not committed)
│   └── gmail_token.json           # Gmail OAuth2 token (auto-generated)
│
├── data/                          # Data files
│   ├── README.md                  # Data directory documentation
│   └── customers.csv              # QuickBooks customer export (not committed)
│
├── automation/                    # Automated batch scripts
│   ├── README.md                  # Automation documentation
│   ├── daily_automation.bat       # Daily email automation
│   └── daily_automation_rdp.bat   # Daily RDP automation
│
├── scripts/                       # Main automation scripts
│   ├── squarespace_to_quickbooks.py  # Squarespace → QuickBooks invoice import
│   ├── payment_fetch.py              # Stripe/PayPal EOM billing
│   ├── pending_order_count.py        # Panel/swatch order count
│   ├── email_helper.py               # Email utilities
│   └── stripe_invoices.py            # Stripe invoice helper
│
├── utils/                         # Utility scripts
│   └── generate_product_mappings.py  # Product mapping generator
│
├── examples/                      # Sample & reference data
│   ├── customers_backup.csv           # Sanitized customer example
│   ├── holiday_sale_mappings.csv      # Holiday sale product mappings
│   ├── exampleCustomer.IIF            # Sample customer IIF format
│   ├── QB item list Oct 2025.xlsx - Sheet1.csv  # QB item list
│   ├── TROW LLC INVOICE FORM.DES      # QB invoice template
│   └── SAMPLE_NEW_CUSTOMERS_REPORT.txt
│
├── tests/                         # Test files & documentation
│   ├── TEST_CASES.md              # Comprehensive test cases
│   ├── test_email.bat             # Email test script
│   ├── run_squarespace.bat        # Squarespace test script
│   ├── run_paypal.bat             # PayPal test script
│   └── ... (other test utilities)
│
└── docs/                          # Documentation
    ├── CHANGELOG.md               # Version history
    ├── EMAIL_SETUP.md             # Gmail OAuth2 setup guide
    ├── PROJECT_STRUCTURE.md       # This file
    ├── PRODUCT_MAPPING_GUIDE.md   # Product mapping guide
    ├── SKU_MAPPING_GUIDE.md       # SKU mapping guide
    ├── FIELDS_CAPTURED.md         # Data fields captured
    ├── SALES_TAX_LOGIC.md         # Sales tax calculation
    ├── RDP_QUICK_START.md         # RDP setup guide
    └── DAILY_AUTOMATION_SETUP.md  # Automation setup guide
```

## Directory Purposes

### `/config/` - Configuration & Credentials
Contains all configuration files, credentials, and application state:
- Product mappings (SKU mapping)
- Gmail OAuth2 credentials (gitignored)
- Import tracking log

### `/data/` - Data Files
Contains data files used by scripts:
- Customer exports from QuickBooks
- Other data files (gitignored for privacy)

### `/automation/` - Scheduled Automation
Contains batch scripts for automated/scheduled tasks:
- Daily automation scripts
- RDP-specific automation

### `/scripts/` - Main Scripts
Three primary automation scripts:
1. **Squarespace to QuickBooks** - Invoice generation
2. **Payment Fetch** - EOM billing reports (Stripe/PayPal)
3. **Pending Order Count** - Panel/swatch order tracking

### `/utils/` - Utilities
Helper scripts for maintenance tasks:
- Product mapping generation
- Data transformation utilities

### `/examples/` - Reference Data
Sample data files and examples:
- Customer data examples
- Holiday sale mappings
- QB templates and formats

### `/tests/` - Testing
Test scripts and comprehensive test documentation:
- Test cases with validation criteria
- Test data and scripts

### `/docs/` - Documentation
All project documentation:
- Setup guides
- Technical documentation
- Process guides

## Quick Start

**Daily Import:**
```bash
python scripts/squarespace_to_quickbooks.py --fulfilled-today --email your@email.com
```

**Single Order Import:**
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 12345 --email your@email.com
```

**Generate Product Mappings:**
```bash
python utils/generate_product_mappings.py
```

**EOM Billing Report:**
```bash
python scripts/payment_fetch.py --csv --start 2025-11-01 --end 2025-11-30
```

## Configuration Files

### Required Setup
1. **Gmail OAuth2** - See `/docs/EMAIL_SETUP.md`
   - Download credentials to `config/gmail_credentials.json`

2. **Product Mapping** - See `/docs/SKU_MAPPING_GUIDE.md`
   - Edit `config/sku_mapping.csv`

3. **Environment Variables**
   ```cmd
   SQUARESPACE_API_KEY=your_key
   EMAIL_USER=sender@email.com
   EMAIL_RECIPIENT=recipient@email.com
   ```

## Generated Files

Output files are created in the root directory:
- `*.iif` - QuickBooks import files
- `*_NEW_CUSTOMERS.txt` - New customer reports
- `*_UNMAPPED_PRODUCTS.txt` - Unmapped product reports
- `*_ENCRYPTED.zip` - Encrypted email attachments

All generated files are gitignored.

## Security Notes

The following files contain sensitive data and are **never committed**:
- `config/gmail_credentials.json` - OAuth2 credentials
- `config/gmail_token.json` - OAuth2 access token
- `config/import_log.csv` - Order tracking (contains order IDs)
- `data/customers.csv` - Customer PII

All are listed in `.gitignore`.
