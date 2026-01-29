"""
QuickBooks Billing Helper
Combines Squarespace order data with payment matching for manual QB entry
"""

import os
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


def get_secret(key: str, default: str = None) -> str:
    """Get secret from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


class SquarespaceOrderFetcher:
    """Fetch full order details from Squarespace API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.squarespace.com/1.0/commerce"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def fetch_orders_by_numbers(self, order_numbers: List[str]) -> List[Dict]:
        """Fetch specific orders by order number - returns full order data"""
        order_set = set(str(n) for n in order_numbers)
        found_orders = []
        cursor = None
        max_pages = 20

        for _ in range(max_pages):
            if not order_set:
                break

            params = {}
            if cursor:
                params['cursor'] = cursor

            response = requests.get(
                f"{self.base_url}/orders",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json()

            for order in data.get("result", []):
                order_num = str(order.get("orderNumber", ""))
                if order_num in order_set:
                    found_orders.append(order)
                    order_set.discard(order_num)

            cursor = data.get("pagination", {}).get("nextPageCursor")
            if not cursor:
                break

        return found_orders


def parse_variant_options(variant_raw) -> str:
    """Parse variant options into readable string"""
    if not variant_raw:
        return ''
    if isinstance(variant_raw, str):
        return variant_raw
    if isinstance(variant_raw, list):
        parts = []
        for opt in variant_raw:
            if isinstance(opt, dict):
                val = opt.get('value') or opt.get('optionValue') or ''
                if val:
                    parts.append(str(val))
            else:
                parts.append(str(opt))
        return ', '.join(parts)
    return str(variant_raw)


def extract_order_details(order: Dict) -> Dict[str, Any]:
    """Extract comprehensive order details for billing"""

    # Basic info
    order_number = str(order.get('orderNumber', ''))
    created_on = order.get('createdOn', '')
    fulfilled_on = order.get('fulfilledOn', '')

    # Parse dates
    order_date = ''
    if created_on:
        try:
            dt = datetime.fromisoformat(created_on.replace('Z', '+00:00'))
            order_date = dt.strftime('%m/%d/%Y')
        except:
            order_date = created_on[:10]

    ship_date = ''
    if fulfilled_on:
        try:
            dt = datetime.fromisoformat(fulfilled_on.replace('Z', '+00:00'))
            ship_date = dt.strftime('%m/%d/%Y')
        except:
            ship_date = fulfilled_on[:10]

    # Customer info from billing address
    billing = order.get('billingAddress', {})
    first_name = billing.get('firstName', '').strip()
    last_name = billing.get('lastName', '').strip()
    customer_name = f"{first_name} {last_name}".strip() or 'Guest'
    customer_email = order.get('customerEmail', '').strip()
    customer_phone = billing.get('phone', '').strip()

    # Billing address
    bill_address = {
        'line1': billing.get('address1', ''),
        'line2': billing.get('address2', ''),
        'city': billing.get('city', ''),
        'state': billing.get('state', ''),
        'zip': billing.get('postalCode', ''),
        'country': billing.get('countryCode', 'US')
    }

    # Shipping address
    shipping = order.get('shippingAddress') or {}
    ship_first = shipping.get('firstName', '').strip()
    ship_last = shipping.get('lastName', '').strip()
    ship_name = f"{ship_first} {ship_last}".strip() or customer_name

    ship_address = {
        'name': ship_name,
        'line1': shipping.get('address1', ''),
        'line2': shipping.get('address2', ''),
        'city': shipping.get('city', ''),
        'state': shipping.get('state', ''),
        'zip': shipping.get('postalCode', ''),
        'country': shipping.get('countryCode', 'US')
    }

    # Line items
    line_items = []
    for item in order.get('lineItems', []):
        product_name = item.get('productName', 'Product')
        variant = parse_variant_options(item.get('variantOptions', ''))
        quantity = item.get('quantity', 1)
        unit_price = float(item.get('unitPricePaid', {}).get('value', 0) or 0)
        line_total = quantity * unit_price
        sku = item.get('sku', '')

        line_items.append({
            'product': product_name,
            'variant': variant,
            'sku': sku,
            'quantity': quantity,
            'unit_price': unit_price,
            'line_total': line_total,
            'description': f"{product_name} - {variant}" if variant else product_name
        })

    # Discounts
    discounts = []
    for disc in order.get('discountLines', []):
        disc_amount = float(disc.get('amount', {}).get('value', 0) or 0)
        if disc_amount > 0:
            disc_name = disc.get('name', '') or disc.get('promoCode', '') or 'Discount'
            discounts.append({
                'name': disc_name,
                'amount': disc_amount
            })

    # Gift card
    gift_card = order.get('giftCardRedemption', {})
    if gift_card:
        gc_amount = float(gift_card.get('amount', {}).get('value', 0) or 0)
        if gc_amount > 0:
            discounts.append({
                'name': f"Gift Card - {gift_card.get('giftCardCode', '')}",
                'amount': gc_amount
            })

    # Totals
    subtotal = float(order.get('subtotal', {}).get('value', 0) or 0)
    shipping_total = float(order.get('shippingTotal', {}).get('value', 0) or 0)
    tax_total = float(order.get('taxTotal', {}).get('value', 0) or 0)
    grand_total = float(order.get('grandTotal', {}).get('value', 0) or 0)
    discount_total = float(order.get('discountTotal', {}).get('value', 0) or 0)

    # Determine if taxable (GA = in-state)
    ship_state = ship_address.get('state', '').upper()
    is_taxable = ship_state == 'GA'

    return {
        'order_number': order_number,
        'order_date': order_date,
        'ship_date': ship_date,
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'billing_address': bill_address,
        'shipping_address': ship_address,
        'line_items': line_items,
        'discounts': discounts,
        'subtotal': subtotal,
        'shipping_total': shipping_total,
        'tax_total': tax_total,
        'discount_total': discount_total,
        'grand_total': grand_total,
        'is_taxable': is_taxable,
        'fulfillment_status': order.get('fulfillmentStatus', ''),
    }


def get_billing_data(order_numbers: List[str],
                     ss_api_key: str,
                     stripe_transactions: List[Dict] = None,
                     paypal_transactions: List[Dict] = None) -> Tuple[List[Dict], Dict]:
    """
    Get comprehensive billing data for orders

    Returns:
        Tuple of (order_details_list, summary)
    """
    # Fetch orders from Squarespace
    fetcher = SquarespaceOrderFetcher(ss_api_key)
    orders_raw = fetcher.fetch_orders_by_numbers(order_numbers)

    # Extract detailed info
    orders = []
    for order in orders_raw:
        details = extract_order_details(order)
        orders.append(details)

    # Match to payments if transactions provided
    if stripe_transactions or paypal_transactions:
        all_transactions = (stripe_transactions or []) + (paypal_transactions or [])

        for order in orders:
            order['payment_matched'] = False
            order['payment_source'] = None
            order['net_amount'] = None
            order['processing_fee'] = None

            order_email = order['customer_email'].lower()
            order_amount = order['grand_total']

            for txn in all_transactions:
                if txn.get('_matched'):
                    continue

                txn_email = (txn.get('customer_email') or '').lower()
                txn_amount = txn.get('gross_amount') or txn.get('gross', 0)

                # Match by email and amount (within 2 cents)
                if order_email and txn_email and order_email == txn_email:
                    if abs(order_amount - txn_amount) <= 0.02:
                        txn['_matched'] = True
                        order['payment_matched'] = True
                        order['payment_source'] = txn.get('source', 'Unknown')
                        order['net_amount'] = txn.get('net_amount') or txn.get('net', 0)
                        order['processing_fee'] = txn.get('processing_fee') or txn.get('fee', 0)
                        order['transaction_id'] = txn.get('transaction_id', '')
                        break

    # Build summary
    summary = {
        'total_orders': len(orders),
        'matched_payments': sum(1 for o in orders if o.get('payment_matched')),
        'total_gross': sum(o['grand_total'] for o in orders),
        'total_net': sum(o.get('net_amount', 0) or 0 for o in orders if o.get('payment_matched')),
        'total_fees': sum(o.get('processing_fee', 0) or 0 for o in orders if o.get('payment_matched')),
        'not_found': [n for n in order_numbers if n not in [o['order_number'] for o in orders]]
    }

    return orders, summary


def format_address(addr: Dict) -> str:
    """Format address dict as multi-line string"""
    lines = []
    if addr.get('name'):
        lines.append(addr['name'])
    if addr.get('line1'):
        lines.append(addr['line1'])
    if addr.get('line2'):
        lines.append(addr['line2'])
    city_state_zip = f"{addr.get('city', '')}, {addr.get('state', '')} {addr.get('zip', '')}".strip()
    if city_state_zip and city_state_zip != ', ':
        lines.append(city_state_zip)
    return '\n'.join(lines)


def generate_qb_entry_text(order: Dict) -> str:
    """Generate formatted text for manual QB entry"""
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"ORDER #{order['order_number']}")
    lines.append(f"{'='*60}")
    lines.append("")

    # Customer
    lines.append(f"CUSTOMER: {order['customer_name']}")
    lines.append(f"EMAIL: {order['customer_email']}")
    if order['customer_phone']:
        lines.append(f"PHONE: {order['customer_phone']}")
    lines.append("")

    # Dates
    lines.append(f"ORDER DATE: {order['order_date']}")
    if order['ship_date']:
        lines.append(f"SHIP DATE: {order['ship_date']}")
    lines.append(f"TAX CODE: {'Tax' if order['is_taxable'] else 'Non'}")
    lines.append("")

    # Ship To
    lines.append("SHIP TO:")
    ship_addr = format_address(order['shipping_address'])
    for line in ship_addr.split('\n'):
        lines.append(f"  {line}")
    lines.append("")

    # Line Items
    lines.append("LINE ITEMS:")
    lines.append("-" * 50)
    for item in order['line_items']:
        desc = item['description'][:40]
        qty = item['quantity']
        price = item['unit_price']
        total = item['line_total']
        lines.append(f"  {desc}")
        lines.append(f"    Qty: {qty}  @  ${price:.2f}  =  ${total:.2f}")

    # Discounts
    if order['discounts']:
        lines.append("")
        lines.append("DISCOUNTS:")
        for disc in order['discounts']:
            lines.append(f"  {disc['name']}: -${disc['amount']:.2f}")

    # Totals
    lines.append("")
    lines.append("-" * 50)
    lines.append(f"SUBTOTAL:     ${order['subtotal']:.2f}")
    if order['discount_total'] > 0:
        lines.append(f"DISCOUNT:    -${order['discount_total']:.2f}")
    lines.append(f"SHIPPING:     ${order['shipping_total']:.2f}")
    lines.append(f"TAX:          ${order['tax_total']:.2f}")
    lines.append(f"TOTAL:        ${order['grand_total']:.2f}")

    # Payment info
    if order.get('payment_matched'):
        lines.append("")
        lines.append("PAYMENT:")
        lines.append(f"  Source: {order['payment_source']}")
        lines.append(f"  Net Received: ${order['net_amount']:.2f}")
        lines.append(f"  Processing Fee: ${order['processing_fee']:.2f}")

    lines.append("")
    return '\n'.join(lines)


