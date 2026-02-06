#!/usr/bin/env python3
"""
Migration script to merge existing SKU mapping files into the new unified format.

Combines:
- config/sku_mapping.csv (SquarespaceProductName, QuickBooksItem)
- examples/holiday_sale_mappings.csv (squarespace_product, qb_holiday_item)

Into:
- config/product_mappings.csv (squarespace_product, squarespace_variant, quickbooks_item)

Usage:
    python scripts/migrate_mappings.py
    python scripts/migrate_mappings.py --regular config/sku_mapping.csv --holiday examples/holiday_sale_mappings.csv --output config/product_mappings.csv
    python scripts/migrate_mappings.py --dry-run
"""

import argparse
import csv
import os
import re
from typing import Dict, List, Tuple, Optional


def parse_product_variant(full_name: str) -> Tuple[str, str]:
    """
    Parse a product name that may contain variant information.

    Handles formats like:
    - "Horween • Dublin - Black - 3-4 oz" -> ("Horween • Dublin", "Black - 3-4 oz")
    - "Saphir • Renovateur" -> ("Saphir • Renovateur", "")
    - "Horween Chromexcel® Leather Panels - 1' Panel (12"x12") - Black - 3-4 oz (1.2-1.6 mm)"
      -> ("Horween Chromexcel® Leather Panels - 1' Panel (12\"x12\")", "Black - 3-4 oz (1.2-1.6 mm)")

    The heuristic: Find the last " - " followed by a color/weight pattern.
    """
    full_name = full_name.strip()

    # Products with no variants (no color/weight pattern)
    # These are simple accessories, tools, etc.
    simple_product_patterns = [
        r'^Saphir •',
        r'^Tokonole •',
        r'^Crystal •',
        r'^The Leather Conditioner',
        r'^Intercom Ecostick',
        r'^Leather Scrap Box',
        r'^Coronado •',
        r'Swatch Books',
        r'^Tulliani Belts',
        r'mm\) Cordovan Belt$',
        r'^Horween • Football',
        r'^Horween • Surprise Side',
        r'^Horween • Basketball',
        r'^Arazzo Portsmouth',
        r'^Italian Crinkle',
        r'• Mystery Bundle',
        r'^SALE ',
        r'^Splenda •',  # Splenda holiday items without variants
        r'^Tempesti • Mystery',
        r'Chromexcel® Strips',
        r'Horsehide Strips',
        r'Double Horsefronts',
        r'Single Horsefronts',
        r'^Calf Lining',
        r'^Highland •',
        r'^Tusting & Burnett •',
    ]

    for pattern in simple_product_patterns:
        if re.search(pattern, full_name, re.IGNORECASE):
            return (full_name, "")

    # Pattern for color - weight (e.g., "Black - 3-4 oz")
    # This captures: Color - Weight oz (optional mm suffix)
    color_weight_pattern = r' - ([A-Za-z][A-Za-z0-9# ]*) - (\d+(?:\.\d+)?-\d+(?:\.\d+)?\s*oz(?:\s*\([^)]+\))?)\s*$'
    match = re.search(color_weight_pattern, full_name)
    if match:
        # Found "Color - Weight oz" at the end
        color = match.group(1).strip()
        weight = match.group(2).strip()
        variant = f"{color} - {weight}"
        product = full_name[:match.start()].strip()
        return (product, variant)

    # Pattern for just weight (e.g., "5-6 oz") - rare but possible
    just_weight_pattern = r' - (\d+(?:\.\d+)?-\d+(?:\.\d+)?\s*oz(?:\s*\([^)]+\))?)\s*$'
    match = re.search(just_weight_pattern, full_name)
    if match:
        weight = match.group(1).strip()
        product = full_name[:match.start()].strip()
        return (product, weight)

    # Panels have a special format with size in the middle
    # "Horween Chromexcel® Leather Panels - 1' Panel (12"x12") - Black - 3-4 oz"
    panel_pattern = r'^(.*?Leather Panels - \d+\' Panel \([^)]+\)) - (.+)$'
    match = re.match(panel_pattern, full_name)
    if match:
        product = match.group(1).strip()
        variant = match.group(2).strip()
        return (product, variant)

    # No variant detected
    return (full_name, "")


def load_regular_mappings(csv_file: str) -> List[Dict[str, str]]:
    """Load regular SKU mappings from config/sku_mapping.csv"""
    mappings = []

    if not os.path.exists(csv_file):
        print(f"Warning: Regular mapping file not found: {csv_file}")
        return mappings

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            sq_product = (row.get('SquarespaceProductName') or '').strip()
            qb_item = (row.get('QuickBooksItem') or '').strip()

            # Skip empty lines and comments
            if not sq_product or sq_product.startswith('#'):
                continue

            if sq_product and qb_item:
                product, variant = parse_product_variant(sq_product)
                mappings.append({
                    'squarespace_product': product,
                    'squarespace_variant': variant,
                    'quickbooks_item': qb_item,
                    'source': 'regular'
                })

    return mappings


