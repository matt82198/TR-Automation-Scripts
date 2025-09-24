"""
Squarespace Panel Calculator
Simple aggregation of panel orders from pending orders
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import os


def extract_panel_info(item: Dict, debug: bool = False) -> Tuple:
    """
    Extract panel size and weight from order item
    Returns: (size, weight, quantity) or (None, None, 0) if not a panel product
    """
    # Get product name
    product_name = item.get("productName", "")

    # Skip if this isn't a panel product
    if "panel" not in product_name.lower():
        return None, None, 0

    quantity = item.get("quantity", 1)

    # Get all variant options
    variants = item.get("variantOptions", [])
    if variants is None:
        variants = []

    # Create a combined string of all variant values
    all_variant_values = " ".join([str(v.get("value", "")) for v in variants if v])

    # Debug first few items
    if debug:
        print(f"\nProduct: {product_name}")
        print(f"Variant values: {all_variant_values}")

    # Extract size - look for standalone 1 or 2
    size = None
    # Split into words/tokens and look for 1 or 2
    tokens = all_variant_values.split()
    for token in tokens:
        # Clean token of common suffixes
        clean_token = token.strip("'\"").lower()
        if clean_token == "1" or clean_token == "1'":
            size = "1'"
            break
        elif clean_token == "2" or clean_token == "2'":
            size = "2'"
            break

    # Extract weight - look for patterns with oz
    weight = None
    variant_lower = all_variant_values.lower()
    if "5-6" in variant_lower or "5-6oz" in variant_lower or "5-6z" in variant_lower:
        weight = "5-6oz"
    elif "3-4" in variant_lower or "3-4oz" in variant_lower or "3-4z" in variant_lower:
        weight = "3-4oz"
    # Also check for patterns without hyphen
    elif "56oz" in variant_lower or "56z" in variant_lower:
        weight = "5-6oz"
    elif "34oz" in variant_lower or "34z" in variant_lower:
        weight = "3-4oz"

    if debug:
        print(f"Extracted -> Size: {size}, Weight: {weight}")

    return size, weight, quantity


def calculate_totals(orders: List[Dict]) -> Tuple[Dict, List[Any]]:
    """
    Calculate total panels needed from orders
    Returns tuple of (dictionary with panel counts by type, list of unspecified items)
    """
    # Use defaultdict to automatically handle new panel types
    totals = defaultdict(int)
    unspecified_items = []
    skipped_count = 0
    debug_count = 0

    for order in orders:
        order_num = order.get("orderNumber")

        for item in order.get("lineItems", []):
            # Enable debug for first 3 panel items to see structure
            debug = debug_count < 3
            size, weight, quantity = extract_panel_info(item, debug=debug)

            if quantity > 0 and debug:
                debug_count += 1

            # Skip non-panel items (where quantity is 0)
            if quantity == 0:
                skipped_count += 1
                continue

            if size and weight:
                # Create key from actual found values
                key = f"{size}_{weight}"
                totals[key] += quantity
            elif quantity > 0:
                # Track panel items that couldn't be categorized
                unspecified_items.append({
                    "order": order_num,
                    "product": item.get("productName"),
                    "quantity": quantity,
                    "missing": f"size: {size or 'unknown'}, weight: {weight or 'unknown'}"
                })
                totals["unspecified"] += quantity

    if skipped_count > 0:
        print(f"Filtered out {skipped_count} non-panel items")

    return dict(totals), unspecified_items


def print_report(totals: Dict, unspecified_items: List):
    """Print a formatted report of panel requirements"""

    print("\n" + "=" * 50)
    print("PANEL TOTALS FROM PENDING ORDERS")
    print("=" * 50)

    grand_total = sum(totals.values())

    if grand_total == 0:
        print("\nNo panels found in orders")
        print("(Only counting products with 'panel' in the name)")
        return

    print(f"\nTotal panels needed: {grand_total}")
    print("\nBreakdown by type:")
    print("-" * 30)

    # Sort for consistent output
    for panel_type in sorted(totals.keys()):
        if panel_type != "unspecified" and totals[panel_type] > 0:
            size, weight = panel_type.split('_')
            print(f"  {size} @ {weight}: {totals[panel_type]} panels")

    if totals.get("unspecified", 0) > 0:
        print(f"\n  Unspecified: {totals['unspecified']} panels")
        print("\n  Items needing review:")
        for item in unspecified_items[:5]:  # Show first 5
            print(f"    - Order #{item['order']}: {item['product']}")
            print(f"      Missing: {item['missing']}")
        if len(unspecified_items) > 5:
            print(f"    ... and {len(unspecified_items) - 5} more")


class SquarespacePanelCalculator:
    """Calculate panel requirements from Squarespace orders"""

    def __init__(self, api_key: str):
        """Initialize with Squarespace API key"""
        self.api_key = api_key
        self.base_url = "https://api.squarespace.com/1.0/commerce"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def test_connection(self) -> bool:
        """Test if the API key works by checking authorization"""
        try:
            print("Testing API connection...")
            # Test with the authorization endpoint first
            response = requests.get(
                "https://api.squarespace.com/1.0/authorization/website",
                headers=self.headers
            )

            print(f"Authorization test status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Connected to site: {data.get('siteTitle', 'Unknown')}")
                print(f"   Site ID: {data.get('id', 'Unknown')}")
                print(f"   URL: {data.get('siteUrl', 'Unknown')}")

                # Now test the orders endpoint
                print("\nTesting Orders API access...")
                orders_response = requests.get(
                    f"{self.base_url}/orders?limit=1",
                    headers=self.headers
                )

                if orders_response.status_code == 200:
                    print("✅ Orders API access confirmed!")
                    return True
                elif orders_response.status_code == 401:
                    print("❌ Orders API access denied. Possible reasons:")
                    print("   1. Your Squarespace plan might need to be Commerce Advanced or Premium")
                    print("   2. The API key might not have 'Orders (Read)' permission")
                    print("   3. Try regenerating the API key with proper permissions")
                    return False
                else:
                    print(f"   Unexpected status: {orders_response.status_code}")
                    return False

            elif response.status_code == 401:
                print("❌ API key is invalid or malformed")
                print("   Check that your API key is copied correctly")
                return False
            else:
                print(f"Unexpected status: {response.status_code}")
                return False
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def fetch_orders(self, fulfillment_status: str = "PENDING", days_back: int = 7) -> List[Dict]:
        """Fetch orders from Squarespace"""
        try:
            modified_after = (datetime.now() - timedelta(days=days_back)).isoformat()

            params = {
                "modifiedAfter": modified_after,
                "fulfillmentStatus": fulfillment_status
            }

            response = requests.get(
                f"{self.base_url}/orders",
                headers=self.headers,
                params=params
            )

            response.raise_for_status()

            orders = response.json().get("result", [])
            print(f"Fetched {len(orders)} {fulfillment_status.lower()} orders")
            return orders

        except requests.exceptions.RequestException as e:
            print(f"Error fetching orders: {e}")
            raise

    def run(self, fulfillment_status: str = "PENDING", days_back: int = 7) -> Dict:
        """
        Main method to fetch orders and calculate totals

        Returns:
            Dictionary with panel totals by type
        """
        # Fetch orders
        orders = self.fetch_orders(fulfillment_status, days_back)

        if not orders:
            print("No orders found")
            return {}

        # Calculate totals using standalone function
        totals, unspecified_items = calculate_totals(orders)

        # Print report using standalone function
        print_report(totals, unspecified_items)

        return totals


def main():
    """Main function to run the panel calculator"""

    # Get API key - you can use environment variable or hardcode for testing
    # Option 1: Environment variable (recommended for production)
    api_key = os.environ.get("SS_API_KEY")

    # Option 2: Hardcode for testing (replace with your actual key)
    if not api_key:
        api_key = "your_api_key_here"  # Replace this with your actual API key

    if api_key == "your_api_key_here":
        print("⚠️ Please set your Squarespace API key!")
        print("\nOption 1 - Set environment variable:")
        print("  Windows: set SQUARESPACE_API_KEY=your-key-here")
        print("  Mac/Linux: export SQUARESPACE_API_KEY=your-key-here")
        print("\nOption 2 - Replace 'your_api_key_here' in the code")
        return

    # Create calculator instance
    calculator = SquarespacePanelCalculator(api_key)

    # Test the connection first
    if not calculator.test_connection():
        print("\n" + "="*60)
        print("TROUBLESHOOTING GUIDE:")
        print("="*60)
        print("\n1. Check your Squarespace plan:")
        print("   - Orders API requires Commerce Advanced or Premium plan")
        print("   - Check: Settings → Billing & Account → Plan")
        print("\n2. Verify API key permissions:")
        print("   - Go to: Settings → Advanced → Developer API Keys")
        print("   - Ensure 'Orders (Read)' is checked")
        print("\n3. Generate a new API key if needed:")
        print("   - Delete the old key and create a new one")
        print("   - Make sure to copy it correctly (no extra spaces)")
        return

    # Run and get totals
    totals = calculator.run(
        fulfillment_status="PENDING",  # or "FULFILLED"
        days_back=7
    )

    # The totals dictionary contains your panel counts
    # You can use this data however you need
    if totals:
        print(f"\nReturned data: {totals}")


if __name__ == "__main__":
    main()