"""
Database utilities for TR Automation Scripts.
Connects to Supabase PostgreSQL for persistent storage.
"""

import os
import psycopg2
from urllib.parse import quote_plus
from contextlib import contextmanager

def get_connection_string():
    """Get database connection string from environment, Streamlit secrets, or secrets.toml."""
    password = None
    host = "db.qbidzaweiypqaufdwqcl.supabase.co"

    # Try Streamlit secrets first (when running in Streamlit)
    try:
        import streamlit as st
        password = st.secrets.get("SUPABASE_DB_PASSWORD")
        host = st.secrets.get("SUPABASE_DB_HOST", host)
    except:
        pass

    # Try environment variables
    if not password:
        password = os.environ.get("SUPABASE_DB_PASSWORD")
        host = os.environ.get("SUPABASE_DB_HOST", host)

    # Try reading secrets.toml directly (local dev)
    if not password:
        try:
            import tomllib
            # Find project root (look for .streamlit folder)
            current = os.path.dirname(os.path.abspath(__file__))
            for _ in range(5):  # Search up to 5 levels
                secrets_path = os.path.join(current, '.streamlit', 'secrets.toml')
                if os.path.exists(secrets_path):
                    with open(secrets_path, 'rb') as f:
                        secrets = tomllib.load(f)
                        # Keys may be at top level or nested under 'auth' section
                        password = secrets.get("SUPABASE_DB_PASSWORD") or secrets.get("auth", {}).get("SUPABASE_DB_PASSWORD")
                        host = secrets.get("SUPABASE_DB_HOST") or secrets.get("auth", {}).get("SUPABASE_DB_HOST", host)
                    break
                current = os.path.dirname(current)
        except Exception:
            pass

    if not password:
        raise ValueError("SUPABASE_DB_PASSWORD not set in environment or secrets")

    encoded_pw = quote_plus(password)
    return f"postgresql://postgres:{encoded_pw}@{host}:5432/postgres"


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = psycopg2.connect(get_connection_string())
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor():
    """Context manager for database cursor with auto-commit."""
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            cur.close()


def query(sql, params=None):
    """Execute a query and return all results."""
    with get_cursor() as cur:
        cur.execute(sql, params or ())
        if cur.description:  # SELECT query
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        return None


def execute(sql, params=None):
    """Execute a statement (INSERT, UPDATE, DELETE)."""
    with get_cursor() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount


# Convenience functions for common operations

def get_product_mapping(squarespace_product, variant=None):
    """Look up QB item for a Squarespace product."""
    if variant:
        result = query(
            "SELECT quickbooks_item FROM product_mappings WHERE squarespace_product = %s AND squarespace_variant = %s",
            (squarespace_product, variant)
        )
    else:
        result = query(
            "SELECT quickbooks_item FROM product_mappings WHERE squarespace_product = %s AND (squarespace_variant IS NULL OR squarespace_variant = '')",
            (squarespace_product,)
        )
    return result[0]['quickbooks_item'] if result else None


def get_unmapped_products():
    """Get all products that need QB items created."""
    return query("SELECT * FROM product_mappings WHERE needs_qb_item = TRUE ORDER BY product_type, squarespace_product")


def get_products_needing_review():
    """Get all products with closest-match that need review."""
    return query("SELECT * FROM product_mappings WHERE needs_review = TRUE ORDER BY product_type, squarespace_product")


def is_order_imported(order_number):
    """Check if an order has already been imported."""
    result = query("SELECT id FROM order_imports WHERE order_number = %s", (str(order_number),))
    return len(result) > 0


def log_order_import(order_number, order_date, customer_email, customer_name, total_amount, iif_file):
    """Log an order import."""
    execute(
        """INSERT INTO order_imports (order_number, order_date, customer_email, customer_name, total_amount, iif_file)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (order_number) DO UPDATE SET imported_at = NOW()""",
        (str(order_number), order_date, customer_email, customer_name, total_amount, iif_file)
    )


def log_customer_match(ss_email, ss_name, qb_name, match_type):
    """Log a customer match for analytics."""
    execute(
        """INSERT INTO customer_matches (squarespace_email, squarespace_name, qb_customer_name, match_type)
           VALUES (%s, %s, %s, %s)""",
        (ss_email, ss_name, qb_name, match_type)
    )


def get_mapping_stats():
    """Get summary statistics for product mappings."""
    stats = {}

    # By product type
    stats['by_type'] = query(
        "SELECT product_type, COUNT(*) as count FROM product_mappings GROUP BY product_type ORDER BY count DESC"
    )

    # Totals
    stats['total'] = query("SELECT COUNT(*) as count FROM product_mappings")[0]['count']
    stats['needs_qb_item'] = query("SELECT COUNT(*) as count FROM product_mappings WHERE needs_qb_item = TRUE")[0]['count']
    stats['needs_review'] = query("SELECT COUNT(*) as count FROM product_mappings WHERE needs_review = TRUE")[0]['count']
    stats['exact_match'] = stats['total'] - stats['needs_qb_item'] - stats['needs_review']

    return stats


if __name__ == "__main__":
    # Test connection
    stats = get_mapping_stats()
    print(f"Total mappings: {stats['total']}")
    print(f"Exact match: {stats['exact_match']}")
    print(f"Needs review: {stats['needs_review']}")
    print(f"Needs QB item: {stats['needs_qb_item']}")
    print("\nBy product type:")
    for row in stats['by_type']:
        print(f"  {row['product_type']}: {row['count']}")
