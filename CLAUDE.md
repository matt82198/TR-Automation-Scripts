# TR Automation Scripts

## Cardinal Rule

**Always use existing scripts with their CLI arguments. Never write ad-hoc Python to replicate what a script already does.** If a script exists for a task, use it. If a script is close but missing a feature, modify the script rather than writing a one-off.

**Actively maintain this file.** When you learn something new about the codebase, add a new script, or discover a pattern, update CLAUDE.md immediately so future sessions have the context.

## Project Overview

Streamlit dashboard and CLI toolset for Tannery Row, a leather goods company. The app (`app.py`) serves as an internal tools portal with role-based access, hosted on Streamlit Cloud. Individual scripts handle Squarespace order processing, QuickBooks billing, payment reconciliation, CRM integration, and inventory tracking. Always run CLI commands from the project root directory.

## Master Script Reference

| Script | Mode | Description |
|--------|------|-------------|
| `squarespace_to_quickbooks.py` | CLI + Streamlit | Convert Squarespace orders to QuickBooks IIF files |
| `payment_fetch.py` | CLI only | Pull Stripe/PayPal transactions for EOM billing (read-only) |
| `mystery_bundle_counter.py` | CLI + Streamlit | Count mystery bundle quantities by leather type (seasonal: Nov-Dec) |
| `leather_weight_calculator.py` | CLI + Streamlit | Calculate/estimate box weights for shipping |
| `toml_to_json.py` | CLI only | Convert TOML files to JSON (no argparse, uses sys.argv) |
| `pending_order_count.py` | Streamlit only | Count pending panels and swatch books |
| `order_payment_matcher.py` | Streamlit only | Match specific orders to payment transactions |
| `quickbooks_billing_helper.py` | **Hidden** | Combine order + payment data for manual QB entry (see Future Plans) |
| `swatch_book_contents.py` | Internal module | Scrape website for leather colors (used by sample inventory sync) |
| `materialbank_method.py` | Streamlit only | Import Material Bank leads into Method CRM |
| `email_helper.py` | Internal module | Email delivery (used by `squarespace_to_quickbooks.py`) |
| `build_sku_mapping.py` | CLI only | Analyze orders and generate SKU mappings (outputs both detailed and simple formats) |
| `order_net_lookup.py` | CLI only | Look up net payment received for specific order(s) (Stripe/PayPal) |
| `cage_inventory_manager.py` | CLI only | Manage cage inventory in Google Sheets (list, add, backup, restore) |
| `stripe_invoices.py` | **Deprecated** | Replaced by `payment_fetch.py` |

---

## CLI-Runnable Scripts

### `squarespace_to_quickbooks.py`

Fetches Squarespace orders and generates IIF files for QuickBooks Desktop import.

**Single or multiple orders:**
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 13825,13868,13870 --customers config/qb_customer_list.csv
```

**Customers-only mode (no invoices, just customer matching/creation report):**
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 13825,13868,13870 --customers config/qb_customer_list.csv --customers-only
```

**Orders fulfilled today:**
```bash
python scripts/squarespace_to_quickbooks.py --fulfilled-today --customers config/qb_customer_list.csv
```

**Date range batch:**
```bash
python scripts/squarespace_to_quickbooks.py --start-date 2025-01-01 --end-date 2025-01-31 --customers config/qb_customer_list.csv
```

**Use Squarespace order numbers as invoice numbers:**
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 13825 --customers config/qb_customer_list.csv --use-ss-invoice-numbers
```

**Override invoice date:**
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 13825 --customers config/qb_customer_list.csv --invoice-date 01/15/2025
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--order-numbers` | None | Comma-separated order numbers |
| `--fulfilled-today` | False | Fetch orders fulfilled today |
| `--start-date` / `--end-date` | None | Date range for batch mode (YYYY-MM-DD) |
| `--customers` | `examples/customers_backup.csv` | QB customer export CSV for smart matching |
| `--product-mapping` | `config/sku_mapping.csv` | Squarespace product to QB item mapping |
| `--holiday-mapping` | `examples/holiday_sale_mappings.csv` | Holiday sale product mappings (priority over regular) |
| `--ar-account` | `Accounts Receivable` | A/R account name in QB |
| `--income-account` | `Merchandise Sales` | Income account name in QB |
| `--use-ss-invoice-numbers` | False | Use SS order numbers as QB invoice numbers (SS-XXXXX prefix) |
| `--invoice-date` | None | Override invoice date for all invoices (MM/DD/YYYY) |
| `--customers-only` | False | Only generate new customers file, skip invoices |
| `--output` | Auto-generated | Override output filename |
| `--email` | None | Email address to send the IIF file to |

#### Output

All output goes to `output/squarespace/`. Generates:

1. `*_NEW_CUSTOMERS.iif` - New customer records (import into QB first)
2. `*_INVOICES.iif` - Invoice records (import after customers)
3. `*_NEW_CUSTOMERS.txt` - Human-readable report with Bill To/Ship To addresses
4. `*_UNMAPPED_PRODUCTS.txt` - Products not found in SKU mapping (if any)
5. `*_ENCRYPTED.zip` - Encrypted archive of all generated files

