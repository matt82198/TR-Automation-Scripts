"""
Tannery Row Internal Tools Dashboard

Run with: streamlit run app.py

For Streamlit Cloud deployment:
- Configure secrets in .streamlit/secrets.toml (see secrets.toml.example)
- Requires Google OAuth setup for authentication
"""

import streamlit as st
import subprocess
import sys
import os
import csv
from datetime import datetime, timedelta
from pathlib import Path

# Add utils and scripts dirs to path for imports
sys.path.insert(0, str(Path(__file__).parent / "utils"))
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

# Import authentication utilities
from auth import check_authentication, show_user_info_sidebar, get_secret

# Import storage utilities (handles cloud vs local automatically)
from gsheets_storage import (
    load_missing_inventory, save_missing_inventory,
    load_coefficients, save_coefficients,
    is_cloud_deployment
)

from pending_order_count import SquarespacePanelCalculator
from payment_fetch import fetch_stripe_readonly, fetch_paypal_readonly
from order_payment_matcher import match_order_batch

# =============================================================================
# Authentication Check
# =============================================================================
# This must run before any other Streamlit commands on cloud deployment

if is_cloud_deployment():
    if not check_authentication():
        st.stop()

# =============================================================================
# Page Configuration (after auth check)
# =============================================================================

st.set_page_config(
    page_title="Tannery Row Tools",
    page_icon="🏭",
    layout="wide"
)

st.title("Tannery Row Internal Tools")
st.markdown("---")

# Sidebar navigation
tool = st.sidebar.radio(
    "Select Tool",
    ["Payment Fetch", "Order Payment Matcher", "Pending Order Count", "Mystery Bundle Counter", "Leather Weight Calculator", "Swatch Book Generator"]
)

# Show user info in sidebar (if authenticated on cloud)
if is_cloud_deployment():
    show_user_info_sidebar()

SCRIPTS_DIR = Path(__file__).parent / "scripts"
OUTPUT_DIR = Path(__file__).parent / "output"
CONFIG_DIR = Path(__file__).parent / "config"
OUTPUT_DIR.mkdir(exist_ok=True)
MISSING_INVENTORY_FILE = CONFIG_DIR / "missing_inventory.csv"
COEFFICIENTS_FILE = CONFIG_DIR / "leather_weight_coefficients.csv"


# Note: load_missing_inventory and save_missing_inventory are now imported from gsheets_storage
# They automatically handle cloud vs local storage


def run_script(cmd, description):
    """Run a script and display output"""
    with st.spinner(f"Running {description}..."):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent),
                timeout=300
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Script timed out after 5 minutes", 1
        except Exception as e:
            return "", str(e), 1


# Payment Fetch Tool
if tool == "Payment Fetch":
    st.header("Payment Fetch")
    st.markdown("Fetch payment data from Stripe and PayPal for a date range.")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=7)
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now()
        )

    if st.button("Fetch Payments", type="primary"):
        cmd = [
            "python",
            str(SCRIPTS_DIR / "payment_fetch.py"),
            "--start-date", start_date.strftime("%Y-%m-%d"),
            "--end-date", end_date.strftime("%Y-%m-%d")
        ]

        stdout, stderr, code = run_script(cmd, "payment fetch")

        if code == 0:
            st.success("Payment fetch completed!")
            st.text(stdout)
        else:
            st.error("Error running payment fetch")
            if stderr:
                st.text(stderr)


