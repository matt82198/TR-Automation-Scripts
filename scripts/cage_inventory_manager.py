"""
Cage Inventory Manager
CLI tool for managing the cage inventory stored in Google Sheets.
Supports bulk add, backup, export, and listing operations.

Uses service account credentials from .streamlit/secrets.toml to connect
to the same Google Sheet that Streamlit Cloud uses.
"""

import argparse
import csv
import sys
import os
from pathlib import Path
from datetime import datetime

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python < 3.11

import gspread
from google.oauth2.service_account import Credentials


# ---------------------------------------------------------------------------
# Google Sheets connection (reuses Streamlit secrets)
# ---------------------------------------------------------------------------

SECRETS_PATH = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
WORKSHEET_NAME = "cage_inventory"
COLUMNS = ["swatch_book", "color", "weight", "date_added"]

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_secrets():
    """Load gsheets connection settings from secrets.toml."""
    with open(SECRETS_PATH, "rb") as f:
        secrets = tomllib.load(f)
    return secrets["connections"]["gsheets"]


def get_gsheet_client():
    """Build an authenticated gspread client from secrets.toml service account."""
    cfg = load_secrets()
    creds_info = {
        "type": cfg["type"],
        "project_id": cfg["project_id"],
        "private_key_id": cfg["private_key_id"],
        "private_key": cfg["private_key"],
        "client_email": cfg["client_email"],
        "client_id": cfg["client_id"],
        "auth_uri": cfg["auth_uri"],
        "token_uri": cfg["token_uri"],
        "auth_provider_x509_cert_url": cfg["auth_provider_x509_cert_url"],
        "client_x509_cert_url": cfg["client_x509_cert_url"],
    }
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds), cfg["spreadsheet"]


def get_worksheet():
    """Open the cage_inventory worksheet."""
    client, spreadsheet_url = get_gsheet_client()
    spreadsheet_id = spreadsheet_url.split("/d/")[1].split("/")[0]
    sh = client.open_by_key(spreadsheet_id)
    try:
        return sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        print(f"Worksheet '{WORKSHEET_NAME}' not found. Creating it...")
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=100, cols=len(COLUMNS))
        ws.update(values=[COLUMNS], range_name="A1:D1")
        return ws


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def load_inventory(ws) -> list[dict]:
    """Read all rows from the worksheet as list of dicts."""
    records = ws.get_all_records()
    # Normalize keys and ensure string values
    inventory = []
    for row in records:
        inventory.append({
            "swatch_book": str(row.get("swatch_book", "")),
            "color": str(row.get("color", "")),
            "weight": str(row.get("weight", "")),
            "date_added": str(row.get("date_added", "")),
        })
    return inventory


def save_inventory(ws, inventory: list[dict]):
    """Overwrite the worksheet with the given inventory (header + data rows)."""
    rows = [COLUMNS]
    for item in inventory:
        rows.append([
            item.get("swatch_book", ""),
            item.get("color", ""),
            item.get("weight", ""),
            item.get("date_added", ""),
        ])
    ws.clear()
    ws.update(values=rows, range_name=f"A1:D{len(rows)}")


def backup_inventory(ws, output_path: str) -> str:
    """Export current inventory to a CSV backup file."""
    inventory = load_inventory(ws)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for item in inventory:
            writer.writerow(item)
    return output_path


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_list(args):
    """List current cage inventory."""
    ws = get_worksheet()
    inventory = load_inventory(ws)
    if not inventory:
        print("Cage is empty.")
        return

    print(f"\nCage Inventory: {len(inventory)} items")
    print("=" * 60)

    # Group by swatch_book
    groups = {}
    for item in inventory:
        sb = item["swatch_book"]
        groups.setdefault(sb, []).append(item)

    for sb_name in sorted(groups.keys()):
        items = groups[sb_name]
        print(f"\n  {sb_name} ({len(items)} items)")
        print(f"  {'-' * 40}")
        for item in sorted(items, key=lambda x: (x["color"], x["weight"])):
            weight_str = f" - {item['weight']}" if item["weight"] else ""
            date_str = f"  (added {item['date_added']})" if item["date_added"] else ""
            print(f"    {item['color']}{weight_str}{date_str}")


def cmd_backup(args):
    """Backup current inventory to CSV."""
    ws = get_worksheet()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = args.output or f"output/cage_inventory_backup_{timestamp}.csv"

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    path = backup_inventory(ws, output_path)
    inventory = load_inventory(ws)
    print(f"Backed up {len(inventory)} items to {path}")


