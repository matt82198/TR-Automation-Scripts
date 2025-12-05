"""
Mystery Bundle Counter
Count total sides/horsefronts needed for holiday mystery bundles in pending Squarespace orders.

Usage:
    python mystery_bundle_counter.py
    python mystery_bundle_counter.py --status PENDING
    python mystery_bundle_counter.py --status FULFILLED
"""

import argparse
import os
import sys
import requests
from collections import defaultdict
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_secret(key: str, default: str = None) -> str:
    """Get secret from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


# Squarespace API configuration
SQUARESPACE_API_KEY = get_secret('SQUARESPACE_API_KEY')
SQUARESPACE_API_URL = "https://api.squarespace.com/1.0/commerce/orders"


def get_headers():
    """Get API headers"""
    return {
        "Authorization": f"Bearer {SQUARESPACE_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "TanneryRow/1.0"
    }


def fetch_orders(status: str = "PENDING") -> List[dict]:
    """Fetch orders from Squarespace API"""
    orders = []
    cursor = None

    while True:
        # Cursor already contains filter info, don't mix with other params
        if cursor:
            params = {"cursor": cursor}
        else:
            params = {"fulfillmentStatus": status}

        response = requests.get(
            SQUARESPACE_API_URL,
            headers=get_headers(),
            params=params
        )

        if response.status_code != 200:
            print(f"Error fetching orders: {response.status_code}")
            break

        data = response.json()
        orders.extend(data.get("result", []))

        pagination = data.get("pagination", {})
        if pagination.get("hasNextPage"):
            cursor = pagination.get("nextPageCursor")
        else:
            break

    return orders


def parse_variant_quantity(variant: str) -> Tuple[int, str]:
    """
    Parse variant string to extract quantity and unit type.
    Returns (quantity, unit_type)

    Examples:
        "6 Double Horsefronts" -> (6, "Double Horsefronts")
        "10 Sides" -> (10, "Sides")
        "1 Side" -> (1, "Side")
        "3 Double Horsefronts" -> (3, "Double Horsefronts")
    """
    variant = variant.strip()
    parts = variant.split(" ", 1)

    if len(parts) >= 2:
        try:
            qty = int(parts[0])
            unit = parts[1]
            return qty, unit
        except ValueError:
            pass

    return 1, variant


def is_mystery_bundle(product_name: str) -> bool:
    """Check if product is a mystery bundle"""
    name_lower = product_name.lower()
    return "mystery bundle" in name_lower or "mystery" in name_lower


def categorize_bundle(product_name: str) -> str:
    """Categorize the mystery bundle type"""
    name_lower = product_name.lower()

    if "horsefront" in name_lower:
        return "Horsefront Mystery Bundle"
    elif "6 oz+" in name_lower or "6oz+" in name_lower or "over 6" in name_lower:
        return "Horween 6oz+ Mystery Bundle"
    elif "3.5-6" in name_lower or "under 6" in name_lower:
        return "Horween 3.5-6oz Mystery Bundle"
    elif "splenda" in name_lower:
        return "Splenda Mystery Bundle"
    elif "tempesti" in name_lower:
        return "Tempesti Mystery Bundle"
    elif "arazzo" in name_lower:
        return "Arazzo Mystery Bundle"
    elif "cavalier" in name_lower:
        if "6oz" in name_lower or "6 oz" in name_lower:
            return "Cavalier 6oz+ Mystery Bundle"
        else:
            return "Cavalier 3.5-6oz Mystery Bundle"
    else:
        return "Other Mystery Bundle"


def count_mystery_bundles(orders: List[dict]) -> Dict:
    """
    Count mystery bundle quantities from orders.
    Returns dict with categories and order details.
    """
    results = {
        "categories": defaultdict(lambda: {"total": 0, "orders": []}),
        "total_orders_with_bundles": 0,
        "order_list": []
    }

    orders_with_bundles = set()

    for order in orders:
        order_number = order.get("orderNumber", "Unknown")
        customer_email = order.get("customerEmail", "")
        billing_name = ""
        if order.get("billingAddress"):
            billing_name = f"{order['billingAddress'].get('firstName', '')} {order['billingAddress'].get('lastName', '')}".strip()

        order_bundles = []

        for item in order.get("lineItems", []):
            product_name = item.get("productName", "")

            if not is_mystery_bundle(product_name):
                continue

            # Get variant info
            variant_options = item.get("variantOptions", [])
            variant_str = " - ".join(v.get("value", "") for v in variant_options)

            # Parse quantity from variant
            qty_from_variant, unit = parse_variant_quantity(variant_str)

            # Get line item quantity (number of times this variant was ordered)
            line_qty = item.get("quantity", 1)

            # Total quantity
            total_qty = qty_from_variant * line_qty

            # Categorize
            category = categorize_bundle(product_name)

            # Add to results
            results["categories"][category]["total"] += total_qty
            results["categories"][category]["orders"].append({
                "order_number": order_number,
                "customer": billing_name or customer_email,
                "quantity": total_qty,
                "variant": variant_str,
                "unit": unit
            })

            # Build display string showing qty breakdown if line_qty > 1
            if line_qty > 1:
                qty_display = f"{total_qty} ({line_qty}x {variant_str})"
            else:
                qty_display = f"{total_qty} ({variant_str})"

            order_bundles.append({
                "category": category,
                "quantity": total_qty,
                "variant": variant_str,
                "unit": unit,
                "qty_display": qty_display
            })

            orders_with_bundles.add(order_number)

        if order_bundles:
            results["order_list"].append({
                "order_number": order_number,
                "customer": billing_name or customer_email,
                "bundles": order_bundles
            })

    results["total_orders_with_bundles"] = len(orders_with_bundles)

    return results


def print_results(results: Dict, status: str):
    """Print formatted results"""
    print()
    print("=" * 70)
    print(f"MYSTERY BUNDLE COUNT - {status} ORDERS")
    print("=" * 70)

    if not results["categories"]:
        print("\nNo mystery bundles found in pending orders.")
        return

    print(f"\nTotal orders with mystery bundles: {results['total_orders_with_bundles']}")
    print()

    # Summary by category
    print("-" * 70)
    print("SUMMARY BY CATEGORY")
    print("-" * 70)

    grand_total_sides = 0
    grand_total_horsefronts = 0
    grand_total_shoulders = 0

    for category in sorted(results["categories"].keys()):
        data = results["categories"][category]
        total = data["total"]

        # Determine unit type based on category
        if "horsefront" in category.lower():
            unit = "Double Horsefronts"
            grand_total_horsefronts += total
        elif "tempesti" in category.lower() or "splenda" in category.lower():
            unit = "Double Shoulders"
            grand_total_shoulders += total
        else:
            unit = "Sides"
            grand_total_sides += total

        print(f"\n{category}:")
        print(f"  Total: {total} {unit}")
        print(f"  Orders: {len(data['orders'])}")

    print()
    print("-" * 70)
    print("GRAND TOTALS")
    print("-" * 70)
    if grand_total_sides > 0:
        print(f"  Total Sides needed: {grand_total_sides}")
    if grand_total_horsefronts > 0:
        print(f"  Total Double Horsefronts needed: {grand_total_horsefronts}")
    if grand_total_shoulders > 0:
        print(f"  Total Double Shoulders needed: {grand_total_shoulders}")

    # Detailed order list
    print()
    print("-" * 70)
    print("ORDERS WITH MYSTERY BUNDLES")
    print("-" * 70)

    for order_info in sorted(results["order_list"], key=lambda x: x["order_number"]):
        print(f"\nOrder #{order_info['order_number']} - {order_info['customer']}")
        for bundle in order_info["bundles"]:
            print(f"  - {bundle['category']}: {bundle['qty_display']}")

    print()
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Count mystery bundles in Squarespace orders")
    parser.add_argument("--status", type=str, default="PENDING",
                       choices=["PENDING", "FULFILLED"],
                       help="Order fulfillment status to check")

    args = parser.parse_args()

    if not SQUARESPACE_API_KEY:
        print("Error: SQUARESPACE_API_KEY environment variable not set")
        sys.exit(1)

    print(f"Fetching {args.status} orders from Squarespace...")
    orders = fetch_orders(args.status)
    print(f"Found {len(orders)} {args.status.lower()} orders")

    results = count_mystery_bundles(orders)
    print_results(results, args.status)


if __name__ == "__main__":
    main()