# Order Payment Matcher
elif tool == "Order Payment Matcher":
    st.header("Order Payment Matcher")
    st.markdown("Match Squarespace order numbers to Stripe/PayPal transactions to get net amounts and fees.")

    # Date range for fetching payments
    st.subheader("Payment Date Range")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=30),
            key="matcher_start"
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            key="matcher_end"
        )

    # Order numbers input
    st.subheader("Order Numbers")
    order_input = st.text_area(
        "Enter order numbers (one per line or comma-separated)",
        height=150,
        placeholder="12345\n12346\n12347\nor\n12345, 12346, 12347"
    )

    if st.button("Match Orders to Payments", type="primary"):
        # Parse order numbers
        order_numbers = []
        if order_input:
            for line in order_input.strip().split('\n'):
                for num in line.split(','):
                    num = num.strip()
                    if num:
                        order_numbers.append(num)

        if not order_numbers:
            st.error("Please enter at least one order number")
        else:
            ss_api_key = get_secret("SQUARESPACE_API_KEY")
            if not ss_api_key:
                st.error("SQUARESPACE_API_KEY environment variable not set")
            else:
                with st.spinner(f"Fetching payments and matching {len(order_numbers)} orders..."):
                    try:
                        # Fetch payment transactions
                        start_str = start_date.strftime("%Y-%m-%d")
                        end_str = end_date.strftime("%Y-%m-%d")

                        stripe_txns = fetch_stripe_readonly(start_str, end_str)
                        paypal_txns = fetch_paypal_readonly(start_str, end_str)

                        # Match orders
                        results, summary = match_order_batch(
                            order_numbers,
                            ss_api_key,
                            stripe_txns,
                            paypal_txns
                        )

                        # Display summary
                        st.success(f"Matched {summary['matched']}/{summary['total_orders']} orders")

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Gross", f"${summary['total_gross']:,.2f}")
                        with col2:
                            st.metric("Total Net", f"${summary['total_net']:,.2f}")
                        with col3:
                            st.metric("Total Fees", f"${summary['total_fees']:,.2f}")
                        with col4:
                            st.metric("Total Write-off", f"${summary['total_write_off']:,.2f}")

                        if summary['not_found']:
                            st.warning(f"Orders not found in Squarespace: {', '.join(summary['not_found'])}")

                        # Display results table
                        st.subheader("Results")

                        # Separate matched and unmatched
                        matched = [r for r in results if r['matched']]
                        unmatched = [r for r in results if not r['matched']]

                        if matched:
                            st.markdown("**Matched Orders:**")
                            for r in matched:
                                with st.expander(f"Order #{r['order_number']} - {r['customer_name']} - ${r['gross_amount']:.2f}"):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**Date:** {r['order_date']}")
                                        st.write(f"**Customer:** {r['customer_name']}")
                                        st.write(f"**Email:** {r['customer_email']}")
                                    with col2:
                                        st.write(f"**Payment Source:** {r['payment_source']}")
                                        st.write(f"**Gross:** ${r['gross_amount']:.2f}")
                                        st.write(f"**Net:** ${r['net_amount']:.2f}")
                                        st.write(f"**Fee:** ${r['processing_fee']:.2f}")
                                        st.write(f"**Write-off:** ${r['write_off']:.2f}")

                        if unmatched:
                            st.markdown("**Unmatched Orders:**")
                            for r in unmatched:
                                st.warning(f"Order #{r['order_number']} - {r['customer_name']} - ${r['gross_amount']:.2f} (No payment match found)")

                    except Exception as e:
                        st.error(f"Error: {e}")
                        import traceback
                        st.text(traceback.format_exc())


