import stripe
import os
import requests
import base64
import csv
from datetime import datetime, timedelta
import argparse
from typing import List, Dict, Any, Optional

# API Keys - READ-ONLY access
stripe.api_key = os.environ.get('STRIPE_API_KEY')
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')
# PAYPAL_MODE defaults to 'live' (your real account). Only set to 'sandbox' for testing
PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'live')


def parse_arguments():
    parser = argparse.ArgumentParser(description='READ-ONLY: Pull transaction data for EOM billing')
    parser.add_argument('--start-date', type=str,
                        default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    parser.add_argument('--end-date', type=str,
                        default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument('--source', choices=['stripe', 'paypal', 'both'], default='both')
    parser.add_argument('--csv', action='store_true', help='Export to CSV')
    return parser.parse_args()


def get_paypal_readonly_token() -> Optional[str]:
    """
    READ-ONLY: Gets authentication token for PayPal
    This token can ONLY read data, cannot create/modify transactions
    """
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        return None

    base_url = 'https://api-m.paypal.com' if PAYPAL_MODE == 'live' else 'https://api-m.sandbox.paypal.com'

    credentials = f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    try:
        # READ-ONLY: This just gets an auth token, doesn't modify anything
        response = requests.post(
            f'{base_url}/v1/oauth2/token',
            headers={
                'Authorization': f'Basic {encoded}',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data={'grant_type': 'client_credentials'}
        )
        response.raise_for_status()
        return response.json().get('access_token')
    except Exception as e:
        print(f"PayPal auth failed: {e}")
        return None


def fetch_stripe_readonly(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    READ-ONLY: Fetches existing Stripe transactions
    Uses only stripe.Charge.list() and stripe.BalanceTransaction.retrieve()
    CANNOT create, modify, or delete anything
    """
    if not stripe.api_key:
        print("WARNING: Stripe API key not set")
        return []

    print(f"READ-ONLY: Fetching Stripe transactions from {start_date} to {end_date}...")

    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
    end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp()) + 86400

    transactions = []
    has_more = True
    starting_after = None

    while has_more:
        # READ-ONLY API call - only lists existing charges
        params = {
            'limit': 100,
            'created': {'gte': start_ts, 'lt': end_ts}
        }
        if starting_after:
            params['starting_after'] = starting_after

        try:
            charges = stripe.Charge.list(**params)  # READ-ONLY operation

            for charge in charges.data:
                if charge.status != 'succeeded':
                    continue

                gross = charge.amount / 100
                fee = 0
                net = gross

                # READ-ONLY: Get fee details from existing transaction
                if charge.balance_transaction:
                    try:
                        balance_txn = stripe.BalanceTransaction.retrieve(
                            charge.balance_transaction  # READ-ONLY operation
                        )
                        fee = balance_txn.fee / 100
                        net = balance_txn.net / 100
                    except:
                        pass

                billing = charge.billing_details or {}

                transactions.append({
                    'date': datetime.fromtimestamp(charge.created).strftime('%Y-%m-%d'),
                    'customer_name': billing.get('name', 'N/A'),
                    'customer_email': billing.get('email', charge.receipt_email or 'N/A'),
                    'gross_amount': gross,
                    'processing_fee': fee,
                    'net_amount': net,
                    'source': 'Stripe',
                    'transaction_id': charge.id
                })

            has_more = charges.has_more
            if has_more and charges.data:
                starting_after = charges.data[-1].id

            print(f"  Found {len(transactions)} Stripe transactions so far...")

        except stripe.error.StripeError as e:
            print(f"Error reading Stripe data: {e}")
            break

    return transactions


def fetch_paypal_readonly(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    READ-ONLY: Fetches existing PayPal transactions
    Uses only GET requests to /v1/reporting/transactions
    CANNOT create, modify, or delete anything
    """
    token = get_paypal_readonly_token()
    if not token:
        print("WARNING: PayPal credentials not set")
        return []

    print(f"READ-ONLY: Fetching PayPal transactions from {start_date} to {end_date}...")

    base_url = 'https://api-m.paypal.com' if PAYPAL_MODE == 'live' else 'https://api-m.sandbox.paypal.com'

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    transactions = []

    # READ-ONLY API call - only GET request to read transactions
    params = {
        'start_date': f"{start_date}T00:00:00.000Z",
        'end_date': f"{end_date}T23:59:59.999Z",
        'fields': 'all',
        'page_size': 100,
        'page': 1
    }

    try:
        # READ-ONLY: GET request only reads data
        response = requests.get(  # GET = READ-ONLY
            f'{base_url}/v1/reporting/transactions',
            headers=headers,
            params=params
        )

        if response.status_code == 403:
            print("\nWARNING: PayPal Transaction Search is disabled.")
            print("   To enable: Call PayPal Support at 1-888-221-1161")
            print("   Ask them to enable 'Transaction Search API'")
            print("\n   Alternative: Download CSV from PayPal Dashboard:")
            print("   Activity -> Statements -> Activity download")
            return []

        response.raise_for_status()
        data = response.json()

        for txn in data.get('transaction_details', []):
            info = txn.get('transaction_info', {})

            # Skip non-successful
            if info.get('transaction_status') not in ['S', 'Completed']:
                continue

            gross = abs(float(info.get('transaction_amount', {}).get('value', 0)))
            fee = abs(float(info.get('fee_amount', {}).get('value', 0)))
            net = gross - fee

            payer = txn.get('payer_info', {})
            name_info = payer.get('payer_name', {})
            name = f"{name_info.get('given_name', '')} {name_info.get('surname', '')}".strip()

            date_str = info.get('transaction_initiated_date', '')
            if date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%Y-%m-%d')
            else:
                formatted_date = start_date

            transactions.append({
                'date': formatted_date,
                'customer_name': name or 'N/A',
                'customer_email': payer.get('email_address', 'N/A'),
                'gross_amount': gross,
                'processing_fee': fee,
                'net_amount': net,
                'source': 'PayPal',
                'transaction_id': info.get('transaction_id', 'N/A')
            })

        print(f"  Found {len(transactions)} PayPal transactions")

    except requests.RequestException as e:
        print(f"Error reading PayPal data: {e}")

    return transactions


def display_summary(transactions: List[Dict[str, Any]]) -> None:
    """Display EOM billing summary (READ-ONLY - just prints to screen)"""
    if not transactions:
        print("\nNo transactions found")
        return

    print(f"\n{'=' * 60}")
    print("EOM BILLING SUMMARY")
    print(f"{'=' * 60}")

    # Calculate totals by source
    totals = {}
    for source in ['Stripe', 'PayPal']:
        source_txns = [t for t in transactions if t['source'] == source]
        if source_txns:
            totals[source] = {
                'count': len(source_txns),
                'gross': sum(t['gross_amount'] for t in source_txns),
                'fees': sum(t['processing_fee'] for t in source_txns),
                'net': sum(t['net_amount'] for t in source_txns)
            }

    # Display by source
    for source, data in totals.items():
        print(f"\n{source}:")
        print(f"  Transactions: {data['count']}")
        print(f"  Gross Revenue: ${data['gross']:,.2f}")
        print(f"  Processing Fees: ${data['fees']:,.2f}")
        print(f"  Net Revenue: ${data['net']:,.2f}")
        if data['gross'] > 0:
            print(f"  Fee Rate: {(data['fees'] / data['gross'] * 100):.2f}%")

    # Grand total
    if len(totals) > 1:
        print(f"\n{'=' * 30}")
        print("COMBINED TOTAL:")
        total_gross = sum(d['gross'] for d in totals.values())
        total_fees = sum(d['fees'] for d in totals.values())
        total_net = sum(d['net'] for d in totals.values())
        print(f"  All Transactions: {len(transactions)}")
        print(f"  Total Gross: ${total_gross:,.2f}")
        print(f"  Total Fees: ${total_fees:,.2f}")
        print(f"  Total Net: ${total_net:,.2f}")
        if total_gross > 0:
            print(f"  Overall Fee Rate: {(total_fees / total_gross * 100):.2f}%")


def export_csv(transactions: List[Dict[str, Any]], start_date: str, end_date: str) -> None:
    """Export to CSV (READ-ONLY - just creates a local file)"""
    filename = f"eom_billing_{start_date}_to_{end_date}.csv"

    with open(filename, 'w', newline='') as f:
        fields = ['date', 'source', 'customer_name', 'customer_email',
                  'gross_amount', 'processing_fee', 'net_amount', 'transaction_id']
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for txn in sorted(transactions, key=lambda x: x['date']):
            writer.writerow(txn)

    print(f"\nSUCCESS: Exported to {filename}")


def main():
    print("=" * 60)
    print("EOM BILLING REPORT - 100% READ-ONLY")
    print("This script ONLY reads existing transaction data")
    print("It CANNOT create, modify, or delete anything")
    print("=" * 60)

    args = parse_arguments()

    all_transactions = []

    # READ-ONLY: Fetch from selected sources
    if args.source in ['stripe', 'both']:
        stripe_txns = fetch_stripe_readonly(args.start_date, args.end_date)
        all_transactions.extend(stripe_txns)

    if args.source in ['paypal', 'both']:
        paypal_txns = fetch_paypal_readonly(args.start_date, args.end_date)
        all_transactions.extend(paypal_txns)

    # Display summary
    display_summary(all_transactions)

    # Export if requested
    if args.csv and all_transactions:
        export_csv(all_transactions, args.start_date, args.end_date)

    # Show setup help if needed
    if not all_transactions:
        print("\nSetup Instructions:")
        if not stripe.api_key:
            print("  Stripe: export STRIPE_API_KEY='sk_live_...'")
        if not PAYPAL_CLIENT_ID:
            print("  PayPal: export PAYPAL_CLIENT_ID='...'")
            print("          export PAYPAL_CLIENT_SECRET='...'")


if __name__ == "__main__":
    main()