#### Customer Matching

The `--customers` flag enables smart matching to avoid QB duplicates. Matching priority:

1. **Email** (exact match) - most reliable
2. **Phone** (normalized match) - very reliable
3. **First + Last name** (both must match) - least reliable, requires both

**Customer list file:** `config/qb_customer_list.csv` - Direct export from QuickBooks Desktop (Customer Center > Export). Reads columns: `Customer`, `Main Email`, `Main Phone`, `First Name`, `Last Name`.

**Import log:** `config/customer_import_log.csv` - Tracks customers created by previous runs. Loaded alongside the QB export to prevent duplicates across runs.

**Duplicate detection:** `config/import_log.csv` - Tracks which order numbers have already been imported. Re-running the same orders will skip them with a warning.

#### Product/SKU Mapping

`config/sku_mapping.csv` maps Squarespace product names to QuickBooks item names.

Format: `SquarespaceProductName,QuickBooksItem`

Supports variant-specific mappings with ` - ` separator:
```
Leather Panel - Horween Predator - Steel - 5-6 oz,Horween Predator Steel 5-6oz
```

#### Required Secrets

- `SQUARESPACE_API_KEY`
- `SHIP_FROM_STATE` (default: GA)
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD` (only if using `--email`)

---

### `payment_fetch.py`

Read-only script that pulls Stripe and PayPal transactions for end-of-month billing reports.

**Default (last 30 days, both sources):**
```bash
python scripts/payment_fetch.py
```

**Specific date range, Stripe only:**
```bash
python scripts/payment_fetch.py --start-date 2025-01-01 --end-date 2025-01-31 --source stripe
```

**PayPal only:**
```bash
python scripts/payment_fetch.py --source paypal
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--start-date` | 30 days ago (YYYY-MM-DD) | Start of date range |
| `--end-date` | Today (YYYY-MM-DD) | End of date range |
| `--source` | `both` | `stripe`, `paypal`, or `both` |
| `--csv` | True (always on) | Export to CSV |

#### Output

CSV written to the current working directory: `eom_billing_{start_date}_to_{end_date}.csv`

Columns: `date`, `source`, `customer_name`, `customer_email`, `gross_amount`, `processing_fee`, `net_amount`, `transaction_id`

#### Required Secrets

- `STRIPE_API_KEY` (read-only restricted key)
- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`
- `PAYPAL_MODE` (default: `live`; set to `sandbox` for testing)

---

### `order_net_lookup.py`

Looks up net payment received (after Stripe/PayPal processing fees) for specific Squarespace order(s).

**Single order:**
```bash
python scripts/order_net_lookup.py 13536
```

**Multiple orders:**
```bash
python scripts/order_net_lookup.py 13536,13537,13538
```

**Stripe only:**
```bash
python scripts/order_net_lookup.py 13536 --source stripe
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `order_numbers` | Required | Comma-separated order number(s) (positional arg) |
| `--days` | `90` | How many days back to search for payments |
| `--source` | `both` | `stripe`, `paypal`, or `both` |

#### Output

Prints to console: gross amount, payment source, processing fee, net received, and transaction ID for each order. For multiple orders, includes a summary with totals.

#### How It Works

1. Fetches order(s) from Squarespace API to get order date and gross amount
2. Pulls Stripe/PayPal transactions for the order date range (+/- 3 days)
3. Matches orders to payments by amount, date, email, and name
4. Displays net received after fees

#### Required Secrets

- `SQUARESPACE_API_KEY`
- `STRIPE_API_KEY` (if searching Stripe)
- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` (if searching PayPal)

---

### `cage_inventory_manager.py`

Manages the cage inventory stored in Google Sheets. Connects directly using service account credentials from `.streamlit/secrets.toml`.

**List current inventory:**
```bash
python scripts/cage_inventory_manager.py list
```

**Backup to CSV:**
```bash
python scripts/cage_inventory_manager.py backup
```

**Add untracked items inline:**
```bash
python scripts/cage_inventory_manager.py add --items "Amalfi Lux Burgundy|2-3 oz" "Black Yellowstone|4-5 oz" "Cognac Classic"
```

**Add catalog items with swatch book name:**
```bash
python scripts/cage_inventory_manager.py add --swatch-book "Horween Dublin" --items "Black|3-4 oz" "Natural|5-6 oz"
```

**Bulk add from CSV:**
```bash
python scripts/cage_inventory_manager.py add --csv items_to_add.csv
```

**Restore from backup:**
```bash
python scripts/cage_inventory_manager.py restore --csv output/cage_inventory_backup_2026-02-16.csv
```

#### Subcommands

