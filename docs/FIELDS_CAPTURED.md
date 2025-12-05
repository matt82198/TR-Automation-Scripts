# Fields Captured from Squarespace

**Complete breakdown of what data is extracted and how it maps to QuickBooks**

## Invoice Header Fields

| Squarespace Field | QuickBooks Field | Notes |
|-------------------|------------------|-------|
| orderNumber | Invoice # | Unique order ID |
| createdOn | Invoice Date | Formatted as MM/DD/YYYY |
| customerEmail | Customer | Used if no name provided |
| billingAddress.firstName | Customer Name | Combined with last name |
| billingAddress.lastName | Customer Name | Combined with first name |
| grandTotal | Invoice Total | Includes items + shipping + tax |

## Line Item Fields (The Main Fields You Need)

| Squarespace Field | QuickBooks Field | How It's Used |
|-------------------|------------------|---------------|
| **productName** | **Item** | ✅ Mapped via sku_mapping.csv (by product name) |
| **variantOptions** | Item (optional) | Combined with product name for variants |
| **quantity** | Quantity | Number of units ordered |
| **customizations** | **Pieces** | ✅ Extracts "pieces" field |
| **variantOptions** | Pieces (fallback) | Parses "12 pieces" format |
| **unitPricePaid.value** | **Price** | Unit price customer paid |
| **shippingAddress.state** | **Taxable** | ✅ Y/N based on in-state vs out-of-state |
| *(calculated)* | **Pieces** | ✅ Quantity × PiecesPerUnit |

## Customer Fields

| Squarespace Field | QuickBooks Field | Notes |
|-------------------|------------------|-------|
| billingAddress.firstName | Customer First Name | |
| billingAddress.lastName | Customer Last Name | |
| customerEmail | Email | For matching/new customers |
| billingAddress.phone | Phone | For matching/new customers |
| billingAddress.address1 | Address Line 1 | |
| billingAddress.address2 | Address Line 2 | |
| billingAddress.city | City | |
| billingAddress.state | State | |
| billingAddress.postalCode | ZIP | |
| billingAddress.countryCode | Country | |

## Additional Fields

| Squarespace Field | QuickBooks Field | Notes |
|-------------------|------------------|-------|
| shippingTotal.value | Shipping Line Item | Separate line, non-taxable |
| taxTotal.value | Sales Tax Line Item | Separate line |
| fulfillmentStatus | (filter only) | Only FULFILLED orders for daily |
| fulfilledOn | (filter only) | Used for --fulfilled-today |
| shippingAddress.state | Taxable determination | Compared to SHIP_FROM_STATE |
| billingAddress.state | Taxable (fallback) | If no shipping address |

## Field Mapping Examples

### Example 1: Simple Line Item
**Squarespace Order:**
```json
{
  "productName": "Leather Wallet",
  "quantity": 2,
  "unitPricePaid": {"value": 45.00}
}
```

**Product Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Leather Wallet,Premium Wallet - Brown
```

**QuickBooks IIF:**
```
Item: Premium Wallet - Brown
Quantity: 2
Price: $45.00
Taxable: Y (if in-state) or N (if out-of-state)
Pieces: 2
```

### Example 2: Bulk Item with Pieces
**Squarespace Order:**
```json
{
  "productName": "Copper Rivets - 100 pack",
  "quantity": 3,
  "unitPricePaid": {"value": 12.00}
}
```

**Product Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Copper Rivets - 100 pack,Copper Rivets (100 pack)
```

**Note:** If your Squarespace product has a customization field "Number of Pieces" with value "100", the pieces will be extracted from there.

**QuickBooks IIF:**
```
Item: Copper Rivets (100 pack)
Quantity: 3
Price: $12.00
Taxable: Y (if in-state) or N (if out-of-state)
Pieces: 3 (or from customization field if available)
```

### Example 3: Custom Pieces Field
**Squarespace Order:**
```json
{
  "productName": "Leather Scraps",
  "quantity": 1,
  "unitPricePaid": {"value": 25.00},
  "customizations": [
    {"label": "Number of Pieces", "value": "24"}
  ]
}
```

**Product Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Leather Scraps,Leather Scraps - Mixed
```

**QuickBooks IIF:**
```
Item: Leather Scraps - Mixed (from mapping)
Quantity: 1
Price: $25.00
Taxable: Y (if in-state) or N (if out-of-state)
Pieces: 24  (from customization)
```

### Example 4: Variant with Pieces
**Squarespace Order:**
```json
{
  "productName": "Brass Buckles",
  "variantOptions": "12 pieces",
  "quantity": 2,
  "unitPricePaid": {"value": 18.00}
}
```

**Product Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Brass Buckles,Brass Buckles (dozen)
```

**QuickBooks IIF:**
```
Item: Brass Buckles (dozen) (from mapping)
Quantity: 2
Price: $18.00
Taxable: Y (if in-state) or N (if out-of-state)
Pieces: 12  (extracted from variant)
```

### Example 5: Out-of-State Order (Non-Taxable)
**Squarespace Order:**
```json
{
  "productName": "Premium Leather Hide",
  "quantity": 1,
  "unitPricePaid": {"value": 60.00},
  "shippingAddress": {"state": "CA"}
}
```

**Product Mapping:**
```csv
SquarespaceProductName,QuickBooksItem
Premium Leather Hide,Premium Leather Hide
```

**QuickBooks IIF:**
```
Item: Premium Leather Hide
Quantity: 1
Price: $60.00
Taxable: N  (out-of-state - CA, shipped from GA)
Pieces: 1
```

## Complete Invoice Example

**Squarespace Order #1001:**
- Customer: John Smith (john@email.com)
- Date: 2025-01-15
- Shipping to: Georgia (in-state, taxable)

**Line Items:**
1. Premium Leather Hide - Qty 2 @ $60.00
2. Brass Buckles - Qty 1 @ $18.00
3. Waxed Thread - Qty 3 @ $5.00
4. Shipping: $12.00
5. Sales Tax: $9.54

**Generated IIF:**
```
CUST    John Smith    123 Main St    [address]    [email]    [phone]

TRNS    INVOICE    01/15/2025    Accounts Receivable    John Smith    153.54    1001
SPL     INVOICE    01/15/2025    Sales    John Smith    -120.00    2    60.00    Premium Leather Hide    Y    2
SPL     INVOICE    01/15/2025    Sales    John Smith    -18.00     1    18.00    Brass Buckles (dozen)   Y    12
SPL     INVOICE    01/15/2025    Sales    John Smith    -15.00     3    5.00     Waxed Thread            N    3
SPL     INVOICE    01/15/2025    Sales    John Smith    -12.00     1    12.00    Shipping                N    1
SPL     INVOICE    01/15/2025    Sales Tax Payable    John Smith    -9.54    1    9.54    Sales Tax    N    0
ENDTRNS
```

## Summary of Key Fields

✅ **Product Name** - Mapped to QB items via sku_mapping.csv (by name, not SKU)
✅ **Quantity** - Units ordered
✅ **Pieces** - Extracted from customizations/variants or calculated
✅ **Price** - Unit price paid
✅ **Taxable** - Y/N based on customer location (ship-to vs ship-from state)
✅ **Customer** - Smart matching or auto-creation

All the fields you need are now captured correctly!
