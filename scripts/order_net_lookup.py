"""
Order Net Lookup
Look up net payment received for specific Squarespace order(s).
Matches orders to Stripe/PayPal transactions and shows gross, fees, and net.
"""

import argparse
import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.payment_fetch import fetch_stripe_readonly, fetch_paypal_readonly
from scripts.order_payment_matcher import SquarespaceOrderFetcher, PaymentMatcher


def get_secret(key, default=None):
    """Get secret from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    # Try loading from secrets.toml directly
    try:
        import tomllib
        toml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 '.streamlit', 'secrets.toml')
        with open(toml_path, 'rb') as f:
            secrets = tomllib.load(f)
        if key in secrets:
            return secrets[key]
    except Exception:
        pass

    return os.environ.get(key, default)


def main():
    parser = argparse.ArgumentParser(description='Look up net payment received for Squarespace order(s)')
    parser.add_argument('order_numbers', type=str,
                        help='Order number(s) to look up. Comma-separated for multiple: 13536,13537')
    parser.add_argument('--days', type=int, default=90,
                        help='How many days back to search for payments (default: 90)')
    parser.add_argument('--source', choices=['stripe', 'paypal', 'both'], default='both',
                        help='Payment source to search (default: both)')
    args = parser.parse_args()

    order_list = [n.strip() for n in args.order_numbers.split(',')]

    # Initialize Stripe API key
    import stripe
    stripe.api_key = get_secret('STRIPE_API_KEY')

    ss_api_key = get_secret('SQUARESPACE_API_KEY')
    if not ss_api_key:
        print("ERROR: SQUARESPACE_API_KEY not set")
        return

    # Fetch orders from Squarespace
    print(f"Fetching {len(order_list)} order(s) from Squarespace...")
    fetcher = SquarespaceOrderFetcher(ss_api_key)
    orders_raw = fetcher.fetch_orders_by_numbers(order_list)
    orders = [fetcher.extract_order_info(o) for o in orders_raw]

    if not orders:
        print("No orders found")
        return

    # Determine date range from order dates
    from datetime import datetime, timedelta
    order_dates = []
    for o in orders:
        if o.get('date'):
            order_dates.append(datetime.strptime(o['date'], '%Y-%m-%d'))

    if order_dates:
        earliest = min(order_dates) - timedelta(days=3)
        latest = max(order_dates) + timedelta(days=3)
    else:
        latest = datetime.now()
        earliest = latest - timedelta(days=args.days)

    start_date = earliest.strftime('%Y-%m-%d')
    end_date = latest.strftime('%Y-%m-%d')

    # Fetch payment transactions
    all_transactions = []
    if args.source in ('stripe', 'both'):
        stripe_txns = fetch_stripe_readonly(start_date, end_date)
        all_transactions.extend(stripe_txns)

    if args.source in ('paypal', 'both'):
        paypal_txns = fetch_paypal_readonly(start_date, end_date)
        all_transactions.extend(paypal_txns)

    if not all_transactions:
        print("No payment transactions found in date range")
        print(f"  Searched: {start_date} to {end_date}")
        return

    # Match orders to payments
    matcher = PaymentMatcher()
    results = matcher.match_orders(orders, all_transactions, order_list)

    # Display results
    print(f"\n{'='*70}")
    print(f"ORDER NET PAYMENT LOOKUP")
    print(f"{'='*70}\n")

    for r in results:
        print(f"Order #{r['order_number']} - {r['customer_name']}")
        print(f"  Gross:  ${r['gross_amount']:.2f}")

        if r['matched']:
            print(f"  Source: {r['payment_source']}")
            print(f"  Fee:    ${r['processing_fee']:.2f}")
            print(f"  Net:    ${r['net_amount']:.2f}")
            if r['write_off'] and abs(r['write_off']) > 0.01:
                print(f"  Diff:   ${r['write_off']:.2f}")
            print(f"  Txn ID: {r['transaction_id']}")
        else:
            print(f"  ** NO PAYMENT MATCH FOUND **")
        print()

    # Summary for multiple orders
    if len(results) > 1:
        matched = [r for r in results if r['matched']]
        print(f"{'-'*70}")
        print(f"SUMMARY: {len(matched)}/{len(results)} matched")
        if matched:
            total_gross = sum(r['gross_amount'] for r in matched)
            total_fees = sum(r['processing_fee'] or 0 for r in matched)
            total_net = sum(r['net_amount'] or 0 for r in matched)
            print(f"  Total Gross: ${total_gross:.2f}")
            print(f"  Total Fees:  ${total_fees:.2f}")
            print(f"  Total Net:   ${total_net:.2f}")


if __name__ == '__main__':
    main()
