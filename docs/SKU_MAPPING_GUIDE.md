# SKU Mapping Guide

**Map Squarespace SKUs to QuickBooks items with taxable status and pieces**

## What Gets Captured from Squarespace

For each line item in an order, the script now captures:

1. **SKU** - Squarespace SKU (mapped to QB item)
2. **Item** - QuickBooks item name (from mapping)
3. **Quantity** - Number of units ordered
4. **Pieces** - Extracted from customizations/variants or from mapping
5. **Price** - Unit price paid
6. **Taxable** - Y/N flag for taxable items

## SKU Mapping File

### Location
`sku_mapping.csv` in the script directory

### Format
```csv
SquarespaceSKU,QuickBooksItem,PiecesPerUnit
SQ-LEATHER-001,Premium Leather Hide,1
SQ-HARDWARE-001,Brass Buckle Set,12
SQ-FABRIC-001,Canvas Fabric Roll,1
```

### Columns

**SquarespaceSKU** - The SKU from Squarespace (must match exactly)
**QuickBooksItem** - The item name in QuickBooks (must exist in QB)
**PiecesPerUnit** - Number of pieces per unit (e.g., 12 for a dozen)

**Note:** Taxable status is determined by customer location (ship-to state), not by item. See `SALES_TAX_LOGIC.md`

## How It Works

### 1. SKU Matching
When processing an order, the script:
- Reads the SKU from each line item
- Looks up the SKU in `sku_mapping.csv`
- Uses the mapped QuickBooks item name

### 2. Sales Tax (Location-Based)

Taxable status is determined by comparing:
- Ship-to state (customer's shipping address)
- Ship-from state (your business location)

**In-state orders:** All items taxable (Y)
**Out-of-state orders:** All items non-taxable (N)

See: `SALES_TAX_LOGIC.md` for details

### 3. Pieces Extraction

The script tries to find "pieces" in this order:

**Priority 1: Customizations**
```
If customer entered "24" in a "Pieces" field
→ Uses 24 pieces
```

**Priority 2: Variant Options**
```
If variant is "12 pieces" or "24 pcs"
→ Extracts the number
```

**Priority 3: SKU Mapping**
```
If PiecesPerUnit = 12 and Quantity = 2
→ Calculates 24 pieces
```

**Default:**
```
→ Uses Quantity as pieces
```

### 3. Taxable Status

- **Y** = Item is taxable (sales tax will be calculated by QB)
- **N** = Item is non-taxable (no sales tax)

This is set per-SKU in the mapping file.

## Setting Up Your Mapping

### Step 1: Export Your Squarespace SKUs

1. Go to Squarespace > Commerce > Inventory
2. Export your product list
3. Note the SKUs for each product

### Step 2: Get QuickBooks Item Names

1. Open QuickBooks Desktop
2. Lists > Item List
3. Note the exact item names (must match exactly)

### Step 3: Create Mapping File

Edit `sku_mapping.csv`:

```csv
SquarespaceSKU,QuickBooksItem,PiecesPerUnit
HIDE-PREM-BRN,Premium Brown Hide,1
HIDE-STD-BLK,Standard Black Hide,1
BUCKLE-BRASS-1,Brass Buckle (dozen),12
THREAD-WAX-BLK,Waxed Thread Black,1
HARDWARE-KIT-A,Hardware Kit A,1
```

Note: No "Taxable" column - tax is based on customer location, not item type.

### Step 4: Test

Run with a single order to verify mapping:

```cmd
python squarespace_to_quickbooks.py --order-numbers 1001
```

Check the IIF file - items should use your QB names.

## Examples

### Example 1: Simple 1-to-1 Mapping
```csv
SquarespaceSKU,QuickBooksItem,PiecesPerUnit
WALLET-001,Leather Wallet - Brown,1
```
- SKU "WALLET-001" → QB item "Leather Wallet - Brown"
- 1 piece per unit
- If customer orders 2 → 2 pieces
- Taxable if in-state, non-taxable if out-of-state

### Example 2: Bulk Items (Pieces Per Unit)
```csv
SquarespaceSKU,QuickBooksItem,PiecesPerUnit
RIVET-COPPER,Copper Rivets,100
```
- If customer orders 2 units → 200 pieces
- Shows 2 quantity, 200 pieces in IIF
- Tax status based on customer location

### Example 3: Customer Customization
If customer enters "24" in a "Pieces" customization field:
```
SKU: LEATHER-SCRAP
Mapping: PiecesPerUnit = 1
Customer enters: 24 pieces
→ Uses 24 (overrides mapping)
```

## IIF Output

### What QuickBooks Receives

For each line item:
```
Item: [QB Item from mapping]
Quantity: [Units ordered]
Price: [Unit price]
Taxable: Y or N (based on customer location)
Pieces: [Calculated pieces]
```

### Example IIF Line (In-State Customer)
```
SPL    INVOICE    01/15/2025    Sales    John Smith    -120.00    2    60.00    Premium Leather Hide    Y    2
```

Fields:
- **Item**: Premium Leather Hide (from mapping)
- **Quantity**: 2
- **Price**: $60.00 each
- **Amount**: -$120.00
- **Taxable**: Y (customer in same state)
- **Pieces**: 2

### Example IIF Line (Out-of-State Customer)
```
SPL    INVOICE    01/15/2025    Sales    Jane Doe    -120.00    2    60.00    Premium Leather Hide    N    2
```

Fields:
- **Taxable**: N (customer in different state)
- All other fields same

## Troubleshooting

### "No SKU mapping file found"
- Create `sku_mapping.csv` in script directory
- Or specify custom path: `--sku-mapping path/to/mapping.csv`

### Items Using Product Names Instead of QB Items
- Check SKU in Squarespace matches mapping file exactly
- SKUs are case-sensitive
- Verify no extra spaces in CSV

### Wrong Taxable Status
- Tax is based on customer location, not SKU mapping
- Check SHIP_FROM_STATE environment variable
- See `SALES_TAX_LOGIC.md` for details

### Pieces Not Calculating Correctly
- Check PiecesPerUnit in mapping
- Look for customizations field in Squarespace order
- Check variant options for "pieces" or "pcs"

## Without SKU Mapping

If you don't provide a mapping file:
- ✓ Script still works
- ✓ Uses Squarespace product names
- ✓ All items default to taxable
- ✓ Pieces = Quantity
- ⚠️ Item names might not match QB exactly

## Updating Mappings

1. Edit `sku_mapping.csv`
2. Add new rows for new products
3. Save the file
4. Run script - new mappings will be used immediately

## Advanced: Multiple Mapping Files

For different product lines:

```cmd
python squarespace_to_quickbooks.py --sku-mapping leather_products.csv
python squarespace_to_quickbooks.py --sku-mapping hardware_products.csv
```

## Daily Automation with SKU Mapping

Edit `daily_automation_rdp.bat`:

```batch
python squarespace_to_quickbooks.py --fulfilled-today --sku-mapping sku_mapping.csv
```

The mapping file will be used for all daily imports.
