"""
Generate intelligent product mappings from Squarespace products to QuickBooks items

Analyzes Squarespace product variants and matches them to QB items based on:
- Leather type (Chromexcel, Essex, Dublin, etc.)
- Color (Black, Brown, Natural, etc.)
- Weight/thickness (3-4 oz, 4-5 oz, etc.)
"""

import csv
import re
from typing import List, Dict, Tuple, Optional


def normalize_weight(weight_str: str) -> str:
    """Normalize weight string for matching"""
    if not weight_str:
        return ""
    # Extract oz pattern
    match = re.search(r'(\d+(?:\.\d+)?)\s*-?\s*(\d+(?:\.\d+)?)\s*oz', weight_str, re.IGNORECASE)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    # Single weight
    match = re.search(r'(\d+(?:\.\d+)?)\s*oz', weight_str, re.IGNORECASE)
    if match:
        return match.group(1)
    return weight_str


def extract_leather_type(product_name: str) -> Optional[str]:
    """Extract leather type from product name"""
    # Map full names to abbreviations used in QB
    type_mapping = {
        'chromexcel': 'chrxl',
        'cxl': 'chrxl',
        'essex': 'essex',
        'dublin': 'dublin',
        'latigo': 'latigo',
        'predator': 'predator',
        'cavalier': 'cavalier',
        'shell cordovan': 'cordovan',
        'cordovan': 'cordovan',
    }

    name_lower = product_name.lower()
    for full_name, abbrev in type_mapping.items():
        if full_name in name_lower:
            return abbrev
    return None


def extract_chromexcel_variant(product_name: str) -> Optional[str]:
    """
    Extract specific Chromexcel variant qualifier from product name.
    Returns the variant name if found, or 'standard' for regular chromexcel.
    """
    name_lower = product_name.lower()

    # Check for specific variants (order matters - check more specific first)
    if 'waxed flesh' in name_lower or 'wf' in name_lower:
        return 'wf'
    if 'beaufort' in name_lower:
        return 'beaufort'
    if 'cavalier' in name_lower:
        return 'cavalier'
    if 'chicago' in name_lower:
        return 'chicago'
    if 'bison' in name_lower:
        return 'bison'
    if 'timber' in name_lower:
        return 'timber'
    if 'carolina brown' in name_lower or 'mill-dyed' in name_lower:
        return 'carolina'
    if 'washed' in name_lower:
        return 'washed'

    # If it contains chromexcel but no qualifier, it's standard Aniline Chromexcel
    if 'chromexcel' in name_lower or 'cxl' in name_lower:
        return 'standard'

    return None


def is_finished_good(product_name: str) -> bool:
    """Check if product is a finished good (wallet, accessory, etc.) vs bulk leather"""
    finished_keywords = [
        'wallet', 'shoe horn', 'card holder', 'note jotter',
        'business card', 'bag', 'apron', 'satchel', 'pouch',
        'keychain', 'belt', 'strap', 'hang tag'
    ]
    name_lower = product_name.lower()
    return any(keyword in name_lower for keyword in finished_keywords)


def parse_squarespace_products(csv_file: str) -> List[Dict]:
    """
    Parse Squarespace products export

    Note: Squarespace exports have one row per variant. The first variant row
    contains the product title, subsequent variant rows have empty titles.
    """
    products = []
    current_product_name = None

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            product_name = row.get('Title', '').strip()
            sku = row.get('SKU', '').strip()

            # Update current product name when we see a new product
            if product_name:
                current_product_name = product_name

            # Skip rows without a current product context or SKU
            if not current_product_name or not sku:
                continue

            # Parse variants
            variants = {}
            for i in range(1, 7):  # Check up to 6 option pairs
                option_name = row.get(f'Option Name {i}', '').strip()
                option_value = row.get(f'Option Value {i}', '').strip()

                if option_name and option_value:
                    variants[option_name.lower()] = option_value

            # Include all variants (even products without variant options)
            products.append({
                'product_name': current_product_name,
                'variants': variants,
                'sku': sku
            })

    return products


