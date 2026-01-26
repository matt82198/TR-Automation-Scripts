import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import stripe

# Get API key from environment variable
stripe.api_key = os.environ.get('STRIPE_INVOICE_PULL_API_KEY')


def parse_arguments():
    """Parse command line arguments for date range"""
    parser = argparse.ArgumentParser(description='Pull Stripe transaction data with net amounts and fees')

    # Add date arguments
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD). Default: 30 days ago',
        default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD). Default: today',
        default=datetime.now().strftime('%Y-%m-%d')
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='Export results to CSV file'
    )

    return parser.parse_args()


def date_to_timestamp(date_str: str) -> int:
    """Convert YYYY-MM-DD string to Unix timestamp"""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return int(dt.timestamp())


def fetch_transactions_with_fees(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Fetch all successful charges/transactions with fees"""
    print(f"Fetching transactions from {start_date} to {end_date}...")

    # Convert dates to timestamps for Stripe API
    start_timestamp = date_to_timestamp(start_date)
    end_timestamp = date_to_timestamp(end_date) + 86400  # Add 1 day to include end date

    all_transaction_data: List[Dict[str, Any]] = []
    has_more = True
    starting_after_id: Optional[str] = None

    while has_more:
        # Build params for charge list - use type Any to avoid type hint issues
        params: Dict[str, Any] = {
            'limit': 100,
            'created': {
                'gte': start_timestamp,
                'lt': end_timestamp
            }
        }

        # Only add starting_after if we have a value
        if starting_after_id is not None:
            params['starting_after'] = starting_after_id

        try:
            # Fetch charges within date range
            charges = stripe.Charge.list(**params)
        except stripe.error.StripeError as e:
            print(f"Error fetching charges: {e}")
            break

        # Process the charges data
        charges_data = charges.get('data', [])

        for charge in charges_data:
            # Skip failed charges
            if charge.get('status') != 'succeeded':
                continue

            # Initialize variables with safe defaults
            fee_amount: float = 0.0
            fee_details: str = ''
            net_amount: float = 0.0

            # Get balance transaction ID safely
            balance_txn_id = charge.get('balance_transaction')

            if balance_txn_id and isinstance(balance_txn_id, str):
                try:
                    balance_txn = stripe.BalanceTransaction.retrieve(balance_txn_id)

                    # Safely get fee and net amounts
                    fee_value = balance_txn.get('fee', 0)
                    net_value = balance_txn.get('net', 0)

                    # Convert to float safely
                    fee_amount = float(fee_value) / 100 if fee_value is not None else 0.0
                    net_amount = float(net_value) / 100 if net_value is not None else 0.0

                    # Get fee breakdown if available
                    fee_details_list = balance_txn.get('fee_details')
                    if fee_details_list and isinstance(fee_details_list, list):
                        fee_types = []
                        for fd in fee_details_list:
                            if isinstance(fd, dict):
                                fee_type = fd.get('type', 'unknown')
                                fee_amt_raw = fd.get('amount', 0)
                                fee_amt = float(fee_amt_raw) / 100 if fee_amt_raw is not None else 0.0
                                fee_types.append(f"{fee_type}: ${fee_amt:.2f}")
                        fee_details = ', '.join(fee_types)

                except stripe.error.StripeError as e:
                    print(f"Warning: Could not fetch fee for charge {charge.get('id', 'unknown')}: {e}")
                    # Fallback calculation
                    amount_value = charge.get('amount', 0)
                    gross = float(amount_value) / 100 if amount_value is not None else 0.0
                    net_amount = gross - fee_amount
            else:
                # No balance transaction - calculate net as gross
                amount_value = charge.get('amount', 0)
                gross = float(amount_value) / 100 if amount_value is not None else 0.0
                net_amount = gross

            # Get customer information safely
            customer_name: str = ''
            customer_email: str = ''

            # Try to get from billing details first
            billing_details = charge.get('billing_details')
            if billing_details and isinstance(billing_details, dict):
                customer_name = str(billing_details.get('name', '') or '')
                customer_email = str(billing_details.get('email', '') or '')

            # If not in billing details and we have a customer ID, fetch customer
            customer_id = charge.get('customer')
            if not customer_name and customer_id and isinstance(customer_id, str):
                try:
                    customer = stripe.Customer.retrieve(customer_id)
                    if not customer_name:
                        name_value = customer.get('name', '')
                        customer_name = str(name_value) if name_value else ''
                    if not customer_email:
                        email_value = customer.get('email', '')
                        customer_email = str(email_value) if email_value else ''
                except stripe.error.StripeError:
                    pass  # Silently fail, we'll use defaults

            # Get receipt email if no customer email
            if not customer_email:
                receipt_email = charge.get('receipt_email', '')
                customer_email = str(receipt_email) if receipt_email else ''

            # Get description safely
            description_value = charge.get('description', '')
            description = str(description_value) if description_value else ''

            # Calculate gross amount
            amount_value = charge.get('amount', 0)
            gross_amount = float(amount_value) / 100 if amount_value is not None else 0.0

            # Get payment method details safely
            payment_method_details = charge.get('payment_method_details')
            payment_method = 'N/A'
            last4 = 'N/A'

            if payment_method_details and isinstance(payment_method_details, dict):
                method_type = payment_method_details.get('type', 'N/A')
                payment_method = str(method_type) if method_type else 'N/A'

                # Get last4 for card payments
                card_details = payment_method_details.get('card')
                if card_details and isinstance(card_details, dict):
                    last4_value = card_details.get('last4', 'N/A')
                    last4 = str(last4_value) if last4_value else 'N/A'

            # Get currency safely
            currency_value = charge.get('currency', 'usd')
            currency = str(currency_value).upper() if currency_value else 'USD'

            # Get created timestamp safely
            created_value = charge.get('created', 0)
            created_timestamp = int(created_value) if created_value else 0

            # Get charge ID safely
            charge_id_value = charge.get('id', 'N/A')
            charge_id = str(charge_id_value) if charge_id_value else 'N/A'

            # Build transaction data
            transaction_data = {
                'date': datetime.fromtimestamp(created_timestamp).strftime('%Y-%m-%d'),
                'time': datetime.fromtimestamp(created_timestamp).strftime('%H:%M:%S'),
                'charge_id': charge_id,
                'customer_id': str(customer_id) if customer_id else 'N/A',
                'customer_name': customer_name or 'N/A',
                'customer_email': customer_email or 'N/A',
                'description': description or 'N/A',
                'gross_amount': gross_amount,
                'processing_fee': fee_amount,
                'net_amount': net_amount,
                'currency': currency,
                'payment_method': payment_method,
                'last4': last4,
                'fee_details': fee_details or 'N/A'
            }

            all_transaction_data.append(transaction_data)

        # Check if there are more results
        has_more = bool(charges.get('has_more', False))

        if has_more and charges_data:
            # Get the last item's ID for pagination
            last_item = charges_data[-1]
            last_id = last_item.get('id')
            if last_id:
                starting_after_id = str(last_id)
            else:
                has_more = False  # Can't paginate without an ID
        else:
            has_more = False

        print(f"Fetched {len(all_transaction_data)} transactions so far...")

    return all_transaction_data


def display_results(transaction_data: List[Dict[str, Any]]) -> None:
    """Display transaction data with net amounts and fees"""
    if not transaction_data:
        print("No transactions found in the specified date range.")
        return

    print(f"\nTotal transactions found: {len(transaction_data)}")
    print("=" * 110)
    print(f"{'Date':<12} {'Customer Name':<25} {'Email':<25} {'Gross':<12} {'Fee':<10} {'Net':<12}")
    print("-" * 110)

    total_gross = 0.0
    total_fees = 0.0
    total_net = 0.0

    for txn in transaction_data:
        # Truncate long names/emails for display
        name = str(txn['customer_name'])
        email = str(txn['customer_email'])

        name_display = (name[:23] + '..') if len(name) > 25 else name
        email_display = (email[:23] + '..') if len(email) > 25 else email

        print(f"{txn['date']:<12} "
              f"{name_display:<25} "
              f"{email_display:<25} "
              f"${txn['gross_amount']:<11.2f} "
              f"${txn['processing_fee']:<9.2f} "
              f"${txn['net_amount']:<11.2f}")

        total_gross += float(txn['gross_amount'])
        total_fees += float(txn['processing_fee'])
        total_net += float(txn['net_amount'])

    print("=" * 110)
    print(f"{'TOTALS':<12} {'':<25} {'':<25} "
          f"${total_gross:<11.2f} "
          f"${total_fees:<9.2f} "
          f"${total_net:<11.2f}")

    print(f"\nSummary:")
    print(f"  Total Gross Revenue: ${total_gross:,.2f}")
    print(f"  Total Processing Fees: ${total_fees:,.2f}")
    print(f"  Total Net Revenue: ${total_net:,.2f}")

    if total_gross > 0:
        print(f"  Average Fee Rate: {(total_fees / total_gross * 100):.2f}%")

    print(f"  Number of Transactions: {len(transaction_data)}")

    if transaction_data:
        print(f"  Average Transaction: ${(total_gross / len(transaction_data)):.2f}")


def export_to_csv(transaction_data: List[Dict[str, Any]], start_date: str, end_date: str) -> None:
    """Export transaction data to CSV file"""
    filename = f"stripe_transactions_{start_date}_to_{end_date}.csv"

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['date', 'time', 'customer_name', 'customer_email', 'description',
                      'gross_amount', 'processing_fee', 'net_amount', 'currency',
                      'payment_method', 'last4', 'charge_id', 'customer_id', 'fee_details']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for txn in transaction_data:
            writer.writerow(txn)

    # Also create a summary CSV
    summary_filename = f"stripe_summary_{start_date}_to_{end_date}.csv"
    with open(summary_filename, 'w', newline='', encoding='utf-8') as csvfile:
        # Group by customer for summary
        customer_totals: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {'gross': 0.0, 'fees': 0.0, 'net': 0.0, 'count': 0, 'email': ''}
        )

        for txn in transaction_data:
            key = str(txn['customer_name'])
            customer_totals[key]['gross'] += float(txn['gross_amount'])
            customer_totals[key]['fees'] += float(txn['processing_fee'])
            customer_totals[key]['net'] += float(txn['net_amount'])
            customer_totals[key]['count'] += 1
            customer_totals[key]['email'] = str(txn['customer_email'])

        writer = csv.writer(csvfile)
        writer.writerow(['Customer Name', 'Email', 'Transaction Count', 'Total Gross', 'Total Fees', 'Total Net'])

        for name, data in sorted(customer_totals.items(), key=lambda x: x[1]['gross'], reverse=True):
            writer.writerow([
                name,
                data['email'],
                data['count'],
                f"{data['gross']:.2f}",
                f"{data['fees']:.2f}",
                f"{data['net']:.2f}"
            ])

    print(f"\n[OK] Transaction details exported to {filename}")
    print(f"[OK] Customer summary exported to {summary_filename}")


def main():
    # Check if API key is set
    if not stripe.api_key:
        print("Error: STRIPE_INVOICE_PULL_API_KEY environment variable not set!")
        print("\nSet it using:")
        print("  export STRIPE_INVOICE_PULL_API_KEY='sk_live_...' # Mac/Linux")
        print("  set STRIPE_INVOICE_PULL_API_KEY=sk_live_...     # Windows")
        return

    # Parse command line arguments
    args = parse_arguments()

    try:
        # Fetch transaction data
        transaction_data = fetch_transactions_with_fees(args.start_date, args.end_date)

        # Display results
        display_results(transaction_data)

        # Export to CSV if requested
        if args.csv:
            export_to_csv(transaction_data, args.start_date, args.end_date)

    except stripe.error.AuthenticationError:
        print("Error: Invalid API key. Please check your STRIPE_INVOICE_PULL_API_KEY.")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()