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
    is_cloud_deployment, log_activity
)

from pending_order_count import SquarespacePanelCalculator
from payment_fetch import fetch_stripe_readonly, fetch_paypal_readonly
from order_payment_matcher import match_order_batch

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
            "Payment Fetch": {
                "description": "Pull EOM billing reports from Stripe and PayPal",
                "permission": "admin"
            },
            "Order Payment Matcher": {
                "description": "Match orders to payment transactions",
                "permission": "admin"
            },
            "QuickBooks Billing": {
                "description": "Copy/paste assistant for QuickBooks invoice entry",
                "permission": "admin"
            }
        }
    },
    "Order Management": {
        "icon": "📦",
        "tools": {
            "Pending Order Count": {
                "description": "Count pending panels and swatch books",
                "permission": "standard"
            },
            "Mystery Bundle Counter": {
                "description": "Track mystery bundle inventory",
                "permission": "standard"
            },
            "Swatch Book Generator": {
                "description": "Generate swatch book page layouts",
                "permission": "standard"
            }
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
        if st.sidebar.button(
            tool_name,
            key=f"btn_{tool_name}",
            use_container_width=True
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

if tool == "Payment Fetch":
    st.header("💰 Payment Fetch")
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
        user_email = st.session_state.get("user_email", "local")
        with st.spinner("Fetching payment data..."):
            try:
                # Fetch directly using the imported functions
                start_str = start_date.strftime("%Y-%m-%d")
                end_str = end_date.strftime("%Y-%m-%d")

                log_activity(user_email, "Payment Fetch", "fetch", f"{start_str} to {end_str}")

                stripe_txns = fetch_stripe_readonly(start_str, end_str)
                paypal_txns = fetch_paypal_readonly(start_str, end_str)

                # Calculate summaries
                stripe_gross = sum(t.get('gross', 0) for t in stripe_txns)
                stripe_fees = sum(t.get('fee', 0) for t in stripe_txns)
                stripe_net = sum(t.get('net', 0) for t in stripe_txns)

                paypal_gross = sum(t.get('gross', 0) for t in paypal_txns)
                paypal_fees = sum(t.get('fee', 0) for t in paypal_txns)
                paypal_net = sum(t.get('net', 0) for t in paypal_txns)

                st.success("Payment fetch completed!")

                # Display summaries
                st.subheader("Summary")
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("**Stripe**")
                    st.write(f"Transactions: {len(stripe_txns)}")
                    st.write(f"Gross: ${stripe_gross:,.2f}")
                    st.write(f"Fees: ${stripe_fees:,.2f}")
                    st.write(f"Net: ${stripe_net:,.2f}")

                with col2:
                    st.markdown("**PayPal**")
                    st.write(f"Transactions: {len(paypal_txns)}")
                    st.write(f"Gross: ${paypal_gross:,.2f}")
                    st.write(f"Fees: ${paypal_fees:,.2f}")
                    st.write(f"Net: ${paypal_net:,.2f}")

                with col3:
                    st.markdown("**Combined**")
                    st.write(f"Transactions: {len(stripe_txns) + len(paypal_txns)}")
                    st.write(f"Gross: ${stripe_gross + paypal_gross:,.2f}")
                    st.write(f"Fees: ${stripe_fees + paypal_fees:,.2f}")
                    st.write(f"Net: ${stripe_net + paypal_net:,.2f}")

                # Generate CSV for download
                csv_lines = ["Date,Source,Description,Gross,Fee,Net"]
                for t in stripe_txns:
                    csv_lines.append(f"{t.get('date','')},Stripe,{t.get('description','')},{t.get('gross',0):.2f},{t.get('fee',0):.2f},{t.get('net',0):.2f}")
                for t in paypal_txns:
                    csv_lines.append(f"{t.get('date','')},PayPal,{t.get('description','')},{t.get('gross',0):.2f},{t.get('fee',0):.2f},{t.get('net',0):.2f}")

                csv_content = "\n".join(csv_lines)
                filename = f"eom_billing_{start_str}_to_{end_str}.csv"

                st.download_button(
                    label="Download CSV",
                    data=csv_content,
                    file_name=filename,
                    mime="text/csv",
                    type="primary"
                )

            except Exception as e:
                st.error(f"Error fetching payments: {e}")
                import traceback
                st.text(traceback.format_exc())


elif tool == "Order Payment Matcher":
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


elif tool == "QuickBooks Billing":
    st.header("💰 QuickBooks Billing Assistant")
    st.markdown("Get order details with payment info for manual QuickBooks entry. Combines order data with Stripe/PayPal payment matching.")

    from quickbooks_billing_helper import (
        get_billing_data, generate_qb_entry_text,
        generate_tab_separated_summary, generate_line_items_table
    )

    # Date range for payment matching
    st.subheader("1. Payment Date Range")
    st.caption("Used to fetch Stripe/PayPal transactions for matching")

    col1, col2 = st.columns(2)
    with col1:
        qb_start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=30),
            key="qb_billing_start"
        )
    with col2:
        qb_end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            key="qb_billing_end"
        )

    # Order numbers input
    st.subheader("2. Order Numbers")
    qb_order_input = st.text_area(
        "Enter order numbers (one per line or comma-separated)",
        height=120,
        placeholder="12345\n12346\n12347",
        key="qb_order_numbers"
    )

    if st.button("Get Billing Data", type="primary", key="qb_fetch"):
        # Parse order numbers
        order_numbers = []
        if qb_order_input:
            for line in qb_order_input.strip().split('\n'):
                for num in line.split(','):
                    num = num.strip()
                    if num:
                        order_numbers.append(num)

        if not order_numbers:
            st.error("Please enter at least one order number")
        else:
            ss_api_key = get_secret("SQUARESPACE_API_KEY")
            if not ss_api_key:
                st.error("SQUARESPACE_API_KEY not configured")
            else:
                with st.spinner(f"Fetching {len(order_numbers)} orders and matching payments..."):
                    try:
                        # Fetch payment transactions
                        start_str = qb_start_date.strftime("%Y-%m-%d")
                        end_str = qb_end_date.strftime("%Y-%m-%d")

                        stripe_txns = fetch_stripe_readonly(start_str, end_str)
                        paypal_txns = fetch_paypal_readonly(start_str, end_str)

                        # Get billing data
                        orders, summary = get_billing_data(
                            order_numbers,
                            ss_api_key,
                            stripe_txns,
                            paypal_txns
                        )

                        # Store in session
                        st.session_state['qb_orders'] = orders
                        st.session_state['qb_summary'] = summary

                        user_email = st.session_state.get("user_email", "local")
                        log_activity(user_email, "QuickBooks Billing", "fetch", f"{len(order_numbers)} orders")

                    except Exception as e:
                        st.error(f"Error: {e}")
                        import traceback
                        st.text(traceback.format_exc())

    # Display results
    if 'qb_orders' in st.session_state and st.session_state['qb_orders']:
        orders = st.session_state['qb_orders']
        summary = st.session_state['qb_summary']

        st.divider()
        st.subheader("3. Results")

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Orders Found", summary['total_orders'])
        with col2:
            st.metric("Payments Matched", summary['matched_payments'])
        with col3:
            st.metric("Total Gross", f"${summary['total_gross']:,.2f}")
        with col4:
            st.metric("Total Net", f"${summary['total_net']:,.2f}")

        if summary['not_found']:
            st.warning(f"Orders not found: {', '.join(summary['not_found'])}")

        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["Summary Table", "Line Items", "Detailed View"])

        with tab1:
            st.markdown("**Copy this table to Excel/Sheets:**")
            summary_table = generate_tab_separated_summary(orders)

            # Display as formatted table
            st.text_area(
                "Tab-separated data (select all and copy)",
                value=summary_table,
                height=200,
                key="qb_summary_table"
            )

            st.download_button(
                label="Download as CSV",
                data=summary_table.replace('\t', ','),
                file_name=f"qb_billing_summary_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv"
            )

        with tab2:
            st.markdown("**All line items with quantities and prices:**")
            line_items_table = generate_line_items_table(orders)

            st.text_area(
                "Tab-separated line items (select all and copy)",
                value=line_items_table,
                height=300,
                key="qb_line_items"
            )

            st.download_button(
                label="Download Line Items CSV",
                data=line_items_table.replace('\t', ','),
                file_name=f"qb_line_items_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv"
            )

        with tab3:
            st.markdown("**Detailed order information for manual entry:**")

            for order in orders:
                with st.expander(f"Order #{order['order_number']} - {order['customer_name']} - ${order['grand_total']:.2f}"):
                    # Quick copy fields
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_input("Customer", order['customer_name'], key=f"cust_{order['order_number']}")
                        st.text_input("Date", order['order_date'], key=f"date_{order['order_number']}")
                        st.text_input("Total", f"${order['grand_total']:.2f}", key=f"total_{order['order_number']}")
                    with col2:
                        st.text_input("Tax Code", "Tax" if order['is_taxable'] else "Non", key=f"tax_{order['order_number']}")
                        if order.get('payment_matched'):
                            st.text_input("Net", f"${order['net_amount']:.2f}", key=f"net_{order['order_number']}")
                            st.text_input("Fee", f"${order['processing_fee']:.2f}", key=f"fee_{order['order_number']}")

                    # Ship to address
                    ship_addr = order['shipping_address']
                    ship_text = f"{ship_addr.get('name', '')}\n{ship_addr.get('line1', '')}"
                    if ship_addr.get('line2'):
                        ship_text += f"\n{ship_addr['line2']}"
                    ship_text += f"\n{ship_addr.get('city', '')}, {ship_addr.get('state', '')} {ship_addr.get('zip', '')}"
                    st.text_area("Ship To", ship_text, height=100, key=f"ship_{order['order_number']}")

                    # Line items
                    st.markdown("**Line Items:**")
                    for i, item in enumerate(order['line_items']):
                        cols = st.columns([3, 1, 1, 1])
                        with cols[0]:
                            st.text(item['description'][:50])
                        with cols[1]:
                            st.text(f"Qty: {item['quantity']}")
                        with cols[2]:
                            st.text(f"${item['unit_price']:.2f}")
                        with cols[3]:
                            st.text(f"${item['line_total']:.2f}")

                    # Totals
                    st.markdown("---")
                    cols = st.columns(4)
                    with cols[0]:
                        st.metric("Subtotal", f"${order['subtotal']:.2f}")
                    with cols[1]:
                        st.metric("Shipping", f"${order['shipping_total']:.2f}")
                    with cols[2]:
                        st.metric("Tax", f"${order['tax_total']:.2f}")
                    with cols[3]:
                        st.metric("Total", f"${order['grand_total']:.2f}")

        # Processing fees summary
        st.divider()
        st.subheader("4. Processing Fees Summary")
        st.markdown("Record these as expenses in QuickBooks:")

        fees_by_source = {}
        for order in orders:
            if order.get('payment_matched') and order.get('processing_fee'):
                source = order['payment_source']
                if source not in fees_by_source:
                    fees_by_source[source] = 0
                fees_by_source[source] += order['processing_fee']

        if fees_by_source:
            for source, total_fee in fees_by_source.items():
                st.info(f"**{source}** processing fees: **${total_fee:.2f}**")
            st.caption("Debit: Processing Fees Expense | Credit: Checking Account (or wherever payment was deposited)")
        else:
            st.info("No payment matches found - fees not calculated")


