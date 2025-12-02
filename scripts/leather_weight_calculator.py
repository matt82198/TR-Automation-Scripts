"""
Leather Weight Calculator
Calculate box weights for shipping based on leather weight coefficients (lbs per sq ft).

Usage:
    python leather_weight_calculator.py --calculate-coefficient --name "Dublin Black 3.5-4 oz" --weight 45.5 --sqft 120
    python leather_weight_calculator.py --estimate-box --name "Dublin Black 3.5-4 oz" --sqft 85
    python leather_weight_calculator.py --list
"""

import argparse
import csv
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


# Coefficient storage file
CONFIG_DIR = Path(__file__).parent.parent / "config"
COEFFICIENTS_FILE = CONFIG_DIR / "leather_weight_coefficients.csv"


def load_coefficients() -> Dict[str, dict]:
    """Load stored weight coefficients from CSV"""
    coefficients = {}
    if COEFFICIENTS_FILE.exists():
        with open(COEFFICIENTS_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row['leather_name'].strip().lower()
                coefficients[key] = {
                    'leather_name': row['leather_name'],
                    'coefficient': float(row['coefficient']),
                    'sample_weight': float(row['sample_weight']) if row.get('sample_weight') else None,
                    'sample_sqft': float(row['sample_sqft']) if row.get('sample_sqft') else None,
                    'last_updated': row.get('last_updated', ''),
                    'notes': row.get('notes', '')
                }
    return coefficients


def save_coefficients(coefficients: Dict[str, dict]):
    """Save weight coefficients to CSV"""
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(COEFFICIENTS_FILE, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['leather_name', 'coefficient', 'sample_weight', 'sample_sqft', 'last_updated', 'notes']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for data in sorted(coefficients.values(), key=lambda x: x['leather_name']):
            writer.writerow(data)


def calculate_coefficient(weight_lbs: float, sqft: float) -> float:
    """Calculate weight coefficient (lbs per sq ft)"""
    if sqft <= 0:
        raise ValueError("Square footage must be greater than 0")
    return weight_lbs / sqft


def estimate_box_weight(coefficient: float, sqft: float) -> float:
    """Estimate box weight based on coefficient and square footage"""
    return coefficient * sqft


def find_leather(name: str, coefficients: Dict[str, dict]) -> Optional[dict]:
    """Find a leather by name (case-insensitive, partial match)"""
    name_lower = name.strip().lower()

    # Exact match first
    if name_lower in coefficients:
        return coefficients[name_lower]

    # Partial match
    matches = []
    for key, data in coefficients.items():
        if name_lower in key or key in name_lower:
            matches.append(data)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"Multiple matches found for '{name}':")
        for m in matches:
            print(f"  - {m['leather_name']} ({m['coefficient']:.4f} lbs/sqft)")
        return None

    return None


def add_or_update_coefficient(name: str, coefficient: float, weight: float = None,
                               sqft: float = None, notes: str = ""):
    """Add or update a leather weight coefficient"""
    coefficients = load_coefficients()
    key = name.strip().lower()

    coefficients[key] = {
        'leather_name': name.strip(),
        'coefficient': coefficient,
        'sample_weight': weight,
        'sample_sqft': sqft,
        'last_updated': datetime.now().strftime('%Y-%m-%d'),
        'notes': notes
    }

    save_coefficients(coefficients)
    return coefficients[key]


def list_coefficients() -> List[dict]:
    """List all stored coefficients"""
    coefficients = load_coefficients()
    return sorted(coefficients.values(), key=lambda x: x['leather_name'])


def interactive_mode():
    """Interactive mode for the calculator"""
    print("\n=== Leather Weight Calculator ===\n")
    print("Options:")
    print("  1. Calculate coefficient from bundle measurement")
    print("  2. Estimate box weight")
    print("  3. List stored coefficients")
    print("  4. Exit")

    while True:
        print()
        choice = input("Select option (1-4): ").strip()

        if choice == '1':
            name = input("Leather name (e.g., 'Dublin Black 3.5-4 oz'): ").strip()
            if not name:
                print("Name is required")
                continue

            try:
                weight = float(input("Bundle weight (lbs): "))
                sqft = float(input("Bundle square footage: "))
            except ValueError:
                print("Invalid number entered")
                continue

            coefficient = calculate_coefficient(weight, sqft)
            notes = input("Notes (optional): ").strip()

            # Save it
            add_or_update_coefficient(name, coefficient, weight, sqft, notes)

            print(f"\nCoefficient calculated and saved:")
            print(f"  {name}: {coefficient:.4f} lbs/sqft")
            print(f"  (Based on {weight} lbs / {sqft} sqft)")

        elif choice == '2':
            name = input("Leather name: ").strip()
            coefficients = load_coefficients()
            leather = find_leather(name, coefficients)

            if not leather:
                print(f"No coefficient found for '{name}'")
                manual = input("Enter coefficient manually? (y/n): ").strip().lower()
                if manual == 'y':
                    try:
                        coefficient = float(input("Coefficient (lbs/sqft): "))
                    except ValueError:
                        print("Invalid number")
                        continue
                else:
                    continue
            else:
                coefficient = leather['coefficient']
                print(f"Using stored coefficient: {coefficient:.4f} lbs/sqft")

            try:
                sqft = float(input("Box square footage: "))
            except ValueError:
                print("Invalid number")
                continue

            box_weight = estimate_box_weight(coefficient, sqft)
            print(f"\nEstimated box weight: {box_weight:.2f} lbs")

        elif choice == '3':
            coefficients_list = list_coefficients()
            if not coefficients_list:
                print("\nNo coefficients stored yet.")
            else:
                print(f"\nStored coefficients ({len(coefficients_list)}):")
                print("-" * 70)
                for c in coefficients_list:
                    sample_info = ""
                    if c['sample_weight'] and c['sample_sqft']:
                        sample_info = f" (from {c['sample_weight']} lbs / {c['sample_sqft']} sqft)"
                    print(f"  {c['leather_name']}: {c['coefficient']:.4f} lbs/sqft{sample_info}")
                print("-" * 70)

        elif choice == '4':
            print("Goodbye!")
            break
        else:
            print("Invalid option")


def main():
    parser = argparse.ArgumentParser(description="Leather Weight Calculator")
    parser.add_argument('--calculate-coefficient', action='store_true',
                        help='Calculate and store a new coefficient')
    parser.add_argument('--estimate-box', action='store_true',
                        help='Estimate box weight using stored coefficient')
    parser.add_argument('--list', action='store_true',
                        help='List all stored coefficients')
    parser.add_argument('--name', type=str, help='Leather name')
    parser.add_argument('--weight', type=float, help='Bundle weight in lbs')
    parser.add_argument('--sqft', type=float, help='Square footage')
    parser.add_argument('--notes', type=str, default='', help='Optional notes')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Run in interactive mode')

    args = parser.parse_args()

    # Default to interactive mode if no arguments
    if not any([args.calculate_coefficient, args.estimate_box, args.list]):
        interactive_mode()
        return

    if args.list:
        coefficients_list = list_coefficients()
        if not coefficients_list:
            print("No coefficients stored yet.")
        else:
            print(f"Stored coefficients ({len(coefficients_list)}):")
            for c in coefficients_list:
                print(f"  {c['leather_name']}: {c['coefficient']:.4f} lbs/sqft")
        return

    if args.calculate_coefficient:
        if not all([args.name, args.weight, args.sqft]):
            print("Error: --name, --weight, and --sqft are required for coefficient calculation")
            return

        coefficient = calculate_coefficient(args.weight, args.sqft)
        add_or_update_coefficient(args.name, coefficient, args.weight, args.sqft, args.notes)
        print(f"Coefficient saved: {args.name} = {coefficient:.4f} lbs/sqft")
        return

    if args.estimate_box:
        if not all([args.name, args.sqft]):
            print("Error: --name and --sqft are required for box estimation")
            return

        coefficients = load_coefficients()
        leather = find_leather(args.name, coefficients)

        if not leather:
            print(f"Error: No coefficient found for '{args.name}'")
            print("Use --calculate-coefficient to add one first, or --list to see available options")
            return

        box_weight = estimate_box_weight(leather['coefficient'], args.sqft)
        print(f"Leather: {leather['leather_name']}")
        print(f"Coefficient: {leather['coefficient']:.4f} lbs/sqft")
        print(f"Box sqft: {args.sqft}")
        print(f"Estimated weight: {box_weight:.2f} lbs")
        return


if __name__ == "__main__":
    main()