def cmd_add(args):
    """Add items from a CSV file or inline arguments."""
    ws = get_worksheet()
    inventory = load_inventory(ws)
    today = datetime.now().strftime("%Y-%m-%d")

    new_items = []

    if args.csv:
        # Load from CSV file
        with open(args.csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                new_items.append({
                    "swatch_book": row.get("swatch_book", "Untracked").strip(),
                    "color": row.get("color", "").strip(),
                    "weight": row.get("weight", "").strip(),
                    "date_added": row.get("date_added", today).strip() or today,
                })
    elif args.items:
        # Inline items: "description|weight" or just "description"
        for raw in args.items:
            parts = raw.split("|", 1)
            desc = parts[0].strip()
            weight = parts[1].strip() if len(parts) > 1 else ""
            sb = args.swatch_book or "Untracked"
            new_items.append({
                "swatch_book": sb,
                "color": desc,
                "weight": weight,
                "date_added": today,
            })
    else:
        print("Error: Provide --csv <file> or --items <item1> <item2> ...")
        sys.exit(1)

    if not new_items:
        print("No items to add.")
        return

    # Backup first if not skipped
    if not args.no_backup:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_path = f"output/cage_inventory_backup_{timestamp}.csv"
        os.makedirs("output", exist_ok=True)
        backup_inventory(ws, backup_path)
        print(f"Backup saved to {backup_path}")

    # Check for duplicates
    existing = set()
    for item in inventory:
        existing.add((item["swatch_book"], item["color"], item["weight"]))

    added = 0
    skipped = 0
    for item in new_items:
        key = (item["swatch_book"], item["color"], item["weight"])
        if key in existing:
            print(f"  [SKIP] Already exists: {item['color']} ({item['swatch_book']})")
            skipped += 1
        else:
            inventory.append(item)
            existing.add(key)
            print(f"  [ADD]  {item['color']}" + (f" - {item['weight']}" if item['weight'] else "") + f" ({item['swatch_book']})")
            added += 1

    if added > 0:
        save_inventory(ws, inventory)
        print(f"\nAdded {added} items, skipped {skipped} duplicates. Total: {len(inventory)}")
    else:
        print(f"\nNo new items added ({skipped} duplicates skipped).")


def cmd_export(args):
    """Export inventory to CSV (same as backup but explicit output path)."""
    ws = get_worksheet()
    output_path = args.output or "output/cage_inventory_export.csv"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    path = backup_inventory(ws, output_path)
    inventory = load_inventory(ws)
    print(f"Exported {len(inventory)} items to {path}")


def cmd_restore(args):
    """Restore inventory from a CSV backup file."""
    ws = get_worksheet()

    # Backup current state first
    if not args.no_backup:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_path = f"output/cage_inventory_backup_{timestamp}.csv"
        os.makedirs("output", exist_ok=True)
        current = load_inventory(ws)
        backup_inventory(ws, backup_path)
        print(f"Current inventory ({len(current)} items) backed up to {backup_path}")

    # Load the restore file
    restore_items = []
    with open(args.csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            restore_items.append({
                "swatch_book": row.get("swatch_book", ""),
                "color": row.get("color", ""),
                "weight": row.get("weight", ""),
                "date_added": row.get("date_added", ""),
            })

    save_inventory(ws, restore_items)
    print(f"Restored {len(restore_items)} items from {args.csv}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Manage cage inventory in Google Sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # List everything in the cage
  python scripts/cage_inventory_manager.py list

  # Backup current inventory
  python scripts/cage_inventory_manager.py backup

  # Add untracked items inline
  python scripts/cage_inventory_manager.py add --items "Amalfi Lux Burgundy|2-3 oz" "Black Yellowstone|4-5 oz" "Cognac Classic"

  # Add from catalog with swatch book name
  python scripts/cage_inventory_manager.py add --swatch-book "Horween Dublin" --items "Black|3-4 oz" "Natural|5-6 oz"

  # Bulk add from CSV file
  python scripts/cage_inventory_manager.py add --csv items_to_add.csv

  # Export to CSV
  python scripts/cage_inventory_manager.py export --output cage_dump.csv

  # Restore from backup
  python scripts/cage_inventory_manager.py restore --csv output/cage_inventory_backup_2025-02-16.csv
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List current cage inventory")

    # backup
    p_backup = subparsers.add_parser("backup", help="Backup inventory to CSV")
    p_backup.add_argument("--output", "-o", help="Output file path")

    # add
    p_add = subparsers.add_parser("add", help="Add items to cage inventory")
    p_add.add_argument("--csv", help="CSV file with items (columns: swatch_book, color, weight)")
    p_add.add_argument("--items", nargs="+", help="Inline items: 'description|weight' or 'description'")
    p_add.add_argument("--swatch-book", help="Swatch book name for inline items (default: Untracked)")
    p_add.add_argument("--no-backup", action="store_true", help="Skip automatic backup before modifying")

    # export
    p_export = subparsers.add_parser("export", help="Export inventory to CSV")
    p_export.add_argument("--output", "-o", help="Output file path")

    # restore
    p_restore = subparsers.add_parser("restore", help="Restore inventory from CSV backup")
    p_restore.add_argument("--csv", required=True, help="CSV file to restore from")
    p_restore.add_argument("--no-backup", action="store_true", help="Skip automatic backup before restoring")

    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "backup": cmd_backup,
        "add": cmd_add,
        "export": cmd_export,
        "restore": cmd_restore,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