# =============================================================================
# ORDER MANAGEMENT
# =============================================================================

elif tool == "Pending Order Count":
    st.header("📦 Pending Order Count")
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
                    user_email = st.session_state.get("user_email", "local")
                    log_activity(user_email, "Pending Order Count", "fetch", "refresh orders")

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

        # Download CSV button
        st.divider()
        csv_lines = ["Type,Product,Variant,Quantity,Missing"]
        for unique_id, count in panels["counts"].items():
            details = panels["details"][unique_id]
            is_missing = "Yes" if unique_id in missing else "No"
            csv_lines.append(f"Panel,{details['product_name']},{details['variant_description']},{count},{is_missing}")
        for unique_id, count in swatch_books["counts"].items():
            details = swatch_books["details"][unique_id]
            is_missing = "Yes" if unique_id in missing else "No"
            csv_lines.append(f"Swatch Book,{details['product_name']},{details['variant_description']},{count},{is_missing}")

        st.download_button(
            label="Download Pending Orders CSV",
            data="\n".join(csv_lines),
            file_name=f"pending_orders_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )


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


elif tool == "Swatch Book Generator":
    st.header("🚚 Swatch Book Generator")
    st.markdown("Generate a PDF reference guide of all leather colors from the website.")

    if st.button("Generate Swatch Book PDF", type="primary"):
        user_email = st.session_state.get("user_email", "local")
        log_activity(user_email, "Swatch Book Generator", "generate", "PDF")

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