| Command | Description |
|---------|-------------|
| `list` | Display all cage items grouped by swatch book |
| `backup` | Export current inventory to CSV (`output/cage_inventory_backup_{timestamp}.csv`) |
| `add` | Add items from `--items` (inline) or `--csv` (file). Auto-backups before modifying |
| `export` | Export to CSV with custom `--output` path |
| `restore` | Overwrite inventory from a CSV backup file. Auto-backups current state first |

#### Add Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--items` | None | Inline items: `"description\|weight"` or `"description"` |
| `--csv` | None | CSV file with columns: `swatch_book`, `color`, `weight` |
| `--swatch-book` | `Untracked` | Swatch book name for inline items |
| `--no-backup` | False | Skip automatic backup before modifying |

#### Data Model

Items use the same schema as Streamlit: `swatch_book`, `color`, `weight`, `date_added`. Custom/untracked items use `swatch_book = "Untracked"` with the description stored in `color`.

#### Required Secrets

- Google Sheets service account credentials in `.streamlit/secrets.toml` under `[connections.gsheets]`

---

### `mystery_bundle_counter.py`

Counts mystery bundle quantities in Squarespace orders, broken down by leather type (sides, horsefronts, shoulders).

**Count pending orders (default):**
```bash
python scripts/mystery_bundle_counter.py
```

**Count fulfilled orders:**
```bash
python scripts/mystery_bundle_counter.py --status FULFILLED
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--status` | `PENDING` | Order fulfillment status: `PENDING` or `FULFILLED` |

#### Required Secrets

- `SQUARESPACE_API_KEY`

---

### `leather_weight_calculator.py`

Calculates and stores weight coefficients for leather types, estimates box weights for shipping.

**Interactive mode:**
```bash
python scripts/leather_weight_calculator.py -i
```

**Calculate and store a coefficient:**
```bash
python scripts/leather_weight_calculator.py --calculate-coefficient --name "Horween Chromexcel" --weight 12.5 --sqft 18 --notes "Standard side"
```

**Estimate a box weight:**
```bash
python scripts/leather_weight_calculator.py --estimate-box --name "Horween Chromexcel" --sqft 25
```