def parse_qb_items(csv_file: str) -> List[Dict]:
    """Parse QuickBooks item list"""
    items = []
    skipped_old = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            item_name = row.get('Item', '').strip()
            description = row.get('Description', '').strip()
            active_status = row.get('Active Status', '').strip()

            # Skip old products (items starting with *)
            if item_name.startswith('*'):
                skipped_old += 1
                continue

            # Only include active inventory items
            if item_name and active_status == 'Active':
                items.append({
                    'item_name': item_name,
                    'description': description
                })

    print(f"  Skipped {skipped_old} old products (starting with *)")
    return items


def match_product_to_qb_item(product: Dict, qb_items: List[Dict]) -> Tuple[Optional[str], str, int]:
    """
    Match a Squarespace product+variant to a QB item

    Strategy depends on product type:
    - Finished goods: Match by product name first, then filter by color/weight
    - Bulk leather: Filter by color first, then weight, then article type

    Returns: (qb_item_name, confidence_level, score)
    Confidence levels: HIGH, MEDIUM, LOW, NEEDS_REVIEW
    """
    product_name = product['product_name']
    variants = product['variants']

    # Extract attributes
    color = variants.get('color', '').strip()
    weight = variants.get('weight', '').strip()
    weight_normalized = normalize_weight(weight)

    # Check if this is a finished good
    if is_finished_good(product_name):
        return match_finished_good_by_name(product_name, color, weight_normalized, qb_items)
    else:
        return match_bulk_leather_by_color(product_name, color, weight_normalized, qb_items)


def match_finished_good_by_name(product_name: str, color: str, weight_normalized: str, qb_items: List[Dict]) -> Tuple[Optional[str], str, int]:
    """Match finished goods by product name first, then color"""
    name_lower = product_name.lower()

    # Extract product-specific keywords
    product_keywords = []
    if 'fat herbie' in name_lower:
        product_keywords = ['fat', 'herbie', 'wallet']
    elif 'shoe horn' in name_lower:
        product_keywords = ['shoe', 'horn']
    elif 'note jotter' in name_lower:
        product_keywords = ['note', 'jotter']
    elif 'slip wallet' in name_lower:
        product_keywords = ['slip', 'wallet']
    elif 'card holder' in name_lower or 'business card' in name_lower:
        product_keywords = ['card', 'holder']
    elif 'enforcer' in name_lower:
        product_keywords = ['enforcer']
    elif 'johnny' in name_lower and 'fox' in name_lower:
        product_keywords = ['johnny', 'fox']
    elif 'quickcash' in name_lower or 'quick cash' in name_lower:
        product_keywords = ['quick', 'cash', 'wallet']
    elif 'wallet' in name_lower:
        product_keywords = ['wallet']

    # STEP 1: Filter QB items by product name keywords
    candidates = []
    for qb_item in qb_items:
        item_name_lower = qb_item['item_name'].lower()
        description_lower = qb_item['description'].lower()
        combined = f"{item_name_lower} {description_lower}"

        # Check if all product keywords are present
        if product_keywords and all(keyword in combined for keyword in product_keywords):
            candidates.append(qb_item)

    # If no exact product match, fall back to color-based filtering
    if not candidates:
        return match_bulk_leather_by_color(product_name, color, weight_normalized, qb_items)

    # STEP 2: From product matches, prefer those with matching color
    if color:
        color_matches = [item for item in candidates if color.lower() in (item['item_name'].lower() + ' ' + item['description'].lower())]
        if color_matches:
            candidates = color_matches

    # STEP 3: Pick best match (shortest/most specific name)
    best_match = min(candidates, key=lambda x: len(x['item_name']))

    # Confidence based on whether color matched
    if color and color.lower() in (best_match['item_name'].lower() + ' ' + best_match['description'].lower()):
        confidence = "HIGH"
        score = 25
    else:
        confidence = "MEDIUM"
        score = 15

    return (best_match['item_name'], confidence, score)