# Pending Order Count
elif tool == "Pending Order Count":
    st.header("Pending Order Count")
    st.markdown("Count pending panels and swatch books from Squarespace orders.")

    # Initialize session state for missing items
    if 'missing_inventory' not in st.session_state:
        st.session_state.missing_inventory = load_missing_inventory(MISSING_INVENTORY_FILE)

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Refresh Orders", type="primary"):
            st.session_state.pop('product_counts', None)
    with col2:
        view_mode = st.radio("View", ["Total Counts", "By Order"], horizontal=True)

    # Fetch orders if not cached
    if 'product_counts' not in st.session_state:
        api_key = get_secret("SQUARESPACE_API_KEY")
        if not api_key:
            st.error("SQUARESPACE_API_KEY environment variable not set")
        else:
            with st.spinner("Fetching pending orders..."):
                try:
                    calculator = SquarespacePanelCalculator(api_key)
                    st.session_state.product_counts = calculator.get_product_counts()
                except Exception as e:
                    st.error(f"Error fetching orders: {e}")

    if 'product_counts' in st.session_state:
        product_counts = st.session_state.product_counts
        panels = product_counts["panels"]
        swatch_books = product_counts["swatch_books"]
        by_order = product_counts.get("by_order", {})
        missing = st.session_state.missing_inventory

        # Track changes
        updated_missing = set(missing)

        if view_mode == "Total Counts":
            st.markdown("**Check items that are missing/out of stock** to prioritize production.")

            # Panels section
            st.subheader("Panels")
            if panels["counts"]:
                panel_total = sum(panels["counts"].values())
                missing_panel_count = sum(
                    panels["counts"][uid] for uid in panels["counts"] if uid in missing
                )
                st.metric("Total Panels Needed", panel_total,
                          delta=f"{missing_panel_count} missing" if missing_panel_count else None,
                          delta_color="inverse")

                for unique_id, count in sorted(panels["counts"].items(),
                                               key=lambda x: x[0] in missing,
                                               reverse=True):
                    details = panels["details"][unique_id]
                    variant_info = f" ({details['variant_description']})" if details['variant_description'] else ""
                    label = f"{details['product_name']}{variant_info} - **{count}** needed"

                    is_missing = st.checkbox(
                        label,
                        value=unique_id in missing,
                        key=f"panel_{unique_id}",
                        help="Check if this item is out of stock"
                    )

                    if is_missing:
                        updated_missing.add(unique_id)
                    else:
                        updated_missing.discard(unique_id)
            else:
                st.info("No panels in pending orders")

            st.divider()

            # Swatch Books section
            st.subheader("Swatch Books")
            if swatch_books["counts"]:
                swatch_total = sum(swatch_books["counts"].values())
                missing_swatch_count = sum(
                    swatch_books["counts"][uid] for uid in swatch_books["counts"] if uid in missing
                )
                st.metric("Total Swatch Books Needed", swatch_total,
                          delta=f"{missing_swatch_count} missing" if missing_swatch_count else None,
                          delta_color="inverse")

                for unique_id, count in sorted(swatch_books["counts"].items(),
                                               key=lambda x: x[0] in missing,
                                               reverse=True):
                    details = swatch_books["details"][unique_id]
                    variant_info = f" ({details['variant_description']})" if details['variant_description'] else ""
                    label = f"{details['product_name']}{variant_info} - **{count}** needed"

                    is_missing = st.checkbox(
                        label,
                        value=unique_id in missing,
                        key=f"swatch_{unique_id}",
                        help="Check if this item is out of stock"
                    )

                    if is_missing:
                        updated_missing.add(unique_id)
                    else:
                        updated_missing.discard(unique_id)
            else:
                st.info("No swatch books in pending orders")

        else:  # By Order view
            st.markdown("Items with missing stock are highlighted.")

            if by_order:
                # Sort orders by date (oldest first) then by order number
                sorted_orders = sorted(by_order.items(),
                                       key=lambda x: (x[1]["date"], x[0]))

                for order_num, order_data in sorted_orders:
                    # Check if any items in this order are missing
                    order_has_missing = any(
                        item["unique_id"] in missing
                        for item in order_data["panels"] + order_data["swatch_books"]
                    )

                    # Create expander with warning icon if missing items
                    icon = "⚠️ " if order_has_missing else ""
                    with st.expander(f"{icon}Order #{order_num} - {order_data['date']}", expanded=order_has_missing):
                        if order_data["panels"]:
                            st.markdown("**Panels:**")
                            for item in order_data["panels"]:
                                variant_info = f" ({item['variant_description']})" if item['variant_description'] else ""
                                is_missing_item = item["unique_id"] in missing
                                marker = "🔴 " if is_missing_item else ""
                                st.markdown(f"- {marker}{item['product_name']}{variant_info} x{item['quantity']}")

                        if order_data["swatch_books"]:
                            st.markdown("**Swatch Books:**")
                            for item in order_data["swatch_books"]:
                                variant_info = f" ({item['variant_description']})" if item['variant_description'] else ""
                                is_missing_item = item["unique_id"] in missing
                                marker = "🔴 " if is_missing_item else ""
                                st.markdown(f"- {marker}{item['product_name']}{variant_info} x{item['quantity']}")
            else:
                st.info("No orders with panels or swatch books")

        # Save if changed
        if updated_missing != missing:
            st.session_state.missing_inventory = updated_missing
            save_missing_inventory(updated_missing, MISSING_INVENTORY_FILE)
            st.toast("Missing inventory updated!")


