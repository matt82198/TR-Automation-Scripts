# Product Mapping Guide - No SKU Required!

**Map Squarespace products to QuickBooks items using product names (SKU not needed)**

**NEW: Supports variant mapping for products with multiple attributes (tannage, weight, color)**

## Simple Approach

You don't need SKUs! Just map your Squarespace product names directly to QuickBooks item names.

For products with variants (like leather with different tannage, weight, and color), you can map specific variant combinations to QuickBooks items.

## Mapping File Format

**File:** `sku_mapping.csv` (despite the name, it uses product names now)

```csv
SquarespaceProductName,QuickBooksItem
Horween Dublin Leather Panels,Premium Leather Hide
Brass Hardware Set,Brass Buckle Set
Waxed Thread - Black,Waxed Thread Spool
```

### Columns Explained

**SquarespaceProductName**
- The product name from Squarespace (exactly as it appears)
- Example: "Horween Dublin Leather Panels"

**QuickBooksItem**
- The item name in QuickBooks (must exist in your QB item list)
- Example: "Premium Leather Hide"

**Note:** Pieces will come from the Squarespace API (customizations or variants), not from the mapping file

## How to Set It Up

### Step 1: Get Your Squarespace Product Names

1. Log into Squarespace
2. Go to Commerce > Inventory
3. Note your product names exactly as they appear
4. Example: "Horween Dublin Leather Panels"

### Step 2: Get Your QuickBooks Item Names

1. Open QuickBooks Desktop
2. Lists > Item List
3. Note your item names exactly as they appear
4. Example: "Premium Leather Hide"

### Step 3: Create the Mapping

Edit `sku_mapping.csv`:

```csv
SquarespaceProductName,QuickBooksItem
Horween Dublin Leather Panels,Premium Leather Hide
Horween Chromexcel Leather,Chromexcel Hide
Brass Hardware Set,Brass Buckle Set
Waxed Thread - Black,Waxed Thread Spool
```

**That's it!** No SKUs needed. Pieces will come from your Squarespace product customizations or variants.

## Matching Rules

The script is smart about matching:

### 1. Exact Match (Best)
```csv
Horween Dublin Leather Panels,Premium Leather Hide
```
If Squarespace product is exactly "Horween Dublin Leather Panels" → Uses "Premium Leather Hide"

### 2. With Variants
```csv
Leather Panel - 2ft,Premium Leather Hide - 2ft
```
Handles variants automatically

### 3. Partial Match
If no exact match, the script tries partial matching:
- "Dublin Leather" will match "Horween Dublin Leather Panels"
- Case-insensitive

### 4. No Match
If no mapping found, uses the Squarespace product name as-is (truncated to 31 characters for QB)

## Examples

### Example 1: Simple Product
**Squarespace:** "Premium Wallet"
**Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Premium Wallet,Leather Wallet - Brown
```
**Result:** QuickBooks gets "Leather Wallet - Brown"

### Example 2: Product with Variants
**Squarespace:** Product = "Leather Panel", Variant = "Size: 2ft"

**Mapping Option A - Map base product:**
```csv
SquarespaceProductName,QuickBooksItem
Leather Panel,Premium Leather Hide
```
**Result:** QuickBooks gets "Premium Leather Hide"

**Mapping Option B - Map with variant:**
```csv
SquarespaceProductName,QuickBooksItem
Leather Panel - Size: 2ft,Premium Leather Hide - 2ft
```
**Result:** QuickBooks gets "Premium Leather Hide - 2ft"

### Example 3: Product with Custom Pieces
**Squarespace:** "Leather Scraps" with customization "Number of Pieces: 24"
**Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Leather Scraps,Leather Scraps - Mixed
```
- Order quantity: 1
- Pieces from API: 24 (from customization field)
- **Result:** QuickBooks gets item "Leather Scraps - Mixed" with Quantity 1, Pieces 24

## What You DON'T Need

❌ SKUs in Squarespace
❌ Complex coding
❌ Product IDs
❌ Custom fields

## What If I Don't Create a Mapping?

Script still works! It will use your Squarespace product names directly in QuickBooks.

