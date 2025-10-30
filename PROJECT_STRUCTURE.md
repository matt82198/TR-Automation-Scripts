# Project Structure

```
TR-Automation-Scripts/
├── README.md                      # Main documentation
├── .gitignore                     # Git ignore rules
├── sku_mapping.csv                # Product mapping (working file)
├── import_log.csv                 # Import tracking log (auto-generated)
│
├── daily_automation.bat           # Daily email automation
├── daily_automation_rdp.bat       # Daily RDP automation
│
├── scripts/                       # Main automation scripts
│   ├── squarespace_to_quickbooks.py  # Invoice import (main)
│   ├── payment_fetch.py              # Stripe/PayPal EOM billing
│   ├── pending_order_count.py        # Panel/swatch order count
│   ├── email_helper.py               # Email utilities
│   └── stripe_invoices.py            # Stripe invoice helper
│
├── utils/                         # Utility scripts
│   └── generate_product_mappings.py  # Product mapping generator
│
├── examples/                      # Sample data files
│   ├── QB item list Oct 2025.xlsx - Sheet1.csv
│   └── products_Nov-14_06-03-09PM.csv
│
├── docs/                          # Documentation
│   ├── PRODUCT_MAPPING_GUIDE.md
│   ├── FIELDS_CAPTURED.md
│   ├── SALES_TAX_LOGIC.md
│   ├── RDP_QUICK_START.md
│   └── DAILY_AUTOMATION_SETUP.md
│
└── tests/                         # Test files
```

## Quick Start

**Daily Import:**
```bash
python scripts\squarespace_to_quickbooks.py --fulfilled-today
```

**Generate Product Mappings:**
```bash
python utils\generate_product_mappings.py
```

**EOM Billing Report:**
```bash
python scripts\payment_fetch.py --csv
```