# Mystery Bundle Counter
elif tool == "Mystery Bundle Counter":
    st.header("Mystery Bundle Counter")
    st.markdown("Count mystery bundle quantities needed from pending Squarespace orders for holiday planning.")

    from mystery_bundle_counter import fetch_orders, count_mystery_bundles

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Refresh Orders", type="primary", key="mystery_refresh"):
            st.session_state.pop('mystery_results', None)
    with col2:
        status_filter = st.radio("Order Status", ["PENDING", "FULFILLED"], horizontal=True, key="mystery_status")

    # Fetch and count if not cached or status changed
    cache_key = f'mystery_results_{status_filter}'
    if cache_key not in st.session_state:
        api_key = get_secret("SQUARESPACE_API_KEY")
        if not api_key:
            st.error("SQUARESPACE_API_KEY environment variable not set")
        else:
            with st.spinner(f"Fetching {status_filter.lower()} orders..."):
                try:
                    orders = fetch_orders(status_filter)
                    results = count_mystery_bundles(orders)
                    results['order_count'] = len(orders)
                    st.session_state[cache_key] = results
                except Exception as e:
                    st.error(f"Error fetching orders: {e}")

    if cache_key in st.session_state:
        results = st.session_state[cache_key]

        st.info(f"Found {results['order_count']} {status_filter.lower()} orders, {results['total_orders_with_bundles']} with mystery bundles")

        # Grand totals
        st.subheader("Grand Totals")
        col1, col2, col3 = st.columns(3)

        # Calculate grand totals
        grand_sides = 0
        grand_horsefronts = 0
        grand_shoulders = 0

        for category, data in results["categories"].items():
            total = data["total"]
            if "horsefront" in category.lower():
                grand_horsefronts += total
            elif "tempesti" in category.lower() or "splenda" in category.lower():
                grand_shoulders += total
            else:
                grand_sides += total

        with col1:
            st.metric("Sides Needed", grand_sides)
        with col2:
            st.metric("Double Horsefronts Needed", grand_horsefronts)
        with col3:
            st.metric("Double Shoulders Needed", grand_shoulders)

        st.divider()

        # Category breakdown
        st.subheader("By Category")
        if results["categories"]:
            for category in sorted(results["categories"].keys()):
                data = results["categories"][category]
                total = data["total"]

                # Determine unit type
                if "horsefront" in category.lower():
                    unit = "Double Horsefronts"
                elif "tempesti" in category.lower() or "splenda" in category.lower():
                    unit = "Double Shoulders"
                else:
                    unit = "Sides"

                with st.expander(f"{category}: **{total} {unit}** ({len(data['orders'])} orders)"):
                    for order in data["orders"]:
                        st.markdown(f"- Order #{order['order_number']} - {order['customer']}: {order['quantity']} ({order['variant']})")
        else:
            st.info("No mystery bundles found in orders.")

        st.divider()

        # Order list
        st.subheader("Orders with Mystery Bundles")
        if results["order_list"]:
            for order_info in sorted(results["order_list"], key=lambda x: x["order_number"]):
                with st.expander(f"Order #{order_info['order_number']} - {order_info['customer']}"):
                    for bundle in order_info["bundles"]:
                        st.markdown(f"- {bundle['category']}: {bundle['qty_display']}")
        else:
            st.info("No orders with mystery bundles.")


