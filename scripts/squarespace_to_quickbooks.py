import os
import requests
import argparse
import csv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple


def get_secret(key: str, default: str = None) -> str:
    """Get secret from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


# Squarespace API Configuration
SQUARESPACE_API_KEY = get_secret('SQUARESPACE_API_KEY')
SQUARESPACE_API_VERSION = '1.0'
SQUARESPACE_BASE_URL = f'https://api.squarespace.com/{SQUARESPACE_API_VERSION}'

# Sales Tax Configuration - set your business state
SHIP_FROM_STATE = get_secret('SHIP_FROM_STATE', 'GA')  # Default: Georgia

# Email Configuration (optional - for daily automation)
EMAIL_HOST = get_secret('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(get_secret('EMAIL_PORT', '587'))
EMAIL_USER = get_secret('EMAIL_USER')
EMAIL_PASSWORD = get_secret('EMAIL_PASSWORD')
EMAIL_RECIPIENT = get_secret('EMAIL_RECIPIENT', 'matt@thetanneryrow.com')


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Import Squarespace invoices to QuickBooks Desktop - Single, multiple, or batch'
    )
    parser.add_argument('--order-numbers', '--order-number', type=str,
                        default=None, dest='order_numbers',
                        help='Specific order number(s) to import. Comma-separated for multiple: 1001,1002,1003')
    parser.add_argument('--fulfilled-today', action='store_true',
                        help='Fetch orders fulfilled today (for daily automation)')
    parser.add_argument('--start-date', type=str,
                        default=None,
                        help='Start date for batch import (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                        default=None,
                        help='End date for batch import (YYYY-MM-DD)')
    parser.add_argument('--output', type=str,
                        default=None,
                        help='Output IIF filename')
    parser.add_argument('--customers', type=str,
                        default='examples/customers_backup.csv',
                        help='CSV file with existing QuickBooks customers (exported from QB)')
    parser.add_argument('--product-mapping', type=str,
                        default='config/sku_mapping.csv',
                        help='CSV file with Squarespace product to QuickBooks item mapping')
    parser.add_argument('--holiday-mapping', type=str,
                        default='examples/holiday_sale_mappings.csv',
                        help='CSV file with holiday sale product mappings (takes priority over regular mappings)')
    parser.add_argument('--ar-account', type=str,
                        default='Accounts Receivable',
                        help='A/R account name in QuickBooks')
    parser.add_argument('--income-account', type=str,
                        default='Merchandise Sales',
                        help='Income account name in QuickBooks')
    parser.add_argument('--email', type=str,
                        default=None,
                        help='Email address to send IIF file to (requires EMAIL_USER and EMAIL_PASSWORD env vars)')
    parser.add_argument('--use-ss-invoice-numbers', action='store_true',
                        help='Use Squarespace order numbers as QB invoice numbers (default: blank)')
    return parser.parse_args()


def fetch_specific_order(order_number: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific order by order number from Squarespace

    Args:
        order_number: The order number to fetch

    Returns:
        Order dictionary or None if not found
    """
    if not SQUARESPACE_API_KEY:
        print("ERROR: SQUARESPACE_API_KEY environment variable not set")
        return None

    headers = {
        'Authorization': f'Bearer {SQUARESPACE_API_KEY}',
        'User-Agent': 'QuickBooksIntegration/1.0'
    }

    try:
        # NOTE: Squarespace API doesn't support filtering by orderNumber parameter
        # We must fetch orders and search for matching orderNumber
        # Start with recent orders to minimize API calls

        cursor = None
        max_pages = 10  # Limit to prevent infinite loops

        for page in range(max_pages):
            params = {}  # Fetch all orders (API returns most recent first)
            if cursor:
                params['cursor'] = cursor

            response = requests.get(
                f'{SQUARESPACE_BASE_URL}/commerce/orders',
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code == 401:
                print("ERROR: Authentication failed. Check your SQUARESPACE_API_KEY")
                return None
            elif response.status_code == 403:
                print("ERROR: Access denied. Ensure you have Commerce Advanced plan")
                return None

            response.raise_for_status()
            data = response.json()

            orders = data.get('result', [])

            # Search for matching order number in this batch
            for order in orders:
                if str(order.get('orderNumber')) == str(order_number):
                    return order

            # Check if there are more pages
            pagination = data.get('pagination', {})
            cursor = pagination.get('nextPageCursor')
            if not cursor:
                break  # No more pages

        print(f"WARNING: Order #{order_number} not found")
        return None

    except requests.RequestException as e:
        print(f"Error fetching order #{order_number}: {e}")
        return None


def fetch_fulfilled_today_orders() -> List[Dict[str, Any]]:
    """
    Fetch orders that were fulfilled today

    Returns:
        List of order dictionaries
    """
    if not SQUARESPACE_API_KEY:
        print("ERROR: SQUARESPACE_API_KEY environment variable not set")
        return []

    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Fetching orders fulfilled today ({today})...")

    headers = {
        'Authorization': f'Bearer {SQUARESPACE_API_KEY}',
        'User-Agent': 'QuickBooksIntegration/1.0'
    }

    # Fetch orders from the last 7 days, then filter by fulfillment date
    start_dt = datetime.now() - timedelta(days=7)
    end_dt = datetime.now() + timedelta(days=1)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    orders = []
    cursor = None
    page = 1

    while True:
        try:
            params = {
                'modifiedAfter': start_ms,
                'modifiedBefore': end_ms,
                'fulfillmentStatus': 'FULFILLED'
            }

            if cursor:
                params['cursor'] = cursor

            response = requests.get(
                f'{SQUARESPACE_BASE_URL}/commerce/orders',
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code == 401:
                print("ERROR: Authentication failed. Check your SQUARESPACE_API_KEY")
                return []
            elif response.status_code == 403:
                print("ERROR: Access denied. Ensure you have Commerce Advanced plan")
                return []

            response.raise_for_status()
            data = response.json()

            result_orders = data.get('result', [])

            # Filter by today's fulfillment date
            for order in result_orders:
                fulfilled_on = order.get('fulfilledOn', '')
                if fulfilled_on:
                    fulfilled_date = fulfilled_on.split('T')[0]
                    if fulfilled_date == today:
                        orders.append(order)

            # Check for pagination
            pagination = data.get('pagination', {})
            if pagination.get('hasNextPage'):
                cursor = pagination.get('nextPageCursor')
                page += 1
            else:
                break

        except requests.RequestException as e:
            print(f"Error fetching orders: {e}")
            break

    print(f"Found {len(orders)} orders fulfilled today")
    return orders


def fetch_squarespace_orders(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Fetch orders from Squarespace Commerce API

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of order dictionaries
    """
    if not SQUARESPACE_API_KEY:
        print("ERROR: SQUARESPACE_API_KEY environment variable not set")
        print("Set it with: export SQUARESPACE_API_KEY='your_api_key_here'")
        return []

    print(f"Fetching Squarespace orders from {start_date} to {end_date}...")

    headers = {
        'Authorization': f'Bearer {SQUARESPACE_API_KEY}',
        'User-Agent': 'QuickBooksIntegration/1.0'
    }

    # Convert dates to timestamps for API query
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    orders = []
    cursor = None
    page = 1

    while True:
        try:
            params = {
                'modifiedAfter': start_ms,
                'modifiedBefore': end_ms
            }

            if cursor:
                params['cursor'] = cursor

            response = requests.get(
                f'{SQUARESPACE_BASE_URL}/commerce/orders',
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code == 401:
                print("ERROR: Authentication failed. Check your SQUARESPACE_API_KEY")
                return []
            elif response.status_code == 403:
                print("ERROR: Access denied. Ensure you have Commerce Advanced plan")
                print("       Orders API requires Commerce Advanced subscription")
                return []

            response.raise_for_status()
            data = response.json()

            result_orders = data.get('result', [])
            orders.extend(result_orders)

            print(f"  Page {page}: Found {len(result_orders)} orders (Total: {len(orders)})")

            # Check for pagination
            pagination = data.get('pagination', {})
            if pagination.get('hasNextPage'):
                cursor = pagination.get('nextPageCursor')
                page += 1
            else:
                break

        except requests.RequestException as e:
            print(f"Error fetching orders: {e}")
            break

    print(f"Successfully fetched {len(orders)} total orders")
    return orders


def format_date_for_qb(date_str: str) -> str:
    """
    Convert ISO date string to QuickBooks format (MM/DD/YYYY)

    Args:
        date_str: ISO format date string

    Returns:
        Formatted date string
    """
    try:
        # Handle both ISO formats with and without milliseconds
        if 'T' in date_str:
            if '.' in date_str:
                dt = datetime.strptime(date_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')
            else:
                dt = datetime.strptime(date_str.split('+')[0].split('Z')[0], '%Y-%m-%dT%H:%M:%S')
        else:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%m/%d/%Y')
    except Exception as e:
        print(f"Warning: Could not parse date {date_str}: {e}")
        return datetime.now().strftime('%m/%d/%Y')


def sanitize_customer_name(name: str) -> str:
    """Clean customer name for QuickBooks - removes problematic characters"""
    if not name:
        return "Guest Customer"
    # Remove colons and other QB-problematic characters
    name = name.replace(':', '').replace('\t', ' ').replace('\n', ' ')
    # Limit length to 41 characters (QB limit)
    return name[:41].strip()


def normalize_for_matching(text: str) -> str:
    """Normalize text for fuzzy matching - lowercase, remove special chars"""
    if not text:
        return ""
    return ''.join(c.lower() for c in text if c.isalnum())


class ProductMapper:
    """Maps Squarespace products to QuickBooks items supporting variants (tannage, color, weight)"""

    # Default path for holiday mappings (auto-loaded if exists)
    DEFAULT_HOLIDAY_MAPPING = 'examples/holiday_sale_mappings.csv'

    # Patterns that indicate a holiday/sale item (case-insensitive)
    HOLIDAY_ITEM_PATTERNS = [
        'mystery bundle',
        'sale ',
        'holiday',
        'margot fog',  # Virgilio Margot Fog holiday sale items
        'puttman',  # Horween Puttman holiday sale
        'chromexcel single horsefronts',  # Horween Chromexcel SHF holiday sale
    ]

    def __init__(self):
        self.product_map = {}  # product_name -> qb_item (simple mappings)
        self.variant_map = {}  # "product - variant" -> qb_item (variant-specific mappings)
        self.holiday_map = {}  # product_name -> qb_holiday_item (holiday sale mappings - checked first)
        self.unmapped_products = []  # Track products that couldn't be mapped (for reporting)

    def _is_holiday_item(self, product_name: str) -> bool:
        """
        Detect if a product is a holiday/sale item based on name patterns.
        These items should use holiday mappings when available.
        """
        name_lower = product_name.lower()
        for pattern in self.HOLIDAY_ITEM_PATTERNS:
            if pattern in name_lower:
                return True
        return False

    def load_product_mapping(self, csv_file: str) -> None:
        """
        Load product mapping from CSV file
        Expected columns: SquarespaceProductName, QuickBooksItem
        Optional format: SquarespaceProductName can include variants like:
          "Leather Panel - Horween Predator - Steel - 5-6 oz"
        """
        if not os.path.exists(csv_file):
            print(f"Warning: Product mapping file not found: {csv_file}")
            print("         Items will use Squarespace product names as-is")
            return

        print(f"Loading product mapping from: {csv_file}")

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    sq_product = row.get('SquarespaceProductName') or ''
                    qb_item = row.get('QuickBooksItem') or ''

                    # Skip empty lines and comment lines
                    if not sq_product or sq_product.startswith('#'):
                        continue

                    sq_product = sq_product.strip()
                    qb_item = qb_item.strip()

                    if sq_product and qb_item:
                        # Check if this is a variant-specific mapping (contains " - ")
                        if ' - ' in sq_product:
                            # Store as variant mapping with full key
                            self.variant_map[sq_product.lower()] = {
                                'qb_item': qb_item,
                                'original_name': sq_product
                            }
                        else:
                            # Store as simple product mapping
                            self.product_map[sq_product.lower()] = {
                                'qb_item': qb_item,
                                'original_name': sq_product
                            }

            print(f"  Loaded {len(self.product_map)} product mappings")
            print(f"  Loaded {len(self.variant_map)} variant-specific mappings")

        except Exception as e:
            print(f"Warning: Could not load product mapping: {e}")

    def load_holiday_mapping(self, csv_file: str) -> None:
        """
        Load holiday sale product mapping from CSV file
        Expected columns: squarespace_product, qb_holiday_item
        Holiday mappings take priority over regular mappings
        """
        if not csv_file:
            return

        if not os.path.exists(csv_file):
            print(f"Warning: Holiday mapping file not found: {csv_file}")
            return

        print(f"Loading holiday sale mappings from: {csv_file}")

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    sq_product = row.get('squarespace_product', '').strip()
                    qb_item = row.get('qb_holiday_item', '').strip()

                    if sq_product and qb_item:
                        # Store as simple product mapping (holiday mappings are product-level only)
                        self.holiday_map[sq_product.lower()] = {
                            'qb_item': qb_item,
                            'original_name': sq_product
                        }

            print(f"  Loaded {len(self.holiday_map)} holiday sale mappings")

        except Exception as e:
            print(f"Warning: Could not load holiday mapping: {e}")

    def _normalize_variant(self, variant) -> str:
        """
        Normalize variant string for matching
        Removes extra spaces, standardizes separators, strips mm measurements
        """
        if not variant:
            return ""
        # Handle list of variants
        if isinstance(variant, list):
            variant = ' - '.join(str(v) for v in variant if v)
        variant = str(variant)
        # Normalize separators and spacing
        normalized = variant.replace(',', ' -').replace('  ', ' ').strip()
        # Remove common prefixes like "Color:", "Size:", etc.
        import re
        normalized = re.sub(r'(Color|Size|Weight|Tannage|Grade):\s*', '', normalized, flags=re.IGNORECASE)
        # Remove mm measurements in parentheses (e.g., "(1.2-1.6 mm)" or "(2.0 – 2.4 mm)")
        # This ensures "English Tan - 5-6 oz (2.0 – 2.4 mm)" matches "English Tan - 5-6 oz"
        normalized = re.sub(r'\s*\([^)]*mm[^)]*\)', '', normalized, flags=re.IGNORECASE).strip()
        return normalized

    def _build_dynamic_qb_item(self, product_name: str, variant: str) -> Optional[str]:
        """
        Dynamically build a QB item name for full hide products based on tannage + color + weight.
        Format: "{Tannage} {Color} {Weight}" e.g., "Derby Black 3.5-4 oz"

        Returns None if product doesn't match full hide pattern.
        """
        import re

        # Known tannage types that follow the "{Tannage} {Color} {Weight}" pattern
        tannage_patterns = {
            'derby': 'Derby',
            'dublin': 'Dublin',
            'essex': 'Essex',
            'chromexcel': 'Chromexcel',
            'cavalier': 'Cavalier',
            'montana': 'Montana',
            'predator': 'Predator',
            'latigo': 'Latigo',
            'krypto': 'Krypto',
            'aspen': 'Aspen',
        }

        # Check if product name matches a known tannage
        product_lower = product_name.lower()
        detected_tannage = None
        for key, tannage_name in tannage_patterns.items():
            if key in product_lower:
                detected_tannage = tannage_name
                break

        if not detected_tannage or not variant:
            return None

        # Skip panels - they have their own mappings
        if 'panel' in product_lower:
            return None

        # Parse variant to extract color and weight
        # Expected format: "Black - 3-4 oz (1.2-1.6 mm)" or "Color: Black - Weight: 3-4 oz"
        variant_normalized = self._normalize_variant(variant)

        # Extract weight - look for patterns like "3-4 oz", "3.5-4 oz", "5-6 oz"
        weight_match = re.search(r'(\d+(?:\.\d+)?-\d+(?:\.\d+)?)\s*oz', variant_normalized, re.IGNORECASE)
        if not weight_match:
            return None

        weight_raw = weight_match.group(1)

        # Normalize weight to QB format (e.g., "3-4" -> "3.5-4")
        weight_parts = weight_raw.split('-')
        if len(weight_parts) == 2:
            low = weight_parts[0].strip()
            high = weight_parts[1].strip()
            # QB often uses "3.5-4 oz" instead of "3-4 oz"
            # Map common variations
            weight_mappings = {
                '3-4': '3.5-4',
                '4-5': '4-5',
                '5-6': '5-6',
                '6-7': '6-7',
                '7-8': '7-8',
                '8-9': '8-9',
                '9-10': '9-10',
                '3-3.5': '3-3.5',
                '3.5-4': '3.5-4',
                '4.5-5': '4.5-5',
                '5.5-6': '5.5-6',
            }
            weight_key = f"{low}-{high}"
            weight = weight_mappings.get(weight_key, weight_key)
        else:
            weight = weight_raw

        # Extract color - everything before the weight pattern
        color_part = re.sub(r'\d+(?:\.\d+)?-\d+(?:\.\d+)?\s*oz.*', '', variant_normalized, flags=re.IGNORECASE).strip()
        color_part = color_part.rstrip(' -').strip()

        if not color_part:
            return None

        # Title case the color
        color = ' '.join(word.capitalize() for word in color_part.split())

        # Build the QB item name
        qb_item = f"{detected_tannage} {color} {weight} oz"

        return qb_item

    def get_mapping(self, product_name: str, variant: str = '', unit_price: float = None) -> str:
        """
        Get QuickBooks item name for a Squarespace product with smart variant matching

        Matching priority:
        0. Holiday sale mapping (ONLY for holiday/sale items like mystery bundles - auto-detected)
        1. Exact match on "ProductName - Variant" (full variant string)
        2. Exact match on product name only
        3. Partial match on variant attributes
        4. Fallback to product name + variant (tracked in unmapped_products for reporting)

        Args:
            product_name: Squarespace product name
            variant: Optional variant (e.g., "Horween Predator - Steel - 5-6 oz")
            unit_price: Optional unit price to help determine if it's a sale item

        Returns:
            QuickBooks item name (always returns a value, but tracks unmapped products)
        """
        lookup_key = product_name.strip().lower()

        # PRIORITY 0: Check holiday sale mappings - ONLY for items that are holiday/sale items
        # Uses intelligent detection: mystery bundles, items with "SALE" prefix, etc.
        if lookup_key in self.holiday_map and self._is_holiday_item(product_name):
            # For holiday items, use holiday mapping
            # Price check: if price >= $200, it's likely NOT a sale item (regular price)
            # EXCEPTION: Mystery bundles are ALWAYS sale items regardless of price
            is_mystery_bundle = 'mystery bundle' in lookup_key
            if unit_price is not None and unit_price >= 200 and not is_mystery_bundle:
                pass  # Skip holiday mapping, continue to regular mappings
            else:
                return self.holiday_map[lookup_key]['qb_item']

        # PRIORITY 1: Try exact match with full variant string
        if variant:
            variant_normalized = self._normalize_variant(variant)

            # Try "ProductName - Variant" combination
            combined_key = f"{product_name} - {variant_normalized}".strip().lower()
            if combined_key in self.variant_map:
                return self.variant_map[combined_key]['qb_item']

            # Try just the variant part (for cases where product name is generic)
            variant_key = variant_normalized.lower()
            for mapped_variant, mapping in self.variant_map.items():
                # Check if the variant attributes match
                if variant_key in mapped_variant or mapped_variant.split(' - ', 1)[-1] == variant_key:
                    return mapping['qb_item']

        # PRIORITY 2: Try exact match on product name only
        if lookup_key in self.product_map:
            return self.product_map[lookup_key]['qb_item']

        # PRIORITY 2.5: Check if product name itself is in variant_map
        # This handles cases where Squarespace product names include variant info
        # (e.g., "Horween • Dearborn - Havana - 3-4 oz" with no separate variant)
        if lookup_key in self.variant_map:
            return self.variant_map[lookup_key]['qb_item']

        # PRIORITY 3: Try partial matching on variant mappings
        # IMPORTANT: Must also match product name to avoid cross-product matches
        if variant:
            variant_normalized = self._normalize_variant(variant).lower()
            best_match = None
            best_match_score = 0

            for mapped_variant, mapping in self.variant_map.items():
                parts = mapped_variant.split(' - ', 1)
                if len(parts) > 1:
                    mapped_product_part = parts[0].lower()
                    mapped_variant_part = parts[1].lower()

                    # Check if product name matches (must have significant overlap)
                    product_words = set(lookup_key.split())
                    mapped_product_words = set(mapped_product_part.split())
                    product_overlap = len(product_words & mapped_product_words)

                    # Skip if product names don't match at all
                    if product_overlap == 0:
                        continue

                    # Count matching variant attributes
                    variant_words = set(variant_normalized.split())
                    mapped_variant_words = set(mapped_variant_part.split())
                    variant_matches = len(variant_words & mapped_variant_words)

                    # Score = product overlap + variant matches
                    score = product_overlap + variant_matches

                    if score > best_match_score:
                        best_match_score = score
                        best_match = mapping['qb_item']

            if best_match and best_match_score >= 3:  # Need product + variant matches
                return best_match

        # PRIORITY 4: Try partial matching on product name
        for mapped_name, mapping in self.product_map.items():
            if mapped_name in lookup_key or lookup_key in mapped_name:
                return mapping['qb_item']

        # PRIORITY 5: Try matching variant alone against product_map (e.g., "Clear" -> "Tokonole Clear 120g")
        if variant:
            variant_key = variant.strip().lower()
            if variant_key in self.product_map:
                return self.product_map[variant_key]['qb_item']

        # PRIORITY 6: Try dynamic QB item name builder for full hides
        # This builds names like "Derby Black 3.5-4 oz" from product + variant
        dynamic_qb_item = self._build_dynamic_qb_item(product_name, variant)
        if dynamic_qb_item:
            return dynamic_qb_item

        # NO MAPPING FOUND - Track for reporting and use fallback
        # Track unmapped product for reporting
        unmapped_entry = {
            'product_name': product_name,
            'variant': variant,
            'suggested_key': f"{product_name} - {variant}" if variant else product_name
        }
        # Avoid duplicates
        if unmapped_entry not in self.unmapped_products:
            self.unmapped_products.append(unmapped_entry)

        # FALLBACK: Use product name + variant as-is
        display_name = product_name
        if variant:
            display_name = f"{product_name} - {variant}"
        return display_name[:31]  # QB item name limit


class CustomerMatcher:
    """Smart customer matching to avoid duplicates"""

    def __init__(self):
        self.customers = []  # List of existing customer records
        self.email_map = {}  # email -> customer_name
        self.phone_map = {}  # phone -> customer_name
        self.lastname_map = {}  # lastname -> [customer_names]
        self.firstname_map = {}  # firstname -> [customer_names]

    def load_existing_customers(self, csv_file: str) -> None:
        """
        Load existing customers from QuickBooks export
        Expected columns: Customer, Main Email, Main Phone, First Name, Last Name, etc.
        """
        if not os.path.exists(csv_file):
            print(f"Warning: Customer file not found: {csv_file}")
            return

        print(f"Loading existing customers from: {csv_file}")

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # QB exports use "Customer" column
                    name = row.get('Customer', '').strip() or row.get('Name', '').strip()
                    if not name:
                        continue

                    customer_record = {'name': name}

                    # Email mapping - QB exports use "Main Email"
                    email = row.get('Main Email', '').strip().lower() or row.get('Email', '').strip().lower()
                    if email:
                        self.email_map[email] = name
                        customer_record['email'] = email

                    # Phone mapping - QB exports use "Main Phone"
                    phone = row.get('Main Phone', '') or row.get('Phone', '') or row.get('Phone Number', '')
                    phone_normalized = normalize_for_matching(phone)
                    if phone_normalized:
                        self.phone_map[phone_normalized] = name
                        customer_record['phone'] = phone_normalized

                    # First name mapping
                    first_name = row.get('First Name', '').strip()
                    if not first_name:
                        # Try to extract from customer name
                        contact = row.get('Contact', '') or row.get('Full Name', '') or name
                        if ' ' in contact:
                            first_name = contact.split()[0]

                    if first_name:
                        first_name_lower = first_name.lower()
                        if first_name_lower not in self.firstname_map:
                            self.firstname_map[first_name_lower] = []
                        self.firstname_map[first_name_lower].append(name)
                        customer_record['first_name'] = first_name

                    # Last name mapping
                    last_name = row.get('Last Name', '').strip()
                    if not last_name:
                        # Try to extract from customer name
                        contact = row.get('Contact', '') or row.get('Full Name', '') or name
                        if ' ' in contact:
                            last_name = contact.split()[-1]

                    if last_name:
                        last_name_lower = last_name.lower()
                        if last_name_lower not in self.lastname_map:
                            self.lastname_map[last_name_lower] = []
                        self.lastname_map[last_name_lower].append(name)
                        customer_record['last_name'] = last_name

                    self.customers.append(customer_record)

            print(f"  Loaded {len(self.customers)} existing customers")
            print(f"  Email lookups: {len(self.email_map)}")
            print(f"  Phone lookups: {len(self.phone_map)}")
            print(f"  First name index: {len(self.firstname_map)} unique first names")
            print(f"  Last name index: {len(self.lastname_map)} unique last names")

        except Exception as e:
            print(f"Warning: Could not load customers: {e}")

    def find_match(self, email: str, phone: str, first_name: str, last_name: str) -> Optional[str]:
        """
        Try to find existing customer by (in order of reliability):
        1. Email (exact match) - most reliable
        2. Phone (normalized match) - very reliable
        3. First + Last name (partial match required) - requires BOTH to match

        Returns: Existing customer name or None (create new customer if None)
        """
        # 1. Try email match (most reliable)
        if email:
            email_lower = email.strip().lower()
            if email_lower in self.email_map:
                return self.email_map[email_lower]

        # 2. Try phone match (very reliable)
        if phone:
            phone_normalized = normalize_for_matching(phone)
            if phone_normalized and phone_normalized in self.phone_map:
                return self.phone_map[phone_normalized]

        # 3. Try name match - MUST have both first AND last name match
        # Last name alone is NOT sufficient (too many false positives)
        if first_name and last_name:
            first_normalized = normalize_for_matching(first_name)
            last_name_lower = last_name.strip().lower()

            if last_name_lower in self.lastname_map:
                candidates = self.lastname_map[last_name_lower]

                for candidate in candidates:
                    candidate_normalized = normalize_for_matching(candidate)
                    # Check if first name (or partial) appears in the customer name
                    # This handles "Robert" matching "Robert F Tanner" or "Bob" matching "Robert Bob Smith"
                    if first_normalized and len(first_normalized) >= 2:
                        # Check for partial first name match (at least 2 chars)
                        if first_normalized in candidate_normalized:
                            return candidate
                        # Also check if candidate's first part matches our first name
                        candidate_parts = candidate.split()
                        if candidate_parts:
                            candidate_first = normalize_for_matching(candidate_parts[0])
                            if candidate_first and first_normalized in candidate_first:
                                return candidate
                            # Check middle name too if exists
                            if len(candidate_parts) > 2:
                                candidate_middle = normalize_for_matching(candidate_parts[1])
                                if candidate_middle and first_normalized in candidate_middle:
                                    return candidate

        # No match found - will create new customer
        return None


def is_in_state_order(order: Dict[str, Any], ship_from_state: str) -> bool:
    """
    Determine if order is in-state (taxable) or out-of-state (non-taxable)

    Args:
        order: Order dictionary from Squarespace
        ship_from_state: State where business is located (e.g., 'GA')

    Returns:
        True if in-state (charge tax), False if out-of-state (no tax)
    """
    # Get shipping address state (handle None explicitly)
    shipping_address = order.get('shippingAddress') or {}
    ship_to_state = (shipping_address.get('state', '') or '').strip().upper()

    # Normalize ship_from_state
    ship_from_normalized = ship_from_state.strip().upper()

    # If no shipping address, try billing address
    if not ship_to_state:
        billing_address = order.get('billingAddress') or {}
        ship_to_state = (billing_address.get('state', '') or '').strip().upper()

    # Compare states
    return ship_to_state == ship_from_normalized


def parse_variant_options(variant_options) -> str:
    """
    Parse Squarespace variant options into a formatted string

    Input: [{'optionName': 'Color', 'value': 'Black'}, {'optionName': 'Size', 'value': "1' Panel"}, ...]
    Output: "Black - 1' Panel (12\"x12\") - 3-4 oz (1.2-1.6 mm)"
    """
    if not variant_options:
        return ''

    if isinstance(variant_options, str):
        # Normalize curly quotes to straight quotes
        variant_options = variant_options.replace('\u2018', "'").replace('\u2019', "'")  # Single quotes
        variant_options = variant_options.replace('\u201c', '"').replace('\u201d', '"')  # Double quotes
        return variant_options

    if isinstance(variant_options, list):
        # Extract just the values
        values = []
        for option in variant_options:
            if isinstance(option, dict) and 'value' in option:
                value = str(option['value'])
                # Normalize curly quotes to straight quotes
                value = value.replace('\u2018', "'").replace('\u2019', "'")  # Single quotes
                value = value.replace('\u201c', '"').replace('\u201d', '"')  # Double quotes
                values.append(value)
        return ' - '.join(values)

    return str(variant_options)


def extract_pieces_from_customizations(item: Dict[str, Any]) -> int:
    """
    Extract pieces from line item customizations or variants

    Args:
        item: Line item from Squarespace order

    Returns:
        Number of pieces (defaults to quantity if not found)
    """
    # Check customizations for "pieces" field
    customizations = item.get('customizations') or []
    for custom in customizations:
        label = custom.get('label', '').lower()
        value = custom.get('value', '')
        if 'piece' in label or 'pcs' in label or 'qty' in label:
            try:
                return int(value)
            except:
                pass

    # Check variant options for pieces
    variant_options = item.get('variantOptions') or ''
    if isinstance(variant_options, list):
        variant_options = ' '.join(str(v) for v in variant_options if v)
    variant_options = str(variant_options)
    if variant_options:
        # Look for patterns like "12 pieces", "24 pcs", "10 sides", etc.
        import re
        match = re.search(r'(\d+)\s*(?:piece|pcs|pc|side)', variant_options.lower())
        if match:
            return int(match.group(1))

    # Default to quantity if no pieces found
    return item.get('quantity', 1)


def log_imported_order(order_number: str, iif_filename: str, log_file: str = 'config/import_log.csv') -> None:
    """
    Log an imported order to prevent duplicate imports

    Args:
        order_number: Squarespace order number
        iif_filename: IIF file that contains this order
        log_file: CSV log file path
    """
    import_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Create log file with header if it doesn't exist
    file_exists = os.path.exists(log_file)

    with open(log_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['order_number', 'date_imported', 'iif_file'])
        writer.writerow([order_number, import_date, iif_filename])


def check_already_imported(order_numbers: List[str], log_file: str = 'config/import_log.csv') -> Tuple[List[str], List[str]]:
    """
    Check which orders have already been imported

    Args:
        order_numbers: List of order numbers to check
        log_file: CSV log file path

    Returns:
        Tuple of (new_orders, already_imported)
    """
    if not os.path.exists(log_file):
        return order_numbers, []

    imported_orders = set()
    with open(log_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            imported_orders.add(row['order_number'])

    new_orders = [num for num in order_numbers if num not in imported_orders]
    already_imported = [num for num in order_numbers if num in imported_orders]

    return new_orders, already_imported


def generate_iif_file(orders: List[Dict[str, Any]], filename: str, ar_account: str, income_account: str,
                      customer_matcher: Optional[CustomerMatcher] = None,
                      sku_mapper: Optional[ProductMapper] = None,
                      use_ss_invoice_numbers: bool = False) -> None:
    """
    Generate IIF files for bulk invoice import to QuickBooks Desktop

    Creates TWO files:
    1. *_NEW_CUSTOMERS.iif - Only new customer records (import first)
    2. *_INVOICES.iif - Only invoices (import after customers)

    Captures: Product-mapped items, Quantity, Pieces, Price, Ship To address

    Args:
        orders: List of order dictionaries from Squarespace
        filename: Output IIF filename base
        ar_account: Accounts Receivable account name
        income_account: Sales/Income account name
        customer_matcher: Optional customer matcher for smart matching
        sku_mapper: Optional product mapper for item mapping
        use_ss_invoice_numbers: If True, use Squarespace order numbers as QB invoice numbers (default: False/blank)
    """
    if not orders:
        print("No orders to export")
        return

    print(f"\nGenerating IIF files...")

    # Show invoice numbering mode
    if use_ss_invoice_numbers:
        print(f"  Invoice numbering: Using Squarespace order numbers with 'SS-' prefix (e.g., SS-1001)")
    else:
        print(f"  Invoice numbering: Blank (manual numbering required after import)")

    # Track customers for reporting
    matched_customers = set()
    new_customers = set()
    customer_records = {}  # customer_name -> customer_info (with tax code)
    invoice_count = 0

    # First pass: collect all unique customers with their info
    for order in orders:
        # Skip canceled orders
        if order.get('fulfillmentStatus') == 'CANCELED':
            continue

        # Get customer details for matching
        billing = order.get('billingAddress', {})

        first_name = billing.get('firstName', '').strip()
        last_name = billing.get('lastName', '').strip()
        email = order.get('customerEmail', '').strip()
        phone = billing.get('phone', '').strip()

        # SMART MATCHING: Try to find existing customer
        customer_name = None
        if customer_matcher:
            customer_name = customer_matcher.find_match(email, phone, first_name, last_name)

        if customer_name:
            # Found existing customer!
            matched_customers.add(customer_name)
        else:
            # Create new customer name
            if first_name and last_name:
                customer_name = f"{first_name} {last_name}"
            elif first_name or last_name:
                customer_name = first_name or last_name
            else:
                customer_name = email.split('@')[0] if email else 'Guest Customer'

            customer_name = sanitize_customer_name(customer_name)
            new_customers.add(customer_name)

            # Store customer details for CUST record (only for new customers)
            if customer_name not in customer_records:
                # Build address per QuickBooks format: BADDR1=street, BADDR2="City, State ZIP"
                addr1 = (billing.get('address1', '') or '').replace('\n', ' ').replace('\r', ' ')[:40]
                address2_raw = (billing.get('address2', '') or '').replace('\n', ' ').replace('\r', ' ')[:40]

                city = (billing.get('city', '') or '').replace('\n', ' ').replace('\r', ' ')
                state = (billing.get('state', '') or '').replace('\n', ' ').replace('\r', ' ')
                zip_code = (billing.get('postalCode', '') or '').replace('\n', ' ').replace('\r', ' ')

                # QuickBooks format: "City, State ZIP" in quotes
                city_state_zip = f"{city}, {state} {zip_code}".strip()

                # For customers without company: BADDR1=name, BADDR2=street, BADDR3="City, State ZIP"
                # Customer name needs to be on first line of bill-to address
                # We'll set this after we have customer_name
                addr2 = addr1  # Street address moves to BADDR2
                addr1 = ''  # Will be set to customer name below
                addr3 = city_state_zip
                addr4 = address2_raw if address2_raw else ''  # Apt/Suite if exists
                addr5 = ''

                # Determine tax code: Georgia state tax if in-state, Non if out-of-state
                is_in_state = is_in_state_order(order, SHIP_FROM_STATE)
                tax_code = 'Tax' if is_in_state else 'Non'

                # Get shipping address for SADDR fields
                shipping = order.get('shippingAddress') or {}
                ship_addr1 = (shipping.get('address1', '') or '').replace('\n', ' ').replace('\r', ' ')[:40]
                ship_address2_raw = (shipping.get('address2', '') or '').replace('\n', ' ').replace('\r', ' ')[:40]

                ship_city = (shipping.get('city', '') or '').replace('\n', ' ').replace('\r', ' ')
                ship_state = (shipping.get('state', '') or '').replace('\n', ' ').replace('\r', ' ')
                ship_zip = (shipping.get('postalCode', '') or '').replace('\n', ' ').replace('\r', ' ')
                ship_city_state_zip = f"{ship_city}, {ship_state} {ship_zip}".strip()

                # Ship to address for customer record - SHIPPING RECIPIENT name on first line
                ship_first = (shipping.get('firstName', '') or '').strip()
                ship_last = (shipping.get('lastName', '') or '').strip()
                ship_recipient_name = f"{ship_first} {ship_last}".strip() if ship_first or ship_last else customer_name
                saddr1 = ship_recipient_name[:40]  # Shipping recipient name on first line
                saddr2 = ship_addr1  # Street address
                saddr3 = ship_city_state_zip  # City, State ZIP
                saddr4 = ship_address2_raw if ship_address2_raw else ''  # Apt/Suite if exists
                saddr5 = ''

                customer_records[customer_name] = {
                    'name': customer_name,
                    'first_name': first_name[:15] if first_name else '',
                    'last_name': last_name[:15] if last_name else '',
                    'company_name': '',  # No company name for individual customers
                    'addr1': customer_name[:40],  # Customer name on first line
                    'addr2': addr2,
                    'addr3': addr3,
                    'addr4': addr4,
                    'addr5': addr5,
                    'saddr1': saddr1,
                    'saddr2': saddr2,
                    'saddr3': saddr3,
                    'saddr4': saddr4,
                    'saddr5': saddr5,
                    'email': email[:80] if email else '',
                    'phone': phone[:21] if phone else '',
                    'taxable': 'Y' if is_in_state else 'N',
                    'tax_code': tax_code
                }

    # FILE 1: NEW CUSTOMERS ONLY (if any)
    customer_filename = filename.replace('.iif', '_NEW_CUSTOMERS.iif')
    if customer_records:
        print(f"  Creating customer file: {customer_filename}")
        with open(customer_filename, 'w', encoding='utf-8') as f:
            # Customer records matching QuickBooks export format with SADDR fields
            f.write("!CUST\tNAME\tBADDR1\tBADDR2\tBADDR3\tBADDR4\tBADDR5\tSADDR1\tSADDR2\tSADDR3\tSADDR4\tSADDR5\tPHONE1\tEMAIL\tTAXABLE\tSALESTAXCODE\tCOMPANYNAME\tFIRSTNAME\tLASTNAME\n")
            for cust_name, cust_info in sorted(customer_records.items()):
                f.write(f"CUST\t{cust_info['name']}\t"
                       f"{cust_info['addr1']}\t{cust_info['addr2']}\t\"{cust_info['addr3']}\"\t{cust_info['addr4']}\t{cust_info['addr5']}\t"
                       f"{cust_info['saddr1']}\t{cust_info['saddr2']}\t\"{cust_info['saddr3']}\"\t{cust_info['saddr4']}\t{cust_info['saddr5']}\t"
                       f"{cust_info['phone']}\t{cust_info['email']}\t"
                       f"{cust_info['taxable']}\t{cust_info['tax_code']}\t"
                       f"{cust_info['company_name']}\t{cust_info['first_name']}\t{cust_info['last_name']}\n")

    # FILE 2: INVOICES ONLY
    invoice_filename = filename.replace('.iif', '_INVOICES.iif')
    print(f"  Creating invoice file: {invoice_filename}")

    with open(invoice_filename, 'w', encoding='utf-8') as f:
        # Invoice headers with ship-to address fields (ADDR1-5 = ship-to address per invoice)
        f.write("!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tDOCNUM\tSHIPDATE\tSHIPVIA\tREP\tADDR1\tADDR2\tADDR3\tADDR4\tADDR5\n")
        # Line items - MEMO for line item descriptions (promo codes, discount names)
        f.write("!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tQNTY\tPRICE\tINVITEM\tMEMO\n")
        f.write("!ENDTRNS\n")

        # Create invoices
        for order in orders:
            # Skip canceled orders
            if order.get('fulfillmentStatus') == 'CANCELED':
                continue

            # Order details
            order_number = order.get('orderNumber', order.get('id', 'UNKNOWN'))
            created_on = order.get('createdOn', datetime.now().isoformat())
            invoice_date = format_date_for_qb(created_on)

            # Ship date - use fulfilledOn if available, otherwise createdOn
            fulfilled_on = order.get('fulfilledOn', created_on)
            ship_date = format_date_for_qb(fulfilled_on)

            # Get customer details again
            billing = order.get('billingAddress', {})
            first_name = billing.get('firstName', '').strip()
            last_name = billing.get('lastName', '').strip()
            email = order.get('customerEmail', '').strip()
            phone = billing.get('phone', '').strip()

            # Get the same customer name we determined earlier
            customer_name = None
            if customer_matcher:
                customer_name = customer_matcher.find_match(email, phone, first_name, last_name)

            if not customer_name:
                if first_name and last_name:
                    customer_name = f"{first_name} {last_name}"
                elif first_name or last_name:
                    customer_name = first_name or last_name
                else:
                    customer_name = email.split('@')[0] if email else 'Guest Customer'
                customer_name = sanitize_customer_name(customer_name)

            # Get Bill To address (from billing address) - clean format with name on first line
            bill_street1 = (billing.get('address1', '') or '').replace('\n', ' ').replace('\r', ' ')[:40]
            bill_address2_raw = (billing.get('address2', '') or '').replace('\n', ' ').replace('\r', ' ')

            bill_city = (billing.get('city', '') or '').replace('\n', ' ').replace('\r', ' ')
            bill_state = (billing.get('state', '') or '').replace('\n', ' ').replace('\r', ' ')
            bill_zip = (billing.get('postalCode', '') or '').replace('\n', ' ').replace('\r', ' ')
            bill_city_state_zip = f"{bill_city}, {bill_state} {bill_zip}".strip()[:40]

            bill_country_code = billing.get('countryCode', '').strip().upper()

            # Build bill-to address with customer name on first line
            bill_addr1 = customer_name[:40]  # Customer name on first line
            if bill_address2_raw:
                # Has apt/suite: Name, Street, Apt, City/State/ZIP
                bill_addr2 = bill_street1
                bill_addr3 = bill_address2_raw[:40]
                bill_addr4 = bill_city_state_zip
                bill_addr5 = '' if bill_country_code == 'US' else bill_country_code
            else:
                # No apt: Name, Street, City/State/ZIP
                bill_addr2 = bill_street1
                bill_addr3 = bill_city_state_zip
                bill_addr4 = '' if bill_country_code == 'US' else bill_country_code
                bill_addr5 = ''

            # Get Ship To address - clean format with recipient name on first line
            shipping = order.get('shippingAddress') or {}
            ship_street1 = (shipping.get('address1', '') or '').replace('\n', ' ').replace('\r', ' ')[:40]
            ship_address2_raw = (shipping.get('address2', '') or '').replace('\n', ' ').replace('\r', ' ')

            ship_city = (shipping.get('city', '') or '').replace('\n', ' ').replace('\r', ' ')
            ship_state = (shipping.get('state', '') or '').replace('\n', ' ').replace('\r', ' ')
            ship_zip = (shipping.get('postalCode', '') or '').replace('\n', ' ').replace('\r', ' ')
            ship_city_state_zip = f"{ship_city}, {ship_state} {ship_zip}".strip()[:40]

            ship_country_code = shipping.get('countryCode', '').strip().upper()

            # Build ship-to address with SHIPPING RECIPIENT name on first line (may differ from customer)
            ship_first = (shipping.get('firstName', '') or '').strip()
            ship_last = (shipping.get('lastName', '') or '').strip()
            ship_recipient_name = f"{ship_first} {ship_last}".strip() if ship_first or ship_last else customer_name
            ship_addr1 = ship_recipient_name[:40]  # Shipping recipient name on first line
            if ship_address2_raw:
                # Has apt/suite: Name, Street, Apt, City/State/ZIP
                ship_addr2 = ship_street1
                ship_addr3 = ship_address2_raw[:40]
                ship_addr4 = ship_city_state_zip
                ship_addr5 = '' if ship_country_code == 'US' else ship_country_code
            else:
                # No apt: Name, Street, City/State/ZIP
                ship_addr2 = ship_street1
                ship_addr3 = ship_city_state_zip
                ship_addr4 = '' if ship_country_code == 'US' else ship_country_code
                ship_addr5 = ''

            # Line items
            line_items = order.get('lineItems', [])
            if not line_items:
                continue

            # Calculate invoice total
            invoice_total = order.get('grandTotal', {}).get('value', 0)
            invoice_total = float(invoice_total) if invoice_total else 0.0

            # Determine invoice number: use SS order number with prefix if flag is set, otherwise blank
            invoice_number = f"SS-{order_number}" if use_ss_invoice_numbers else ''

            # TRNS line - Invoice header with per-order ship-to address
            # REP field left blank - QuickBooks requires Name:EntityType:Initials format if used
            # ADDR1-5 = ship-to address for this invoice (can differ from customer default)
            f.write(f"TRNS\t\tINVOICE\t{invoice_date}\t{ar_account}\t{customer_name}\t{invoice_total}\t{invoice_number}\t"
                   f"{ship_date}\tUPS\t\t{ship_addr1}\t{ship_addr2}\t\"{ship_addr3}\"\t{ship_addr4}\t{ship_addr5}\n")

            # SPL lines - Line items with product mapping, quantity, pieces, price, description
            # Tax is handled by customer tax code, not per-item
            for item in line_items:
                # Get product info
                product_name = item.get('productName', 'Product')
                variant_raw = item.get('variantOptions', '')
                variant = parse_variant_options(variant_raw)

                # Get price (needed for sale vs regular item detection)
                unit_price = item.get('unitPricePaid', {}).get('value', 0)
                unit_price = float(unit_price) if unit_price else 0.0

                # Map Squarespace product to QuickBooks item
                if sku_mapper:
                    qb_item = sku_mapper.get_mapping(product_name, variant, unit_price)
                else:
                    # No mapper - use product name as-is
                    if variant:
                        qb_item = f"{product_name} - {variant}"
                    else:
                        qb_item = product_name
                    qb_item = qb_item.replace('\t', ' ').replace('\n', ' ')[:31]

                # Build description - full product name with variant
                description = product_name
                if variant:
                    description = f"{product_name} - {variant}"
                description = description.replace('\t', ' ').replace('\n', ' ')[:4095]  # QB description limit

                # Get quantity
                quantity = item.get('quantity', 1)

                # Extract pieces from API data (customizations/variants)
                pieces = extract_pieces_from_customizations(item)
                if pieces == quantity:  # No pieces field found in API, default to quantity
                    pieces = quantity

                # Calculate line total (unit_price already extracted above for mapping)
                line_total = -(quantity * unit_price)  # Negative for QB convention

                # Write line item (empty INVITEMDESC - testing if QB uses item default or blanks it)
                f.write(f"SPL\t\tINVOICE\t{invoice_date}\t{income_account}\t{customer_name}\t{line_total}\t{quantity}\t{unit_price}\t{qb_item}\t\n")

            # Discount line items - process each discount from discountLines
            # Each discount can be: promo code, automatic discount, or gift card
            discount_lines = order.get('discountLines', [])
            for disc in discount_lines:
                disc_amount = float(disc.get('amount', {}).get('value', 0) or 0)
                if disc_amount <= 0:
                    continue

                disc_name = disc.get('name', '') or ''
                disc_promo = disc.get('promoCode', '') or ''

                # Determine QB item and description based on discount type
                # 1. "Early Access" automatic discount -> specific QB item
                if 'early access' in disc_name.lower():
                    qb_discount_item = '2025 Early Access 10% Off'
                    disc_desc = ''  # Item name is descriptive enough
                # 2. Promo code entered by customer -> Non-inventory Item with code in desc
                elif disc_promo:
                    qb_discount_item = 'Non-inventory Item'
                    disc_desc = disc_promo  # e.g., CYPRESS2025
                # 3. Other automatic discounts (Free Samples, etc.) -> Non-inventory Item with name in desc
                else:
                    qb_discount_item = 'Non-inventory Item'
                    disc_desc = disc_name  # e.g., "Free Samples with Order"

                # Write discount line with description (positive amount = reduces invoice total in QB)
                f.write(f"SPL\t\tINVOICE\t{invoice_date}\t{income_account}\t{customer_name}\t{disc_amount}\t1\t{-disc_amount}\t{qb_discount_item}\t{disc_desc}\n")

            # Also check for gift card redemption (separate from discountLines)
            gift_card = order.get('giftCardRedemption', {})
            if gift_card:
                gc_amount = float(gift_card.get('amount', {}).get('value', 0) or 0)
                if gc_amount > 0:
                    gc_code = gift_card.get('giftCardCode', 'Gift Card')
                    gc_desc = f"Gift Card - {gc_code}"
                    f.write(f"SPL\t\tINVOICE\t{invoice_date}\t{income_account}\t{customer_name}\t{gc_amount}\t1\t{-gc_amount}\tNon-inventory Item\t{gc_desc}\n")

            # Freight line item - ALWAYS included, even if $0 (no quantity for freight)
            shipping_total = order.get('shippingTotal', {}).get('value', 0)
            shipping_total = float(shipping_total) if shipping_total else 0.0
            f.write(f"SPL\t\tINVOICE\t{invoice_date}\t{income_account}\t{customer_name}\t{-shipping_total}\t\t{shipping_total}\tFreight\t\n")

            # QuickBooks will calculate sales tax automatically based on customer tax code - no manual line item needed

            # End this invoice transaction
            f.write("ENDTRNS\n")
            invoice_count += 1

            # Log this order as imported
            log_imported_order(order_number, invoice_filename)

    # Generate new customers report
    report_filename = filename.replace('.iif', '_NEW_CUSTOMERS.txt')
    with open(report_filename, 'w', encoding='utf-8') as report:
        report.write("=" * 70 + "\n")
        report.write("NEW CUSTOMERS CREATED FROM SQUARESPACE IMPORT\n")
        report.write("=" * 70 + "\n\n")

        if customer_matcher:
            report.write(f"Total Invoices: {invoice_count}\n")
            report.write(f"Existing Customers (matched): {len(matched_customers)}\n")
            report.write(f"NEW CUSTOMERS (flagged): {len(new_customers)}\n\n")
            report.write("-" * 70 + "\n\n")
        else:
            report.write(f"Total Invoices: {invoice_count}\n")
            report.write(f"Customers in IIF file: {len(new_customers)}\n\n")
            report.write("NOTE: No customer matching was performed.\n")
            report.write("QuickBooks will compare by name and create only truly new customers.\n\n")
            report.write("-" * 70 + "\n\n")

        if new_customers:
            report.write("FLAGGED NEW CUSTOMERS:\n")
            report.write("(These customer records are in the IIF file)\n\n")

            for i, cust_name in enumerate(sorted(new_customers), 1):
                cust_info = customer_records.get(cust_name, {})
                report.write(f"{i}. {cust_name}\n")
                if cust_info.get('email'):
                    report.write(f"   Email: {cust_info['email']}\n")
                if cust_info.get('phone'):
                    report.write(f"   Phone: {cust_info['phone']}\n")
                if cust_info.get('addr1'):
                    report.write(f"   Address: {cust_info['addr1']}\n")
                    if cust_info.get('addr3'):  # City, State, ZIP
                        report.write(f"            {cust_info['addr3']}\n")
                report.write("\n")
        else:
            report.write("No new customers - all orders matched existing customers!\n")

    # Generate unmapped products report (if any)
    if sku_mapper and sku_mapper.unmapped_products:
        unmapped_filename = filename.replace('.iif', '_UNMAPPED_PRODUCTS.txt')
        with open(unmapped_filename, 'w', encoding='utf-8') as unmapped_report:
            unmapped_report.write("=" * 70 + "\n")
            unmapped_report.write("UNMAPPED PRODUCTS - ACTION REQUIRED\n")
            unmapped_report.write("=" * 70 + "\n\n")
            unmapped_report.write(f"Found {len(sku_mapper.unmapped_products)} product(s) without mappings.\n\n")
            unmapped_report.write("These products were included in the IIF file using their Squarespace names.\n")
            unmapped_report.write("QuickBooks will CREATE NEW ITEMS for these products.\n\n")
            unmapped_report.write("⚠️  RECOMMENDED ACTION:\n")
            unmapped_report.write("   1. Add these mappings to config/sku_mapping.csv\n")
            unmapped_report.write("   2. Re-run the import to use your QuickBooks item names\n\n")
            unmapped_report.write("-" * 70 + "\n\n")
            unmapped_report.write("UNMAPPED PRODUCTS:\n\n")

            for i, product in enumerate(sku_mapper.unmapped_products, 1):
                unmapped_report.write(f"{i}. Product: {product['product_name']}\n")
                if product['variant']:
                    unmapped_report.write(f"   Variant: {product['variant']}\n")
                unmapped_report.write(f"   ⚠️  Will create QB item: \"{product['suggested_key'][:31]}\"\n\n")
                unmapped_report.write(f"   To map this product, add to config/sku_mapping.csv:\n")
                unmapped_report.write(f"   {product['suggested_key']},YourQuickBooksItemName\n\n")
                unmapped_report.write("-" * 70 + "\n\n")

        print(f"\n{'='*60}")
        print(f"WARNING: {len(sku_mapper.unmapped_products)} UNMAPPED PRODUCT(S)")
        print(f"{'='*60}")
        print(f"UNMAPPED PRODUCTS REPORT: {unmapped_filename}")
        print(f"\nThese products will create NEW ITEMS in QuickBooks.")
        print(f"Review the report and add mappings to config/sku_mapping.csv if needed.")

    print(f"\n{'='*60}")
    print(f"SUCCESS! Created IIF files:")
    print(f"{'='*60}")
    if customer_records:
        print(f"NEW CUSTOMERS: {customer_filename}")
        print(f"   ({len(customer_records)} new customer(s) with tax codes)")
    print(f"INVOICES: {invoice_filename}")
    print(f"   ({invoice_count} invoice(s) with Ship To addresses)")
    print(f"{'='*60}")

    if customer_matcher:
        print(f"\nCUSTOMER SUMMARY:")
        print(f"  EXISTING customers (matched): {len(matched_customers)}")
        print(f"  NEW customers (flagged): {len(new_customers)}")

        if new_customers:
            print(f"\n  NEW CUSTOMERS THAT WILL BE CREATED:")
            for name in sorted(new_customers)[:15]:
                print(f"    - {name}")
            if len(new_customers) > 15:
                print(f"    ... and {len(new_customers) - 15} more")
    else:
        print(f"\nCUSTOMER SUMMARY:")
        print(f"  Customers in IIF: {len(new_customers)}")
        print(f"  NOTE: These are FLAGGED as potentially new")
        print(f"  INFO: QuickBooks will skip any that already exist (matches by name)")

        if new_customers and len(new_customers) <= 20:
            print(f"\n  CUSTOMERS IN IIF FILE:")
            for name in sorted(new_customers):
                print(f"    - {name}")

    print(f"\nNEW CUSTOMERS REPORT: {report_filename}")

    if sku_mapper and sku_mapper.unmapped_products:
        unmapped_filename = filename.replace('.iif', '_UNMAPPED_PRODUCTS.txt')
        print(f"UNMAPPED PRODUCTS REPORT: {unmapped_filename}")

    print(f"\nSALES TAX CALCULATION:")
    print(f"  Ship from state: {SHIP_FROM_STATE}")
    print(f"  In-state orders: Taxable (Y)")
    print(f"  Out-of-state orders: Non-taxable (N)")
    print(f"\nHOW IT WORKS:")
    print(f"  1. Existing customers: Invoices created immediately")
    print(f"  2. New customers: Customer created, THEN invoice created")
    print(f"  3. QuickBooks skips customers that already exist (by name)")
    print(f"  4. Tax status determined by ship-to address")

    if sku_mapper and sku_mapper.unmapped_products:
        print(f"  5. Unmapped products: QB creates new items (review report first!)")

    print(f"\nTO IMPORT:")
    if customer_records:
        print(f"  1. Review new customers report: {report_filename}")
        print(f"  2. Import customers FIRST: {customer_filename}")
        print(f"     (File > Utilities > Import > IIF Files)")
        print(f"  3. Verify new customers created with correct tax codes")
        print(f"  4. Import invoices SECOND: {invoice_filename}")
    else:
        print(f"  1. No new customers - all matched existing!")
        print(f"  2. Import invoices: {invoice_filename}")
        print(f"     (File > Utilities > Import > IIF Files)")

    if sku_mapper and sku_mapper.unmapped_products:
        print(f"\n  WARNING - REVIEW UNMAPPED PRODUCTS FIRST:")
        print(f"      {unmapped_filename}")
        print(f"      Add mappings to config/sku_mapping.csv and re-run if needed")


def create_encrypted_zip(files: List[str], zip_filename: str, password: str) -> str:
    """
    Create a password-protected ZIP file with AES-256 encryption

    Args:
        files: List of file paths to include in the ZIP
        zip_filename: Output ZIP filename
        password: Password for encryption

    Returns:
        Path to created ZIP file
    """
    try:
        import pyzipper
    except ImportError:
        print("ERROR: pyzipper not installed. Installing...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'pyzipper'])
        import pyzipper

    with pyzipper.AESZipFile(zip_filename, 'w', compression=pyzipper.ZIP_DEFLATED,
                              encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode('utf-8'))
        for file_path in files:
            if os.path.exists(file_path):
                zf.write(file_path, os.path.basename(file_path))

    return zip_filename


def get_gmail_oauth_token(token_file: str = 'config/gmail_token.json') -> str:
    """
    Get OAuth2 access token for Gmail using Google Sign-In.
    Handles initial authentication and token refresh.

    Args:
        token_file: Path to store refresh token

    Returns:
        Access token for Gmail API
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Installing required Google auth libraries...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'google-auth-oauthlib', 'google-auth-httplib2', 'google-api-python-client'])
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    creds = None

    # Load existing token
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing Gmail access token...")
            creds.refresh(Request())
        else:
            # Need OAuth2 credentials file
            creds_file = 'config/gmail_credentials.json'
            if not os.path.exists(creds_file):
                print("\nERROR: config/gmail_credentials.json not found!")
                print("\nTo set up Gmail OAuth2:")
                print("1. Go to: https://console.cloud.google.com/")
                print("2. Create a new project (or select existing)")
                print("3. Enable Gmail API")
                print("4. Create OAuth 2.0 Client ID (Desktop app)")
                print("5. Download credentials as 'config/gmail_credentials.json'")
                print("6. Place file in the config/ directory")
                raise FileNotFoundError("config/gmail_credentials.json not found")

            print("\nOpening browser for Google Sign-In...")
            print("Please authorize the application to send emails on your behalf.")
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future use
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    return creds.token


def send_email_with_attachment_oauth(recipient: str, subject: str, body: str, attachment_path: str,
                                      sender_email: str) -> None:
    """
    Send email with attachment via Gmail using OAuth2

    Args:
        recipient: Email address to send to
        subject: Email subject
        body: Email body text
        attachment_path: Path to file to attach
        sender_email: Sender's Gmail address
    """
    # Get OAuth2 access token
    access_token = get_gmail_oauth_token()

    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = subject

    # Add body
    msg.attach(MIMEText(body, 'plain'))

    # Add attachment
    with open(attachment_path, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
    msg.attach(part)

    # Send email using OAuth2
    import base64

    # Encode message
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

    # Send via Gmail API
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
    except ImportError:
        import subprocess
        subprocess.check_call(['pip', 'install', 'google-api-python-client'])
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

    # Create credentials from token
    creds = Credentials(token=access_token)
    service = build('gmail', 'v1', credentials=creds)

    message = {'raw': raw_message}
    service.users().messages().send(userId='me', body=message).execute()


def main():
    print("=" * 60)
    print("SQUARESPACE INVOICE IMPORT TO QUICKBOOKS")
    print("Import: Single, Multiple, or Batch")
    print("=" * 60)

    args = parse_arguments()

    # Initialize customer matcher
    customer_matcher = None
    if args.customers:
        customer_matcher = CustomerMatcher()
        customer_matcher.load_existing_customers(args.customers)
        print()
    else:
        print("\nNOTE: No customer file provided")
        print("      Customer records will be included in IIF file")
        print("      QuickBooks will skip existing customers automatically")
        print("      (matches by name - use --customers flag for smarter matching)")
        print()

    # Initialize product mapper
    sku_mapper = ProductMapper()
    if args.product_mapping and os.path.exists(args.product_mapping):
        sku_mapper.load_product_mapping(args.product_mapping)
    else:
        print(f"NOTE: No product mapping file found: {args.product_mapping}")
        print("      Items will use Squarespace product names as-is")
        print("      Create config/sku_mapping.csv to map Squarespace products to QuickBooks items")

    # Load holiday sale mappings - either from explicit flag or auto-detect from default location
    # Holiday mappings are applied intelligently only to holiday/sale items (mystery bundles, etc.)
    holiday_mapping_file = args.holiday_mapping
    if not holiday_mapping_file and os.path.exists(ProductMapper.DEFAULT_HOLIDAY_MAPPING):
        holiday_mapping_file = ProductMapper.DEFAULT_HOLIDAY_MAPPING
        print(f"Auto-loading holiday mappings from: {holiday_mapping_file}")
    if holiday_mapping_file:
        sku_mapper.load_holiday_mapping(holiday_mapping_file)

    print()

    # Determine import mode: specific orders, fulfilled today, or date range
    orders = []

    if args.fulfilled_today:
        # FULFILLED TODAY MODE - for daily automation
        print("Mode: Orders fulfilled today\n")
        fetched_orders = fetch_fulfilled_today_orders()

        # Check for duplicates
        if fetched_orders:
            order_nums = [str(o.get('orderNumber', o.get('id', ''))) for o in fetched_orders]
            new_orders, already_imported = check_already_imported(order_nums)

            if already_imported:
                print(f"\nWARNING: {len(already_imported)} order(s) already imported:")
                for num in already_imported[:10]:
                    print(f"  - Order #{num}")
                if len(already_imported) > 10:
                    print(f"  ... and {len(already_imported) - 10} more")
                print(f"\nSkipping {len(already_imported)} duplicate(s), importing {len(new_orders)} new order(s)")

                # Filter to only new orders
                orders = [o for o in fetched_orders if str(o.get('orderNumber', o.get('id', ''))) in new_orders]
            else:
                orders = fetched_orders
        else:
            orders = []

    elif args.order_numbers:
        # SPECIFIC ORDER MODE - fetch individual orders
        order_list = [num.strip() for num in args.order_numbers.split(',')]

        # Check for duplicates first
        new_orders, already_imported = check_already_imported(order_list)

        if already_imported:
            print(f"\nWARNING: {len(already_imported)} order(s) already imported:")
            for num in already_imported:
                print(f"  - Order #{num} - SKIPPING (already in config/import_log.csv)")
            print()

        if new_orders:
            print(f"Fetching {len(new_orders)} new order(s)...\n")
            for order_num in new_orders:
                order = fetch_specific_order(order_num)
                if order:
                    orders.append(order)
                    print(f"  [OK] Order #{order_num} - {order.get('customerEmail', 'N/A')}")
                else:
                    print(f"  [NOT FOUND] Order #{order_num}")

            print(f"\nFetched {len(orders)} of {len(new_orders)} requested orders")
        else:
            print("\nAll requested orders have already been imported. Check config/import_log.csv")

    else:
        # BATCH MODE - fetch by date range
        if not args.start_date:
            args.start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not args.end_date:
            args.end_date = datetime.now().strftime('%Y-%m-%d')

        orders = fetch_squarespace_orders(args.start_date, args.end_date)

    if not orders:
        print("\nNo orders to import")
        if not SQUARESPACE_API_KEY:
            print("\nSETUP REQUIRED:")
            print("  1. Get API Key: Squarespace > Settings > Advanced > Developer API Keys")
            print("  2. Set variable: set SQUARESPACE_API_KEY=your_key_here")
            print("\nNote: Requires Commerce Advanced plan")
        return

    # Generate output filename
    if args.output:
        output_file = args.output
    elif args.fulfilled_today:
        today = datetime.now().strftime('%Y-%m-%d')
        output_file = f"squarespace_fulfilled_{today}.iif"
    elif args.order_numbers:
        # For specific orders, use order numbers in filename
        order_list = [num.strip() for num in args.order_numbers.split(',')]
        if len(order_list) == 1:
            output_file = f"squarespace_invoice_{order_list[0]}.iif"
        else:
            output_file = f"squarespace_invoices_{len(orders)}_orders.iif"
    else:
        output_file = f"squarespace_invoices_{args.start_date}_to_{args.end_date}.iif"

    # Generate IIF file
    generate_iif_file(orders, output_file, args.ar_account, args.income_account, customer_matcher, sku_mapper, args.use_ss_invoice_numbers)

    # Email if requested
    if args.email:
        # Get sender email from environment, or use recipient email for OAuth
        sender_email = EMAIL_USER or EMAIL_RECIPIENT or args.email
        if not sender_email:
            print("\nERROR: Sender email address required")
            print("Set EMAIL_USER environment variable")
            return

        recipient = args.email
        print(f"\n{'='*60}")
        print(f"SENDING ENCRYPTED EMAIL")
        print(f"{'='*60}")

        try:
            # Generate random password for ZIP encryption
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits + string.punctuation
            zip_password = ''.join(secrets.choice(alphabet) for _ in range(16))

            # Collect all files to send
            files_to_send = []
            invoice_file = output_file.replace('.iif', '_INVOICES.iif')
            customer_file = output_file.replace('.iif', '_NEW_CUSTOMERS.iif')
            report_file = output_file.replace('.iif', '_NEW_CUSTOMERS.txt')

            if os.path.exists(invoice_file):
                files_to_send.append(invoice_file)
            if os.path.exists(customer_file):
                files_to_send.append(customer_file)
            if os.path.exists(report_file):
                files_to_send.append(report_file)

            if not files_to_send:
                print("ERROR: No files to send")
                return

            # Create encrypted ZIP
            zip_filename = output_file.replace('.iif', '_ENCRYPTED.zip')
            print(f"Creating encrypted ZIP: {zip_filename}")
            create_encrypted_zip(files_to_send, zip_filename, zip_password)

            # Send email
            subject = f"QuickBooks IIF Files - {datetime.now().strftime('%Y-%m-%d')}"
            body = f"""QuickBooks IIF files are attached in an encrypted ZIP file.

Files included:
{chr(10).join(['  - ' + os.path.basename(f) for f in files_to_send])}

Order count: {len(orders)}

IMPORTANT: The ZIP file is password-protected with AES-256 encryption.
Password: {zip_password}

(Store this password securely - it will not be sent again)

Import instructions:
1. Extract the ZIP file using the password above
2. Import customers first: {os.path.basename(customer_file) if os.path.exists(customer_file) else 'N/A'}
3. Import invoices second: {os.path.basename(invoice_file)}
"""

            print(f"Sending email to: {recipient}")
            print(f"From: {sender_email}")
            send_email_with_attachment_oauth(
                recipient=recipient,
                subject=subject,
                body=body,
                attachment_path=zip_filename,
                sender_email=sender_email
            )

            print(f"\n{'='*60}")
            print(f"EMAIL SENT SUCCESSFULLY")
            print(f"{'='*60}")
            print(f"Recipient: {recipient}")
            print(f"Attachment: {zip_filename}")
            print(f"\nZIP PASSWORD: {zip_password}")
            print(f"{'='*60}")
            print(f"\nIMPORTANT: Share this password with the recipient via a")
            print(f"separate secure channel (text, phone call, etc.)")
            print(f"{'='*60}")

        except FileNotFoundError as e:
            print(f"\nERROR: {e}")
            print("\nSee EMAIL_SETUP.md for detailed setup instructions")
        except Exception as e:
            print(f"\nERROR: Email failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