def generate_tab_separated_summary(orders: List[Dict]) -> str:
    """Generate tab-separated data for copying to Excel"""
    lines = []

    # Header
    header = [
        'Order #', 'Date', 'Customer', 'Email', 'Ship To State',
        'Subtotal', 'Shipping', 'Tax', 'Discount', 'Total',
        'Payment Source', 'Net', 'Fee', 'Taxable'
    ]
    lines.append('\t'.join(header))

    # Data rows
    for order in orders:
        row = [
            order['order_number'],
            order['order_date'],
            order['customer_name'],
            order['customer_email'],
            order['shipping_address'].get('state', ''),
            f"{order['subtotal']:.2f}",
            f"{order['shipping_total']:.2f}",
            f"{order['tax_total']:.2f}",
            f"{order['discount_total']:.2f}",
            f"{order['grand_total']:.2f}",
            order.get('payment_source', '') or '',
            f"{order.get('net_amount', 0) or 0:.2f}",
            f"{order.get('processing_fee', 0) or 0:.2f}",
            'Yes' if order['is_taxable'] else 'No'
        ]
        lines.append('\t'.join(row))

    return '\n'.join(lines)


def generate_line_items_table(orders: List[Dict]) -> str:
    """Generate tab-separated line items for all orders"""
    lines = []

    # Header
    header = ['Order #', 'Customer', 'Product', 'Variant', 'Qty', 'Unit Price', 'Line Total']
    lines.append('\t'.join(header))

    # Data rows
    for order in orders:
        for item in order['line_items']:
            row = [
                order['order_number'],
                order['customer_name'],
                item['product'],
                item['variant'],
                str(item['quantity']),
                f"{item['unit_price']:.2f}",
                f"{item['line_total']:.2f}"
            ]
            lines.append('\t'.join(row))

        # Add shipping as line item
        if order['shipping_total'] > 0:
            row = [
                order['order_number'],
                order['customer_name'],
                'Freight',
                '',
                '1',
                f"{order['shipping_total']:.2f}",
                f"{order['shipping_total']:.2f}"
            ]
            lines.append('\t'.join(row))

        # Add discounts
        for disc in order['discounts']:
            row = [
                order['order_number'],
                order['customer_name'],
                disc['name'],
                'Discount',
                '1',
                f"-{disc['amount']:.2f}",
                f"-{disc['amount']:.2f}"
            ]
            lines.append('\t'.join(row))

    return '\n'.join(lines)