**Without mapping:**
- Squarespace: "Horween Dublin Leather Panels"
- QuickBooks: "Horween Dublin Leather Panels" (or truncated to 31 chars)
- Pieces: From Squarespace customizations/variants, or defaults to quantity

**With mapping:**
- Squarespace: "Horween Dublin Leather Panels"
- QuickBooks: "Premium Leather Hide" (your choice!)
- Pieces: From Squarespace customizations/variants, or defaults to quantity

## Testing Your Mapping

1. Create `sku_mapping.csv` with a few products
2. Run with one order:
```cmd
python squarespace_to_quickbooks.py --order-numbers 1001
```
3. Check the IIF file - verify QB item names are correct
4. Adjust mapping as needed

## Troubleshooting

**Product not mapping:**
- Check exact spelling in Squarespace vs CSV
- Look for extra spaces
- Try partial name

**Wrong QB item showing:**
- Verify QB item name is exact (case-sensitive in QuickBooks)
- Check for typos in CSV

**Pieces not showing correctly:**
- Check Squarespace customization fields (look for "pieces", "quantity", etc.)
- Check variant options for piece counts (e.g., "12 pieces")
- If neither exists, pieces will default to order quantity

## Real Example

Your Squarespace products:
1. Horween Dublin Leather Panels
2. Horween Chromexcel Leather
3. Brass Hardware Set
4. Waxed Thread - Black

Your QuickBooks items:
1. Premium Leather Hide
2. Chromexcel Hide
3. Brass Buckle Set
4. Waxed Thread Spool

**Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Horween Dublin Leather Panels,Premium Leather Hide
Horween Chromexcel Leather,Chromexcel Hide
Brass Hardware Set,Brass Buckle Set
Waxed Thread - Black,Waxed Thread Spool
```

Done! No SKUs needed. Pieces will come from your Squarespace product customizations.

---

## Advanced: Variant Mapping (Tannage, Color, Weight)

**For products with multiple attributes like leather panels**

If your products have variants with combinations of attributes (base tannage, color, weight/grade), you can map specific variant combinations to different QuickBooks items.

### How Variant Mapping Works

**Pattern:** ProductName - Attribute1 - Attribute2 - Attribute3

**Example:** "Leather Panel - Horween Predator - Steel - 5-6 oz"

### Variant Mapping CSV Format

```csv
SquarespaceProductName,QuickBooksItem
Leather Panel - Horween Predator - Steel - 5-6 oz,Predator Steel 5-6 oz
Leather Panel - Italian Nubuck - French Navy - 3.5-4 oz,Italian Nubuck French Navy
Leather Panel - Horween Shell Cordovan - Natural - Grade S,Cord Natural Grade S
```

### Matching Priority

The script uses intelligent matching with this priority:

1. **Exact variant match** - Full "ProductName - Variant" string
2. **Product name only** - Base product without variants
3. **Partial variant match** - Matches on 2+ variant attributes
4. **Fallback** - Uses Squarespace product + variant as-is

### Example: Leather Products

**Squarespace Product Structure:**
- Product Name: "Leather Panel"
- Variant Options: "Horween Predator - Steel - 5-6 oz"

**Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Leather Panel - Horween Predator - Steel - 5-6 oz,Predator Steel 5-6 oz
Leather Panel - Italian Nubuck - French Navy - 3.5-4 oz,Italian Nubuck French Navy
Leather Panel - Italian Nubuck - School Grey - 3.5-4 oz,Italian Nubuck School Grey
Leather Panel - Italian Nubuck - Taupe - 3.5-4 oz,Italian Nubuck Taupe
Leather Panel - Italian Nubuck - Milk Chocolate - 3.5-4 oz,Italian Nubuck Milk Chocolate
Leather Panel - Horween Shell Cordovan - Natural - Grade S,Cord Natural Grade S
Leather Panel - Horween Shell Cordovan - Bourbon - Grade XS,Cord Bourbon Grade XS
```

**Result in QuickBooks:**
- Order with "Leather Panel" + variant "Horween Predator - Steel - 5-6 oz"
- → Maps to QB item: "Predator Steel 5-6 oz"

### Variant Attribute Pattern

