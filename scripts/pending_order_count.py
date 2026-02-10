"""
Squarespace Panel Counter
Simple panel product counting using modern Squarespace API
"""

import requests
import os
from typing import Dict
from collections import defaultdict


class SquarespacePanelCalculator:
    """Calculate panel counts from Squarespace orders using modern API"""

    def __init__(self, api_key: str):
        """Initialize with Squarespace API key"""
        self.api_key = api_key
        self.base_url = "https://api.squarespace.com/1.0/commerce"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def fetch_orders(self, fulfillment_status: str = "PENDING") -> list:
        """Fetch all orders from Squarespace API with pagination"""
        all_orders = []
        cursor = None

        while True:
            # Cursor already contains filter info, don't mix with other params
            if cursor:
                params = {"cursor": cursor}
            else:
                params = {"fulfillmentStatus": fulfillment_status}

            response = requests.get(
                f"{self.base_url}/orders",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json()

            orders = data.get("result", [])
            all_orders.extend(orders)

            cursor = data.get("pagination", {}).get("nextPageCursor")
            if not cursor:
                break

        return all_orders

    def count_products(self, orders: list) -> Dict[str, Dict[str, Dict]]:
        """Count panel and swatch book products from orders using SKU and variant info"""
        panel_counts = defaultdict(int)
        swatch_book_counts = defaultdict(int)
        panel_details = {}
        swatch_book_details = {}
        # Track items by order number
        orders_by_number = {}

        for order in orders:
            order_number = order.get("orderNumber", "Unknown")
            order_date = order.get("createdOn", "")[:10] if order.get("createdOn") else ""

            if order_number not in orders_by_number:
                orders_by_number[order_number] = {
                    "date": order_date,
                    "panels": [],
                    "swatch_books": []
                }

            for item in order.get("lineItems", []):
                product_name = item.get("productName", "")
                product_name_lower = product_name.lower()
                quantity = item.get("quantity", 0)
                sku = item.get("sku", "")
                product_id = item.get("productId", "")
                variant_id = item.get("variantId", "")

                # Build variant description from variant options
                variant_options = item.get("variantOptions", [])
                variant_desc = " - ".join([f"{opt.get('optionName', '')}: {opt.get('value', '')}"
                                         for opt in variant_options if opt])

                # Create unique identifier using SKU or fallback to product+variant IDs
                unique_id = sku if sku else f"{product_id}_{variant_id}"

                item_info = {
                    "unique_id": unique_id,
                    "product_name": product_name,
                    "variant_description": variant_desc,
                    "quantity": quantity
                }

                if "panel" in product_name_lower:
                    panel_counts[unique_id] += quantity
                    panel_details[unique_id] = {
                        "product_name": product_name,
                        "sku": sku,
                        "variant_description": variant_desc,
                        "product_id": product_id,
                        "variant_id": variant_id
                    }
                    orders_by_number[order_number]["panels"].append(item_info)
                elif "swatch" in product_name_lower and "book" in product_name_lower:
                    swatch_book_counts[unique_id] += quantity
                    swatch_book_details[unique_id] = {
                        "product_name": product_name,
                        "sku": sku,
                        "variant_description": variant_desc,
                        "product_id": product_id,
                        "variant_id": variant_id
                    }
                    orders_by_number[order_number]["swatch_books"].append(item_info)

        # Filter out orders with no panels or swatch books
        orders_by_number = {k: v for k, v in orders_by_number.items()
                           if v["panels"] or v["swatch_books"]}

        return {
            "panels": {"counts": dict(panel_counts), "details": panel_details},
            "swatch_books": {"counts": dict(swatch_book_counts), "details": swatch_book_details},
            "by_order": orders_by_number
        }

    def get_product_counts(self, fulfillment_status: str = "PENDING") -> Dict[str, Dict[str, Dict]]:
        """Main method to get panel and swatch book counts"""
        orders = self.fetch_orders(fulfillment_status)
        return self.count_products(orders)

    def fetch_all_panel_variants(self) -> list:
        """Fetch all panel product variants from the Squarespace Products API.
        Returns list of dicts with product_name, color, weight."""
        variants = []
        cursor = None

        while True:
            params = {"cursor": cursor} if cursor else {}
            response = requests.get(
                f"{self.base_url}/products",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json()

            for product in data.get("result", []):
                name = product.get("name", "")
                if "panel" not in name.lower():
                    continue

                for variant in product.get("variants", []):
                    attrs = variant.get("attributes", {})
                    color = attrs.get("Color", "")
                    weight = attrs.get("Weight", "")
                    if color:
                        variants.append({
                            'product_name': name,
                            'color': color,
                            'weight': weight
                        })

            cursor = data.get("pagination", {}).get("nextPageCursor")
            if not cursor:
                break

        return variants


def main():
    """Main function"""
    api_key = os.environ.get("SQUARESPACE_API_KEY")

    if not api_key:
        print("Please set SQUARESPACE_API_KEY environment variable")
        return

    calculator = SquarespacePanelCalculator(api_key)
    product_counts = calculator.get_product_counts()

    panels = product_counts["panels"]
    swatch_books = product_counts["swatch_books"]

    print("Panel counts:")
    if panels["counts"]:
        for unique_id, count in panels["counts"].items():
            details = panels["details"][unique_id]
            variant_info = f" ({details['variant_description']})" if details['variant_description'] else ""
            sku_info = f" [SKU: {details['sku']}]" if details['sku'] else f" [ID: {unique_id}]"
            print(f"  {details['product_name']}{variant_info}{sku_info}: {count}")

        panel_total = sum(panels["counts"].values())
        print(f"Total panels: {panel_total}")
    else:
        print("  No panels found")
        print("Total panels: 0")

    print("\nSwatch book counts:")
    if swatch_books["counts"]:
        for unique_id, count in swatch_books["counts"].items():
            details = swatch_books["details"][unique_id]
            variant_info = f" ({details['variant_description']})" if details['variant_description'] else ""
            sku_info = f" [SKU: {details['sku']}]" if details['sku'] else f" [ID: {unique_id}]"
            print(f"  {details['product_name']}{variant_info}{sku_info}: {count}")

        swatch_total = sum(swatch_books["counts"].values())
        print(f"Total swatch books: {swatch_total}")
    else:
        print("  No swatch books found")
        print("Total swatch books: 0")


if __name__ == "__main__":
    main()