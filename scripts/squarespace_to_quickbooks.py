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


# Squarespace API Configuration
SQUARESPACE_API_KEY = os.environ.get('SQUARESPACE_API_KEY')
SQUARESPACE_API_VERSION = '1.0'
SQUARESPACE_BASE_URL = f'https://api.squarespace.com/{SQUARESPACE_API_VERSION}'

# Sales Tax Configuration - set your business state
SHIP_FROM_STATE = os.environ.get('SHIP_FROM_STATE', 'GA')  # Default: Georgia

# Email Configuration (optional - for daily automation)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', 'matt@thetanneryrow.com')


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Import Squarespace invoices to QuickBooks Desktop - Single, multiple, or batch'
    )
    parser.add_argument('--order-numbers', type=str,
                        default=None,
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
                        default=None,
                        help='CSV file with existing QuickBooks customers (exported from QB)')
    parser.add_argument('--product-mapping', type=str,
                        default='sku_mapping.csv',
                        help='CSV file with Squarespace product to QuickBooks item mapping')
    parser.add_argument('--ar-account', type=str,
                        default='Accounts Receivable',
                        help='A/R account name in QuickBooks')
    parser.add_argument('--income-account', type=str,
                        default='Sales',
                        help='Income account name in QuickBooks')
    parser.add_argument('--email', type=str,
                        default=None,
                        help='Email address to send IIF file to (requires EMAIL_USER and EMAIL_PASSWORD env vars)')
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
        # Search for order by order number
        params = {'orderNumber': order_number}

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
        if orders:
            return orders[0]  # Return first matching order

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

    def __init__(self):
        self.product_map = {}  # product_name -> qb_item (simple mappings)
        self.variant_map = {}  # "product - variant" -> qb_item (variant-specific mappings)
        self.unmapped_products = []  # Track products that couldn't be mapped (for reporting)

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
                    sq_product = row.get('SquarespaceProductName', '').strip()
                    qb_item = row.get('QuickBooksItem', '').strip()

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

    def _normalize_variant(self, variant: str) -> str:
        """
        Normalize variant string for matching
        Removes extra spaces, standardizes separators
        """
        if not variant:
            return ""
        # Normalize separators and spacing
        normalized = variant.replace(',', ' -').replace('  ', ' ').strip()
        # Remove common prefixes like "Color:", "Size:", etc.
        import re
        normalized = re.sub(r'(Color|Size|Weight|Tannage|Grade):\s*', '', normalized, flags=re.IGNORECASE)
        return normalized

    def get_mapping(self, product_name: str, variant: str = '') -> str:
        """
        Get QuickBooks item name for a Squarespace product with smart variant matching

        Matching priority:
        1. Exact match on "ProductName - Variant" (full variant string)
        2. Exact match on product name only
        3. Partial match on variant attributes
        4. Fallback to product name + variant (tracked in unmapped_products for reporting)

        Args:
            product_name: Squarespace product name
            variant: Optional variant (e.g., "Horween Predator - Steel - 5-6 oz")

        Returns:
            QuickBooks item name (always returns a value, but tracks unmapped products)
        """
        lookup_key = product_name.strip().lower()

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

        # PRIORITY 3: Try partial matching on variant mappings
        if variant:
            variant_normalized = self._normalize_variant(variant).lower()
            # Look for variant mappings that contain the variant attributes
            best_match = None
            best_match_score = 0

            for mapped_variant, mapping in self.variant_map.items():
                # Extract variant portion (after first " - ")
                parts = mapped_variant.split(' - ', 1)
                if len(parts) > 1:
                    mapped_variant_part = parts[1]
                    # Count matching words
                    variant_words = set(variant_normalized.lower().split())
                    mapped_words = set(mapped_variant_part.lower().split())
                    matches = len(variant_words & mapped_words)

                    if matches > best_match_score:
                        best_match_score = matches
                        best_match = mapping['qb_item']

            if best_match and best_match_score >= 2:  # At least 2 matching attributes
                return best_match

        # PRIORITY 4: Try partial matching on product name
        for mapped_name, mapping in self.product_map.items():
            if mapped_name in lookup_key or lookup_key in mapped_name:
                return mapping['qb_item']

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

                    self.customers.append(customer_record)

            print(f"  Loaded {len(self.customers)} existing customers")
            print(f"  Email lookups: {len(self.email_map)}")
            print(f"  Phone lookups: {len(self.phone_map)}")
            print(f"  Last name index: {len(self.lastname_map)} unique last names")

        except Exception as e:
            print(f"Warning: Could not load customers: {e}")

    def find_match(self, email: str, phone: str, first_name: str, last_name: str) -> Optional[str]:
        """
        Try to find existing customer by:
        1. Email (exact match)
        2. Phone (normalized match)
        3. Last name + first name (fuzzy)

        Returns: Existing customer name or None
        """
        # 1. Try email match (most reliable)
        if email:
            email_lower = email.strip().lower()
            if email_lower in self.email_map:
                return self.email_map[email_lower]

        # 2. Try phone match
        if phone:
            phone_normalized = normalize_for_matching(phone)
            if phone_normalized in self.phone_map:
                return self.phone_map[phone_normalized]

        # 3. Try last name + first name match
        if last_name:
            last_name_lower = last_name.strip().lower()
            if last_name_lower in self.lastname_map:
                candidates = self.lastname_map[last_name_lower]

                # If only one person with that last name, match it
                if len(candidates) == 1:
                    return candidates[0]

                # Multiple matches - try to narrow by first name
                if first_name:
                    first_normalized = normalize_for_matching(first_name)
                    for candidate in candidates:
                        # Check if first name appears in the customer name
                        if first_normalized in normalize_for_matching(candidate):
                            return candidate

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
    # Get shipping address state
    shipping_address = order.get('shippingAddress', {})
    ship_to_state = shipping_address.get('state', '').strip().upper()

    # Normalize ship_from_state
    ship_from_normalized = ship_from_state.strip().upper()

    # If no shipping address, try billing address
    if not ship_to_state:
        billing_address = order.get('billingAddress', {})
        ship_to_state = billing_address.get('state', '').strip().upper()

    # Compare states
    return ship_to_state == ship_from_normalized


