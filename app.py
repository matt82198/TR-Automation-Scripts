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
    load_sample_inventory, save_sample_inventory,
    load_panel_inventory, save_panel_inventory,
    load_mystery_panel_count, save_mystery_panel_count,
    load_cage_inventory, save_cage_inventory,
    is_cloud_deployment, log_activity
)

from pending_order_count import SquarespacePanelCalculator
from payment_fetch import fetch_stripe_readonly, fetch_paypal_readonly
from order_payment_matcher import match_order_batch, PaymentMatcher, SquarespaceOrderFetcher as PaymentOrderFetcher
from squarespace_to_quickbooks import ProductMapper, CustomerMatcher, SHIP_FROM_STATE
from qb_invoice_generator import generate_invoice_excel

# =============================================================================
# Prevent search engine indexing (internal tool only)
# =============================================================================
st.markdown(
    '<meta name="robots" content="noindex, nofollow">',
    unsafe_allow_html=True
)

# =============================================================================
# Tool Configuration
# =============================================================================

TOOL_CATEGORIES = {
    "Billing & Payments": {
        "icon": "💰",
        "tools": {
            "Order Payment Matcher": {
                "description": "Match orders to payment transactions",
                "permission": "admin"
            },
            "QB Invoice Generator (Alpha)": {
                "description": "Generate QB-ready Excel invoices with payment matching",
                "permission": "admin"
            },
        }
    },
    "Order Management": {
        "icon": "📦",
        "tools": {
            "Manufacturing Inventory": {
                "description": "Pending orders, panel inventory, and sample tracking",
                "permission": "standard"
            },
            "Mystery Bundle Counter": {
                "description": "Track mystery bundle inventory (Nov-Dec only)",
                "permission": "standard",
                "seasonal": [11, 12]
            },
        }
    },
    "Inventory & Shipping": {
        "icon": "🚚",
        "tools": {
            "Leather Weight Calculator": {
                "description": "Calculate box weights for shipping",
                "permission": "standard"
            }
        }
    },
    "Customer Management": {
        "icon": "👥",
        "tools": {
            "Material Bank Leads": {
                "description": "Import leads to Method CRM",
                "permission": "materialbank"
            }
        }
    },
    "Admin Tools": {
        "icon": "🔧",
        "tools": {
            "Method CRM Admin": {
                "description": "Fix orphaned contacts and cleanup activities",
                "permission": "admin"
            }
        }
    }
}

# Permissions file
PERMISSIONS_FILE = Path(__file__).parent / "config" / "tool_permissions.csv"