def load_holiday_mappings(csv_file: str) -> List[Dict[str, str]]:
    """Load holiday sale mappings from examples/holiday_sale_mappings.csv"""
    mappings = []

    if not os.path.exists(csv_file):
        print(f"Warning: Holiday mapping file not found: {csv_file}")
        return mappings

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            sq_product = row.get('squarespace_product', '').strip()
            qb_item = row.get('qb_holiday_item', '').strip()

            if sq_product and qb_item:
                product, variant = parse_product_variant(sq_product)
                mappings.append({
                    'squarespace_product': product,
                    'squarespace_variant': variant,
                    'quickbooks_item': qb_item,
                    'source': 'holiday'
                })

    return mappings


def merge_mappings(regular: List[Dict], holiday: List[Dict]) -> List[Dict]:
    """
    Merge regular and holiday mappings, with holiday taking precedence.

    Returns deduplicated list sorted by product name then variant.
    """
    # Use (product, variant) as key
    merged = {}

    # Load regular first
    for m in regular:
        key = (m['squarespace_product'].lower(), m['squarespace_variant'].lower())
        merged[key] = m.copy()

    # Holiday overwrites regular
    for m in holiday:
        key = (m['squarespace_product'].lower(), m['squarespace_variant'].lower())
        if key in merged:
            # Holiday overrides - keep holiday mapping
            merged[key] = m.copy()
            merged[key]['overridden'] = True
        else:
            merged[key] = m.copy()

    # Sort by product then variant
    result = list(merged.values())
    result.sort(key=lambda x: (x['squarespace_product'].lower(), x['squarespace_variant'].lower()))

    return result


def write_unified_mappings(mappings: List[Dict], output_file: str) -> None:
    """Write merged mappings to the new unified CSV format."""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['squarespace_product', 'squarespace_variant', 'quickbooks_item'])

        for m in mappings:
            writer.writerow([
                m['squarespace_product'],
                m['squarespace_variant'],
                m['quickbooks_item']
            ])


def print_summary(mappings: List[Dict]) -> None:
    """Print migration summary statistics."""
    total = len(mappings)
    with_variant = sum(1 for m in mappings if m['squarespace_variant'])
    without_variant = total - with_variant
    from_regular = sum(1 for m in mappings if m.get('source') == 'regular')
    from_holiday = sum(1 for m in mappings if m.get('source') == 'holiday')
    overridden = sum(1 for m in mappings if m.get('overridden'))

    print("\n=== Migration Summary ===")
    print(f"Total mappings: {total}")
    print(f"  With variant: {with_variant}")
    print(f"  Without variant (defaults): {without_variant}")
    print(f"  From regular file: {from_regular}")
    print(f"  From holiday file: {from_holiday}")
    if overridden:
        print(f"  Overridden by holiday: {overridden}")


def print_sample(mappings: List[Dict], count: int = 10) -> None:
    """Print sample of migrated mappings."""
    print(f"\n=== Sample Mappings (first {count}) ===")
    print(f"{'Product':<50} {'Variant':<30} {'QB Item':<30}")
    print("-" * 110)

    for m in mappings[:count]:
        product = m['squarespace_product'][:48] + '..' if len(m['squarespace_product']) > 50 else m['squarespace_product']
        variant = m['squarespace_variant'][:28] + '..' if len(m['squarespace_variant']) > 30 else m['squarespace_variant']
        qb_item = m['quickbooks_item'][:28] + '..' if len(m['quickbooks_item']) > 30 else m['quickbooks_item']
        print(f"{product:<50} {variant:<30} {qb_item:<30}")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate existing SKU mapping files to unified format'
    )
    parser.add_argument('--regular', type=str, default='config/sku_mapping.csv',
                        help='Regular SKU mapping file (default: config/sku_mapping.csv)')
    parser.add_argument('--holiday', type=str, default='examples/holiday_sale_mappings.csv',
                        help='Holiday sale mapping file (default: examples/holiday_sale_mappings.csv)')
    parser.add_argument('--output', type=str, default='config/product_mappings.csv',
                        help='Output unified mapping file (default: config/product_mappings.csv)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview migration without writing output file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed output including all mappings')

    args = parser.parse_args()

    print(f"Loading regular mappings from: {args.regular}")
    regular_mappings = load_regular_mappings(args.regular)
    print(f"  Loaded {len(regular_mappings)} regular mappings")

    print(f"\nLoading holiday mappings from: {args.holiday}")
    holiday_mappings = load_holiday_mappings(args.holiday)
    print(f"  Loaded {len(holiday_mappings)} holiday mappings")

    print("\nMerging mappings...")
    merged = merge_mappings(regular_mappings, holiday_mappings)

    print_summary(merged)
    print_sample(merged, 15)

    if args.verbose:
        print("\n=== All Mappings ===")
        for m in merged:
            print(f"  {m['squarespace_product']} | {m['squarespace_variant']} -> {m['quickbooks_item']}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would write {len(merged)} mappings to: {args.output}")
    else:
        write_unified_mappings(merged, args.output)
        print(f"\nWrote {len(merged)} mappings to: {args.output}")
        print("\nMigration complete!")
        print("\nNext steps:")
        print("  1. Review the output file for accuracy")
        print("  2. Update squarespace_to_quickbooks.py to use new ProductMapper")
        print("  3. Test with sample orders before removing old files")


if __name__ == '__main__':
    main()
