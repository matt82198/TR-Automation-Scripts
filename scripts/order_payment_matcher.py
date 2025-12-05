"""
Order Payment Matcher
Matches specific Squarespace order numbers to Stripe/PayPal transactions
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher


class SquarespaceOrderFetcher:
    """Fetch specific orders from Squarespace API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.squarespace.com/1.0/commerce"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def fetch_orders_by_numbers(self, order_numbers: List[str]) -> List[Dict]:
        """Fetch specific orders by order number"""
        order_set = set(str(n) for n in order_numbers)
        found_orders = []
        cursor = None

        while order_set:
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

    def extract_order_info(self, order: Dict) -> Dict:
        """Extract relevant info from order for matching"""
        billing = order.get('billingAddress', {})

        first_name = billing.get('firstName', '').strip()
        last_name = billing.get('lastName', '').strip()
        full_name = f"{first_name} {last_name}".strip()

        created = order.get("createdOn", "")
        order_date = ""
        if created:
            order_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            order_date = order_dt.strftime('%Y-%m-%d')

        grand_total = order.get('grandTotal', {}).get('value', 0)
        grand_total = float(grand_total) if grand_total else 0.0

        return {
            'order_number': str(order.get('orderNumber', '')),
            'date': order_date,
            'customer_name': full_name,
            'customer_email': order.get('customerEmail', '').strip().lower(),
            'gross_amount': grand_total,
            'fulfillment_status': order.get('fulfillmentStatus', ''),
        }


class PaymentMatcher:
    """Match Squarespace orders to payment transactions"""

    def __init__(self, tolerance_days: int = 3, amount_tolerance: float = 0.02):
        self.tolerance_days = tolerance_days
        self.amount_tolerance = amount_tolerance

    def normalize_name(self, name: str) -> str:
        return ' '.join(name.lower().split())

    def names_match(self, name1: str, name2: str) -> bool:
        n1 = self.normalize_name(name1)
        n2 = self.normalize_name(name2)
        if not n1 or not n2:
            return False
        if n1 == n2:
            return True
        if n1 in n2 or n2 in n1:
            return True
        return SequenceMatcher(None, n1, n2).ratio() > 0.8

    def amounts_match(self, amt1: float, amt2: float) -> bool:
        return abs(amt1 - amt2) <= self.amount_tolerance

    def dates_match(self, date1: str, date2: str) -> bool:
        try:
            d1 = datetime.strptime(date1, '%Y-%m-%d')
            d2 = datetime.strptime(date2, '%Y-%m-%d')
            return abs((d1 - d2).days) <= self.tolerance_days
        except:
            return False

    def find_match(self, order: Dict, transactions: List[Dict]) -> Optional[Dict]:
        """Find matching transaction for an order"""
        order_email = (order.get('customer_email') or '').lower()
        order_name = order.get('customer_name') or ''
        order_amount = order.get('gross_amount') or 0
        order_date = order.get('date') or ''

        best_match = None
        best_score = 0

        for txn in transactions:
            if txn.get('_matched'):
                continue

            txn_email = (txn.get('customer_email') or '').lower()
            txn_name = txn.get('customer_name') or ''
            txn_amount = txn.get('gross_amount') or 0
            txn_date = txn.get('date') or ''

            if not self.amounts_match(order_amount, txn_amount):
                continue
            if not self.dates_match(order_date, txn_date):
                continue

            score = 0
            if order_email and txn_email and order_email == txn_email:
                score += 100
            if self.names_match(order_name, txn_name):
                score += 50
            if order_date == txn_date:
                score += 10

            if score > best_score:
                best_score = score
                best_match = txn

        return best_match

    def match_orders(self, orders: List[Dict], transactions: List[Dict], order_numbers: List[str] = None) -> List[Dict]:
        """Match orders to payments, preserving input order"""
        results = []

        for txn in transactions:
            txn['_matched'] = False

        # Create lookup by order number
        order_lookup = {o['order_number']: o for o in orders}

        # Process in original order if provided
        if order_numbers:
            ordered_list = []
            for num in order_numbers:
                if num in order_lookup:
                    ordered_list.append(order_lookup[num])
            orders = ordered_list

        for order in orders:
            match = self.find_match(order, transactions)

            result = {
                'order_number': order['order_number'],
                'order_date': order['date'],
                'customer_name': order['customer_name'],
                'customer_email': order['customer_email'],
                'gross_amount': order['gross_amount'],
                'matched': False,
                'payment_source': None,
                'net_amount': None,
                'processing_fee': None,
                'write_off': None,
                'transaction_id': None,
            }

            if match:
                match['_matched'] = True
                result['matched'] = True
                result['payment_source'] = match['source']
                result['net_amount'] = match['net_amount']
                result['processing_fee'] = match['processing_fee']
                result['write_off'] = round(order['gross_amount'] - match['net_amount'], 2)
                result['transaction_id'] = match['transaction_id']

            results.append(result)

        return results


def match_order_batch(order_numbers: List[str],
                      ss_api_key: str,
                      stripe_transactions: List[Dict],
                      paypal_transactions: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Match a batch of order numbers to payment transactions

    Args:
        order_numbers: List of Squarespace order numbers to match
        ss_api_key: Squarespace API key
        stripe_transactions: List of Stripe transactions from payment_fetch
        paypal_transactions: List of PayPal transactions from payment_fetch

    Returns:
        Tuple of (matched_results, summary_stats)
    """
    fetcher = SquarespaceOrderFetcher(ss_api_key)
    orders_raw = fetcher.fetch_orders_by_numbers(order_numbers)
    orders = [fetcher.extract_order_info(o) for o in orders_raw]

    all_transactions = stripe_transactions + paypal_transactions

    matcher = PaymentMatcher()
    results = matcher.match_orders(orders, all_transactions, order_numbers)

    matched = [r for r in results if r['matched']]
    unmatched = [r for r in results if not r['matched']]

    summary = {
        'total_orders': len(results),
        'matched': len(matched),
        'unmatched': len(unmatched),
        'total_gross': sum(r['gross_amount'] for r in matched),
        'total_net': sum(r['net_amount'] or 0 for r in matched),
        'total_fees': sum(r['processing_fee'] or 0 for r in matched),
        'total_write_off': sum(r['write_off'] or 0 for r in matched),
        'not_found': [n for n in order_numbers if n not in [r['order_number'] for r in results]],
    }

    return results, summary