def load_user_permissions():
    """Load user permissions from CSV file."""
    permissions = {}
    if PERMISSIONS_FILE.exists():
        with open(PERMISSIONS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get('email', '').strip().lower()
                if email and not email.startswith('#'):
                    permissions[email] = {
                        'role': row.get('role', 'standard').strip().lower(),
                        'tools': row.get('tools', '').strip(),
                        'materialbank': row.get('materialbank', '').strip().lower() == 'true'
                    }
    return permissions

def get_user_permissions():
    """Get the current user's full permissions."""
    # For local development, default to admin with all access
    if not is_cloud_deployment():
        return {"role": "admin", "tools": "all", "materialbank": True}

    # If auth is skipped (SKIP_AUTH=true), grant admin access
    if os.environ.get('SKIP_AUTH', '').lower() == 'true' or get_secret('SKIP_AUTH', '').lower() == 'true':
        return {"role": "admin", "tools": "all", "materialbank": True}

    # Check session for authenticated user email
    user_email = st.session_state.get("user_email", "").lower()
    permissions = load_user_permissions()

    # If user is in permissions file, use their configured role
    if user_email in permissions:
        return permissions[user_email]

    # Default: any authenticated @thetanneryrow.com user gets standard role
    if user_email.endswith("@thetanneryrow.com"):
        return {"role": "standard", "tools": "", "materialbank": False}

    return {"role": "none", "tools": "", "materialbank": False}

def get_user_role():
    """Get the current user's role (for display purposes)."""
    perms = get_user_permissions()
    return perms['role'], perms['tools']

def has_permission(tool_name, tool_permission_level):
    """Check if current user has permission for a tool."""
    user_perms = get_user_permissions()
    user_role = user_perms['role']

    # Admin has all access
    if user_role == "admin":
        return True

    # No role = no access
    if user_role == "none":
        return False

    # Material Bank requires special flag
    if tool_permission_level == "materialbank":
        return user_perms.get('materialbank', False)

    # Custom role - check specific tools
    if user_role == "custom":
        allowed_tools = [t.strip() for t in user_perms['tools'].split(';')]
        return tool_name in allowed_tools

    # Standard role - only standard permission tools
    if user_role == "standard":
        return tool_permission_level == "standard"

    return False

def get_available_tools():
    """Get list of tools available to the current user."""
    available = {}
    for category, cat_data in TOOL_CATEGORIES.items():
        category_tools = {}
        for tool_name, tool_data in cat_data["tools"].items():
            if has_permission(tool_name, tool_data["permission"]):
                category_tools[tool_name] = tool_data
        if category_tools:
            available[category] = {
                "icon": cat_data["icon"],
                "tools": category_tools
            }
    return available

# =============================================================================
# Authentication Check
# =============================================================================
if not check_authentication():
    st.stop()

# =============================================================================
# Page Configuration
# =============================================================================

st.set_page_config(
    page_title="Tannery Row Tools",
    page_icon="🏭",
    layout="wide"
)

st.title("Tannery Row Internal Tools")

# Show user role badge
user_role, _ = get_user_role()
if user_role == "admin":
    st.caption("🔑 Admin Access")

st.markdown("---")

# =============================================================================
# Sidebar Navigation with Categories
# =============================================================================

available_tools = get_available_tools()

st.sidebar.title("Navigation")

if not available_tools:
    st.error("No tools available for your access level.")
    st.stop()

# Build tool list with category grouping
all_tools = []
tool_to_info = {}
for category, cat_data in available_tools.items():
    for tool_name, tool_data in cat_data["tools"].items():
        all_tools.append(tool_name)
        tool_to_info[tool_name] = {
            "category": category,
            "icon": cat_data["icon"],
            "description": tool_data["description"]
        }

# Display categories and tools
for category, cat_data in available_tools.items():
    st.sidebar.markdown(f"**{cat_data['icon']} {category}**")
    tool_names = list(cat_data["tools"].keys())

    for tool_name in tool_names:
        tool_data = cat_data["tools"][tool_name]
        seasonal = tool_data.get("seasonal")
        is_off_season = bool(seasonal and datetime.now().month not in seasonal)
        if st.sidebar.button(
            tool_name,
            key=f"btn_{tool_name}",
            use_container_width=True,
            disabled=is_off_season
        ):
            st.session_state.selected_tool = tool_name

    st.sidebar.markdown("")  # Spacing between categories

# Get selected tool (default to first if not set)
if 'selected_tool' not in st.session_state or st.session_state.selected_tool not in all_tools:
    st.session_state.selected_tool = all_tools[0]

tool = st.session_state.selected_tool

# Show current selection and description
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Selected:** {tool}")
st.sidebar.caption(tool_to_info[tool]["description"])

# Show user info in sidebar
show_user_info_sidebar()

st.sidebar.markdown("---")
st.sidebar.caption(f"Role: {user_role.title()}")

# =============================================================================
# Paths
# =============================================================================

SCRIPTS_DIR = Path(__file__).parent / "scripts"
OUTPUT_DIR = Path(__file__).parent / "output"
CONFIG_DIR = Path(__file__).parent / "config"
OUTPUT_DIR.mkdir(exist_ok=True)
MISSING_INVENTORY_FILE = CONFIG_DIR / "missing_inventory.csv"
COEFFICIENTS_FILE = CONFIG_DIR / "leather_weight_coefficients.csv"


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


# =============================================================================
# BILLING & PAYMENTS
# =============================================================================

if tool == "Order Payment Matcher":
    st.header("💰 Order Payment Matcher")
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
                try:
                    # Fetch payment transactions with progress
                    start_str = start_date.strftime("%Y-%m-%d")
                    end_str = end_date.strftime("%Y-%m-%d")

                    user_email = st.session_state.get("user_email", "local")
                    log_activity(user_email, "Order Payment Matcher", "match", f"{len(order_numbers)} orders")

                    status = st.empty()
                    status.info("Fetching Stripe transactions (this may take a minute for large date ranges)...")
                    stripe_txns = fetch_stripe_readonly(start_str, end_str)

                    status.info(f"Found {len(stripe_txns)} Stripe transactions. Fetching PayPal...")
                    paypal_txns = fetch_paypal_readonly(start_str, end_str)

                    status.info(f"Found {len(paypal_txns)} PayPal transactions. Matching {len(order_numbers)} orders...")

                    # Match orders
                    results, summary = match_order_batch(
                        order_numbers,
                        ss_api_key,
                        stripe_txns,
                        paypal_txns
                    )

                    status.empty()

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

                    # Generate CSV for download
                    csv_lines = ["Order Number,Date,Customer,Email,Payment Source,Gross,Net,Fee,Write-off,Matched"]
                    for r in results:
                        net = f"{r['net_amount']:.2f}" if r['net_amount'] is not None else ""
                        fee = f"{r['processing_fee']:.2f}" if r['processing_fee'] is not None else ""
                        writeoff = f"{r['write_off']:.2f}" if r['write_off'] is not None else ""
                        csv_lines.append(f"{r['order_number']},{r['order_date']},{r['customer_name']},{r['customer_email']},{r['payment_source']},{r['gross_amount']:.2f},{net},{fee},{writeoff},{r['matched']}")

                    csv_content = "\n".join(csv_lines)
                    st.download_button(
                        label="Download Results CSV",
                        data=csv_content,
                        file_name=f"order_payment_match_{datetime.now().strftime('%Y-%m-%d')}.csv",
                        mime="text/csv",
                        type="primary"
                    )

                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.text(traceback.format_exc())


elif tool == "QB Invoice Generator (Alpha)":
    st.header("🧾 QB Invoice Generator (Alpha)")
    st.markdown("Generate QB-ready Excel invoices with payment matching, product mapping, and customer matching.")
    st.warning("**Alpha** — This tool is under development. Verify output before importing into QuickBooks.")

    # Date range for fetching payments
    st.subheader("Payment Date Range")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=30),
            key="qbgen_start"
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            key="qbgen_end"
        )

    # Order numbers input
    st.subheader("Order Numbers")
    order_input = st.text_area(
        "Enter Squarespace order numbers (one per line or comma-separated)",
        height=150,
        placeholder="12345\n12346\n12347\nor\n12345, 12346, 12347",
        key="qbgen_orders"
    )

    if st.button("Generate Invoices", type="primary"):
        # Parse order numbers
        order_numbers = []
        if order_input:
            for line in order_input.strip().split('\n'):
                for num in line.split(','):
                    num = num.strip().lstrip('#')
                    if num.isdigit():
                        order_numbers.append(num)

        if not order_numbers:
            st.error("Please enter at least one order number.")
        else:
            ss_api_key = get_secret("SQUARESPACE_API_KEY")
            if not ss_api_key:
                st.error("SQUARESPACE_API_KEY environment variable not set")
            else:
                try:
                    start_str = start_date.strftime("%Y-%m-%d")
                    end_str = end_date.strftime("%Y-%m-%d")

                    user_email = st.session_state.get("user_email", "local")
                    log_activity(user_email, "QB Invoice Generator", "generate", f"{len(order_numbers)} orders")

                    status = st.empty()

                    # Step 1: Fetch payment transactions
                    status.info("Fetching Stripe transactions...")
                    stripe_txns = fetch_stripe_readonly(start_str, end_str)

                    status.info(f"Found {len(stripe_txns)} Stripe transactions. Fetching PayPal...")
                    paypal_txns = fetch_paypal_readonly(start_str, end_str)
                    all_transactions = stripe_txns + paypal_txns

                    # Step 2: Fetch full orders from Squarespace
                    status.info(f"Fetching {len(order_numbers)} orders from Squarespace...")
                    from quickbooks_billing_helper import SquarespaceOrderFetcher
                    fetcher = SquarespaceOrderFetcher(ss_api_key)
                    orders_raw = fetcher.fetch_orders_by_numbers(order_numbers)

                    # Step 3: Match payments
                    status.info("Matching orders to payments...")
                    payment_fetcher = PaymentOrderFetcher(ss_api_key)
                    orders_for_matching = [payment_fetcher.extract_order_info(o) for o in orders_raw]
                    matcher = PaymentMatcher()
                    payment_results = matcher.match_orders(orders_for_matching, all_transactions, order_numbers)

                    # Step 4: Load product mapper
                    status.info("Loading product mappings...")
                    sku_mapper = ProductMapper()
                    sku_mapping_file = str(Path(__file__).parent / "config" / "sku_mapping.csv")
                    sku_mapper.load_product_mapping(sku_mapping_file)

                    # Load holiday mappings if they exist
                    holiday_file = str(Path(__file__).parent / "examples" / "holiday_sale_mappings.csv")
                    if os.path.exists(holiday_file):
                        sku_mapper.load_holiday_mapping(holiday_file)

                    # Step 5: Load customer matcher
                    status.info("Loading customer data...")
                    customer_matcher = CustomerMatcher()
                    customer_file = str(Path(__file__).parent / "config" / "qb_customer_list.csv")
                    if os.path.exists(customer_file):
                        customer_matcher.load_existing_customers(customer_file)
                    customer_matcher.load_customer_import_log()

                    # Step 6: Generate Excel
                    status.info("Generating Excel workbook...")
                    excel_data = generate_invoice_excel(
                        orders_raw,
                        payment_results,
                        sku_mapper,
                        customer_matcher,
                        SHIP_FROM_STATE
                    )

                    status.empty()

                    # Build summary stats
                    matched_results = [r for r in payment_results if r['matched']]
                    unmatched_results = [r for r in payment_results if not r['matched']]
                    not_found = [n for n in order_numbers if n not in [str(r['order_number']) for r in payment_results]]

                    total_gross = sum(r.get('gross_amount', 0) or 0 for r in matched_results)
                    total_net = sum(r.get('net_amount', 0) or 0 for r in matched_results)
                    total_fees = sum(r.get('processing_fee', 0) or 0 for r in matched_results)
                    total_writeoff = sum(r.get('write_off', 0) or 0 for r in matched_results)

                    # Display summary
                    st.success(f"Generated invoices for {len(orders_raw)} orders ({len(matched_results)} payments matched)")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Gross", f"${total_gross:,.2f}")
                    with col2:
                        st.metric("Total Net", f"${total_net:,.2f}")
                    with col3:
                        st.metric("Total Fees", f"${total_fees:,.2f}")
                    with col4:
                        st.metric("Total Write-off", f"${total_writeoff:,.2f}")

                    if not_found:
                        st.warning(f"Orders not found in Squarespace: {', '.join(not_found)}")

                    # Report unmapped products
                    if sku_mapper.unmapped_products:
                        with st.expander(f"⚠️ {len(sku_mapper.unmapped_products)} Unmapped Product(s)", expanded=False):
                            for product in sku_mapper.unmapped_products:
                                st.text(f"  {product}")

                    # Display results
                    st.subheader("Results")

                    if matched_results:
                        st.markdown("**Matched Orders:**")
                        for r in matched_results:
                            with st.expander(f"Order #{r['order_number']} - {r['customer_name']} - ${r['gross_amount']:.2f}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Customer:** {r['customer_name']}")
                                    st.write(f"**Email:** {r['customer_email']}")
                                    st.write(f"**Date:** {r['order_date']}")
                                with col2:
                                    st.write(f"**Source:** {r['payment_source']}")
                                    st.write(f"**Net:** ${r['net_amount']:.2f}")
                                    st.write(f"**Fee:** ${r['processing_fee']:.2f}")
                                    st.write(f"**Write-off:** ${r['write_off']:.2f}")

                    if unmatched_results:
                        st.markdown("**Unmatched Orders:**")
                        for r in unmatched_results:
                            st.warning(f"Order #{r['order_number']} - {r['customer_name']} - ${r['gross_amount']:.2f} (No payment match found)")

                    # Excel download button
                    st.download_button(
                        label="Download Excel Invoices",
                        data=excel_data,
                        file_name=f"qb_invoices_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )

                except Exception as e:
                    st.error(f"Error: {e}")
                    import traceback
                    st.text(traceback.format_exc())


# =============================================================================
# ORDER MANAGEMENT
# =============================================================================

elif tool == "Manufacturing Inventory":
    st.header("📦 Manufacturing Inventory")

    from collections import defaultdict
    from swatch_book_contents import SwatchBookGenerator

    SAMPLE_INVENTORY_FILE = Path(__file__).parent / "config" / "sample_inventory.csv"
    PANEL_INVENTORY_FILE = Path(__file__).parent / "config" / "panel_inventory.csv"
    CAGE_INVENTORY_FILE = Path(__file__).parent / "config" / "cage_inventory.csv"

    STATUS_OPTIONS = ['in_stock', 'low_stock', 'out_of_stock']
    STATUS_LABELS = {'in_stock': 'In Stock', 'low_stock': 'Low Stock', 'out_of_stock': 'Out of Stock'}
    STATUS_COLORS = {'in_stock': '🟢', 'low_stock': '🟡', 'out_of_stock': '🔴'}

    # Load cage inventory for cross-referencing across all tabs
    if 'cage_inventory' not in st.session_state:
        st.session_state.cage_inventory = load_cage_inventory(CAGE_INVENTORY_FILE)
    # Build cage lookup: dict of (swatch_book, color) -> set of weights in cage
    cage_lookup = defaultdict(set)
    for item in st.session_state.cage_inventory:
        cage_lookup[(item['swatch_book'], item['color'])].add(item.get('weight', ''))

    def is_in_cage(product_name, color, weight=''):
        """Check if leather is available in the cage. Normalizes panel product names.
        Weight matching: cage entry with no weight matches anything. If cage has weight, must match."""
        def _check(name, color, weight):
            key = (name, color)
            if key in cage_lookup:
                cage_weights = cage_lookup[key]
                # Cage entry with no weight = matches anything
                if '' in cage_weights:
                    return True
                # If checking with a specific weight, must match
                if weight and weight in cage_weights:
                    return True
                # If checking without weight (samples), match if any cage entry exists
                if not weight:
                    return True
            return False

        # Direct match (sample inventory names like "Horween Dublin")
        if _check(product_name, color, weight):
            return True
        # Strip " Leather Panels" for panel product names
        normalized = product_name.replace(" Leather Panels", "").replace(" Leather Panel", "")
        # Also strip brand bullet separators (e.g. "Horween • Dublin" -> check both forms)
        for sep in [' • ', ' \u2022 ', ' - ']:
            normalized = normalized.replace(sep, ' ')
        if _check(normalized, color, weight):
            return True
        return False

    def get_item_readiness(product_name, variant_desc, item_type='panel'):
        """Determine readiness of a pending order item from inventory data.
        Returns (icon, label) tuple."""
        # Parse color and weight from variant description
        color = ''
        weight = ''
        for part in variant_desc.split(' - '):
            part = part.strip()
            if part.startswith('Color:'):
                color = part.replace('Color:', '').strip()
            elif part.startswith('Weight:'):
                weight = part.replace('Weight:', '').strip()
        if not color:
            color = variant_desc

        # Check cage first (highest priority - ready to cut)
        if color and is_in_cage(product_name, color, weight):
            return '📦', 'In Cage'

        # Check panel or sample inventory
        if item_type == 'panel':
            pi = st.session_state.get('panel_inventory', [])
            for item in pi:
                name_match = item['swatch_book'] == product_name
                color_match = item['color'] == color
                weight_match = (not weight or not item.get('weight')) or item.get('weight', '') == weight
                if name_match and color_match and weight_match:
                    status = item['status']
                    if status == 'in_stock':
                        return '🟢', 'In Stock'
                    elif status == 'low_stock':
                        return '🟡', 'Low Stock'
                    else:
                        return '🔴', 'Out of Stock'
        else:  # swatch book
            si = st.session_state.get('sample_inventory', [])
            # Normalize product name for sample matching (strip "Swatch Book -" etc.)
            for item in si:
                if item['color'] == color and product_name.endswith(item['swatch_book']):
                    status = item['status']
                    if status == 'in_stock':
                        return '🟢', 'In Stock'
                    elif status == 'low_stock':
                        return '🟡', 'Low Stock'
                    else:
                        return '🔴', 'Out of Stock'

        return '⬜', 'Not Tracked'

    tab_pending, tab_panels, tab_samples, tab_cage = st.tabs(["Pending Orders", "Panel Inventory", "Sample Inventory", "Cage Inventory"])

    # =========================================================================
    # TAB 1: Pending Orders (existing functionality)
    # =========================================================================
    with tab_pending:
        st.markdown("Priority list for pending panels and swatch books. Status is pulled from inventory.")

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
                        user_email = st.session_state.get("user_email", "local")
                        log_activity(user_email, "Manufacturing Inventory", "fetch", "refresh pending orders")

                        calculator = SquarespacePanelCalculator(api_key)
                        st.session_state.product_counts = calculator.get_product_counts()
                    except Exception as e:
                        st.error(f"Error fetching orders: {e}")

        if 'product_counts' in st.session_state:
            product_counts = st.session_state.product_counts
            panels = product_counts["panels"]
            swatch_books = product_counts["swatch_books"]
            by_order = product_counts.get("by_order", {})

            if view_mode == "Total Counts":
                # Readiness priority order for sorting: Out of Stock > Not Tracked > Low Stock > In Stock > In Cage
                READINESS_SORT = {'🔴': 0, '⬜': 1, '🟡': 2, '🟢': 3, '📦': 4}

                # Panels section
                st.subheader("Panels")
                if panels["counts"]:
                    panel_total = sum(panels["counts"].values())

                    # Calculate readiness stats
                    panel_readiness = {}
                    for uid in panels["counts"]:
                        d = panels["details"][uid]
                        icon, _ = get_item_readiness(d['product_name'], d['variant_description'], 'panel')
                        panel_readiness[uid] = icon

                    ready_count = sum(panels["counts"][uid] for uid in panels["counts"] if panel_readiness[uid] in ('📦', '🟢'))
                    not_ready_count = panel_total - ready_count

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Total Panels Needed", panel_total)
                    c2.metric("Ready", ready_count)
                    c3.metric("Not Ready", not_ready_count)

                    for unique_id, count in sorted(panels["counts"].items(),
                                                   key=lambda x: READINESS_SORT.get(panel_readiness[x[0]], 5)):
                        details = panels["details"][unique_id]
                        variant_info = f" ({details['variant_description']})" if details['variant_description'] else ""
                        icon, label = get_item_readiness(details['product_name'], details['variant_description'], 'panel')
                        st.markdown(f"{icon} {details['product_name']}{variant_info} - **{count}** needed — *{label}*")
                else:
                    st.info("No panels in pending orders")

                st.divider()

                # Swatch Books section
                st.subheader("Swatch Books")
                if swatch_books["counts"]:
                    swatch_total = sum(swatch_books["counts"].values())

                    swatch_readiness = {}
                    for uid in swatch_books["counts"]:
                        d = swatch_books["details"][uid]
                        icon, _ = get_item_readiness(d['product_name'], d['variant_description'], 'swatch_book')
                        swatch_readiness[uid] = icon

                    ready_count = sum(swatch_books["counts"][uid] for uid in swatch_books["counts"] if swatch_readiness[uid] in ('📦', '🟢'))
                    not_ready_count = swatch_total - ready_count

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Total Swatch Books Needed", swatch_total)
                    c2.metric("Ready", ready_count)
                    c3.metric("Not Ready", not_ready_count)

                    for unique_id, count in sorted(swatch_books["counts"].items(),
                                                   key=lambda x: READINESS_SORT.get(swatch_readiness[x[0]], 5)):
                        details = swatch_books["details"][unique_id]
                        variant_info = f" ({details['variant_description']})" if details['variant_description'] else ""
                        icon, label = get_item_readiness(details['product_name'], details['variant_description'], 'swatch_book')
                        st.markdown(f"{icon} {details['product_name']}{variant_info} - **{count}** needed — *{label}*")
                else:
                    st.info("No swatch books in pending orders")

            else:  # By Order view
                st.markdown("Orders sorted by readiness — not-ready orders shown first.")

                if by_order:
                    READINESS_SORT = {'🔴': 0, '⬜': 1, '🟡': 2, '🟢': 3, '📦': 4}

                    # Calculate per-order readiness
                    order_readiness = {}
                    for order_num, order_data in by_order.items():
                        all_items = order_data["panels"] + order_data["swatch_books"]
                        item_icons = []
                        for item in all_items:
                            itype = 'panel' if item in order_data["panels"] else 'swatch_book'
                            icon, _ = get_item_readiness(item['product_name'], item['variant_description'], itype)
                            item_icons.append(icon)

                        if all(i in ('📦', '🟢') for i in item_icons):
                            order_readiness[order_num] = ('✅', 'Ready')
                        elif any(i in ('🔴', '⬜') for i in item_icons):
                            order_readiness[order_num] = ('🔴', 'Not Ready')
                        else:
                            order_readiness[order_num] = ('🟡', 'Partial')

                    # Sort: not ready first, then partial, then ready; within groups by date
                    ORDER_SORT = {'🔴': 0, '🟡': 1, '✅': 2}
                    sorted_orders = sorted(by_order.items(),
                                           key=lambda x: (ORDER_SORT.get(order_readiness[x[0]][0], 3), x[1]["date"], x[0]))

                    for order_num, order_data in sorted_orders:
                        r_icon, r_label = order_readiness[order_num]
                        is_not_ready = r_icon != '✅'
                        with st.expander(f"{r_icon} Order #{order_num} - {order_data['date']} — {r_label}", expanded=is_not_ready):
                            if order_data["panels"]:
                                st.markdown("**Panels:**")
                                for item in order_data["panels"]:
                                    variant_info = f" ({item['variant_description']})" if item['variant_description'] else ""
                                    icon, label = get_item_readiness(item['product_name'], item['variant_description'], 'panel')
                                    st.markdown(f"- {icon} {item['product_name']}{variant_info} x{item['quantity']} — *{label}*")

                            if order_data["swatch_books"]:
                                st.markdown("**Swatch Books:**")
                                for item in order_data["swatch_books"]:
                                    variant_info = f" ({item['variant_description']})" if item['variant_description'] else ""
                                    icon, label = get_item_readiness(item['product_name'], item['variant_description'], 'swatch_book')
                                    st.markdown(f"- {icon} {item['product_name']}{variant_info} x{item['quantity']} — *{label}*")
                else:
                    st.info("No orders with panels or swatch books")

            # Download CSV button
            st.divider()
            csv_lines = ["Type,Product,Variant,Quantity,Status"]
            for unique_id, count in panels["counts"].items():
                details = panels["details"][unique_id]
                _, label = get_item_readiness(details['product_name'], details['variant_description'], 'panel')
                csv_lines.append(f"Panel,{details['product_name']},{details['variant_description']},{count},{label}")
            for unique_id, count in swatch_books["counts"].items():
                details = swatch_books["details"][unique_id]
                _, label = get_item_readiness(details['product_name'], details['variant_description'], 'swatch_book')
                csv_lines.append(f"Swatch Book,{details['product_name']},{details['variant_description']},{count},{label}")

            st.download_button(
                label="Download Pending Orders CSV",
                data="\n".join(csv_lines),
                file_name=f"pending_orders_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv"
            )

    # =========================================================================
    # TAB 2: Panel Inventory
    # =========================================================================
    with tab_panels:
        st.markdown("Track panel availability by color for each leather type.")

        # --- Mystery Panels ---
        MYSTERY_PANEL_FILE = Path(__file__).parent / "config" / "mystery_panel_count.txt"

        if 'mystery_panel_count' not in st.session_state:
            st.session_state.mystery_panel_count = load_mystery_panel_count(MYSTERY_PANEL_FILE)

        st.subheader("Mystery Panels")
        mystery_count = st.number_input(
            "Ready to ship",
            min_value=0,
            value=st.session_state.mystery_panel_count,
            step=1,
            key="mystery_panel_input"
        )
        if mystery_count != st.session_state.mystery_panel_count:
            st.session_state.mystery_panel_count = mystery_count
            save_mystery_panel_count(mystery_count, MYSTERY_PANEL_FILE)
            st.toast("Mystery panel count updated!")

        st.divider()

        # --- Regular Panels ---
        if 'panel_inventory' not in st.session_state:
            raw = load_panel_inventory(PANEL_INVENTORY_FILE)
            # Deduplicate by (swatch_book, color, weight)
            seen = set()
            deduped = []
            for item in raw:
                key = (item['swatch_book'], item['color'], item.get('weight', ''))
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            st.session_state.panel_inventory = deduped

        pi_inventory = st.session_state.panel_inventory

        with st.expander("Sync from Store", expanded=not pi_inventory):
            st.caption("Pull all panel products and variants from the Squarespace store catalog.")
            if st.button("Sync Panels", type="primary"):
                user_email = st.session_state.get("user_email", "local")
                log_activity(user_email, "Manufacturing Inventory", "sync", "panel inventory")

                api_key = get_secret("SQUARESPACE_API_KEY")
                if not api_key:
                    st.error("SQUARESPACE_API_KEY not set")
                else:
                    with st.spinner("Fetching all panel products from store..."):
                        calculator = SquarespacePanelCalculator(api_key)
                        all_variants = calculator.fetch_all_panel_variants()

                    if not all_variants:
                        st.info("No panel products found in the store.")
                    else:
                        existing = {(item['swatch_book'], item['color'], item.get('weight', '')): item for item in pi_inventory}

                        new_variants = []
                        for v in all_variants:
                            key = (v['product_name'], v['color'], v['weight'])
                            if key not in existing:
                                existing[key] = True
                                new_variants.append({
                                    'swatch_book': v['product_name'],
                                    'color': v['color'],
                                    'weight': v['weight'],
                                    'status': 'in_stock',
                                    'last_updated': datetime.now().strftime('%Y-%m-%d')
                                })

                        if new_variants:
                            pi_inventory.extend(new_variants)
                            st.session_state.panel_inventory = pi_inventory
                            save_panel_inventory(pi_inventory, PANEL_INVENTORY_FILE)
                            st.success(f"Added {len(new_variants)} new panel variant(s)")
                            for c in new_variants:
                                weight_info = f" ({c['weight']})" if c['weight'] else ""
                                st.write(f"  + {c['swatch_book']} - {c['color']}{weight_info}")
                            st.rerun()
                        else:
                            st.info("Panel inventory is already up to date.")

        if not pi_inventory:
            st.info("No panel inventory data yet. Use **Sync from Orders** above to populate.")
        else:
            total = len(pi_inventory)
            in_stock = sum(1 for i in pi_inventory if i['status'] == 'in_stock')
            low_stock = sum(1 for i in pi_inventory if i['status'] == 'low_stock')
            out_of_stock = sum(1 for i in pi_inventory if i['status'] == 'out_of_stock')

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Colors", total)
            m2.metric("In Stock", in_stock)
            m3.metric("Low Stock", low_stock)
            m4.metric("Out of Stock", out_of_stock)

            st.divider()

            by_tannery = defaultdict(lambda: defaultdict(list))
            for item in pi_inventory:
                sb = item['swatch_book']
                parts = sb.split(' ', 1)
                tannery = parts[0] if parts else 'Other'
                by_tannery[tannery][sb].append(item)

            pi_changed = False

            for tannery in sorted(by_tannery.keys()):
                swatch_books_group = by_tannery[tannery]
                with st.expander(f"**{tannery}** ({sum(len(colors) for colors in swatch_books_group.values())} colors)", expanded=False):
                    for sb_name in sorted(swatch_books_group.keys()):
                        colors = swatch_books_group[sb_name]
                        sb_out = sum(1 for c in colors if c['status'] == 'out_of_stock')
                        sb_low = sum(1 for c in colors if c['status'] == 'low_stock')
                        suffix = ""
                        if sb_out:
                            suffix += f" | 🔴 {sb_out}"
                        if sb_low:
                            suffix += f" | 🟡 {sb_low}"

                        leather_type = sb_name.split(' ', 1)[1] if ' ' in sb_name else sb_name
                        st.markdown(f"**{leather_type}** ({len(colors)} colors{suffix})")

                        for ci, color_item in enumerate(sorted(colors, key=lambda x: (x['color'], x.get('weight', '')))):
                            col1, col2 = st.columns([3, 2])
                            with col1:
                                current = color_item['status']
                                cage_icon = " 📦" if is_in_cage(sb_name, color_item['color'], color_item.get('weight', '')) else ""
                                weight_label = f" - {color_item['weight']}" if color_item.get('weight') else ""
                                st.write(f"{STATUS_COLORS.get(current, '')} {color_item['color']}{weight_label}{cage_icon}")
                            with col2:
                                weight_key = color_item.get('weight', '').replace(' ', '')
                                key = f"pi_{sb_name}_{color_item['color']}_{weight_key}_{ci}"
                                new_status = st.selectbox(
                                    "Status",
                                    STATUS_OPTIONS,
                                    index=STATUS_OPTIONS.index(current),
                                    format_func=lambda x: STATUS_LABELS[x],
                                    key=key,
                                    label_visibility="collapsed"
                                )
                                if new_status != current:
                                    color_item['status'] = new_status
                                    color_item['last_updated'] = datetime.now().strftime('%Y-%m-%d')
                                    pi_changed = True

                        st.markdown("---")

            if pi_changed:
                st.session_state.panel_inventory = pi_inventory
                save_panel_inventory(pi_inventory, PANEL_INVENTORY_FILE)
                st.toast("Panel inventory updated!")

    # =========================================================================
    # TAB 3: Sample Inventory
    # =========================================================================
    with tab_samples:
        st.markdown("Track sample swatch availability by color for each swatch book.")

        if 'sample_inventory' not in st.session_state:
            raw = load_sample_inventory(SAMPLE_INVENTORY_FILE)
            seen = set()
            deduped = []
            for item in raw:
                key = (item['swatch_book'], item['color'])
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            st.session_state.sample_inventory = deduped

        si_inventory = st.session_state.sample_inventory

        with st.expander("Sync from Website", expanded=not si_inventory):
            st.caption("Scrape the Tannery Row website to find new colors or detect removed ones.")
            if st.button("Sync Samples", type="primary"):
                user_email = st.session_state.get("user_email", "local")
                log_activity(user_email, "Manufacturing Inventory", "sync", "sample inventory")

                with st.spinner("Scraping website for current colors..."):
                    generator = SwatchBookGenerator()
                    results = generator.run()

                if not results:
                    st.error("Could not fetch swatch book data from the website.")
                else:
                    existing = {(item['swatch_book'], item['color']): item for item in si_inventory}
                    scraped_keys = set()

                    new_colors = []
                    for swatch_name, info in results.items():
                        for color in info['colors']:
                            key = (swatch_name, color)
                            scraped_keys.add(key)
                            if key not in existing:
                                new_colors.append({
                                    'swatch_book': swatch_name,
                                    'color': color,
                                    'status': 'in_stock',
                                    'last_updated': datetime.now().strftime('%Y-%m-%d')
                                })

                    removed_keys = [k for k in existing if k not in scraped_keys]

                    updated = [item for item in si_inventory if (item['swatch_book'], item['color']) in scraped_keys]
                    updated.extend(new_colors)

                    st.session_state.sample_inventory = updated
                    save_sample_inventory(updated, SAMPLE_INVENTORY_FILE)

                    if new_colors:
                        st.success(f"Added {len(new_colors)} new color(s)")
                        for c in new_colors:
                            st.write(f"  + {c['swatch_book']} - {c['color']}")
                    if removed_keys:
                        st.warning(f"Removed {len(removed_keys)} color(s) no longer on website")
                        for sb, color in removed_keys:
                            st.write(f"  - {sb} - {color}")
                    if not new_colors and not removed_keys:
                        st.info("Sample inventory is already up to date.")

                    si_inventory = st.session_state.sample_inventory
                    st.rerun()

        if not si_inventory:
            st.info("No sample inventory data yet. Use **Sync from Website** above to populate.")
        else:
            total = len(si_inventory)
            in_stock = sum(1 for i in si_inventory if i['status'] == 'in_stock')
            low_stock = sum(1 for i in si_inventory if i['status'] == 'low_stock')
            out_of_stock = sum(1 for i in si_inventory if i['status'] == 'out_of_stock')

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Colors", total)
            m2.metric("In Stock", in_stock)
            m3.metric("Low Stock", low_stock)
            m4.metric("Out of Stock", out_of_stock)

            # --- Print PDF ---
            with st.expander("Print Swatch Book PDF"):
                st.caption("Generate a printable PDF reference guide from current inventory data.")
                if st.button("Generate PDF", type="primary", key="gen_swatch_pdf"):
                    from fpdf import FPDF

                    # Group inventory by tannery -> swatch book
                    pdf_tannery = defaultdict(lambda: defaultdict(list))
                    for item in si_inventory:
                        sb = item['swatch_book']
                        parts = sb.split(' ', 1)
                        tannery = parts[0] if parts else 'Other'
                        pdf_tannery[tannery][sb].append(item)

                    pdf = FPDF()
                    pdf.set_auto_page_break(auto=True, margin=20)

                    # Title page
                    pdf.add_page()
                    pdf.ln(80)
                    pdf.set_font("Helvetica", "B", 28)
                    pdf.cell(0, 15, "THE TANNERY ROW", ln=True, align="C")
                    pdf.set_font("Helvetica", "", 14)
                    pdf.cell(0, 10, "", ln=True)
                    pdf.cell(0, 10, "SWATCH BOOK REFERENCE GUIDE", ln=True, align="C")
                    pdf.cell(0, 10, "", ln=True)
                    pdf.set_font("Helvetica", "", 11)
                    pdf.cell(0, 10, datetime.now().strftime("%B %Y"), ln=True, align="C")
                    pdf.cell(0, 10, "", ln=True)
                    pdf.cell(0, 8, f"{len(si_inventory)} colors across {len(set(i['swatch_book'] for i in si_inventory))} swatch books", ln=True, align="C")

                    # Table of contents
                    pdf.add_page()
                    pdf.set_font("Helvetica", "B", 18)
                    pdf.cell(0, 12, "Table of Contents", ln=True)
                    pdf.ln(5)
                    for tannery in sorted(pdf_tannery.keys()):
                        books = pdf_tannery[tannery]
                        pdf.set_font("Helvetica", "B", 12)
                        pdf.cell(0, 8, tannery.upper(), ln=True)
                        pdf.set_font("Helvetica", "", 10)
                        for sb_name in sorted(books.keys()):
                            leather_type = sb_name.split(' ', 1)[1] if ' ' in sb_name else sb_name
                            count = len(books[sb_name])
                            pdf.cell(10)
                            pdf.cell(0, 6, f"{leather_type} ({count} colors)", ln=True)
                        pdf.ln(3)

                    # Each swatch book page
                    for tannery in sorted(pdf_tannery.keys()):
                        books = pdf_tannery[tannery]
                        for sb_name in sorted(books.keys()):
                            colors = books[sb_name]
                            leather_type = sb_name.split(' ', 1)[1] if ' ' in sb_name else sb_name

                            pdf.add_page()
                            pdf.set_font("Helvetica", "", 10)
                            pdf.cell(0, 6, tannery.upper(), ln=True)
                            pdf.set_font("Helvetica", "B", 16)
                            pdf.cell(0, 10, leather_type, ln=True)
                            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                            pdf.ln(5)
                            pdf.set_font("Helvetica", "", 10)
                            pdf.cell(0, 6, f"{len(colors)} Colors", ln=True)
                            pdf.ln(3)

                            for color in sorted(colors, key=lambda x: x['color']):
                                status = color['status']
                                marker = {"in_stock": "[OK]", "low_stock": "[LOW]", "out_of_stock": "[OOS]"}.get(status, "")
                                pdf.set_font("Helvetica", "", 11)
                                pdf.cell(10)
                                pdf.cell(0, 7, f"{color['color']}  {marker}", ln=True)

                    pdf_bytes = pdf.output()
                    st.download_button(
                        label="Download Swatch Book PDF",
                        data=bytes(pdf_bytes),
                        file_name=f"Swatch_Book_Reference_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                        mime="application/pdf"
                    )
                    st.success("PDF generated!")

            st.divider()

            by_tannery = defaultdict(lambda: defaultdict(list))
            for item in si_inventory:
                sb = item['swatch_book']
                parts = sb.split(' ', 1)
                tannery = parts[0] if parts else 'Other'
                by_tannery[tannery][sb].append(item)

            si_changed = False

            for tannery in sorted(by_tannery.keys()):
                swatch_books_group = by_tannery[tannery]
                with st.expander(f"**{tannery}** ({sum(len(colors) for colors in swatch_books_group.values())} colors)", expanded=False):
                    for sb_name in sorted(swatch_books_group.keys()):
                        colors = swatch_books_group[sb_name]
                        sb_out = sum(1 for c in colors if c['status'] == 'out_of_stock')
                        sb_low = sum(1 for c in colors if c['status'] == 'low_stock')
                        suffix = ""
                        if sb_out:
                            suffix += f" | 🔴 {sb_out}"
                        if sb_low:
                            suffix += f" | 🟡 {sb_low}"

                        leather_type = sb_name.split(' ', 1)[1] if ' ' in sb_name else sb_name
                        st.markdown(f"**{leather_type}** ({len(colors)} colors{suffix})")

                        for ci, color_item in enumerate(sorted(colors, key=lambda x: x['color'])):
                            col1, col2 = st.columns([3, 2])
                            with col1:
                                current = color_item['status']
                                cage_icon = " 📦" if is_in_cage(sb_name, color_item['color']) else ""
                                st.write(f"{STATUS_COLORS.get(current, '')} {color_item['color']}{cage_icon}")
                            with col2:
                                key = f"si_{sb_name}_{color_item['color']}_{ci}"
                                new_status = st.selectbox(
                                    "Status",
                                    STATUS_OPTIONS,
                                    index=STATUS_OPTIONS.index(current),
                                    format_func=lambda x: STATUS_LABELS[x],
                                    key=key,
                                    label_visibility="collapsed"
                                )
                                if new_status != current:
                                    color_item['status'] = new_status
                                    color_item['last_updated'] = datetime.now().strftime('%Y-%m-%d')
                                    si_changed = True

                        st.markdown("---")

            if si_changed:
                st.session_state.sample_inventory = si_inventory
                save_sample_inventory(si_inventory, SAMPLE_INVENTORY_FILE)
                st.toast("Sample inventory updated!")

    # =========================================================================
    # TAB 4: Cage Inventory
    # =========================================================================
    with tab_cage:
        st.markdown("Track what leather is in the cage and ready to be cut for panels or samples.")

        cage_inventory = st.session_state.cage_inventory

        # --- Add to cage form ---
        st.subheader("Add Leather to Cage")

        entry_mode = st.radio(
            "Entry mode",
            ["From Catalog", "Custom Entry"],
            horizontal=True,
            key="cage_entry_mode"
        )

        if entry_mode == "From Catalog":
            # Load sample inventory for dropdown options
            if 'sample_inventory' not in st.session_state:
                raw = load_sample_inventory(SAMPLE_INVENTORY_FILE)
                seen = set()
                deduped = []
                for item in raw:
                    key = (item['swatch_book'], item['color'])
                    if key not in seen:
                        seen.add(key)
                        deduped.append(item)
                st.session_state.sample_inventory = deduped

            si_data = st.session_state.sample_inventory
            if not si_data:
                st.warning("Sync Sample Inventory first to populate swatch book options.")
            else:
                sb_names = sorted(set(item['swatch_book'] for item in si_data))
                selected_sb = st.selectbox("Swatch Book", sb_names, key="cage_sb_select")

                sb_colors = sorted(set(
                    item['color'] for item in si_data if item['swatch_book'] == selected_sb
                ))
                selected_color = st.selectbox("Color", sb_colors, key="cage_color_select")

                weight_options = ["(none)", "2-3 oz", "3-4 oz", "4-5 oz", "5-6 oz", "6-7 oz", "7-8 oz", "8-9 oz", "9+ oz"]
                selected_weight = st.selectbox("Weight (optional)", weight_options, key="cage_weight_select")
                cage_weight = "" if selected_weight == "(none)" else selected_weight

                if st.button("Add to Cage", type="primary", key="cage_add_catalog"):
                    already = any(
                        item['swatch_book'] == selected_sb
                        and item['color'] == selected_color
                        and item.get('weight', '') == cage_weight
                        for item in cage_inventory
                    )
                    if already:
                        weight_info = f" ({cage_weight})" if cage_weight else ""
                        st.warning(f"{selected_sb} - {selected_color}{weight_info} is already in the cage.")
                    else:
                        cage_inventory.append({
                            'swatch_book': selected_sb,
                            'color': selected_color,
                            'weight': cage_weight,
                            'date_added': datetime.now().strftime('%Y-%m-%d')
                        })
                        st.session_state.cage_inventory = cage_inventory
                        save_cage_inventory(cage_inventory, CAGE_INVENTORY_FILE)
                        weight_info = f" ({cage_weight})" if cage_weight else ""
                        st.toast(f"Added {selected_sb} - {selected_color}{weight_info} to cage!")
                        st.rerun()

        else:  # Custom Entry
            st.caption("Add items not in the catalog. These will be grouped under **Untracked**.")
            custom_desc = st.text_input("Description", placeholder="e.g. Amalfi Lux Burgundy, Black Tea Core Cypress", key="cage_custom_desc")
            custom_weight = st.text_input("Weight (optional)", placeholder="e.g. 3-4 oz", key="cage_custom_weight")
            cage_weight = custom_weight.strip()

            if st.button("Add to Cage", type="primary", key="cage_add_custom"):
                if not custom_desc.strip():
                    st.warning("Description is required.")
                else:
                    desc = custom_desc.strip()
                    already = any(
                        item['swatch_book'] == "Untracked"
                        and item['color'] == desc
                        and item.get('weight', '') == cage_weight
                        for item in cage_inventory
                    )
                    if already:
                        weight_info = f" ({cage_weight})" if cage_weight else ""
                        st.warning(f"{desc}{weight_info} is already in the cage.")
                    else:
                        cage_inventory.append({
                            'swatch_book': "Untracked",
                            'color': desc,
                            'weight': cage_weight,
                            'date_added': datetime.now().strftime('%Y-%m-%d')
                        })
                        st.session_state.cage_inventory = cage_inventory
                        save_cage_inventory(cage_inventory, CAGE_INVENTORY_FILE)
                        weight_info = f" ({cage_weight})" if cage_weight else ""
                        st.toast(f"Added {desc}{weight_info} to cage (untracked)!")
                        st.rerun()

        st.divider()

        # --- Current cage contents ---
        st.subheader("Current Cage Contents")

        if not cage_inventory:
            st.info("Cage is empty.")
        else:
            cage_search = st.text_input("Search cage...", key="cage_search", placeholder="Filter by name, color, or weight")
            cage_search_lower = cage_search.strip().lower()

            # Filter items if search is active
            if cage_search_lower:
                filtered_inventory = [
                    item for item in cage_inventory
                    if cage_search_lower in str(item.get('swatch_book', '')).lower()
                    or cage_search_lower in str(item.get('color', '')).lower()
                    or cage_search_lower in str(item.get('weight', '')).lower()
                ]
            else:
                filtered_inventory = cage_inventory

            st.metric("Items in Cage", f"{len(filtered_inventory)}" if not cage_search_lower else f"{len(filtered_inventory)} / {len(cage_inventory)}")

            # Group by swatch book
            cage_by_sb = defaultdict(list)
            for item in filtered_inventory:
                cage_by_sb[str(item.get('swatch_book', ''))].append(item)

            to_remove = []

            for sb_name in sorted(cage_by_sb.keys()):
                items = cage_by_sb[sb_name]
                with st.expander(f"**{sb_name}** ({len(items)} items)", expanded=True):
                    for ci, item in enumerate(sorted(items, key=lambda x: (str(x.get('color', '')), str(x.get('weight', ''))))):
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            weight_label = f" - {item['weight']}" if item.get('weight') else ""
                            st.write(f"{item['color']}{weight_label}  *(added {item['date_added']})*")
                        with col2:
                            weight_key = str(item.get('weight', '')).replace(' ', '')
                            if st.button("Remove", key=f"cage_rm_{sb_name}_{item['color']}_{weight_key}_{ci}", type="secondary"):
                                to_remove.append((item['swatch_book'], item['color'], item.get('weight', '')))

            if to_remove:
                cage_inventory = [
                    item for item in cage_inventory
                    if (item['swatch_book'], item['color'], item.get('weight', '')) not in to_remove
                ]
                st.session_state.cage_inventory = cage_inventory
                save_cage_inventory(cage_inventory, CAGE_INVENTORY_FILE)
                st.toast(f"Removed {len(to_remove)} item(s) from cage")
                st.rerun()


elif tool == "Mystery Bundle Counter":
    st.header("📦 Mystery Bundle Counter")
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
                    user_email = st.session_state.get("user_email", "local")
                    log_activity(user_email, "Mystery Bundle Counter", "fetch", status_filter)

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

        # Download CSV button
        if results["order_list"]:
            st.divider()
            csv_lines = ["Order Number,Customer,Category,Quantity,Variant"]
            for order_info in results["order_list"]:
                for bundle in order_info["bundles"]:
                    csv_lines.append(f"{order_info['order_number']},{order_info['customer']},{bundle['category']},{bundle['qty_display']},")

            # Add summary
            csv_lines.append("")
            csv_lines.append("SUMMARY")
            csv_lines.append(f"Sides Needed,{grand_sides}")
            csv_lines.append(f"Double Horsefronts Needed,{grand_horsefronts}")
            csv_lines.append(f"Double Shoulders Needed,{grand_shoulders}")

            st.download_button(
                label="Download Mystery Bundles CSV",
                data="\n".join(csv_lines),
                file_name=f"mystery_bundles_{status_filter.lower()}_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv"
            )


# =============================================================================
# INVENTORY & SHIPPING
# =============================================================================

elif tool == "Leather Weight Calculator":
    st.header("🚚 Leather Weight Calculator")
    st.markdown("Calculate box weights for shipping based on leather weight coefficients (lbs per sq ft).")

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

                    user_email = st.session_state.get("user_email", "local")
                    log_activity(user_email, "Leather Weight Calculator", "save", f"{leather_name}: {new_coefficient:.4f}")

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


# =============================================================================
# CUSTOMER MANAGEMENT
# =============================================================================

elif tool == "Material Bank Leads":
    st.header("👥 Material Bank Lead Import")
    st.markdown("Import leads from Material Bank exports into Method CRM and create activities with follow-ups.")

    import pandas as pd
    from materialbank_method import (
        get_api_key, load_existing_contacts, convert_materialbank_to_method,
        process_materialbank_import, process_activities_only,
        fetch_all_mb_activities, find_duplicate_activities, cleanup_activities,
        fix_orphaned_contacts, get_contact_by_email, get_headers, BASE_URL,
        api_request_with_retry, create_customer
    )
    from gsheets_storage import get_last_materialbank_import, log_materialbank_import

    MATERIALBANK_LOG = CONFIG_DIR / "materialbank_import_log.csv"

    # Show last import info (uses cloud or local automatically)
    last_import = get_last_materialbank_import(MATERIALBANK_LOG)
    if last_import:
        st.info(f"**Last Import:** {last_import['date']} — {last_import['lead_name']} ({last_import['lead_company']}) — {last_import['activities_created']} activities")
    else:
        st.info("No previous imports recorded.")

    st.divider()

    # Check for API key
    if not get_api_key():
        st.error("METHOD_API_KEY not configured. Add it to environment variables or Streamlit secrets.")
        st.stop()

    # File upload
    uploaded_file = st.file_uploader(
        "Upload Material Bank Export CSV",
        type=['csv'],
        help="Upload the CSV export from Material Bank containing lead data"
    )

    if uploaded_file:
        # Load and preview
        mb_df = pd.read_csv(uploaded_file)
        st.success(f"Loaded {len(mb_df)} rows from {uploaded_file.name}")

        # Store emails from uploaded file for targeted cleanup
        uploaded_emails = set(mb_df['Email'].str.lower().str.strip().dropna().unique())
        st.session_state['mb_uploaded_emails'] = uploaded_emails
        st.session_state['mb_uploaded_filename'] = uploaded_file.name

        # Preview
        with st.expander("Preview Data", expanded=False):
            st.dataframe(mb_df.head(20))

        # Import mode selection
        st.subheader("Import Mode")
        import_mode = st.radio(
            "Choose import method:",
            ["csv_download", "activities_only", "full_api"],
            format_func=lambda x: {
                "csv_download": "📥 Download CSV for Method Import (then create activities via API)",
                "activities_only": "📋 Create Activities Only (contacts already imported via CSV)",
                "full_api": "🔄 Full API Import (creates Customers + Contacts + Activities)"
            }[x],
            help="CSV download uses less API quota. Full API is fully automated but uses more quota."
        )

        # Options
        col1, col2 = st.columns(2)
        with col1:
            check_existing = st.checkbox("Skip existing contacts", value=False,
                                         help="Use when re-uploading a CSV after a failure - skips contacts already processed in a previous attempt")
        with col2:
            create_followups = st.checkbox("Create follow-up activities", value=True,
                                           help="Create 'Intro EMAIL' follow-up activities for each lead")

        # Analyze button
        if st.button("Analyze Import", type="secondary"):
            with st.spinner("Analyzing..."):
                existing_contacts = {}
                if check_existing:
                    existing_contacts = load_existing_contacts()
                    st.info(f"Found {len(existing_contacts)} existing contacts in Method")

                method_df, stats = convert_materialbank_to_method(mb_df, set(existing_contacts.keys()) if check_existing else None)

                st.subheader("Import Preview")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Rows", stats['total_rows'])
                with col2:
                    st.metric("Unique Leads", stats['unique_leads'])
                with col3:
                    st.metric("Already Exist", stats['excluded_existing'])
                with col4:
                    st.metric("New Leads", stats['new_leads'])

                if len(method_df) > 0:
                    with st.expander("New Leads to Import", expanded=True):
                        st.dataframe(method_df[['FirstName', 'LastName', 'CompanyName', 'Email']])

                    # Store in session for import
                    st.session_state['mb_ready_df'] = mb_df
                    st.session_state['mb_method_df'] = method_df
                    st.session_state['mb_existing_contacts'] = existing_contacts
                    st.session_state['mb_stats'] = stats
                    st.session_state['mb_import_mode'] = import_mode
                    st.session_state['mb_skip_existing'] = check_existing
                else:
                    st.warning("No new leads to import - all contacts already exist in Method")
                    # Still store for activities_only mode
                    st.session_state['mb_ready_df'] = mb_df
                    st.session_state['mb_existing_contacts'] = existing_contacts
                    st.session_state['mb_import_mode'] = import_mode
                    st.session_state['mb_skip_existing'] = check_existing

        # Import section (only show if ready)
        if 'mb_ready_df' in st.session_state:
            st.divider()
            current_mode = st.session_state.get('mb_import_mode', 'full_api')

            # === CSV DOWNLOAD MODE ===
            if current_mode == "csv_download":
                st.subheader("📥 Step 1: Download CSV for Method Import")
                st.markdown("Download this CSV and import it into Method CRM to create Customers and Contacts.")

                if 'mb_method_df' in st.session_state:
                    method_df = st.session_state['mb_method_df']
                    csv_data = method_df.to_csv(index=False)
                    st.download_button(
                        label="Download Method Import CSV",
                        data=csv_data,
                        file_name=f"method_import_{datetime.now().strftime('%Y-%m-%d')}.csv",
                        mime="text/csv",
                        type="primary"
                    )
                    st.info(f"CSV contains {len(method_df)} new leads to import.")

                st.subheader("📋 Step 2: Create Activities")
                st.markdown("After importing the CSV to Method, click below to create MB Samples activities.")

                if st.button("Create Activities for Imported Contacts", type="primary"):
                    # Reload contacts to get the newly imported ones
                    with st.spinner("Loading contacts and creating activities..."):
                        fresh_contacts = load_existing_contacts()
                        user_email = st.session_state.get("user_email", "local")
                        log_activity(user_email, "Material Bank Leads", "activities_only", "started")

                        results = process_activities_only(
                            st.session_state['mb_ready_df'],
                            fresh_contacts
                        )

                    st.subheader("Activity Creation Results")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Activities Created", results['activities_created'])
                    with col2:
                        st.metric("Follow-ups Created", results['followups_created'])
                    with col3:
                        st.metric("Skipped (no contact)", results.get('skipped', 0))

                    if results['errors']:
                        with st.expander(f"Errors ({len(results['errors'])})"):
                            for err in results['errors']:
                                st.text(err)

                    st.success("Activities created!")

            # === ACTIVITIES ONLY MODE ===
            elif current_mode == "activities_only":
                st.subheader("📋 Create Activities Only")
                st.markdown("Creates MB Samples activities for contacts that already exist in Method.")

                col1, col2 = st.columns([1, 3])
                with col1:
                    dry_run = st.checkbox("Dry Run", value=True, help="Preview without making changes")

                if st.button("Create Activities" if not dry_run else "Preview Activities", type="primary" if not dry_run else "secondary"):
                    with st.spinner("Processing..."):
                        fresh_contacts = load_existing_contacts()
                        user_email = st.session_state.get("user_email", "local")
                        if not dry_run:
                            log_activity(user_email, "Material Bank Leads", "activities_only", "started")

                        results = process_activities_only(
                            st.session_state['mb_ready_df'],
                            fresh_contacts,
                            dry_run=dry_run
                        )

                    prefix = "Would Create " if dry_run else ""
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(f"{prefix}Activities", results['activities_created'])
                    with col2:
                        st.metric(f"{prefix}Follow-ups", results['followups_created'])
                    with col3:
                        st.metric("Skipped (no contact)", results.get('skipped', 0))

                    if results.get('skipped_details'):
                        with st.expander(f"Skipped - No Contact Found ({len(results['skipped_details'])})"):
                            for detail in results['skipped_details']:
                                st.text(f"{detail['name']} ({detail['email']})")

                    if not dry_run:
                        st.success("Activities created!")

            # === FULL API MODE ===
            else:
                st.subheader("🔄 Full API Import")
                col1, col2 = st.columns([1, 3])
                with col1:
                    dry_run = st.checkbox("Dry Run", value=True, help="Preview what will be created without making changes")
                with col2:
                    button_label = "Preview Import (Dry Run)" if dry_run else "Import to Method CRM"
                    button_type = "secondary" if dry_run else "primary"

                if st.button(button_label, type=button_type):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def progress_callback(msg, pct):
                        if pct is not None:
                            progress_bar.progress(pct / 100)
                        status_text.text(msg)

                    spinner_text = "Previewing import..." if dry_run else "Importing leads and creating activities..."
                    with st.spinner(spinner_text):
                        user_email = st.session_state.get("user_email", "local")
                        if not dry_run:
                            log_activity(user_email, "Material Bank Leads", "import", "started")

                        results = process_materialbank_import(
                            st.session_state['mb_ready_df'],
                            st.session_state['mb_existing_contacts'],
                            progress_callback,
                            dry_run=dry_run,
                            skip_existing=st.session_state.get('mb_skip_existing', False)
                        )

                    # Show results
                    if dry_run:
                        st.subheader("Dry Run Preview")
                        st.info("This is a preview. No changes were made to Method CRM.")
                    else:
                        st.subheader("Import Results")

                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    prefix = "Would " if dry_run else ""
                    with col1:
                        st.metric("Leads Processed", results['leads_processed'])
                    with col2:
                        st.metric(f"{prefix}Create Customers", results.get('customers_created', 0))
                    with col3:
                        st.metric(f"{prefix}Create Contacts", results.get('contacts_created', 0))
                    with col4:
                        st.metric(f"{prefix}Create Activities", results['activities_created'])
                    with col5:
                        st.metric("Existing Updated", results.get('existing_updated', 0))
                    with col6:
                        st.metric(f"{prefix}Create Follow-ups", results['followups_created'])

                    if results.get('skipped_existing', 0) > 0:
                        st.info(f"Skipped {results['skipped_existing']} existing contacts (already in Method)")

                    if results['errors']:
                        st.warning(f"{len(results['errors'])} errors occurred")
                        with st.expander("View Errors"):
                            for err in results['errors']:
                                st.text(err)

                    if results['details']:
                        expander_title = "What Would Be Created" if dry_run else "Import Details"
                        with st.expander(expander_title, expanded=True):
                            for detail in results['details']:
                                if detail.get('contact_created'):
                                    status = "NEW contact" + ("" if dry_run else f" #{detail.get('contact_id', 'N/A')}")
                                else:
                                    status = "existing contact"
                                activity_str = "" if dry_run else f" - Activity #{detail.get('activity_id', 'N/A')}"
                                st.markdown(f"- **{detail['name']}** ({detail['company']}) - {detail['samples']} samples{activity_str} [{status}]")

                        # Only log actual imports, not dry runs
                        if not dry_run:
                            user_email = st.session_state.get("user_email", "local")
                            log_materialbank_import(results['details'], results['activities_created'], user_email, MATERIALBANK_LOG)

                    # Only clear session state after actual import, not dry run
                    if not dry_run:
                        del st.session_state['mb_ready_df']
                        del st.session_state['mb_existing_contacts']
                        del st.session_state['mb_stats']
                        st.success("Import complete!")
                    else:
                        st.info("Dry run complete. Uncheck 'Dry Run' and click again to perform the actual import.")


# =============================================================================
# ADMIN TOOLS
# =============================================================================

elif tool == "Method CRM Admin":
    st.header("🔧 Method CRM Admin")
    st.markdown("Administrative tools for fixing data issues in Method CRM.")

    import pandas as pd
    import time
    from materialbank_method import (
        get_api_key, fix_orphaned_contacts, get_contact_by_email, get_headers, BASE_URL,
        fetch_all_mb_activities, find_duplicate_activities, cleanup_activities
    )
    from gsheets_storage import log_activity

    # Check for API key
    if not get_api_key():
        st.error("METHOD_API_KEY not configured. Add it to environment variables or Streamlit secrets.")
        st.stop()

    # ==========================================================================
    # FIX ORPHANED CONTACTS SECTION
    # ==========================================================================
    st.subheader("Fix Orphaned Contacts")
    st.markdown("""
    Fix contacts that were imported without Customer Lead records.
    Upload a Material Bank CSV to identify which contacts to check.
    """)

    # File upload for targeting
    admin_csv = st.file_uploader(
        "Upload Material Bank CSV to target specific contacts",
        type=['csv'],
        key="admin_csv_upload"
    )

    if admin_csv:
        admin_df = pd.read_csv(admin_csv)
        admin_emails = set(admin_df['Email'].str.lower().str.strip().dropna().unique())
        st.session_state['admin_target_emails'] = admin_emails
        st.session_state['admin_csv_df'] = admin_df
        st.success(f"Loaded {len(admin_emails)} unique emails from {admin_csv.name}")

    has_csv = 'admin_target_emails' in st.session_state and st.session_state['admin_target_emails']

    if has_csv:
        target_emails = list(st.session_state['admin_target_emails'])
        st.info(f"Will check **{len(target_emails)}** emails from uploaded CSV")
    else:
        st.warning("Upload a Material Bank CSV above to enable orphan check.")
        target_emails = None

    if st.button("Check for Orphaned Contacts", disabled=not has_csv, key="admin_check_orphans"):
        if not target_emails:
            st.error("Please upload a CSV file first.")
        else:
            orphan_check_results = {'orphaned': [], 'already_linked': [], 'not_found': []}
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, email in enumerate(target_emails):
                pct = int(100 * idx / len(target_emails))
                progress_bar.progress(pct)
                status_text.text(f"Checking {idx+1}/{len(target_emails)}: {email}")

                contact = get_contact_by_email(email)
                time.sleep(0.15)

                if not contact:
                    orphan_check_results['not_found'].append(email)
                elif contact.get('Entity_RecordID'):
                    orphan_check_results['already_linked'].append({
                        'email': email,
                        'name': contact.get('Name'),
                        'customer_id': contact.get('Entity_RecordID')
                    })
                else:
                    orphan_check_results['orphaned'].append({
                        'email': email,
                        'name': contact.get('Name'),
                        'contact_id': contact.get('RecordID'),
                        'company': contact.get('CompanyName')
                    })

            progress_bar.progress(100)
            status_text.text("Check complete!")

            st.session_state['admin_orphan_results'] = orphan_check_results

            # Display results
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Orphaned", len(orphan_check_results['orphaned']))
            with col2:
                st.metric("Already Linked", len(orphan_check_results['already_linked']))
            with col3:
                st.metric("Not Found", len(orphan_check_results['not_found']))

            if orphan_check_results['orphaned']:
                with st.expander(f"Preview Orphaned Contacts ({len(orphan_check_results['orphaned'])})"):
                    for c in orphan_check_results['orphaned'][:20]:
                        st.text(f"{c.get('name', 'N/A')} - {c.get('email')} ({c.get('company', 'N/A')})")
                    if len(orphan_check_results['orphaned']) > 20:
                        st.text(f"... and {len(orphan_check_results['orphaned']) - 20} more")
            else:
                st.success("No orphaned contacts found!")

    # Show fix button if we have orphaned contacts
    if 'admin_orphan_results' in st.session_state:
        results = st.session_state['admin_orphan_results']
        orphaned = results.get('orphaned', [])

        if orphaned:
            st.divider()

            # Build CSV data lookup for company names
            csv_data = {}
            if 'admin_csv_df' in st.session_state:
                admin_df = st.session_state['admin_csv_df']
                for email in [o['email'] for o in orphaned]:
                    rows = admin_df[admin_df['Email'].str.lower().str.strip() == email.lower()]
                    if len(rows) > 0:
                        row = rows.iloc[0]
                        csv_data[email.lower()] = {
                            'company': row.get('Company', ''),
                            'first_name': row.get('First Name', ''),
                            'last_name': row.get('Last Name', ''),
                            'phone': row.get('Work Phone') if pd.notna(row.get('Work Phone')) else None,
                            'mobile': row.get('Mobile Phone') if pd.notna(row.get('Mobile Phone')) else None,
                        }
                st.info(f"Will use company names from uploaded CSV for {len(csv_data)} contacts.")

            # Dry run checkbox
            dry_run = st.checkbox("Dry run (preview only, no changes)", value=True, key="admin_fix_dryrun")

            if st.button(f"{'Preview' if dry_run else 'Fix'} {len(orphaned)} Orphaned Contacts", type="primary", key="admin_fix_orphans"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                retry_status = st.empty()

                def update_progress(msg, pct):
                    if pct is not None:
                        progress_bar.progress(min(pct, 100))
                    status_text.text(msg)
                    retry_status.empty()

                def handle_retry(attempt, wait_seconds, reason):
                    if reason == "rate_limit":
                        reason_text = "⚠️ Rate limited by API"
                    else:
                        reason_text = "⚠️ Connection error"

                    if wait_seconds >= 60:
                        retry_status.warning(f"{reason_text} - Retry {attempt}: waiting {wait_seconds} seconds...")
                    else:
                        retry_status.info(f"{reason_text} - Retry {attempt}: waiting {wait_seconds} seconds...")

                user_email = st.session_state.get("user_email", "local")
                if not dry_run:
                    log_activity(user_email, "Method CRM Admin", "fix_orphans", "started")

                fix_results = fix_orphaned_contacts(
                    progress_callback=update_progress,
                    target_emails=[o['email'] for o in orphaned],
                    dry_run=dry_run,
                    csv_data=csv_data if csv_data else None,
                    retry_callback=handle_retry
                )

                retry_status.empty()

                # Display results
                st.subheader("Fix Results" if not dry_run else "Dry Run Preview")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Customers Created", fix_results['customers_created'])
                with col2:
                    st.metric("Contacts Created", fix_results['contacts_created'])
                with col3:
                    st.metric("Orphans Deleted", fix_results['orphans_deleted'])
                with col4:
                    st.metric("Activities Relinked", fix_results['activities_relinked'])

                if fix_results['errors']:
                    st.warning(f"{len(fix_results['errors'])} errors occurred:")
                    with st.expander("View Errors"):
                        for err in fix_results['errors']:
                            st.text(f"• {err}")

                    existing_company_errors = [e for e in fix_results['errors'] if 'already in use' in e.lower() or 'Name is already' in e]
                    if existing_company_errors:
                        st.info("Some contacts work at companies that already exist in Method. These need to be linked to existing customers.")

                if fix_results['details']:
                    with st.expander("Details"):
                        for d in fix_results['details']:
                            status = d.get('status', 'unknown')
                            name = d.get('name', d.get('email'))
                            company = d.get('company', '')
                            st.text(f"{name} ({company}): {status}")

                if not dry_run:
                    log_activity(user_email, "Method CRM Admin", "fix_orphans",
                                f"completed: {fix_results['customers_created']} customers, {fix_results['contacts_created']} contacts")
                    st.success("Fix complete!")
                    if 'admin_orphan_results' in st.session_state:
                        del st.session_state['admin_orphan_results']

    # ==========================================================================
    # CLEANUP ACTIVITIES SECTION
    # ==========================================================================
    st.divider()
    st.subheader("Cleanup Activities")
    st.markdown("Remove duplicate activities and link orphaned activities to contacts.")

    # Scope selection
    has_admin_csv = 'admin_target_emails' in st.session_state and st.session_state['admin_target_emails']
    if has_admin_csv:
        email_count = len(st.session_state['admin_target_emails'])
        cleanup_scope = st.radio(
            "Cleanup scope:",
            ["uploaded_file", "all"],
            format_func=lambda x: f"From uploaded file only ({email_count} emails)" if x == "uploaded_file" else "All MB Samples activities",
            horizontal=True,
            key="admin_cleanup_scope"
        )
    else:
        cleanup_scope = "all"
        st.info("Upload a CSV file above to enable targeted cleanup for specific emails.")

    if st.button("Check for Issues", key="admin_check_issues"):
        with st.spinner("Scanning for orphaned activities and duplicates..."):
            all_activities = fetch_all_mb_activities()

            # Filter by scope if needed
            if cleanup_scope == "uploaded_file" and has_admin_csv:
                target_emails = st.session_state['admin_target_emails']
                all_activities = [a for a in all_activities if (a.get('ContactEmail') or '').lower().strip() in target_emails]
                st.info(f"Filtered to {len(all_activities)} activities matching uploaded emails")

            orphaned = [a for a in all_activities if not a.get('Contacts_RecordID')]
            duplicates = find_duplicate_activities(all_activities)

            st.session_state['admin_cleanup_scope_val'] = cleanup_scope

        issues_found = False

        if duplicates:
            st.warning(f"Found **{len(duplicates)}** duplicate activities (same email + date).")
            st.session_state['admin_duplicates_count'] = len(duplicates)
            issues_found = True

            with st.expander("Preview Duplicates", expanded=False):
                for act in duplicates[:20]:
                    st.text(f"#{act['RecordID']}: {act.get('ContactName', 'N/A')} ({act.get('ContactEmail', 'N/A')}) - {act.get('DueDateStart', 'N/A')[:10]}")
                if len(duplicates) > 20:
                    st.text(f"... and {len(duplicates) - 20} more")

        if orphaned:
            st.warning(f"Found **{len(orphaned)}** orphaned activities without linked contacts.")
            st.session_state['admin_orphaned_activities'] = orphaned
            issues_found = True

            with st.expander("Preview Orphaned Activities", expanded=False):
                for act in orphaned[:20]:
                    st.text(f"#{act['RecordID']}: {act.get('ContactName', 'N/A')} ({act.get('ContactEmail', 'N/A')})")
                if len(orphaned) > 20:
                    st.text(f"... and {len(orphaned) - 20} more")

        if not issues_found:
            st.success("No issues found. All activities are properly linked with no duplicates!")
            if 'admin_orphaned_activities' in st.session_state:
                del st.session_state['admin_orphaned_activities']
            if 'admin_duplicates_count' in st.session_state:
                del st.session_state['admin_duplicates_count']

    has_issues = st.session_state.get('admin_orphaned_activities') or st.session_state.get('admin_duplicates_count', 0) > 0
    if has_issues:
        orphaned_count = len(st.session_state.get('admin_orphaned_activities', []))
        dup_count = st.session_state.get('admin_duplicates_count', 0)
        total_issues = orphaned_count + dup_count
        if st.button(f"Run Cleanup ({total_issues} issues)", type="primary", key="admin_run_cleanup"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(msg, pct=None):
                status_text.text(msg)
                if pct is not None:
                    progress_bar.progress(pct / 100)

            with st.spinner("Running cleanup..."):
                user_email = st.session_state.get("user_email", "local")
                log_activity(user_email, "Method CRM Admin", "cleanup", "started")

                # Get target emails if scoped to uploaded file
                target_emails = None
                if st.session_state.get('admin_cleanup_scope_val') == 'uploaded_file':
                    target_emails = st.session_state.get('admin_target_emails')

                results = cleanup_activities(progress_callback=update_progress, target_emails=target_emails)

            progress_bar.progress(100)

            # Show results
            st.subheader("Cleanup Results")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Duplicates Removed", results.get('duplicates_removed', 0))
            with col2:
                st.metric("Activities Linked", results.get('activities_linked', 0))

            if results.get('errors'):
                st.warning(f"{len(results['errors'])} errors occurred")
                with st.expander("View Errors"):
                    for err in results['errors']:
                        st.text(err)

            # Clear session state
            if 'admin_orphaned_activities' in st.session_state:
                del st.session_state['admin_orphaned_activities']
            if 'admin_duplicates_count' in st.session_state:
                del st.session_state['admin_duplicates_count']
            if 'admin_cleanup_scope_val' in st.session_state:
                del st.session_state['admin_cleanup_scope_val']

            log_activity(user_email, "Method CRM Admin", "cleanup", f"completed: {results.get('duplicates_removed', 0)} duplicates removed, {results.get('activities_linked', 0)} linked")
            st.success("Cleanup complete!")


# =============================================================================
# Footer
# =============================================================================

st.markdown("---")
st.caption("Tannery Row Internal Tools • v2.0")
