"""
Google Sheets storage layer for persistent data on Streamlit Cloud.

Replaces local CSV file storage with Google Sheets for:
- import_log (order import tracking)
- missing_inventory (out-of-stock tracking)
- leather_weight_coefficients (calculated coefficients)

Requires st-gsheets-connection and proper secrets configuration.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Set, List, Any, Optional
import csv
from pathlib import Path

# Try to import Google Sheets connection
try:
    from streamlit_gsheets import GSheetsConnection
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False


def is_cloud_deployment() -> bool:
    """Check if running on Streamlit Cloud with Google Sheets configured."""
    if not GSHEETS_AVAILABLE:
        return False
    try:
        return hasattr(st, 'secrets') and 'connections' in st.secrets and 'gsheets' in st.secrets.connections
    except Exception:
        return False


def get_gsheets_connection():
    """Get Google Sheets connection if available."""
    if not is_cloud_deployment():
        return None
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.warning(f"Could not connect to Google Sheets: {e}")
        return None


# =============================================================================
# Import Log Storage
# =============================================================================

def load_import_log_cloud() -> Set[str]:
    """Load imported order numbers from Google Sheets."""
    conn = get_gsheets_connection()
    if not conn:
        return set()

    try:
        df = conn.read(worksheet="import_log", ttl=60)
        if df is not None and 'order_number' in df.columns:
            return set(df['order_number'].astype(str).tolist())
    except Exception as e:
        st.warning(f"Could not load import log from Google Sheets: {e}")

    return set()


def save_import_log_cloud(order_number: str, iif_file: str = ""):
    """Add an order to the import log in Google Sheets."""
    conn = get_gsheets_connection()
    if not conn:
        return

    try:
        # Read existing data
        df = conn.read(worksheet="import_log", ttl=0)
        if df is None or df.empty:
            df = pd.DataFrame(columns=['order_number', 'date_imported', 'iif_file'])

        # Add new row
        new_row = pd.DataFrame([{
            'order_number': str(order_number),
            'date_imported': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'iif_file': iif_file
        }])
        df = pd.concat([df, new_row], ignore_index=True)

        # Write back
        conn.update(worksheet="import_log", data=df)
    except Exception as e:
        st.warning(f"Could not save to import log: {e}")


def load_import_log_local(file_path: Path) -> Set[str]:
    """Load imported order numbers from local CSV file."""
    imported = set()
    if file_path.exists():
        with open(file_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                imported.add(row['order_number'])
    return imported


def load_import_log(file_path: Optional[Path] = None) -> Set[str]:
    """
    Load imported order numbers from storage.
    Uses Google Sheets on cloud, local CSV otherwise.
    """
    if is_cloud_deployment():
        return load_import_log_cloud()
    elif file_path:
        return load_import_log_local(file_path)
    return set()


# =============================================================================
# Missing Inventory Storage
# =============================================================================

def load_missing_inventory_cloud() -> Set[str]:
    """Load missing inventory IDs from Google Sheets."""
    conn = get_gsheets_connection()
    if not conn:
        return set()

    try:
        df = conn.read(worksheet="missing_inventory", ttl=60)
        if df is not None and 'unique_id' in df.columns:
            return set(df['unique_id'].astype(str).tolist())
    except Exception as e:
        st.warning(f"Could not load missing inventory from Google Sheets: {e}")

    return set()


def save_missing_inventory_cloud(missing_ids: Set[str]):
    """Save missing inventory IDs to Google Sheets."""
    conn = get_gsheets_connection()
    if not conn:
        return

    try:
        df = pd.DataFrame([
            {'unique_id': uid, 'date_marked': datetime.now().strftime('%Y-%m-%d')}
            for uid in sorted(missing_ids)
        ])
        conn.update(worksheet="missing_inventory", data=df)
    except Exception as e:
        st.warning(f"Could not save missing inventory: {e}")


def load_missing_inventory_local(file_path: Path) -> Set[str]:
    """Load missing inventory IDs from local CSV file."""
    missing = set()
    if file_path.exists():
        with open(file_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                missing.add(row['unique_id'])
    return missing


def save_missing_inventory_local(file_path: Path, missing_ids: Set[str]):
    """Save missing inventory IDs to local CSV file."""
    with open(file_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['unique_id', 'date_marked'])
        for uid in sorted(missing_ids):
            writer.writerow([uid, datetime.now().strftime('%Y-%m-%d')])


def load_missing_inventory(file_path: Optional[Path] = None) -> Set[str]:
    """
    Load missing inventory IDs from storage.
    Uses Google Sheets on cloud, local CSV otherwise.
    """
    if is_cloud_deployment():
        return load_missing_inventory_cloud()
    elif file_path:
        return load_missing_inventory_local(file_path)
    return set()


def save_missing_inventory(missing_ids: Set[str], file_path: Optional[Path] = None):
    """
    Save missing inventory IDs to storage.
    Uses Google Sheets on cloud, local CSV otherwise.
    """
    if is_cloud_deployment():
        save_missing_inventory_cloud(missing_ids)
    elif file_path:
        save_missing_inventory_local(file_path, missing_ids)


# =============================================================================
# Leather Weight Coefficients Storage
# =============================================================================

def load_coefficients_cloud() -> Dict[str, Dict[str, Any]]:
    """Load leather weight coefficients from Google Sheets."""
    conn = get_gsheets_connection()
    if not conn:
        return {}

    try:
        df = conn.read(worksheet="leather_coefficients", ttl=60)
        if df is None or df.empty:
            return {}

        coefficients = {}
        for _, row in df.iterrows():
            key = str(row.get('leather_name', '')).strip().lower()
            if key:
                coefficients[key] = {
                    'leather_name': row.get('leather_name', ''),
                    'coefficient': float(row.get('coefficient', 0)),
                    'sample_weight': float(row.get('sample_weight', 0)),
                    'sample_sqft': float(row.get('sample_sqft', 0)),
                    'last_updated': str(row.get('last_updated', '')),
                    'notes': str(row.get('notes', ''))
                }
        return coefficients
    except Exception as e:
        st.warning(f"Could not load coefficients from Google Sheets: {e}")

    return {}


def save_coefficients_cloud(coefficients: Dict[str, Dict[str, Any]]):
    """Save leather weight coefficients to Google Sheets."""
    conn = get_gsheets_connection()
    if not conn:
        return

    try:
        rows = []
        for key, data in coefficients.items():
            rows.append({
                'leather_name': data.get('leather_name', ''),
                'coefficient': data.get('coefficient', 0),
                'sample_weight': data.get('sample_weight', 0),
                'sample_sqft': data.get('sample_sqft', 0),
                'last_updated': data.get('last_updated', ''),
                'notes': data.get('notes', '')
            })
        df = pd.DataFrame(rows)
        conn.update(worksheet="leather_coefficients", data=df)
    except Exception as e:
        st.warning(f"Could not save coefficients: {e}")


def load_coefficients_local(file_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load leather weight coefficients from local CSV file."""
    coefficients = {}
    if file_path.exists():
        with open(file_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row['leather_name'].strip().lower()
                coefficients[key] = {
                    'leather_name': row['leather_name'],
                    'coefficient': float(row['coefficient']),
                    'sample_weight': float(row.get('sample_weight', 0)),
                    'sample_sqft': float(row.get('sample_sqft', 0)),
                    'last_updated': row.get('last_updated', ''),
                    'notes': row.get('notes', '')
                }
    return coefficients


def save_coefficients_local(file_path: Path, coefficients: Dict[str, Dict[str, Any]]):
    """Save leather weight coefficients to local CSV file."""
    with open(file_path, 'w', newline='') as f:
        fieldnames = ['leather_name', 'coefficient', 'sample_weight', 'sample_sqft', 'last_updated', 'notes']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for data in coefficients.values():
            writer.writerow({
                'leather_name': data['leather_name'],
                'coefficient': data['coefficient'],
                'sample_weight': data.get('sample_weight', ''),
                'sample_sqft': data.get('sample_sqft', ''),
                'last_updated': data.get('last_updated', ''),
                'notes': data.get('notes', '')
            })


def load_coefficients(file_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Load leather weight coefficients from storage.
    Uses Google Sheets on cloud, local CSV otherwise.
    """
    if is_cloud_deployment():
        return load_coefficients_cloud()
    elif file_path:
        return load_coefficients_local(file_path)
    return {}


def save_coefficients(coefficients: Dict[str, Dict[str, Any]], file_path: Optional[Path] = None):
    """
    Save leather weight coefficients to storage.
    Uses Google Sheets on cloud, local CSV otherwise.
    """
    if is_cloud_deployment():
        save_coefficients_cloud(coefficients)
    elif file_path:
        save_coefficients_local(file_path, coefficients)