**List all stored coefficients:**
```bash
python scripts/leather_weight_calculator.py --list
```

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--calculate-coefficient` | False | Calculate and store a new coefficient |
| `--estimate-box` | False | Estimate box weight using stored coefficient |
| `--list` | False | List all stored coefficients |
| `--name` | None | Leather name |
| `--weight` | None | Bundle weight in lbs |
| `--sqft` | None | Square footage |
| `--notes` | None | Optional notes |
| `-i`, `--interactive` | False | Interactive mode |

#### Storage

Coefficients stored in `config/leather_weight_coefficients.csv`.

---

### `toml_to_json.py`

Simple utility to convert TOML files to JSON. Uses `sys.argv` (no argparse).

```bash
python scripts/toml_to_json.py .streamlit/secrets.toml output.json
```

If output path is omitted, prints JSON to stdout:
```bash
python scripts/toml_to_json.py .streamlit/secrets.toml
```

---

## Streamlit-Only Scripts

These scripts have no CLI entry point. They are imported and called by `app.py`.

### `pending_order_count.py`

Counts pending panels and swatch books from Squarespace orders.

- **Class:** `SquarespacePanelCalculator` - Fetches orders with pagination, parses SKUs, counts products
- **Key method:** `get_product_counts()` - Returns dicts with counts + details by `unique_id`
- **Features:** Missing item flagging, per-order tracking

### `order_payment_matcher.py`

Matches specific Squarespace orders to Stripe/PayPal payment transactions.

- **Class:** `SquarespaceOrderFetcher` - Fetch specific orders by number
- **Key function:** `match_order_batch(order_numbers, ss_api_key, stripe_txns, paypal_txns)` - Returns matched payment source, net amount, fees, write-offs
- **Depends on:** `payment_fetch.py` for transaction data

### `quickbooks_billing_helper.py`

Combines order data + payment matching for manual QuickBooks entry.

- **Class:** `SquarespaceOrderFetcher`
- **Key functions:** `get_billing_data()`, `generate_tab_separated_summary()`, `generate_line_items_table()`
- **Features:** Multiple export formats for different QB entry workflows

### `swatch_book_contents.py`

Generates swatch book reference PDF by scraping the Tannery Row website.

- **Class:** `SwatchBookGenerator` - Crawls category pages, extracts color variants
- **Output:** Page files in `output/swatch_book_pages_{date}/` + combined PDF in `output/swatch_books/`
- **Depends on:** `beautifulsoup4`, `requests`

### `materialbank_method.py`

Imports Material Bank leads into Method CRM. Creates contacts, companies, and follow-up activities.

- **Key functions:** `process_materialbank_import(df, existing_contacts, progress_callback, dry_run)`, `fix_orphaned_contacts()`, `cleanup_activities()`
- **API:** Method CRM REST API
- **Note:** The Method API key is hardcoded at line 16 rather than read from secrets (inconsistent with other scripts)
- **Features:** Dry-run preview, activity due dates (1 week after sample order), duplicate detection, rate-limit retries (3s/60s/60s)

### `email_helper.py`

Internal module for sending IIF files via SMTP/Gmail. Not standalone.

- **Key function:** `send_iif_email(iif_file, report_file, recipient, ...)`
- **Used by:** `squarespace_to_quickbooks.py`

---

## Utilities

### `utils/auth.py`

Streamlit authentication and authorization.

- `check_authentication()` - Main auth gate called at top of `app.py`
- `is_streamlit_cloud()` - Detect deployment environment
- **Auth methods:** Google OAuth (cloud), password + email domain check (fallback), `SKIP_AUTH=true` (local dev)
- **Domains:** `@thetanneryrow.com` auto-approved

### `utils/gsheets_storage.py`

Persistent data storage abstraction. Uses Google Sheets on Streamlit Cloud, falls back to local CSV files for local development.

- `load_import_log()` / `save_import_log()` - Order import tracking
- `load_missing_inventory()` / `save_missing_inventory()` - Out-of-stock tracking
- `load_coefficients()` / `save_coefficients()` - Weight coefficients
- `log_activity()` - Activity audit log
- **Sheet worksheets:** `import_log`, `missing_inventory`, `leather_coefficients`, `activity_log`

### `utils/database.py`

PostgreSQL database utilities for persistent storage. Connects to Supabase.

- `get_connection()` / `get_cursor()` - Context managers for DB access
- `query(sql, params)` - Execute SELECT and return list of dicts
- `execute(sql, params)` - Execute INSERT/UPDATE/DELETE
- `get_product_mapping(product, variant)` - Look up QB item
- `get_unmapped_products()` - Products needing QB items
- `is_order_imported(order_number)` - Check duplicate imports
- `log_order_import(...)` - Record order import
- `get_mapping_stats()` - Summary statistics

---

## Database (Supabase PostgreSQL)

The project uses a Supabase PostgreSQL database for persistent storage. Connection credentials are in `.streamlit/secrets.toml`.

### Tables

| Table | Purpose |
|-------|---------|
| `product_mappings` | Squarespace product → QuickBooks item mappings |
| `qb_items` | QuickBooks item reference list |
| `order_imports` | Tracks which orders have been imported |
| `customer_matches` | Logs customer matching decisions |

### Schema: product_mappings

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `internal_sku` | VARCHAR(100) | Generated SKU code |
| `squarespace_product` | VARCHAR(500) | Product name from SS |
| `squarespace_variant` | VARCHAR(500) | Variant name |
| `squarespace_sku` | VARCHAR(50) | SS SKU code |
| `quickbooks_item` | VARCHAR(500) | Matched QB item name |
| `tannage` | VARCHAR(100) | Parsed tannage |
| `color` | VARCHAR(100) | Parsed color |
| `weight` | VARCHAR(50) | Parsed weight |
| `product_type` | VARCHAR(50) | full_hide, panel, accessory, etc. |
| `needs_qb_item` | BOOLEAN | True if fell back to MISCELLANEOUS |
| `needs_review` | BOOLEAN | True if closest match (weight mismatch) |
| `created_at` | TIMESTAMP | Record creation time |

### Connecting to the Database

**From Python:**
```python
from utils.database import query, get_mapping_stats

# Get all products needing QB items
unmapped = query("SELECT * FROM product_mappings WHERE needs_qb_item = TRUE")

# Get stats
stats = get_mapping_stats()
print(f"Total: {stats['total']}, Exact: {stats['exact_match']}")
```

**Direct connection (psql, DBeaver, etc.):**
- Host: `db.qbidzaweiypqaufdwqcl.supabase.co`
- Port: `5432`
- Database: `postgres`
- User: `postgres`
- Password: See `SUPABASE_DB_PASSWORD` in secrets.toml

**Supabase Dashboard:**
https://supabase.com/dashboard/project/qbidzaweiypqaufdwqcl/editor

### Refreshing Product Mappings

After running `build_sku_mapping.py`, reload the database:

```python
from utils.database import execute, get_cursor
import csv