# Leather Weight Calculator
elif tool == "Leather Weight Calculator":
    st.header("Leather Weight Calculator")
    st.markdown("Calculate box weights for shipping based on leather weight coefficients (lbs per sq ft).")

    # Note: load_coefficients and save_coefficients are imported from gsheets_storage
    # They automatically handle cloud vs local storage

    # Load coefficients
    coefficients = load_coefficients(COEFFICIENTS_FILE)

    # Tabs for different operations
    tab1, tab2, tab3 = st.tabs(["Estimate Box Weight", "Calculate Coefficient", "Stored Coefficients"])

    with tab1:
        st.subheader("Estimate Box Weight")

        if not coefficients:
            st.info("No coefficients stored yet. Use the 'Calculate Coefficient' tab to add one.")
        else:
            # Leather selection
            leather_names = sorted([c['leather_name'] for c in coefficients.values()])
            selected_leather = st.selectbox("Select Leather", leather_names, key="estimate_leather")

            if selected_leather:
                leather_key = selected_leather.strip().lower()
                leather_data = coefficients.get(leather_key)

                if leather_data:
                    st.caption(f"Coefficient: {leather_data['coefficient']:.4f} lbs/sqft")

                    box_sqft = st.number_input("Box Square Footage", min_value=0.0, step=1.0, key="box_sqft")

                    if box_sqft > 0:
                        estimated_weight = leather_data['coefficient'] * box_sqft
                        st.metric("Estimated Box Weight", f"{estimated_weight:.2f} lbs")

    with tab2:
        st.subheader("Calculate New Coefficient")
        st.markdown("Weigh a bundle of leather and enter the total square footage to calculate the weight coefficient.")

        col1, col2 = st.columns(2)
        with col1:
            leather_name = st.text_input("Leather Name", placeholder="e.g., Dublin Black FF 3.5-4 oz", key="new_leather_name")
        with col2:
            notes = st.text_input("Notes (optional)", placeholder="e.g., from shipment 12/2024", key="new_notes")

        col3, col4 = st.columns(2)
        with col3:
            bundle_weight = st.number_input("Bundle Weight (lbs)", min_value=0.0, step=0.1, key="bundle_weight")
        with col4:
            bundle_sqft = st.number_input("Bundle Square Footage", min_value=0.0, step=1.0, key="bundle_sqft")

        if bundle_weight > 0 and bundle_sqft > 0:
            new_coefficient = bundle_weight / bundle_sqft
            st.info(f"Calculated coefficient: **{new_coefficient:.4f} lbs/sqft**")

            if st.button("Save Coefficient", type="primary"):
                if not leather_name.strip():
                    st.error("Please enter a leather name")
                else:
                    key = leather_name.strip().lower()
                    coefficients[key] = {
                        'leather_name': leather_name.strip(),
                        'coefficient': new_coefficient,
                        'sample_weight': bundle_weight,
                        'sample_sqft': bundle_sqft,
                        'last_updated': datetime.now().strftime('%Y-%m-%d'),
                        'notes': notes
                    }
                    save_coefficients(coefficients, COEFFICIENTS_FILE)
                    st.success(f"Saved: {leather_name} = {new_coefficient:.4f} lbs/sqft")
                    st.rerun()

    with tab3:
        st.subheader("Stored Coefficients")

        if not coefficients:
            st.info("No coefficients stored yet.")
        else:
            st.caption(f"{len(coefficients)} coefficients stored")

            # Display as table
            for key, data in sorted(coefficients.items(), key=lambda x: x[1]['leather_name']):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"**{data['leather_name']}**")
                    if data.get('notes'):
                        st.caption(data['notes'])
                with col2:
                    st.write(f"{data['coefficient']:.4f} lbs/sqft")
                with col3:
                    if data.get('sample_weight') and data.get('sample_sqft'):
                        st.caption(f"{data['sample_weight']} lbs / {data['sample_sqft']} sqft")

                st.divider()


# Swatch Book Generator
elif tool == "Swatch Book Generator":
    st.header("Swatch Book Generator")
    st.markdown("Generate a PDF reference guide of all leather colors from the website.")

    if st.button("Generate Swatch Book PDF", type="primary"):
        cmd = ["python", str(SCRIPTS_DIR / "swatch_book_contents.py")]

        stdout, stderr, code = run_script(cmd, "swatch book generator")

        if code == 0:
            st.success("Swatch book generated!")
            st.text(stdout)

            pdf_path = Path(__file__).parent / "Swatch_Book_Reference.pdf"
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="Download PDF",
                        data=f.read(),
                        file_name="Swatch_Book_Reference.pdf",
                        mime="application/pdf"
                    )
        else:
            st.error("Error generating swatch book")
            if stderr:
                st.text(stderr)


# Footer
st.markdown("---")
st.caption("Tannery Row Internal Tools")
