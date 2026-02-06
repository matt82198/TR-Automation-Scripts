#!/usr/bin/env python3
"""
Build SKU mapping from Squarespace orders matched to QuickBooks items.

Fetches recent orders from Squarespace API, parses products into components
(tannage, color, weight), and matches against QB item list using exact
component matching.

Usage:
    python scripts/build_sku_mapping.py
    python scripts/build_sku_mapping.py --orders 200
    python scripts/build_sku_mapping.py --qb-items examples/qb_items.csv --output output/mappings.csv
"""

import argparse
import csv
import os
import re
import requests
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass


def get_secret(key: str, default: str = None) -> str:
    """Get secret from Streamlit secrets or environment variable."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


SQUARESPACE_API_KEY = get_secret('SQUARESPACE_API_KEY')
SQUARESPACE_BASE_URL = 'https://api.squarespace.com/1.0'


@dataclass
class LeatherComponents:
    """Parsed components of a leather product."""
    tannage: str  # Dublin, Derby, Essex, Chromexcel, etc.
    color: str    # Black, Brown, Natural, English Tan, etc.
    weight: str   # 3-4 oz, 5-6 oz, etc. (normalized)
    raw_weight: str  # Original weight string
    product_type: str  # full_hide, panel, horsefront, strips, accessory, etc.
    brand: str    # Horween, Tempesti, Walpier, etc.


# Known tannages - order matters for matching (longer/more specific first)
TANNAGES = [
    # Compound tannages first (more specific)
    'Cavalier Chromexcel', 'Cavalier Chrxl',
    'Chromexcel', 'Chrxl',  # Abbreviation
    'Dublin',
    'Derby',
    'Essex',
    'Cavalier',
    'Montana',
    'Predator',
    'Latigo', 'Illini Latigo',
    'Vermont',
    'Aspen',
    'Krypto',
    'Cypress',
    'Buckaroo',
    'Orion',
    'Legacy',
    'Plainsman',
    'Dearborn',
    'LaSalle', 'Lasalle',
    'Glove',
    'Featherlite',
    'Rockford',
    'Yellowstone',
    'Puttman',
    'Regency', 'Regency Calf',
    'Buttero',
    'Baku',
    'Elbamatt', 'Elbamatt Liscio', 'Elbamatt Lux',
    'Maine', 'Maine Liscio', 'Maine Eco Lux',
    'Margot', 'Margot Fog',
    'Vachetta',
    'Smoked Matte',
    'Tuscany',
    'Museum',
    'Rocky',
    'Sierra',
    'Fenice',
    'Pinnacle',
    # C.F. Stead tannages
    'Waxy Commander', 'Doeskin', 'Suede',
    'Kudu Waxy', 'Kudu Classic', 'Kudu Reverse', 'Kudu',
    'Crazy Cow',
    # Tusting & Burnett tannages
    'Mad Dog', 'Sokoto', 'Sokoto Bookbinding', 'Sokoto Dip',
    # Splenda tannages
    'Classic', 'Splenda Classic',
    # C.F. Stead additional
    'Waxy Mohawk',
    # Arazzo tannages (upholstery)
    'Alaska', 'Abilene', 'Allure', 'Amalfi', 'Antique Retro', 'Barbary', 'Bayou', 'Boulder',
    'Portsmouth',
    # Virgilio tannages
    'Pierrot Lux', 'Pierrot',
    # Italian misc
    'Nubuck', 'Italian Nubuck', 'Crocco', 'Italian Crocco', 'Crinkle', 'Italian Crinkle',
    # Material types (for strips)
    'Russet Horsehide', 'Horsehide', 'Horsebutt', 'Handstained',
    # Calf lining
    'Glovey',
    # Country Cow (standalone brand/tannage)
    'Country Cow',
]

# Known colors - order matters (longer/more specific first)
COLORS = [
    # Multi-word colors first
    'Greener Pastures', 'Greener P',  # QB abbreviation
    'Light Natural', 'Lt Natural', 'Lt Nat',    # QB abbreviation
    'Dark Brown', 'Dark Cognac', 'Dark Chestnut', 'Dark Coffee', 'Dark Olive',
    'Light Chestnut',
    'English Tan', 'English T',  # QB abbreviation
    'Brown Nut', 'Nut Brown',
    'Carolina Brown', 'Chicago Tan',
    'Color #8', 'Color 8', '#8',
    'Cobalt Blue', 'Ink Blue', 'Fun Blue',
    'Golf Green',
    'London Bus Red', 'Lollipop Red',
    'Burnt Orange',
    'Olde English', 'Olde Eng',  # QB abbreviation
    'Russet Brown',
    'Dark Rio',
    'Jet Black',
    'Tristan Red',  # Mad Dog color
    # Single-word colors
    'Black', 'Brown', 'Natural', 'Tan', 'Chestnut', 'Cognac',
    'Whiskey', 'Whisky', 'Burgundy',
    'Navy', 'Ink', 'Olive', 'Vetiver', 'Harvest', 'Green', 'White', 'Acorn',
    'Espresso', 'Coffee', 'Charcoal', 'Steel',
    'Rio', 'Bone', 'Ivory', 'Wheat',
    # Italian colors
    'Alloro', 'Cammello', 'Ambra', 'Fieno', 'T. Moro',
    'Cobalto', 'Olmo', 'Castagna', 'Siena', 'Girasole', 'Topo',
    # C.F. Stead colors
    'Mole', 'Snuff', 'Wheatbuck',
    # Mad Dog colors
    'Mojito', 'Coyote', 'Danube', 'Orange',
    # Other
    'Purple', 'Sienna', 'Russet',
    # Lining colors
    'Faggio', 'British Tan',
    # Racing colors (bookbinding)
    'Racing Green', 'Midnight Navy', 'Cranberry', 'Azure',
    # Kudu/Stead colors
    'Deep Forest', 'Baltic', 'Loden', 'Autumn Spice', 'Caramel',
    'Teak', 'Bitter Chocolate', 'Brandy', 'Cloud',
    # More accessory colors
    'Coach',
]

# Color equivalences for matching (QB often abbreviates)
COLOR_EQUIVALENTS = {
    'greener pastures': ['greener p', 'greener pastures', 'greener'],
    'greener p': ['greener pastures', 'greener p', 'greener'],
    'greener': ['greener pastures', 'greener p', 'greener'],
    'light natural': ['lt natural', 'lt nat', 'light natural', 'lt'],
    'lt natural': ['light natural', 'lt nat', 'lt natural'],
    'lt nat': ['light natural', 'lt natural', 'lt nat'],
    'brown nut': ['nut brown', 'brown nut'],
    'nut brown': ['brown nut', 'nut brown'],
    'english tan': ['english t', 'english tan', 'eng tan', 'eng t'],
    'english t': ['english tan', 'english t', 'eng tan'],
    'olde english': ['olde eng', 'olde english'],
    'olde eng': ['olde english', 'olde eng'],
    'color #8': ['color 8', 'color #8', '#8'],
    'color 8': ['color #8', 'color 8', '#8'],
    'dark brown': ['dk brown', 'dark brown', 'brown'],
    'dark cognac': ['dk cognac', 'dark cognac'],
    'london bus red': ['london bus', 'london bus red'],
    'midnight navy': ['navy', 'midnight navy'],
    'russet brown': ['russet', 'russet brown'],
    'fun blue': ['blue', 'fun blue'],
}

# Weight normalization: map Squarespace weight ranges to possible QB formats
# Uses lenient matching - if SS range overlaps QB range, it's a match
# Prefer higher weight within range
WEIGHT_NORMALIZATIONS = {
    # Full oz ranges - expanded to accept sub-ranges (prefer higher)
    '3-4': ['3.5-4', '3-4', '3-3.5', '4-5'],  # Added 4-5 as fallback
    '4-5': ['4.5-5', '4-5', '4-4.5', '5-6', '3.5-4'],  # Adjacent ranges
    '5-6': ['5.5-6', '5-6', '5-5.5', '6-7', '4.5-5'],
    '6-7': ['6.5-7', '6-7', '6-6.5', '5.5-6'],
    '7-8': ['7.5-8', '7-8', '7-7.5', '8-9'],
    '8-9': ['8.5-9', '8/9', '8-9', '8-8.5', '9-10'],
    '9-10': ['9.5-10', '9/10', '9-10', '9-9.5'],
    # Half oz ranges - very lenient, accept overlapping
    '3-3.5': ['3-3.5', '3-4', '3.5-4'],
    '3.5-4': ['3.5-4', '3-4', '4-5', '4-4.5'],
    '4-4.5': ['4-4.5', '4-5', '4.5-5', '3.5-4'],
    '4.5-5': ['4.5-5', '4-5', '4.5-5.5', '5-5.5', '5-6'],
    '4.5-5.5': ['4.5-5.5', '4.5-5', '5-5.5', '5-6', '4-5'],  # C.F. Stead lenient
    '5-5.5': ['5-5.5', '5-6', '5.5-6', '4.5-5'],
    '5.5-6': ['5.5-6', '5-6', '6-7'],
    # mm weights (Italian/upholstery leathers) - very lenient
    '0.9-1.1': ['0.9-1.1', '0.9/1.1', '1.0-1.2', '1-1.2'],
    '1.0-1.2': ['1.0-1.2', '1.0/1.2', '0.9-1.1', '1-1.2', '1.2-1.4'],
    '1-1.2': ['1-1.2', '1.0-1.2', '0.9-1.1'],
    '1.2-1.4': ['1.2-1.4', '1.2/1.4', '1.0-1.2', '1.4-1.6'],
    '1.3-1.5': ['1.3-1.5', '1.2-1.4', '1.4-1.6'],
    '1.4-1.6': ['1.4-1.6', '1.4/1.6', '1.2-1.4', '1.6-1.8'],
    '1.8-2.0': ['1.8-2.0', '1.8/2.0', '1.8-2.2', '2.0-2.2'],
    '1.8-2.2': ['1.8-2.2', '1.8-2.0', '2.0-2.2', '2.2-2.4'],
    '2.0-2.2': ['2.0-2.2', '2.0/2.2', '1.8-2.0', '1.8-2.2'],
    '2.6-2.8': ['2.6-2.8', '2.6/2.8'],
}


def normalize_weight(weight: str) -> str:
    """Normalize weight string for matching."""
    if not weight:
        return ''
    # Remove 'oz', 'mm', spaces, parentheses
    w = weight.lower().replace('oz', '').replace('mm', '').replace(' ', '')
    w = re.sub(r'\([^)]*\)', '', w).strip()
    # Normalize dash variants
    w = w.replace('–', '-').replace('—', '-')
    return w


def get_weight_variants(weight: str) -> List[str]:
    """Get all possible QB weight formats for a given weight."""
    normalized = normalize_weight(weight)
    return WEIGHT_NORMALIZATIONS.get(normalized, [normalized])


def parse_squarespace_product(product_name: str, variant: str = '') -> Optional[LeatherComponents]:
    """
    Parse a Squarespace product into components.

    Examples:
        "Horween • Dublin - Black - 3-4 oz" -> (Dublin, Black, 3-4)
        "Horween Dublin Leather Panels - 1' Panel (12"x12") - Black - 3-4 oz" -> (Dublin, Black, 3-4, panel)
    """
    full_name = product_name
    if variant:
        full_name = f"{product_name} - {variant}"

    # Detect product type
    name_lower = full_name.lower()
    product_type = 'full_hide'
    if 'panel' in name_lower and 'mystery' not in name_lower:
        product_type = 'panel'
    elif 'horsefront' in name_lower or 'dhf' in name_lower or 'shf' in name_lower:
        product_type = 'horsefront'
    elif 'strip' in name_lower:
        product_type = 'strips'
    elif 'mystery bundle' in name_lower or 'mystery leather' in name_lower:
        product_type = 'mystery_bundle'
    elif 'swatch' in name_lower or 'sample book' in name_lower:
        product_type = 'sample_book'
    elif any(x in name_lower for x in ['saphir', 'tokonole', 'conditioner', 'brush', 'cream', 'balm', 'glue', 'belt', 'bag', 'wallet', 'ecostick']):
        product_type = 'accessory'
    elif 'basketball' in name_lower:
        product_type = 'basketball'
    elif 'football' in name_lower:
        product_type = 'football'
    elif 'calf lining' in name_lower or 'lining' in name_lower:
        product_type = 'lining'
    elif 'scrap' in name_lower:
        product_type = 'scrap'
    elif 'bookbinding' in name_lower:
        product_type = 'bookbinding'

    # Detect brand
    brand = ''
    if 'horween' in full_name.lower():
        brand = 'Horween'
    elif 'tempesti' in full_name.lower():
        brand = 'Tempesti'
    elif 'walpier' in full_name.lower() or 'buttero' in full_name.lower():
        brand = 'Walpier'
    elif 'virgilio' in full_name.lower():
        brand = 'Virgilio'
    elif 'splenda' in full_name.lower():
        brand = 'Splenda'
    elif 'onda verde' in full_name.lower():
        brand = 'Onda Verde'
    elif 'tusting' in full_name.lower():
        brand = 'Tusting & Burnett'
    elif 'c.f. stead' in full_name.lower() or 'cf stead' in full_name.lower():
        brand = 'CF Stead'

    # Find tannage
    tannage = ''
    name_lower = full_name.lower()
    for t in TANNAGES:
        if t.lower() in name_lower:
            tannage = t
            break

    # Find color - look in variant first, then full name
    color = ''
    search_text = variant if variant else full_name
    search_lower = search_text.lower()
    for c in COLORS:
        if c.lower() in search_lower:
            color = c
            break

    # Find weight - pattern like "3-4 oz", "1.0-1.2 mm", or "9+ oz"
    weight = ''
    raw_weight = ''
    weight_match = re.search(r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*(oz|mm)', full_name, re.IGNORECASE)
    if weight_match:
        raw_weight = weight_match.group(0)
        weight = f"{weight_match.group(1)}-{weight_match.group(2)}"
    else:
        # Try "9+ oz" pattern (means 9 oz and up)
        plus_match = re.search(r'(\d+)\+?\s*oz', full_name, re.IGNORECASE)
        if plus_match:
            raw_weight = plus_match.group(0)
            weight = f"{plus_match.group(1)}+"

    return LeatherComponents(
        tannage=tannage,
        color=color,
        weight=weight,
        raw_weight=raw_weight,
        product_type=product_type,
        brand=brand
    )


def parse_qb_item(item_name: str) -> Dict[str, str]:
    """
    Parse a QB item name into searchable components.

    Examples:
        "*Black Dublin 4-4.5 oz" -> {tannage: Dublin, color: Black, weight: 4-4.5}
        "Dublin Black 3.5-4 oz" -> {tannage: Dublin, color: Black, weight: 3.5-4}
        "Panel Chrxl Black 3.5-4 oz" -> {tannage: Chrxl, color: Black, weight: 3.5-4, type: panel}
    """
    # Remove leading asterisk and "Sides" prefix
    name = item_name.lstrip('*').strip()
    name = re.sub(r'^Sides\s+', '', name, flags=re.IGNORECASE)

    components = {
        'tannage': '',
        'color': '',
        'weight': '',
        'is_panel': 'panel' in name.lower(),
        'is_dhf': 'dhf' in name.lower() or 'double horsefront' in name.lower(),
        'is_shf': 'shf' in name.lower() or 'single horsefront' in name.lower(),
        'is_holiday': 'holiday' in name.lower(),
        'raw': item_name,
    }

    name_lower = name.lower()

    # Find tannage
    for t in TANNAGES:
        if t.lower() in name_lower:
            components['tannage'] = t
            break

    # Find color
    for c in COLORS:
        if c.lower() in name_lower:
            components['color'] = c
            break

    # Find weight
    weight_match = re.search(r'(\d+(?:\.\d+)?)\s*[-–/]\s*(\d+(?:\.\d+)?)\s*(oz|z|mm)?', name, re.IGNORECASE)
    if weight_match:
        components['weight'] = f"{weight_match.group(1)}-{weight_match.group(2)}"

    return components


def load_qb_items(csv_file: str) -> List[Dict[str, str]]:
    """Load and parse QB items from CSV."""
    items = []

    if not os.path.exists(csv_file):
        print(f"Warning: QB item file not found: {csv_file}")
        return items

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_name = row.get('Item', '').strip()
            if not item_name:
                continue

            parsed = parse_qb_item(item_name)
            parsed['active'] = row.get('Active Status', '') == 'Active'
            items.append(parsed)

    return items


def colors_match(color1: str, color2: str) -> bool:
    """Check if two colors match, accounting for equivalents."""
    if not color1 or not color2:
        return False
    c1 = color1.lower().strip()
    c2 = color2.lower().strip()
    if c1 == c2:
        return True
    # Check equivalents
    equivalents = COLOR_EQUIVALENTS.get(c1, [c1])
    return c2 in equivalents


def find_sample_book_match(components: LeatherComponents, qb_items: List[Dict], product_name: str, variant: str = '') -> Optional[str]:
    """
    Find matching Sample Book QB item.

    QB format: "Sample Book - {Brand} {Tannage}" or "Sample Book - All {Brand}"
    Examples:
        - "Sample Book - Horween Dublin"
        - "Sample Book - All Horween"
        - "Sample Book - Walpier Buttero"
        - "Sample Book - Italian Nubuck" (TR Collection variant)
    """
    # Build search terms based on brand and tannage
    search_terms = []

    # TR Collection Swatch Books - variant IS the tannage/type
    if 'tr collection' in product_name.lower() and variant:
        # Direct match: "Sample Book - {variant}"
        search_terms.append(f"sample book - {variant.lower()}")
        # Also try without "Italian" prefix if present
        if variant.lower().startswith('italian '):
            search_terms.append(f"sample book - {variant.lower()}")
        # Special case for Nappa Lamb -> Kid, Lamb, Goat
        if 'lamb' in variant.lower() or 'nappa' in variant.lower():
            search_terms.append('sample book - kid, lamb, goat')

    # Tusting & Burnett Swatch Books - variant IS the type
    if 'tusting' in product_name.lower() and variant:
        # Handle "Sokoto Dip-Dye" -> "T & B Dip Dye"
        if 'dip' in variant.lower():
            search_terms.append('sample book - t & b dip dye')
        # Handle "Marsh" -> "T & B Marsh"
        if 'marsh' in variant.lower():
            search_terms.append('sample book - t & b marsh')
        # Generic: "Sample Book - T & B {variant}"
        search_terms.append(f"sample book - t & b {variant.lower()}")

    # Les Rives Swatch Books - variant IS the type
    if 'les rives' in product_name.lower() and variant:
        search_terms.append(f"sample book - les rives {variant.lower()}")
        search_terms.append(f"sample book - {variant.lower()}")

    # Onda Verde Swatch Books - variant IS the type
    if 'onda verde' in product_name.lower() and variant:
        search_terms.append(f"sample book - onda verde {variant.lower()}")
        search_terms.append(f"sample book - {variant.lower()}")

    if components.brand and components.tannage:
        # Try specific: "Sample Book - Horween Dublin"
        search_terms.append(f"sample book - {components.brand.lower()} {components.tannage.lower()}")

    if components.tannage:
        # Try tannage only
        search_terms.append(f"sample book - {components.tannage.lower()}")
        # Also try with "Horween" prefix for Horween tannages
        if 'horween' in product_name.lower():
            search_terms.append(f"sample book - horween {components.tannage.lower()}")

    if components.brand:
        # Fallback to "All {Brand}"
        search_terms.append(f"sample book - all {components.brand.lower()}")

    # Special cases
    if 'walpier' in product_name.lower():
        search_terms.append('sample book - all walpier')
    if 'stead' in product_name.lower() or 'c.f. stead' in product_name.lower():
        search_terms.append('sample book - all stead')
        if components.tannage:
            search_terms.append(f"sample book - stead {components.tannage.lower()}")
    if 'tempesti' in product_name.lower():
        search_terms.append('sample book - all tempesti')

    for qb in qb_items:
        qb_raw = qb.get('raw', '').lower()
        if not qb_raw.startswith('sample book'):
            continue

        for term in search_terms:
            # Fuzzy match - check if search term is contained or close
            if term in qb_raw:
                return qb.get('raw')
            # Also check partial matches for abbreviated names
            term_parts = term.replace('sample book - ', '').split()
            if all(part in qb_raw for part in term_parts):
                return qb.get('raw')

    return None


def find_accessory_match(components: LeatherComponents, qb_items: List[Dict], product_name: str, variant: str) -> Optional[str]:
    """
    Find matching accessory QB item by keyword matching.

    Accessories have unique identifiers:
    - Tokonole products: "Tokonole Clear 120g", "Tokonole Leather Care Cream"
    - Ecostick: "Ecostick 1816B"
    - Saphir: "Saphir Pate de Luxe", "Saphir Nappa Balm"
    - Belts: Commission (cordovan belts are custom work)
    """
    full_name = f"{product_name} {variant}".lower()

    # Tokonole matching
    if 'tokonole' in full_name:
        if 'care cream' in full_name or 'conditioning' in full_name or 'balm' in full_name:
            # Tokonole Leather Care Cream
            for qb in qb_items:
                if 'tokonole' in qb.get('raw', '').lower() and 'care' in qb.get('raw', '').lower():
                    return qb.get('raw')
        elif 'burnishing' in full_name or 'gum' in full_name:
            # Tokonole Burnishing Gum - look for size and color
            color = 'clear'
            if 'black' in full_name:
                color = 'black'
            elif 'brown' in full_name:
                color = 'brown'

            size = '120g'
            if '500' in full_name:
                size = '500g'

            for qb in qb_items:
                qb_raw = qb.get('raw', '').lower()
                if 'tokonole' in qb_raw and color in qb_raw and size in qb_raw:
                    return qb.get('raw')

    # Saphir matching
    if 'saphir' in full_name:
        # Map Saphir product types to QB names
        if 'pate de luxe' in full_name or 'p\xe2te de luxe' in full_name or 'wax polish' in full_name:
            for qb in qb_items:
                if 'saphir pate de luxe' in qb.get('raw', '').lower():
                    return qb.get('raw')
        elif 'nappa' in full_name:
            for qb in qb_items:
                if 'saphir nappa' in qb.get('raw', '').lower():
                    return qb.get('raw')
        elif 'renovateur' in full_name:
            for qb in qb_items:
                if 'saphir renovateur' in qb.get('raw', '').lower():
                    return qb.get('raw')
        elif 'cordovan' in full_name:
            for qb in qb_items:
                if 'saphir cordovan' in qb.get('raw', '').lower():
                    return qb.get('raw')
        elif 'oiled' in full_name:
            for qb in qb_items:
                if 'saphir oiled' in qb.get('raw', '').lower():
                    return qb.get('raw')
        elif 'brush' in full_name:
            for qb in qb_items:
                if 'saphir brush' in qb.get('raw', '').lower():
                    return qb.get('raw')
        elif 'cloth' in full_name:
            for qb in qb_items:
                if 'saphir cloth' in qb.get('raw', '').lower():
                    return qb.get('raw')

    # Ecostick matching
    if 'ecostick' in full_name:
        # Extract product number like "1816B"
        match = re.search(r'(\d+\w*)', full_name)
        if match:
            product_num = match.group(1).upper()
            for qb in qb_items:
                qb_raw = qb.get('raw', '').lower()
                if 'ecostick' in qb_raw and product_num.lower() in qb_raw:
                    return qb.get('raw')
        else:
            # Default to 1816B (most common)
            for qb in qb_items:
                if 'ecostick 1816b' in qb.get('raw', '').lower():
                    return qb.get('raw')

    # Belts - cordovan belts are typically Commission items
    if 'belt' in full_name:
        for qb in qb_items:
            if qb.get('raw', '').lower() == 'commission':
                return qb.get('raw')

    # Leather Conditioner
    if 'conditioner' in full_name:
        # "The Leather Conditioner" is TR's branded product
        for qb in qb_items:
            qb_raw = qb.get('raw', '').lower()
            if 'tr leather conditioner' in qb_raw:
                return qb.get('raw')
        # Fallback to generic
        for qb in qb_items:
            qb_raw = qb.get('raw', '').lower()
            if 'leather conditioner' in qb_raw and 'rita' not in qb_raw:
                return qb.get('raw')

    return None


def find_sports_leather_match(components: LeatherComponents, qb_items: List[Dict], product_name: str, variant: str) -> Optional[str]:
    """
    Find matching sports leather (basketball/football) QB item.

    QB format:
    - "Horween 2003C Basketball Leather"
    - "Horween 8064 Football Leather"
    - "Horween Football - Black, 4-5 oz"
    """
    full_name = f"{product_name} {variant}".lower()

    # Look for product number (like 8064, 2003C)
    product_num_match = re.search(r'(\d{3,4}[A-Z]?)', full_name, re.IGNORECASE)
    product_num = product_num_match.group(1).upper() if product_num_match else ''

    if components.product_type == 'basketball':
        # Try to match by product number first
        if product_num:
            for qb in qb_items:
                qb_raw = qb.get('raw', '').lower()
                if 'basketball' in qb_raw and product_num.lower() in qb_raw:
                    return qb.get('raw')
        # Then try by color/weight
        if components.color:
            for qb in qb_items:
                qb_raw = qb.get('raw', '').lower()
                if 'basketball' in qb_raw and components.color.lower() in qb_raw:
                    return qb.get('raw')
        # Default to 2003C Basketball Leather (standard 5oz)
        return 'Horween 2003C Basketball Leather'

    if components.product_type == 'football':
        # Try to match by product number first
        if product_num:
            for qb in qb_items:
                qb_raw = qb.get('raw', '').lower()
                if 'football' in qb_raw and product_num.lower() in qb_raw:
                    return qb.get('raw')
        # Then try by color/weight
        if components.color:
            for qb in qb_items:
                qb_raw = qb.get('raw', '').lower()
                if 'football' in qb_raw and components.color.lower() in qb_raw:
                    return qb.get('raw')

    return None


def find_lining_match(components: LeatherComponents, qb_items: List[Dict], product_name: str, variant: str) -> Optional[str]:
    """
    Find matching lining (Glovey calf lining) QB item.

    QB format: "Glovey {Color} Calf Lining"
    """
    color = components.color.lower() if components.color else ''

    # Calf lining -> Glovey
    for qb in qb_items:
        qb_raw = qb.get('raw', '').lower()
        if 'glovey' in qb_raw and 'calf lining' in qb_raw:
            if color and color in qb_raw:
                return qb.get('raw')

    # Goat lining
    if 'goat' in product_name.lower():
        for qb in qb_items:
            qb_raw = qb.get('raw', '').lower()
            if 'goat lining' in qb_raw:
                if color and color in qb_raw:
                    return qb.get('raw')

    return None


def find_bookbinding_match(components: LeatherComponents, qb_items: List[Dict], product_name: str, variant: str) -> Optional[str]:
    """
    Find matching Sokoto Bookbinding QB item.

    QB formats:
    - "T & B Sokoto Book Chestnut 2 oz" (short form)
    - "Tusting & Burnett Sokoto Bookbinding - Chestnut, 2-2.5 oz" (long form)
    """
    color = components.color.lower() if components.color else ''

    for qb in qb_items:
        qb_raw = qb.get('raw', '').lower()
        # Match both "sokoto book" (short) and "sokoto bookbinding" (long)
        if 'sokoto' in qb_raw and ('book' in qb_raw or 'bookbinding' in qb_raw):
            if color and color in qb_raw:
                return qb.get('raw')

    return None


def find_strips_match(components: LeatherComponents, qb_items: List[Dict], product_name: str, variant: str) -> Optional[str]:
    """
    Find matching strips QB item.

    QB formats:
    - "Horween Russet Horsehide Strips Hard Rolled - 7-9 oz"
    - "Horween Handstained Strip - Black"
    - "Horsebutt Strips Chrxl Black"
    """
    full_name = f"{product_name} {variant}".lower()

    # Russet Horsehide Strips
    if 'russet' in full_name and ('horsehide' in full_name or 'strip' in full_name):
        # Determine roll type: hard rolled vs soft rolled
        roll_type = 'soft rolled' if 'soft' in full_name else 'hard rolled'
        roll_abbrev = 'sr' if roll_type == 'soft rolled' else 'hr'

        # Get weight - handle "9+ oz" as "9 oz and up"
        weight = components.weight
        weight_search_terms = []
        if weight:
            if weight.endswith('+'):
                # "9+" means "9 oz and up" - search for this exact pattern
                base = weight.replace('+', '')
                weight_search_terms = [f'{base} oz and up', 'and up', base]
            else:
                weight_search_terms = get_weight_variants(weight)

        # Find all matching items, then pick best by weight preference
        candidates = []
        for qb in qb_items:
            qb_raw = qb.get('raw', '').lower()
            if 'russet' in qb_raw and 'strip' in qb_raw:
                # Check roll type
                roll_match = (roll_type in qb_raw or
                              roll_abbrev in qb_raw.split() or
                              f'strips {roll_abbrev}' in qb_raw)
                if roll_match:
                    # Check weight if we have one
                    if weight_search_terms:
                        # Score by how specific the match is
                        for i, wv in enumerate(weight_search_terms):
                            if wv in qb_raw:
                                # Lower index = higher priority (more specific)
                                candidates.append((i, qb.get('raw')))
                                break
                    else:
                        candidates.append((999, qb.get('raw')))

        if candidates:
            # Return best match (lowest priority index = most specific)
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

    # Handstained Strips
    if 'handstained' in full_name or 'hand stained' in full_name:
        color = components.color.lower() if components.color else ''
        for qb in qb_items:
            qb_raw = qb.get('raw', '').lower()
            if 'handstained' in qb_raw and 'strip' in qb_raw:
                if color and color in qb_raw:
                    return qb.get('raw')

    # Horsebutt Strips
    if 'horsebutt' in full_name:
        color = components.color.lower() if components.color else ''
        for qb in qb_items:
            qb_raw = qb.get('raw', '').lower()
            if 'horsebutt' in qb_raw and 'strip' in qb_raw:
                if color and color in qb_raw:
                    return qb.get('raw')

    return None


def find_qb_match(components: LeatherComponents, qb_items: List[Dict], product_name: str = '', variant: str = '') -> Optional[str]:
    """
    Find matching QB item using STRICT component matching.

    ALL of these must match:
    1. Tannage must match exactly (Chromexcel/Chrxl are equivalent)
    2. Color must match exactly (with known equivalents)
    3. Weight must match (with normalization)
    4. Product type must match (panel vs full hide vs horsefront)

    Returns None if any required component doesn't match.
    """
    # Handle sample books with fuzzy matching
    if components.product_type == 'sample_book':
        match = find_sample_book_match(components, qb_items, product_name, variant)
        return match if match else 'MISCELLANOUS LEATHER'

    # Handle accessories with keyword matching
    if components.product_type == 'accessory':
        match = find_accessory_match(components, qb_items, product_name, variant)
        return match if match else 'MISCELLANOUS LEATHER'

    # Handle strips with specialized matching
    if components.product_type == 'strips':
        match = find_strips_match(components, qb_items, product_name, variant)
        if match:
            return match
        # Fall through to standard matching if no specific match

    # Handle sports leather
    if components.product_type in ('basketball', 'football'):
        match = find_sports_leather_match(components, qb_items, product_name, variant)
        return match if match else 'MISCELLANOUS LEATHER'

    # Handle calf lining
    if components.product_type == 'lining':
        match = find_lining_match(components, qb_items, product_name, variant)
        return match if match else 'MISCELLANOUS LEATHER'

    # Handle bookbinding
    if components.product_type == 'bookbinding':
        match = find_bookbinding_match(components, qb_items, product_name, variant)
        return match if match else 'MISCELLANOUS LEATHER'

    # Handle scrap boxes
    if components.product_type == 'scrap':
        return 'Scrap Leather'

    # Handle gift cards (not redemptions)
    if 'gift card' in product_name.lower() and 'redemption' not in product_name.lower():
        return 'Gift card'

    # Handle mystery bundles
    if components.product_type == 'mystery_bundle':
        # Mystery Leather Panels need a new QB item
        if 'mystery leather panel' in product_name.lower():
            return 'MISCELLANOUS LEATHER'
        # Other mystery bundles are previous years' sales - skip/ignore
        return None  # Deprecated - previous year sale items

    # Skip items without enough components to match
    if not components.tannage or not components.color:
        if not components.tannage:
            return 'MISCELLANOUS LEATHER'  # Fallback when we can't parse

    # Build list of acceptable tannage values
    tannage_variants = {components.tannage.lower()}
    if components.tannage.lower() == 'chromexcel':
        tannage_variants.add('chrxl')
    elif components.tannage.lower() == 'chrxl':
        tannage_variants.add('chromexcel')
    elif components.tannage.lower() == 'cavalier chromexcel':
        tannage_variants.add('cavalier chrxl')
    elif components.tannage.lower() == 'cavalier chrxl':
        tannage_variants.add('cavalier chromexcel')
    elif components.tannage.lower() == 'splenda classic':
        tannage_variants.add('classic')
    elif components.tannage.lower() == 'classic' and 'splenda' in product_name.lower():
        tannage_variants.add('splenda classic')

    # Get acceptable weight values
    weight_variants = set()
    if components.weight:
        for w in get_weight_variants(components.weight):
            weight_variants.add(normalize_weight(w))

    matches = []

    for qb in qb_items:
        # STRICT CHECK 1: Tannage must match
        qb_tannage = qb.get('tannage', '').lower()
        if not qb_tannage:
            continue
        if qb_tannage not in tannage_variants:
            # Check if tannage is contained (for compound names)
            tannage_ok = False
            for tv in tannage_variants:
                if tv in qb_tannage or qb_tannage in tv:
                    tannage_ok = True
                    break
            if not tannage_ok:
                continue

        # STRICT CHECK 2: Color must match (if we have a color)
        if components.color:
            qb_color = qb.get('color', '').lower()
            if not colors_match(components.color, qb_color):
                continue

        # STRICT CHECK 3: Weight must match (if we have a weight)
        # Exception: horsefronts often don't have weight in QB item name
        if components.weight:
            qb_weight = normalize_weight(qb.get('weight', ''))
            if qb_weight:  # QB item has weight - must match
                if qb_weight not in weight_variants:
                    continue
            elif components.product_type != 'horsefront':
                # QB item has no weight, and we're not a horsefront - skip
                continue
            # else: horsefront without weight in QB - that's OK

        # STRICT CHECK 4: Product type must match
        type_ok = False
        if components.product_type == 'panel':
            type_ok = qb.get('is_panel', False)
        elif components.product_type == 'horsefront':
            # SHF maps to DHF equivalent (half price), so only match DHF items
            type_ok = qb.get('is_dhf', False)
        elif components.product_type == 'full_hide':
            type_ok = not qb.get('is_panel') and not qb.get('is_dhf') and not qb.get('is_shf') and not qb.get('is_holiday')
        elif components.product_type == 'strips':
            type_ok = 'strip' in qb.get('raw', '').lower()
        else:
            type_ok = True  # Other types don't have strict matching

        if not type_ok:
            continue

        # This item matches all criteria
        score = 10  # Base score for matching
        if qb.get('active'):
            score += 1  # Prefer active items

        matches.append((score, qb.get('raw')))

    if not matches:
        # Try to find closest match by tannage+color (ignore weight)
        closest = find_closest_match(components, qb_items)
        if closest:
            return closest  # Will be flagged as needs_review

        # No match found - fall back to MISCELLANEOUS LEATHER
        return 'MISCELLANOUS LEATHER'

    # Return highest scoring match
    matches.sort(key=lambda x: -x[0])
    return matches[0][1]


def find_closest_match(components: LeatherComponents, qb_items: List[Dict]) -> Optional[str]:
    """
    Find closest QB match by tannage+color, ignoring weight.
    Used as fallback when exact weight match not found.
    Returns the match with highest weight (safest for billing).
    """
    if not components.tannage:
        return None

    # Build tannage variants
    tannage_variants = {components.tannage.lower()}
    if components.tannage.lower() == 'chromexcel':
        tannage_variants.add('chrxl')
    elif components.tannage.lower() == 'chrxl':
        tannage_variants.add('chromexcel')
    elif components.tannage.lower() == 'cavalier chromexcel':
        tannage_variants.add('cavalier chrxl')

    candidates = []

    for qb in qb_items:
        qb_tannage = qb.get('tannage', '').lower()
        if not qb_tannage:
            continue

        # Check tannage match
        tannage_ok = qb_tannage in tannage_variants
        if not tannage_ok:
            for tv in tannage_variants:
                if tv in qb_tannage or qb_tannage in tv:
                    tannage_ok = True
                    break

        if not tannage_ok:
            continue

        # Check color match (if we have one)
        if components.color:
            if not colors_match(components.color, qb.get('color', '')):
                continue

        # Check product type
        type_ok = False
        if components.product_type == 'panel':
            type_ok = qb.get('is_panel', False)
        elif components.product_type == 'horsefront':
            # SHF maps to DHF equivalent (half price)
            type_ok = qb.get('is_dhf', False)
        elif components.product_type == 'full_hide':
            type_ok = not qb.get('is_panel') and not qb.get('is_dhf') and not qb.get('is_shf') and not qb.get('is_holiday')
        else:
            type_ok = True

        if not type_ok:
            continue

        # Score by weight - prefer higher weights
        weight = qb.get('weight', '')
        weight_score = 0
        if weight:
            # Extract first number for sorting
            import re
            match = re.search(r'(\d+(?:\.\d+)?)', weight)
            if match:
                weight_score = float(match.group(1))

        candidates.append((weight_score, qb.get('raw')))

    if not candidates:
        return None

    # Return highest weight match
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def fetch_squarespace_orders(count: int = 100) -> List[Dict]:
    """Fetch recent orders from Squarespace API."""
    if not SQUARESPACE_API_KEY:
        print("ERROR: SQUARESPACE_API_KEY not set")
        return []

    headers = {
        'Authorization': f'Bearer {SQUARESPACE_API_KEY}',
        'User-Agent': 'SKUMappingBuilder/1.0'
    }

    orders = []
    cursor = None

    while len(orders) < count:
        params = {}
        if cursor:
            params['cursor'] = cursor

        try:
            response = requests.get(
                f'{SQUARESPACE_BASE_URL}/commerce/orders',
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            batch = data.get('result', [])
            if not batch:
                break

            orders.extend(batch)

            pagination = data.get('pagination', {})
            if not pagination.get('hasNextPage'):
                break
            cursor = pagination.get('nextPageCursor')

        except Exception as e:
            print(f"Error fetching orders: {e}")
            break

    return orders[:count]


def extract_unique_products(orders: List[Dict]) -> List[Dict]:
    """Extract unique (product, variant) combinations from orders."""
    seen = set()
    products = []

    for order in orders:
        for item in order.get('lineItems', []):
            product_name = item.get('productName', '')

            # Build variant string from customizations
            variant_parts = []
            customizations = item.get('customizations') or []
            for custom in customizations:
                value = custom.get('value', '')
                if value:
                    variant_parts.append(value)
            variant = ' - '.join(variant_parts)

            # Also check variantOptions
            variant_options = item.get('variantOptions') or []
            for opt in variant_options:
                value = opt.get('value', '')
                if value and value not in variant:
                    variant_parts.append(value)
            variant = ' - '.join(variant_parts)

            key = (product_name, variant)
            if key not in seen:
                seen.add(key)
                products.append({
                    'product_name': product_name,
                    'variant': variant,
                    'sku': item.get('sku', ''),
                    'quantity': item.get('quantity', 1),
                })

    return products


def generate_sku(components: LeatherComponents, product_name: str) -> str:
    """Generate a consistent internal SKU."""
    parts = []

    # Brand prefix
    brand_codes = {
        'Horween': 'HOR',
        'Tempesti': 'TEM',
        'Walpier': 'WAL',
        'Virgilio': 'VIR',
        'Splenda': 'SPL',
        'Onda Verde': 'OND',
        'Tusting & Burnett': 'TUS',
        'CF Stead': 'CFS',
    }
    if components.brand:
        parts.append(brand_codes.get(components.brand, components.brand[:3].upper()))

    # Product type prefix
    type_codes = {
        'panel': 'PNL',
        'horsefront': 'HF',
        'strips': 'STR',
        'mystery_bundle': 'MYS',
        'sample_book': 'SMP',
        'accessory': 'ACC',
    }
    if components.product_type != 'full_hide':
        parts.append(type_codes.get(components.product_type, ''))

    # Tannage
    tannage_codes = {
        'Dublin': 'DUB',
        'Derby': 'DRB',
        'Essex': 'ESX',
        'Chromexcel': 'CHX',
        'Chrxl': 'CHX',
        'Cavalier': 'CAV',
        'Montana': 'MON',
        'Predator': 'PRD',
        'Latigo': 'LAT',
        'Vermont': 'VRM',
        'Aspen': 'ASP',
        'Buttero': 'BUT',
        'Margot': 'MAR',
        'Vachetta': 'VAC',
    }
    if components.tannage:
        parts.append(tannage_codes.get(components.tannage, components.tannage[:3].upper()))

    # Color
    color_codes = {
        'Black': 'BLK',
        'Brown': 'BRN',
        'Natural': 'NAT',
        'English Tan': 'ENG',
        'Brown Nut': 'NUT',
        'Nut Brown': 'NUT',
        'Chestnut': 'CHE',
        'Cognac': 'COG',
        'Whiskey': 'WHI',
        'Burgundy': 'BUR',
        'Color #8': 'C8',
        'Navy': 'NAV',
        'Olive': 'OLV',
        'Greener Pastures': 'GRN',
    }
    if components.color:
        parts.append(color_codes.get(components.color, components.color[:3].upper()))

    # Weight
    if components.weight:
        weight_code = components.weight.replace('-', '').replace('.', '')
        parts.append(weight_code)

    sku = '-'.join(p for p in parts if p)
    return sku if sku else 'UNKNOWN'


def main():
    parser = argparse.ArgumentParser(description='Build SKU mapping from Squarespace orders')
    parser.add_argument('--orders', type=int, default=100,
                        help='Number of recent orders to fetch (default: 100)')
    parser.add_argument('--qb-items', type=str,
                        default='examples/QB item list Oct 2025.xlsx - Sheet1.csv',
                        help='QB item list CSV file')
    parser.add_argument('--output', type=str, default='config/product_mappings.csv',
                        help='Output mapping CSV file')
    parser.add_argument('--show-unmatched', action='store_true',
                        help='Show products that could not be matched')

    args = parser.parse_args()

    # Load QB items
    print(f"Loading QB items from: {args.qb_items}")
    qb_items = load_qb_items(args.qb_items)
    print(f"  Loaded {len(qb_items)} QB items")
    active_count = sum(1 for q in qb_items if q.get('active'))
    print(f"  Active items: {active_count}")

    # Fetch Squarespace orders
    print(f"\nFetching {args.orders} recent orders from Squarespace...")
    orders = fetch_squarespace_orders(args.orders)
    print(f"  Fetched {len(orders)} orders")

    # Extract unique products
    products = extract_unique_products(orders)
    print(f"  Found {len(products)} unique product/variant combinations")

    # Match products to QB items
    print("\nMatching products to QB items...")
    mappings = []
    exact_match = 0
    closest_match = 0
    fallback_count = 0
    unmatched = []
    fallback_items = []
    review_items = []

    for prod in products:
        components = parse_squarespace_product(prod['product_name'], prod['variant'])

        # First try exact match
        qb_item = find_qb_match(components, qb_items, prod['product_name'], prod['variant'])

        sku = generate_sku(components, prod['product_name'])

        # Determine match type
        is_fallback = qb_item == 'MISCELLANOUS LEATHER'

        # Check if this was a closest match (weight mismatch) vs exact
        is_closest_match = False
        if qb_item and not is_fallback and components.weight:
            # Verify if weight actually matches
            qb_weight = ''
            for qb in qb_items:
                if qb.get('raw') == qb_item:
                    qb_weight = qb.get('weight', '')
                    break
            if qb_weight:
                weight_variants = get_weight_variants(components.weight)
                normalized_variants = [normalize_weight(w) for w in weight_variants]
                if normalize_weight(qb_weight) not in normalized_variants:
                    is_closest_match = True

        mapping = {
            'internal_sku': sku,
            'squarespace_product': prod['product_name'],
            'squarespace_variant': prod['variant'],
            'squarespace_sku': prod.get('sku', ''),
            'quickbooks_item': qb_item or '',
            'tannage': components.tannage,
            'color': components.color,
            'weight': components.weight,
            'product_type': components.product_type,
            'needs_qb_item': 'Y' if is_fallback else '',
            'needs_review': 'Y' if is_closest_match else '',
        }
        mappings.append(mapping)

        # Skip deprecated items (None return)
        if qb_item is None:
            continue

        if qb_item and not is_fallback and not is_closest_match:
            exact_match += 1
        elif is_closest_match:
            closest_match += 1
            review_items.append(mapping)
        elif is_fallback:
            fallback_count += 1
            fallback_items.append(mapping)
        else:
            unmatched.append(mapping)

    print(f"  Exact match: {exact_match}/{len(products)}")
    print(f"  Closest match (needs review): {closest_match}")
    print(f"  Fallback to MISC (needs QB item): {fallback_count}")
    print(f"  Unmatched: {len(unmatched)}")

    # Show items that need review (closest match, weight mismatch)
    if args.show_unmatched and review_items:
        print("\n=== Closest Match - Needs Review (weight mismatch) ===")
        for m in review_items[:20]:
            print(f"  {m['squarespace_product']}")
            if m['squarespace_variant']:
                print(f"    Variant: {m['squarespace_variant']}")
            print(f"    Parsed: {m['tannage']} / {m['color']} / {m['weight']} ({m['product_type']})")
            print(f"    Matched to: {m['quickbooks_item']}")

    # Show items that need QB updates
    if args.show_unmatched and fallback_items:
        print("\n=== Needs QB Item (no match found) ===")
        for m in fallback_items[:30]:
            print(f"  {m['squarespace_product']}")
            if m['squarespace_variant']:
                print(f"    Variant: {m['squarespace_variant']}")
            print(f"    Parsed: {m['tannage']} / {m['color']} / {m['weight']} ({m['product_type']})")

    if args.show_unmatched and unmatched:
        print("\n=== Truly Unmatched Products ===")
        for m in unmatched[:20]:
            print(f"  {m['squarespace_product']}")
            if m['squarespace_variant']:
                print(f"    Variant: {m['squarespace_variant']}")
            print(f"    Parsed: {m['tannage']} / {m['color']} / {m['weight']} ({m['product_type']})")

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['internal_sku', 'squarespace_product', 'squarespace_variant',
                      'squarespace_sku', 'quickbooks_item', 'tannage', 'color',
                      'weight', 'product_type', 'needs_qb_item', 'needs_review']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mappings)

    print(f"\nWrote {len(mappings)} mappings to: {args.output}")

    # Summary by product type
    print("\n=== Summary by Product Type ===")
    by_type = {}
    for m in mappings:
        t = m['product_type']
        if t not in by_type:
            by_type[t] = {'total': 0, 'matched': 0}
        by_type[t]['total'] += 1
        if m['quickbooks_item']:
            by_type[t]['matched'] += 1

    for t, counts in sorted(by_type.items()):
        pct = (counts['matched'] / counts['total'] * 100) if counts['total'] > 0 else 0
        print(f"  {t}: {counts['matched']}/{counts['total']} ({pct:.0f}%)")


if __name__ == '__main__':
    main()