def match_bulk_leather_by_color(product_name: str, color: str, weight_normalized: str, qb_items: List[Dict]) -> Tuple[Optional[str], str, int]:
    """Match bulk leather by filtering: color -> weight -> article type"""
    # STEP 1: Filter by COLOR first (exact match)
    candidates = qb_items
    if color:
        color_lower = color.lower()
        color_matches = []
        for qb_item in qb_items:
            item_name_lower = qb_item['item_name'].lower()
            description_lower = qb_item['description'].lower()
            combined = f"{item_name_lower} {description_lower}"

            if color_lower in combined:
                color_matches.append(qb_item)

        if color_matches:
            candidates = color_matches

    # STEP 2: Filter by WEIGHT (exact or close match)
    if weight_normalized and candidates:
        weight_matches = []
        for qb_item in candidates:
            item_name_lower = qb_item['item_name'].lower()
            description_lower = qb_item['description'].lower()
            combined = f"{item_name_lower} {description_lower}"

            # Try exact weight match
            if weight_normalized.lower().replace('-', '') in combined.replace('-', '').replace('.', ''):
                weight_matches.append((qb_item, 'exact'))
            # Try partial weight match (e.g., "4" in "4-5")
            elif any(part in combined for part in weight_normalized.split('-')):
                weight_matches.append((qb_item, 'partial'))

        if weight_matches:
            # Prefer exact matches over partial
            exact_matches = [item for item, match_type in weight_matches if match_type == 'exact']
            if exact_matches:
                candidates = exact_matches
            else:
                candidates = [item for item, _ in weight_matches]

    # STEP 3: Pick best ARTICLE match from remaining candidates
    if not candidates:
        return (None, "NEEDS_REVIEW", 0)

    best_match = None
    best_score = 0

    # Extract key terms from product name for scoring
    name_lower = product_name.lower()

    for qb_item in candidates:
        item_name = qb_item['item_name']
        item_name_lower = item_name.lower()
        description_lower = qb_item['description'].lower()
        combined = f"{item_name_lower} {description_lower}"

        score = 0

        # Check for chromexcel variant matching
        cxl_variant = extract_chromexcel_variant(product_name)
        if cxl_variant:
            qb_variant = None
            if 'wf chrxl' in item_name_lower or 'waxed flesh chrxl' in item_name_lower:
                qb_variant = 'wf'
            elif 'beaufort chrxl' in item_name_lower:
                qb_variant = 'beaufort'
            elif 'cavalier chrxl' in item_name_lower or (item_name_lower.startswith('cavalier') and 'chrxl' in combined):
                qb_variant = 'cavalier'
            elif 'chicago chrxl' in item_name_lower:
                qb_variant = 'chicago'
            elif 'bison chrxl' in item_name_lower:
                qb_variant = 'bison'
            elif 'chrxl' in item_name_lower and not any(qual in item_name_lower for qual in ['beaufort', 'cavalier', 'wf', 'chicago', 'bison', 'timber', 'washed']):
                qb_variant = 'standard'

            if cxl_variant == qb_variant:
                score += 10

        # Check leather type
        leather_type = extract_leather_type(product_name)
        if leather_type and leather_type in combined:
            score += 5

        # Give small bonus for shorter QB item names (likely more specific)
        score += max(0, 10 - len(item_name.split()))

        if score > best_score:
            best_score = score
            best_match = item_name

    # Determine confidence level
    if best_score >= 15:  # Good variant + color + weight match
        confidence = "HIGH"
    elif best_score >= 10:  # Good match with variant or leather type
        confidence = "MEDIUM"
    elif best_match:
        confidence = "LOW"
    else:
        confidence = "NEEDS_REVIEW"

    return (best_match, confidence, best_score)