def extract_pieces_from_customizations(item: Dict[str, Any]) -> int:
    """
    Extract pieces from line item customizations or variants

    Args:
        item: Line item from Squarespace order

    Returns:
        Number of pieces (defaults to quantity if not found)
    """
    # Check customizations for "pieces" field
    customizations = item.get('customizations', [])
    for custom in customizations:
        label = custom.get('label', '').lower()
        value = custom.get('value', '')
        if 'piece' in label or 'pcs' in label or 'qty' in label:
            try:
                return int(value)
            except:
                pass

    # Check variant options for pieces
    variant_options = item.get('variantOptions', '')
    if variant_options:
        # Look for patterns like "12 pieces", "24 pcs", etc.
        import re
        match = re.search(r'(\d+)\s*(?:piece|pcs|pc)', variant_options.lower())
        if match:
            return int(match.group(1))

    # Default to quantity if no pieces found
    return item.get('quantity', 1)


def log_imported_order(order_number: str, iif_filename: str, log_file: str = 'import_log.csv') -> None:
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


def check_already_imported(order_numbers: List[str], log_file: str = 'import_log.csv') -> Tuple[List[str], List[str]]:
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
                      sku_mapper: Optional[ProductMapper] = None) -> None:
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
    """
    if not orders:
        print("No orders to export")
        return

    print(f"\nGenerating IIF files...")

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
                # Build address lines
                addr1 = billing.get('address1', '')
                addr2 = billing.get('address2', '')
                city = billing.get('city', '')
                state = billing.get('state', '')
                zip_code = billing.get('postalCode', '')

                # Format: Address1, Address2, City State ZIP, Country
                addr_line3 = f"{city} {state} {zip_code}".strip() if city or state or zip_code else ''
                country = billing.get('countryCode', '')

                # Determine tax code: Illinois state tax if in-state, Non if out-of-state
                is_in_state = is_in_state_order(order, SHIP_FROM_STATE)
                tax_code = 'Tax' if is_in_state else 'Non'  # Adjust 'Tax' to your QB tax code name

                customer_records[customer_name] = {
                    'name': customer_name,
                    'addr1': addr1[:41] if addr1 else '',
                    'addr2': addr2[:41] if addr2 else '',
                    'addr3': addr_line3[:41] if addr_line3 else '',
                    'addr4': country[:41] if country else '',
                    'addr5': '',  # Extra address line
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
            # Customer records with tax codes
            f.write("!CUST\tNAME\tBDADDR1\tBDADDR2\tBDADDR3\tBDADDR4\tBDADDR5\tEMAIL\tPHONE1\tTAXABLE\tSALESTAXCODE\n")
            for cust_name, cust_info in sorted(customer_records.items()):
                f.write(f"CUST\t{cust_info['name']}\t{cust_info['addr1']}\t{cust_info['addr2']}\t"
                       f"{cust_info['addr3']}\t{cust_info['addr4']}\t{cust_info['addr5']}\t"
                       f"{cust_info['email']}\t{cust_info['phone']}\t{cust_info['taxable']}\t{cust_info['tax_code']}\n")

    # FILE 2: INVOICES ONLY
    invoice_filename = filename.replace('.iif', '_INVOICES.iif')
    print(f"  Creating invoice file: {invoice_filename}")

    with open(invoice_filename, 'w', encoding='utf-8') as f:
        # Invoice headers with Ship To address fields
        f.write("!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tSHIPDATE\tSHIPVIA\tREP\tSHIPTOADDR1\tSHIPTOADDR2\tSHIPTOADDR3\tSHIPTOADDR4\tSHIPTOADDR5\n")
        # Line items - removed TAXABLE since customer tax code handles it
        f.write("!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tQNTY\tPRICE\tINVITEM\tOTHER1\tINVITEMDESC\n")
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

            # Get Ship To address
            shipping = order.get('shippingAddress', {})
            ship_addr1 = shipping.get('address1', '')[:41]
            ship_addr2 = shipping.get('address2', '')[:41]
            ship_city = shipping.get('city', '')
            ship_state = shipping.get('state', '')
            ship_zip = shipping.get('postalCode', '')
            ship_addr3 = f"{ship_city} {ship_state} {ship_zip}".strip()[:41]
            ship_country = shipping.get('countryCode', '')[:41]

            # Line items
            line_items = order.get('lineItems', [])
            if not line_items:
                continue

            # Calculate invoice total
            invoice_total = order.get('grandTotal', {}).get('value', 0)

            # TRNS line - Invoice header with Ship To address
            f.write(f"TRNS\t\tINVOICE\t{invoice_date}\t{ar_account}\t{customer_name}\t{invoice_total}\t"
                   f"{ship_date}\tUPS\tSHOP\t{ship_addr1}\t{ship_addr2}\t{ship_addr3}\t{ship_country}\t\n")

            # SPL lines - Line items with product mapping, quantity, pieces, price, description
            # Tax is handled by customer tax code, not per-item
            for item in line_items:
                # Get product info
                product_name = item.get('productName', 'Product')
                variant = item.get('variantOptions', '')

                # Map Squarespace product to QuickBooks item
                if sku_mapper:
                    qb_item = sku_mapper.get_mapping(product_name, variant)
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

                # Get price
                unit_price = item.get('unitPricePaid', {}).get('value', 0)
                line_total = -(quantity * unit_price)  # Negative for QB convention

                # Write line item - no TAXABLE field (customer tax code handles it)
                f.write(f"SPL\t\tINVOICE\t{invoice_date}\t{income_account}\t{customer_name}\t{line_total}\t{quantity}\t{unit_price}\t{qb_item}\t{pieces}\t{description}\n")

            # Discount line items - capture discount codes and gift cards as "Non-inventory Item"
            discounts = order.get('discountTotal', {}).get('value', 0)
            if discounts > 0:
                # Get discount code info if available
                discount_code = ''
                promo_code = order.get('formSubmission', {})
                if isinstance(promo_code, list) and promo_code:
                    for field in promo_code:
                        if field.get('label', '').lower() in ['discount', 'promo', 'coupon']:
                            discount_code = field.get('value', '')
                            break

                # Check for discount code in order metadata
                if not discount_code:
                    discount_code = order.get('discountCode', '')

                # Check for gift card redemption
                gift_card = order.get('giftCardRedemption', {})
                if gift_card:
                    gift_card_code = gift_card.get('giftCardCode', 'Gift Card')
                    discount_desc = f"Gift Card - {gift_card_code}"
                elif discount_code:
                    discount_desc = f"Discount Code - {discount_code}"
                else:
                    discount_desc = "Discount applied"

                # Write discount as "Non-inventory Item" (positive discount = negative amount)
                f.write(f"SPL\t\tINVOICE\t{invoice_date}\t{income_account}\t{customer_name}\t{discounts}\t1\t{-discounts}\tNon-inventory Item\t1\t{discount_desc}\n")

            # Freight line item - ALWAYS included, even if $0
            shipping_total = order.get('shippingTotal', {}).get('value', 0)
            f.write(f"SPL\t\tINVOICE\t{invoice_date}\t{income_account}\t{customer_name}\t{-shipping_total}\t1\t{shipping_total}\tFreight\t1\tShipping and handling\n")

            # Tax as separate line item
            tax = order.get('taxTotal', {}).get('value', 0)
            if tax > 0:
                f.write(f"SPL\t\tINVOICE\t{invoice_date}\tSales Tax Payable\t{customer_name}\t{-tax}\t1\t{tax}\tSales Tax\t0\tSales Tax\n")

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
            unmapped_report.write("   1. Add these mappings to sku_mapping.csv\n")
            unmapped_report.write("   2. Re-run the import to use your QuickBooks item names\n\n")
            unmapped_report.write("-" * 70 + "\n\n")
            unmapped_report.write("UNMAPPED PRODUCTS:\n\n")

            for i, product in enumerate(sku_mapper.unmapped_products, 1):
                unmapped_report.write(f"{i}. Product: {product['product_name']}\n")
                if product['variant']:
                    unmapped_report.write(f"   Variant: {product['variant']}\n")
                unmapped_report.write(f"   ⚠️  Will create QB item: \"{product['suggested_key'][:31]}\"\n\n")
                unmapped_report.write(f"   To map this product, add to sku_mapping.csv:\n")
                unmapped_report.write(f"   {product['suggested_key']},YourQuickBooksItemName\n\n")
                unmapped_report.write("-" * 70 + "\n\n")

        print(f"\n{'='*60}")
        print(f"⚠️  WARNING: {len(sku_mapper.unmapped_products)} UNMAPPED PRODUCT(S)")
        print(f"{'='*60}")
        print(f"📄 UNMAPPED PRODUCTS REPORT: {unmapped_filename}")
        print(f"\nThese products will create NEW ITEMS in QuickBooks.")
        print(f"Review the report and add mappings to sku_mapping.csv if needed.")

    print(f"\n{'='*60}")
    print(f"SUCCESS! Created IIF files:")
    print(f"{'='*60}")
    if customer_records:
        print(f"📄 NEW CUSTOMERS: {customer_filename}")
        print(f"   ({len(customer_records)} new customer(s) with tax codes)")
    print(f"📄 INVOICES: {invoice_filename}")
    print(f"   ({invoice_count} invoice(s) with Ship To addresses)")
    print(f"{'='*60}")

    if customer_matcher:
        print(f"\nCUSTOMER SUMMARY:")
        print(f"  ✓ EXISTING customers (matched): {len(matched_customers)}")
        print(f"  ⚠ NEW customers (flagged): {len(new_customers)}")

        if new_customers:
            print(f"\n  NEW CUSTOMERS THAT WILL BE CREATED:")
            for name in sorted(new_customers)[:15]:
                print(f"    • {name}")
            if len(new_customers) > 15:
                print(f"    ... and {len(new_customers) - 15} more")
    else:
        print(f"\nCUSTOMER SUMMARY:")
        print(f"  Customers in IIF: {len(new_customers)}")
        print(f"  ⚠ These are FLAGGED as potentially new")
        print(f"  ℹ QuickBooks will skip any that already exist (matches by name)")

        if new_customers and len(new_customers) <= 20:
            print(f"\n  CUSTOMERS IN IIF FILE:")
            for name in sorted(new_customers):
                print(f"    • {name}")

    print(f"\n📄 NEW CUSTOMERS REPORT: {report_filename}")

    if sku_mapper and sku_mapper.unmapped_products:
        unmapped_filename = filename.replace('.iif', '_UNMAPPED_PRODUCTS.txt')
        print(f"📄 UNMAPPED PRODUCTS REPORT: {unmapped_filename}")

    print(f"\nSALES TAX CALCULATION:")
    print(f"  Ship from state: {SHIP_FROM_STATE}")
    print(f"  In-state orders → Taxable (Y)")
    print(f"  Out-of-state orders → Non-taxable (N)")
    print(f"\nHOW IT WORKS:")
    print(f"  1. Existing customers → Invoices created immediately")
    print(f"  2. New customers → Customer created, THEN invoice created")
    print(f"  3. QuickBooks skips customers that already exist (by name)")
    print(f"  4. Tax status determined by ship-to address")

    if sku_mapper and sku_mapper.unmapped_products:
        print(f"  5. Unmapped products → QB creates new items (review report first!)")

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
        print(f"\n  ⚠️  REVIEW UNMAPPED PRODUCTS FIRST:")
        print(f"      {unmapped_filename}")
        print(f"      Add mappings to sku_mapping.csv and re-run if needed")


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
        print()
    else:
        print(f"NOTE: No product mapping file found: {args.product_mapping}")
        print("      Items will use Squarespace product names as-is")
        print("      Create sku_mapping.csv to map Squarespace products to QuickBooks items")
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
                print(f"\n⚠️  WARNING: {len(already_imported)} order(s) already imported:")
                for num in already_imported[:10]:
                    print(f"  • Order #{num}")
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
            print(f"\n⚠️  WARNING: {len(already_imported)} order(s) already imported:")
            for num in already_imported:
                print(f"  • Order #{num} - SKIPPING (already in import_log.csv)")
            print()

        if new_orders:
            print(f"Fetching {len(new_orders)} new order(s)...\n")
            for order_num in new_orders:
                order = fetch_specific_order(order_num)
                if order:
                    orders.append(order)
                    print(f"  ✓ Order #{order_num} - {order.get('customerEmail', 'N/A')}")
                else:
                    print(f"  ✗ Order #{order_num} - Not found")

            print(f"\nFetched {len(orders)} of {len(new_orders)} requested orders")
        else:
            print("\nAll requested orders have already been imported. Check import_log.csv")

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
    generate_iif_file(orders, output_file, args.ar_account, args.income_account, customer_matcher, sku_mapper)

    # Email if requested
    if args.email or (args.fulfilled_today and EMAIL_USER and EMAIL_PASSWORD):
        recipient = args.email or EMAIL_RECIPIENT
        report_file = output_file.replace('.iif', '_NEW_CUSTOMERS.txt')

        # Import email helper
        try:
            from email_helper import send_iif_email

            # Count new customers from the report file
            new_customer_count = 0
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('NEW CUSTOMERS (flagged):'):
                            new_customer_count = int(line.split(':')[1].strip())
                            break
            except:
                pass

            send_iif_email(
                iif_file=output_file,
                report_file=report_file,
                recipient=recipient,
                invoice_count=len(orders),
                new_customer_count=new_customer_count,
                smtp_host=EMAIL_HOST,
                smtp_port=EMAIL_PORT,
                smtp_user=EMAIL_USER,
                smtp_password=EMAIL_PASSWORD
            )
        except Exception as e:
            print(f"Email failed: {e}")


if __name__ == "__main__":
    main()