**Common Patterns:**
1. **Base Tannage** - The leather type (e.g., "Horween Predator", "Italian Nubuck", "Horween Shell Cordovan")
2. **Color** - The color variant (e.g., "Steel", "French Navy", "Natural", "Bourbon")
3. **Weight/Grade** - The thickness or grade (e.g., "5-6 oz", "3.5-4 oz", "Grade S", "Grade XS")

### Flexible Matching Examples

**Example 1: Different Separator Formats**

Squarespace sends: "Tannage: Horween Predator, Color: Steel, Weight: 5-6 oz"

The script normalizes this to: "Horween Predator - Steel - 5-6 oz"

Your mapping works with either format!

**Example 2: Partial Matching**

Mapping entry:
```csv
Leather Panel - Italian Nubuck - French Navy - 3.5-4 oz,Italian Nubuck French Navy
```

Will match these Squarespace variants:
- "Italian Nubuck - French Navy - 3.5-4 oz" ✓
- "Color: French Navy, Tannage: Italian Nubuck, Weight: 3.5-4 oz" ✓
- "French Navy Italian Nubuck 3.5-4 oz" ✓

**Example 3: Missing One Attribute**

If Squarespace only sends "Italian Nubuck - French Navy" (no weight), the script will still match based on the 2 matching attributes.

### Setting Up Variant Mappings

**Step 1: Identify Your Variant Pattern**

Look at your Squarespace product variants. Common patterns:
- `Tannage - Color - Weight`
- `Base - Color - Grade`
- `Type - Finish - Thickness`

**Step 2: Export a Sample Order**

Run the script once without mapping to see how variants appear:
```cmd
python squarespace_to_quickbooks.py --order-numbers 1001
```

Check the IIF file description field to see the full variant string.

**Step 3: Create Mapping Entries**

For each variant combination, add a row:
```csv
SquarespaceProductName,QuickBooksItem
ProductName - Variant1 - Variant2 - Variant3,QB Item Name
```

**Step 4: Test and Refine**

Run with one order and verify the mapping:
```cmd
python squarespace_to_quickbooks.py --order-numbers 1001
```

### Mixing Simple and Variant Mappings

You can have both simple product mappings and variant-specific mappings in the same file:

```csv
SquarespaceProductName,QuickBooksItem
Brass Hardware Set,Brass Buckle Set
Waxed Thread - Black,Waxed Thread Spool
Leather Panel - Horween Predator - Steel - 5-6 oz,Predator Steel 5-6 oz
Leather Panel - Italian Nubuck - French Navy - 3.5-4 oz,Italian Nubuck French Navy
```

The script automatically detects which type of mapping to use based on whether the SquarespaceProductName contains " - " separators.

### Troubleshooting Variant Mappings

**Variant not matching:**
- Check the separator pattern (should be " - " with spaces)
- Verify attribute order matches Squarespace
- Try removing common prefixes like "Color:", "Size:", etc.
- Run a test order to see the actual variant string

**Wrong QB item showing:**
- Check for typos in the mapping file
- Ensure attributes are in the correct order
- Verify QuickBooks item name exists in QB

**Partial matches not working:**
- Ensure at least 2 attributes match
- Check that attribute words are spelled exactly
- Try an exact match entry first

### Real-World Example

**Your Squarespace Setup:**
- Product: "Leather Panel"
- Variants: Multiple combinations of tannage, color, weight

**Squarespace Order Example:**
- Customer orders "Leather Panel"
- Selects variant: "Horween Predator - Steel - 5-6 oz"

**Your Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Leather Panel - Horween Predator - Steel - 5-6 oz,Predator Steel 5-6 oz
```

**QuickBooks Invoice Result:**
- Item: "Predator Steel 5-6 oz" ✓
- Description: "Horween Predator - Steel, 5-6 oz" ✓
- Quantity: [from order]
- Pieces: [from customization or quantity]

Perfect match!

---

## Unmapped Products Report

**Automatic tracking of products without mappings**

### What It Does

When you run the import, the script automatically tracks any products that don't have mappings in `sku_mapping.csv`. Instead of silently creating new QuickBooks items, it generates a detailed report.

### Generated Reports

After each import, you'll get:
1. `*_UNMAPPED_PRODUCTS.txt` - Lists all products without mappings (if any)
2. `*_NEW_CUSTOMERS.txt` - Lists all new customers (always generated)

### Unmapped Products Report Format

```
======================================================================
UNMAPPED PRODUCTS - ACTION REQUIRED
======================================================================