with get_cursor() as cur:
    cur.execute('TRUNCATE product_mappings RESTART IDENTITY;')
    with open('config/product_mappings.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cur.execute('''INSERT INTO product_mappings (...) VALUES (...)''', (...))
```

Or use the Supabase dashboard to import CSV directly.

---

## Product/SKU Mapping Maintenance

Products from Squarespace must be mapped to QuickBooks item names. The mapping file is `config/sku_mapping.csv`.

### How Matching Works

1. **Parse Squarespace product** into components: Tannage + Color + Weight + Product Type
2. **Search QB items** for matching components (lenient weight matching - prefers higher weight in range)
3. **Fallback** to `MISCELLANOUS LEATHER` for items that don't match (flagged in output for QB update)

### QB Item Naming Conventions

| Product Type | QB Format | Example |
|--------------|-----------|---------|
| Full hide | `{Tannage} {Color} {Weight}` or `*{Color} {Tannage} {Weight}` | `Dublin Black 3.5-4 oz`, `*Black Dublin 4-4.5 oz` |
| Panel | `Panel {Tannage} {Color} {Weight}` | `Panel Dublin Lt Nat 5-6 oz` |
| Double Horsefront | `DHF {Tannage} {Color}` (often no weight) | `DHF Aspen Cognac` |
| Single Horsefront | `SHF {Tannage} {Color}` | `SHF Chrxl Black` |
| Russet Strips | `Horween Russet Horsehide Strips {Roll Type} - {Weight}` | `Horween Russet Horsehide Strips Hard Rolled - 7-9 oz` |
| Sample Book | `Sample Book - {Brand} {Tannage}` | `Sample Book - Horween Dublin` |
| Sports Leather | `Horween {Number} {Type} Leather` | `Horween 8064 Football Leather` |
| Calf Lining | `Glovey {Color} Calf Lining` | `Glovey Black Calf Lining` |
| Bookbinding | `Tusting & Burnett Sokoto Bookbinding - {Color}` | `Tusting & Burnett Sokoto Bookbinding - Chestnut, 2-2.5 oz` |

### Common Abbreviations in QB

| Full Name | QB Abbreviation |
|-----------|-----------------|
| English Tan | English T |
| Olde English | Olde Eng |
| Greener Pastures | Greener P |
| Light Natural | Lt Nat |
| Chromexcel | Chrxl |
| Brown Nut | Nut Brown |
| Midnight Navy | Navy |
| Hard Rolled | HR |
| Soft Rolled | SR |

### Color Equivalents

Some colors match across different naming conventions:

| Squarespace Color | Also Matches |
|-------------------|--------------|
| Dark Brown | Brown, Dk Brown |
| Fun Blue | Blue |
| Midnight Navy | Navy |
| Nut Brown | Brown Nut |

### Weight Normalization

Squarespace uses whole ranges (3-4 oz) but QB items may use half-ounce variants. Matching is **lenient** - prefers higher weight as long as it fits in the SS range:

| Squarespace | QuickBooks Matches (preferred first) |
|-------------|--------------------------------------|
| 3-4 oz | 3.5-4, 3-4, 3-3.5 |
| 4-5 oz | 4.5-5, 4-5, 4-4.5 |
| 5-6 oz | 5.5-6, 5-6, 5-5.5 |
| 4.5-5.5 oz | 4.5-5.5, 4.5-5, 5-5.5 (overlapping ranges OK) |
| 9+ oz | 9 oz and up |

### Known Tannages by Brand

**Horween:** Dublin, Derby, Essex, Chromexcel (Chrxl), Cavalier, Cavalier Chromexcel, Montana, Montana Bison, Predator, Latigo, Illini Latigo, Vermont, Aspen, Krypto, Cypress, Pinnacle, Dearborn, Orion, Legacy, Plainsman, Buckaroo, LaSalle, Glove, Featherlite, Rockford, Yellowstone, Puttman, Russet Horsehide, Horsebutt, Handstained, Chamois, Chromepak, Pioneer Reindeer, Grand Slam

**C.F. Stead:** Waxy Commander, Waxy Mohawk, Waxed Elk, Kudu Waxy, Kudu Classic, Kudu Reverse, Crazy Cow, Doeskin, Suede, Regency Calf, Rambler, Desert Oasis Suede, Janus Calf, Repello

**Walpier/Italian:** Buttero, Baku, Elbamatt, Maine, Margot, Vachetta, Tuscany, Museum, Rocky, Sierra, Fenice, Smoked Matte

**Tempesti:** Elbamatt Liscio, Maine Eco Lux, Baku

**Virgilio:** Pierrot Lux

**Tusting & Burnett:** Mad Dog, Sokoto, Sokoto Bookbinding, Sokoto Dip, Marsh

**Splenda:** Classic (Splenda Classic), Atlanta, BOM, Kansas, Sole Bends

**Arazzo (upholstery):** Alaska, Abilene, Allure, Amalfi, Portsmouth, Boulder, Barbary, Impression, Lucca, Sonoma, Hair-on-Hides

**Onda Verde:** Monroe Calf, Metal Antique, Amalfi Lux, Gunmetal

**Other:** Country Cow, Glovey (lining), Italian Nubuck, Italian Crocco, Italian Crinkle, Italian Softee, Nappa Lamb

### Known Brands

Horween, Tempesti, Walpier/Conceria Walpier, Virgilio, Splenda, Tusting & Burnett, C.F. Stead, Onda Verde, Arazzo, Les Rives, Country Cow, Nappa Lamb

### Product Types Detected

| Type | Detection Pattern | Notes |
|------|-------------------|-------|
| panel | "panel" in name (not mystery) | Matches QB items starting with "Panel" |
| horsefront | "horsefront", "dhf", "shf" | Matches DHF/SHF prefix items |
| strips | "strip" in name | Special handling for Russet, Handstained, Horsebutt |
| sample_book | "swatch", "sample book" | Fuzzy matches to "Sample Book - {Brand} {Tannage}" |
| accessory | tokonole, saphir, ecostick, belt, conditioner, glue | Keyword matching to specific QB items |
| basketball | "basketball" | Matches Horween basketball items |
| football | "football" | Matches Horween football items |
| lining | "lining", "calf lining" | Matches Glovey lining items |
| bookbinding | "bookbinding" | Matches Sokoto Bookbinding items |
| mystery_bundle | "mystery bundle", "mystery leather" | Falls back to MISCELLANEOUS |
| scrap | "scrap" in name | Maps to "Scrap Leather" |
| merchandise | "t-shirt", "tri-blend", "shoe horn", "waxed canvas" | Excluded (non-leather) |
| full_hide | default | Standard tannage/color/weight matching |

### Match Rate by Product Type (3000 orders)

| Product Type | Match Rate | Notes |
|--------------|------------|-------|
| Accessories | 86/86 (100%) | Tokonole, Ecostick, Saphir, Conditioner, Wallets matched |
| Strips | 24/24 (100%) | Russet HR/SR 9+ oz, Handstained, Horsebutt all matched |
| Panels | 155/155 (100%) | Lt Nat abbreviation handled, Cavalier Chrxl panels |
| Horsefronts | 37/37 (100%) | SHF maps to DHF equivalent (half price billing) |
| Full hides | 498/498 (100%) | Direct match or closest weight fallback |
| Sample books | 57/57 (100%) | Brand-specific matching (T&B, Les Rives, Onda Verde) |
| Lining | 5/5 (100%) | Glovey Calf Lining matching |
| Sports | 4/4 (100%) | Basketball (default 5oz), Football matching |
| Bookbinding | 5/5 (100%) | Sokoto Bookbinding (short "Book" and long form) |
| Scrap | 4/4 (100%) | Maps to "Scrap Leather" |
| Merchandise | 0/20 (0%) | T-shirts, shoe horns - excluded from mapping |
| Mystery bundles | 1/17 (6%) | Only "Mystery Leather Panels" needs mapping, rest deprecated |

**Overall: 806/912 (88%) exact match, 21 (2%) closest match (needs review), 49 (5%) MISCELLANEOUS, 36 excluded**

### Match Types

| Type | Percentage | Description |
|------|------------|-------------|
| Exact Match | 88% | All components match (tannage, color, weight, type) |
| Closest Match | 2% | Tannage+color match, weight unavailable - flagged `needs_review=Y` |
| MISCELLANEOUS | 5% | No match found - flagged `needs_qb_item=Y` |
| Excluded | 4% | Previous year sales + merchandise - not in output |

**Closest Match items** are typically Tempesti leathers where QB only has one weight available (e.g., Elbamatt 4.5-5 oz) but Squarespace has a different weight (1.0-1.2mm). These are matched to the available weight and flagged for review.

**MISCELLANEOUS items** are genuine inventory gaps where no QB item exists. These need new QB items created.

### Ignored Items (Excluded from Mapping)

The following are automatically skipped (return None, not included in output CSV):

- **Previous years' mystery bundles** - Holiday sale bundles from prior years are deprecated:
  - Horween Mystery Bundle, Tempesti Mystery Bundle
  - Full Side Mystery Bundle, C.F. Stead Mystery Bundle
  - Horsefront Mystery Bundle (legacy versions)
  - Any mystery bundle that is NOT "Mystery Leather Panels"
- **Gift Card Redemption** - Only occurs for walk-in sales, not online billing
- **Merchandise** - Non-leather products:
  - Tannery Row Cotton T-Shirt, Tri-Blend T-Shirt
  - Highland Cordovan Shoe Horn
  - Red House Waxed Canvas Satchel

**Exception:** "Mystery Leather Panels" IS included and maps to `MISCELLANOUS LEATHER` (needs QB item).

### Special Matching Rules

**Horsefronts (SHF → DHF):** Single horsefronts (SHF) map to the equivalent double horsefront (DHF) item in QuickBooks. Bill at half price. There are no SHF-specific QB items.

**Sample Books by Brand:**
- Horween: `Sample Book - Horween {Tannage}`
- Tempesti: `Sample Book - Tempesti {Tannage}`
- Tusting & Burnett: `Sample Book - T & B {Type}` (Dip Dye, Marsh, Sokoto)
- Les Rives: `Sample Book - Les Rives {Type}` (Techno, Piuma)
- Onda Verde: `Sample Book - Onda Verde {Type}` (Ghiaccio Calf)

**Basketball Leather:** Default weight is 5oz. Maps to `Horween 2003C Basketball Leather`.

**Scrap Boxes:** All scrap products map to `Scrap Leather`.

**Gift Cards:** `Tannery Row Gift Card` has its own mapping. `Gift Card Redemption` is ignored (walk-in sales only).

### Items That Commonly Need QB Updates

From 1000-order analysis, these product patterns fall back to MISCELLANEOUS and need new QB items:

1. **New color/tannage combos** - Country Cow Purple, Pierrot Lux colors, Yellowstone Charcoal
2. **Surprise bundles** - Horween Surprise Side, Horsefront Mystery Bundle
3. **Nappa Lamb variants** - Burgundy, Murano (no QB items exist)
4. **Italian specialty** - Italian Crinkle, Les Rives Gunmetal
5. **Sole leather** - Splenda Sole Bends (different weights)
6. **Miscellaneous** - Crystal Lemongrass, Crazy Cow Coach, Calf Lining (TR Collection)

### Adding New Mappings

Edit `config/sku_mapping.csv` directly. Format: `SquarespaceProductName,QuickBooksItem`

**By product type:**

1. **Leather products** (hides, panels, horsefronts): Usually auto-match if tannage/color/weight are correct
2. **Accessories**: Tokonole, Ecostick, Saphir, Conditioner products auto-match by keyword
3. **Sample books**: Auto-match to "Sample Book - {Brand} {Tannage}" pattern
4. **Mystery bundles**: Map to current year's holiday bucket item or MISCELLANEOUS
5. **Items falling back to MISCELLANEOUS**: Check if QB needs a new item, or add explicit mapping

### Finding Unmapped Products

When running `squarespace_to_quickbooks.py`, unmapped products are written to `output/squarespace/*_UNMAPPED_PRODUCTS.txt`.

For bulk analysis:
```bash
python scripts/build_sku_mapping.py --orders 1000 --show-unmatched
```

Output includes `needs_qb_item` column flagging items that fell back to MISCELLANEOUS LEATHER.

### Analysis Script

`scripts/build_sku_mapping.py` fetches Squarespace orders and attempts to match products to QB items:

```bash
python scripts/build_sku_mapping.py --orders 1000 --qb-items "examples/QB item list Oct 2025.xlsx - Sheet1.csv"
```

Output goes to `config/product_mappings.csv` with columns:
- `internal_sku`, `squarespace_product`, `squarespace_variant`, `squarespace_sku`
- `quickbooks_item`, `tannage`, `color`, `weight`, `product_type`
- `needs_qb_item` (Y if fell back to MISCELLANEOUS - needs new QB item created)
- `needs_review` (Y if closest match used - weight mismatch, verify correct)

---

## Configuration Files

| File | Format | Purpose |
|------|--------|---------|
| `config/sku_mapping.csv` | `SquarespaceProductName,QuickBooksItem` | Product name to QB item mapping (primary) |
| `config/product_mappings.csv` | CSV | Generated mapping from `build_sku_mapping.py` analysis |
| `config/qb_customer_list.csv` | QB export CSV | Existing QB customers for duplicate matching |
| `config/customer_import_log.csv` | CSV | Tracks customers created by previous script runs |
| `config/import_log.csv` | CSV (`order_number,date_imported,iif_file`) | Tracks imported orders to prevent duplicates |
| `config/tool_permissions.csv` | CSV (`email,role,tools,materialbank`) | User access control for Streamlit dashboard |
| `config/materialbank_import_log.csv` | CSV | Material Bank lead import tracking |
| `config/missing_inventory.csv` | CSV (`unique_id`) | Out-of-stock product tracking |
| `config/leather_weight_coefficients.csv` | CSV | Calculated weight coefficients per leather type |
| `examples/customers_backup.csv` | CSV | Sample QB customer export |
| `examples/holiday_sale_mappings.csv` | CSV | Holiday sale product mappings (priority over regular) |

---

## Secrets / Environment

The codebase uses a dual-path system for secrets: tries `streamlit.st.secrets[key]` first, falls back to `os.environ[key]`. This allows the same code to run on Streamlit Cloud (secrets in `.streamlit/secrets.toml`) and locally (environment variables or the same TOML file).

### Required Keys

| Key | Used By | Description |
|-----|---------|-------------|
| `SQUARESPACE_API_KEY` | Most scripts | Squarespace Commerce API bearer token |
| `STRIPE_API_KEY` | `payment_fetch.py`, `order_payment_matcher.py` | Stripe read-only restricted key |
| `PAYPAL_CLIENT_ID` | `payment_fetch.py`, `order_payment_matcher.py` | PayPal OAuth client ID |
| `PAYPAL_CLIENT_SECRET` | `payment_fetch.py`, `order_payment_matcher.py` | PayPal OAuth client secret |
| `METHOD_API_KEY` | `materialbank_method.py` | Method CRM API key (currently hardcoded, not read from secrets) |
| `SUPABASE_DB_PASSWORD` | `utils/database.py` | Supabase PostgreSQL password |

### Optional Keys

| Key | Default | Description |
|-----|---------|-------------|
| `SHIP_FROM_STATE` | `GA` | Affects tax code determination |
| `PAYPAL_MODE` | `live` | `live` or `sandbox` |
| `EMAIL_HOST` | None | SMTP host (e.g., `smtp.gmail.com`) |
| `EMAIL_PORT` | None | SMTP port (e.g., `587`) |
| `EMAIL_USER` | None | SMTP username |
| `EMAIL_PASSWORD` | None | SMTP password (Gmail app password) |
| `SKIP_AUTH` | None | Set to `true` to bypass Streamlit auth (local dev only) |
| `SUPABASE_DB_HOST` | `db.qbidzaweiypqaufdwqcl.supabase.co` | Supabase database host |

### Google Sheets (Streamlit Cloud only)

Configured under `[connections.gsheets]` in `secrets.toml`. Requires a Google service account with access to the target spreadsheet. Used by `utils/gsheets_storage.py` for persistent storage.

---

## Output Locations

| Directory | Contents |
|-----------|----------|
| `output/squarespace/` | IIF files, customer reports, encrypted zips |
| `output/squarespace/archive/` | Previous batch outputs |
| `output/billing/` | Some IIF files generated through Streamlit billing tools |
| `output/swatch_books/` | Generated swatch book PDFs |
| `output/swatch_book_pages_{date}/` | Individual swatch book page files |
| `output/materialbank/` | Material Bank import outputs |
| Current working directory | EOM billing CSVs from `payment_fetch.py` CLI |

---

## Common Workflows

### Daily billing batch
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 13825,13868,13870,13871 --customers config/qb_customer_list.csv --use-ss-invoice-numbers
```
Then import `*_NEW_CUSTOMERS.iif` first, then `*_INVOICES.iif` into QuickBooks.

### Check customer matching without generating invoices
```bash
python scripts/squarespace_to_quickbooks.py --order-numbers 13825,13868 --customers config/qb_customer_list.csv --customers-only
```

### EOM billing report
```bash
python scripts/payment_fetch.py --start-date 2025-01-01 --end-date 2025-01-31
```

### Refreshing the QB customer list
Export from QuickBooks Desktop: Customer Center > Export to CSV. Save to `config/qb_customer_list.csv`.

### Check pending mystery bundles
```bash
python scripts/mystery_bundle_counter.py
```

---

## Streamlit Dashboard

### Running Locally

```bash
streamlit run app.py
```

Set `SKIP_AUTH=true` as an environment variable to bypass authentication in local development. The app auto-grants admin access when running locally.

### Tool Categories

| Category | Tools | Permission Level |
|----------|-------|-----------------|
| Billing & Payments | Payment Fetch, Order Payment Matcher, QuickBooks Billing | admin |
| Order Management | Pending Order Count, Mystery Bundle Counter, Swatch Book Generator | standard |
| Inventory & Shipping | Leather Weight Calculator | standard |
| Customer Management | Material Bank Leads | materialbank (special flag) |
| Admin Tools | Method CRM Admin (fix orphans, cleanup activities) | admin |

### Permissions Model

Controlled by `config/tool_permissions.csv`:

| Role | Access |
|------|--------|
| `admin` | All tools |
| `standard` | Order Management + Inventory & Shipping |
| `custom` | Specific tools listed in `tools` column (semicolon-separated) |
| `none` | No access |

The `materialbank` column (`true`/`false`) independently enables Material Bank Leads regardless of role.

---

## Deployment

### Streamlit Cloud (Production)

Deployed from this repo. Secrets configured in Streamlit Cloud dashboard (mirrors `.streamlit/secrets.toml` structure). Google Sheets used for persistent storage.

### Docker

```bash
docker build -t tr-automation .
docker run -p 8501:8501 -v /path/to/secrets.toml:/app/.streamlit/secrets.toml tr-automation
```

- Base image: `python:3.11-slim`
- Exposes port 8501
- Health check: `curl --fail http://localhost:8501/_stcore/health`
- Entrypoint: `streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true`

### Local Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requires `.streamlit/secrets.toml` with API keys or equivalent environment variables.

---

## Future Plans

### QuickBooks Billing Tool (Streamlit)

The current `quickbooks_billing_helper.py` Streamlit tool has been hidden from the dashboard. It needs to be rebuilt to export an Excel file with line items formatted for direct copy-paste into QuickBooks Desktop Enterprise invoice entry.

**Requirements:**
- Input: Squarespace order numbers (same as current)
- Output: Downloadable `.xlsx` file with columns matching QB Desktop Enterprise invoice line item entry (Item, Description, Qty, Rate, Amount, Tax Code)
- Each order should be a separate sheet or clearly separated section
- Line items should use the QB item names from `config/sku_mapping.csv` mapping (not raw Squarespace product names)
- Include customer name, invoice date, ship-to address, and payment info (Stripe/PayPal match)
- Format should allow selecting all line item rows in Excel and pasting directly into a QB Desktop Enterprise invoice

**Existing code to leverage:**
- `scripts/quickbooks_billing_helper.py` — has `get_billing_data()`, `generate_line_items_table()` (needs rework)
- `scripts/squarespace_to_quickbooks.py` — has SKU mapping and customer matching logic
- `scripts/payment_fetch.py` — Stripe/PayPal transaction fetching