def generate_mappings(squarespace_csv: str, qb_csv: str, output_csv: str):
    """Generate product mappings with confidence levels"""
    print("Loading Squarespace products...")
    sq_products = parse_squarespace_products(squarespace_csv)
    print(f"  Found {len(sq_products)} products with variants")

    print("\nLoading QuickBooks items...")
    qb_items = parse_qb_items(qb_csv)
    print(f"  Found {len(qb_items)} active QB items (old products excluded)")

    print("\nGenerating mappings for ALL products...")
    mappings = []
    stats = {
        'HIGH': 0,
        'MEDIUM': 0,
        'LOW': 0,
        'NEEDS_REVIEW': 0
    }

    for product in sq_products:
        product_name = product['product_name']
        variants = product['variants']
        sku = product['sku']

        # Build variant string
        variant_parts = []

        # Common order: color, weight (for better readability)
        color = variants.get('color', '')
        weight = variants.get('weight', '')

        if color:
            variant_parts.append(color)
        if weight:
            # Clean up weight display
            variant_parts.append(weight.split('(')[0].strip())

        # Create full Squarespace key
        if variant_parts:
            sq_key = f"{product_name} - {' - '.join(variant_parts)}"
        else:
            # Product without variants (or non-standard variants)
            sq_key = product_name

        # Try to match (always returns a result)
        qb_item, confidence, score = match_product_to_qb_item(product, qb_items)

        stats[confidence] += 1

        if qb_item and confidence in ['HIGH', 'MEDIUM']:
            # Good match - use it
            mappings.append({
                'SquarespaceProductName': sq_key,
                'QuickBooksItem': qb_item,
                'Confidence': confidence,
                'SKU': sku,
                'Score': score
            })
        elif qb_item and confidence == 'LOW':
            # Weak match - flag for review
            mappings.append({
                'SquarespaceProductName': sq_key,
                'QuickBooksItem': f"[{confidence}] {qb_item}",
                'Confidence': confidence,
                'SKU': sku,
                'Score': score
            })
        else:
            # No match or needs review - create suggested name
            leather_type = extract_leather_type(product_name)
            suggested_name = f"{color} {leather_type or 'Leather'} {normalize_weight(weight)}".strip()
            mappings.append({
                'SquarespaceProductName': sq_key,
                'QuickBooksItem': f"[NEEDS_REVIEW] {suggested_name[:30]}",
                'Confidence': 'NEEDS_REVIEW',
                'SKU': sku,
                'Score': score
            })

    # Write mappings to CSV
    print(f"\nWriting mappings to {output_csv}...")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['SquarespaceProductName', 'QuickBooksItem', 'Confidence', 'SKU', 'Score']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mappings)

    # Also write a clean version without confidence column for direct use
    clean_output = output_csv.replace('.csv', '_clean.csv')
    with open(clean_output, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['SquarespaceProductName', 'QuickBooksItem']
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(mappings)

    print(f"\n{'='*60}")
    print(f"SUCCESS! Mapped ALL {len(mappings)} products")
    print(f"{'='*60}")
    print(f"\nCONFIDENCE BREAKDOWN:")
    print(f"  HIGH confidence:        {stats['HIGH']:3d} (use as-is)")
    print(f"  MEDIUM confidence:      {stats['MEDIUM']:3d} (review recommended)")
    print(f"  LOW confidence:         {stats['LOW']:3d} (flagged - verify before use)")
    print(f"  NEEDS_REVIEW:           {stats['NEEDS_REVIEW']:3d} (manual mapping required)")
    print(f"\nFILES GENERATED:")
    print(f"  {output_csv} - Full output with confidence levels")
    print(f"  {clean_output} - Clean version for direct use")
    print(f"\nNEXT STEPS:")
    print(f"  1. Review items marked [LOW] and [NEEDS_REVIEW]")
    print(f"  2. Update QB item names for flagged items")
    print(f"  3. Remove confidence flags: [LOW], [NEEDS_REVIEW]")
    print(f"  4. Copy cleaned mappings to sku_mapping.csv")


if __name__ == "__main__":
    generate_mappings(
        squarespace_csv="examples/products_Nov-14_06-03-09PM.csv",
        qb_csv="examples/QB item list Oct 2025.xlsx - Sheet1.csv",
        output_csv="sku_mapping_generated.csv"
    )