Found 3 product(s) without mappings.

These products were included in the IIF file using their Squarespace names.
QuickBooks will CREATE NEW ITEMS for these products.

⚠️  RECOMMENDED ACTION:
   1. Add these mappings to sku_mapping.csv
   2. Re-run the import to use your QuickBooks item names

----------------------------------------------------------------------

UNMAPPED PRODUCTS:

1. Product: Leather Panel
   Variant: Horween Chromexcel - Bourbon - 7-8 oz
   ⚠️  Will create QB item: "Leather Panel - Horween Chr"

   To map this product, add to sku_mapping.csv:
   Leather Panel - Horween Chromexcel - Bourbon - 7-8 oz,YourQuickBooksItemName

----------------------------------------------------------------------
```

### Workflow: Handling Unmapped Products

**Option 1: Import As-Is (Quick)**
1. Run the import: `python squarespace_to_quickbooks.py --fulfilled-today`
2. Review the `_UNMAPPED_PRODUCTS.txt` report
3. Import the IIF file into QuickBooks
4. QuickBooks will create new items with Squarespace names (truncated to 31 characters)
5. Manually rename items in QuickBooks if needed

**Option 2: Add Mappings First (Recommended)**
1. Run the import: `python squarespace_to_quickbooks.py --fulfilled-today`
2. Review the `_UNMAPPED_PRODUCTS.txt` report
3. Add mappings to `sku_mapping.csv` for unmapped products:
   ```csv
   Leather Panel - Horween Chromexcel - Bourbon - 7-8 oz,Chromexcel Bourbon 7-8 oz
   ```
4. Re-run the import
5. Now the IIF file uses your QuickBooks item names!
6. Import to QuickBooks

### Example: First Import with New Variants

**Scenario:** You added a new leather variant to Squarespace

**1. First Run:**
```cmd
python squarespace_to_quickbooks.py --order-numbers 1001
```

**2. Output:**
```
⚠️  WARNING: 1 UNMAPPED PRODUCT(S)
📄 UNMAPPED PRODUCTS REPORT: squarespace_invoice_1001_UNMAPPED_PRODUCTS.txt

These products will create NEW ITEMS in QuickBooks.
Review the report and add mappings to sku_mapping.csv if needed.
```

**3. Check the Report:**
```
1. Product: Leather Panel
   Variant: Horween Shell Cordovan - Navy - Grade A
   ⚠️  Will create QB item: "Leather Panel - Horween She"
```

**4. Add Mapping:**
Edit `sku_mapping.csv`:
```csv
Leather Panel - Horween Shell Cordovan - Navy - Grade A,Shell Cordovan Navy A
```

**5. Re-run:**
```cmd
python squarespace_to_quickbooks.py --order-numbers 1001
```

**6. Result:**
```
✓ All products mapped successfully
```

Now the IIF file uses "Shell Cordovan Navy A" instead of the truncated Squarespace name!

### Why This Matters

**Without Mapping:**
- QB Item Name: "Leather Panel - Horween She" (truncated)
- Hard to read in reports
- Doesn't match your existing item naming convention

**With Mapping:**
- QB Item Name: "Shell Cordovan Navy A"
- Clean, readable
- Matches your existing items
- Easier inventory management

### Daily Automation with Unmapped Products

If running daily automation, unmapped products are automatically tracked:

```cmd
python squarespace_to_quickbooks.py --fulfilled-today
```

**If unmapped products found:**
- Report is generated automatically
- IIF file still created (can be imported)
- Email includes warning about unmapped products (if email configured)
- You can add mappings and re-run the next day

**Best Practice:**
- Review unmapped products report weekly
- Add new mappings as you add new variants in Squarespace
- Keep `sku_mapping.csv` up to date

