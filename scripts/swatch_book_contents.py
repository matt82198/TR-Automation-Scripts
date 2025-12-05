"""
Swatch Book Contents Generator

Scrapes the Squarespace website to get all color variations for each leather type,
then generates separate page files for each swatch book for easy printing.
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from typing import Dict, List, Set, Tuple
from urllib.parse import urljoin
from datetime import datetime


class SwatchBookGenerator:
    """Generate swatch book contents by scraping the Squarespace website"""

    def __init__(self, base_url: str = "https://www.thetanneryrow.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_leather_product_links(self) -> List[Tuple[str, str]]:
        """Get all leather product links from category pages"""
        products = []
        visited_urls = set()

        category_urls = [
            f"{self.base_url}/horween",
            f"{self.base_url}/all-leather",
            f"{self.base_url}/walpier",
            f"{self.base_url}/virgilio",
            f"{self.base_url}/tempesti",
        ]

        print("Scanning category pages for leather products...")

        for cat_url in category_urls:
            try:
                resp = self.session.get(cat_url, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                for link in soup.find_all('a', href=True):
                    href = link['href']
                    text = link.get_text(strip=True)

                    if not href.startswith('/'):
                        continue
                    if href in ['/', '/cart', '/search']:
                        continue

                    if '/all-leather/' in href:
                        full_url = urljoin(self.base_url, href)
                        if full_url not in visited_urls and text:
                            visited_urls.add(full_url)
                            products.append((text, full_url))

            except Exception as e:
                print(f"  Error fetching {cat_url}: {e}")

        seen = set()
        unique_products = []
        for name, url in products:
            if url not in seen:
                seen.add(url)
                unique_products.append((name, url))

        print(f"  Found {len(unique_products)} unique product links")
        return unique_products

    def extract_product_colors(self, product_url: str) -> Tuple[str, List[str], List[str]]:
        """Extract color and weight options from a product page"""
        colors = []
        weights = []
        product_name = ""

        try:
            resp = self.session.get(product_url, timeout=15)
            if resp.status_code != 200:
                return product_name, colors, weights

            soup = BeautifulSoup(resp.text, 'html.parser')

            title = soup.find('h1')
            if title:
                product_name = title.get_text(strip=True)

            for script in soup.find_all('script'):
                if script.string and 'variants' in script.string and 'attributes' in script.string:
                    color_matches = re.findall(r'"Color":\s*"([^"]+)"', script.string)
                    colors.extend(color_matches)

                    weight_matches = re.findall(r'"Weight":\s*"([^"]+)"', script.string)
                    weights.extend(weight_matches)

            colors = sorted(list(set(colors)))
            weights = sorted(list(set(weights)))

        except Exception as e:
            print(f"  Error parsing {product_url}: {e}")

        return product_name, colors, weights

    def get_all_leather_colors(self) -> Dict[str, Dict]:
        """Get all leather products with their color variants"""
        products = self.get_leather_product_links()
        leather_products = {}

        skip_keywords = ['panel', 'strip', 'swatch', 'hang tag', 'horsefront',
                        'bundle', 'mystery', 'scrap', 'conditioner', 'glue']

        print("\nFetching color variants for each leather product...")

        for name, url in products:
            name_lower = name.lower()

            if any(skip in name_lower for skip in skip_keywords):
                continue

            product_name, colors, weights = self.extract_product_colors(url)

            if colors:
                leather_products[product_name or name] = {
                    'colors': colors,
                    'weights': weights,
                    'url': url
                }
                print(f"  {product_name or name}: {len(colors)} colors")

        return leather_products

    def get_tannery_from_product(self, product_name: str) -> str:
        """Extract the tannery name from a product name"""
        product_lower = product_name.lower()

        if 'horween' in product_lower:
            return 'Horween'
        elif 'walpier' in product_lower:
            return 'Walpier'
        elif 'virgilio' in product_lower:
            return 'Virgilio'
        elif 'tempesti' in product_lower:
            return 'Tempesti'
        else:
            return 'Other'

    def get_leather_type_from_product(self, product_name: str) -> str:
        """Extract the leather type (article) from a product name"""
        name = product_name

        prefixes = ['Horween •', 'Horween �', 'Conceria Walpier •', 'Conceria Walpier �',
                   'Virgilio •', 'Virgilio �', 'Tempesti •', 'Tempesti �']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
                break

        return name

    def run(self) -> Dict[str, Dict]:
        """Main method to generate swatch book contents"""

        print("=" * 60)
        print("FETCHING LEATHER PRODUCTS FROM WEBSITE")
        print("=" * 60)
        leather_products = self.get_all_leather_colors()

        tanneries = defaultdict(list)
        for product_name, info in leather_products.items():
            tannery = self.get_tannery_from_product(product_name)
            leather_type = self.get_leather_type_from_product(product_name)
            tanneries[tannery].append({
                'full_name': product_name,
                'leather_type': leather_type,
                'colors': info['colors'],
                'weights': info['weights']
            })

        results = {}

        for tannery in sorted(tanneries.keys()):
            products = tanneries[tannery]

            for product in sorted(products, key=lambda x: x['leather_type']):
                leather_type = product['leather_type']
                colors = product['colors']
                swatch_book_name = f"{tannery} {leather_type}"

                results[swatch_book_name] = {
                    'tannery': tannery,
                    'leather_type': leather_type,
                    'colors': colors,
                    'color_count': len(colors)
                }

        return results

    def sanitize_filename(self, name: str) -> str:
        """Make a string safe for use as a filename"""
        # Replace problematic characters
        name = name.replace('®', '')
        name = name.replace('•', '')
        name = name.replace('/', '-')
        name = name.replace('\\', '-')
        name = name.replace(':', '-')
        name = name.replace('*', '')
        name = name.replace('?', '')
        name = name.replace('"', '')
        name = name.replace('<', '')
        name = name.replace('>', '')
        name = name.replace('|', '')
        name = re.sub(r'\s+', '_', name.strip())
        return name

    def generate_separate_pages(self, results: Dict[str, Dict], output_dir: str):
        """Generate separate page files for each swatch book"""

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Group by tannery
        by_tannery = defaultdict(list)
        for swatch_name, info in results.items():
            by_tannery[info['tannery']].append((swatch_name, info))

        file_count = 0

        # 00 - Title Page
        title_lines = []
        title_lines.append("")
        title_lines.append("")
        title_lines.append("")
        title_lines.append("")
        title_lines.append("")
        title_lines.append("╔══════════════════════════════════════════════════════════════════╗")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                    T H E   T A N N E R Y   R O W                 ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                   ─────────────────────────────                  ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                    SWATCH BOOK REFERENCE GUIDE                   ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                                                                  ║")
        title_lines.append(f"║                         {datetime.now().strftime('%B %Y'):^20}                   ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("║                                                                  ║")
        title_lines.append("╚══════════════════════════════════════════════════════════════════╝")
        title_lines.append("")
        title_lines.append("")

        with open(os.path.join(output_dir, "00_Title_Page.txt"), 'w', encoding='utf-8') as f:
            f.write('\n'.join(title_lines))
        file_count += 1

        # 01 - Table of Contents
        toc_lines = []
        toc_lines.append("")
        toc_lines.append("")
        toc_lines.append("")
        toc_lines.append("                         TABLE OF CONTENTS")
        toc_lines.append("                         ─────────────────")
        toc_lines.append("")
        toc_lines.append("")

        for tannery in sorted(by_tannery.keys()):
            items = by_tannery[tannery]
            toc_lines.append(f"    {tannery.upper()}")
            toc_lines.append("")
            for swatch_name, info in sorted(items, key=lambda x: x[0]):
                toc_lines.append(f"        • {info['leather_type']}")
            toc_lines.append("")
            toc_lines.append("")

        with open(os.path.join(output_dir, "01_Table_of_Contents.txt"), 'w', encoding='utf-8') as f:
            f.write('\n'.join(toc_lines))
        file_count += 1

        # Each Tannery Section
        page_num = 2
        for tannery in sorted(by_tannery.keys()):
            items = by_tannery[tannery]

            # Tannery divider page
            divider_lines = []
            divider_lines.append("")
            divider_lines.append("")
            divider_lines.append("")
            divider_lines.append("")
            divider_lines.append("")
            divider_lines.append("")
            divider_lines.append("")
            divider_lines.append("")
            divider_lines.append("┌──────────────────────────────────────────────────────────────────┐")
            divider_lines.append("│                                                                  │")
            divider_lines.append("│                                                                  │")
            divider_lines.append(f"│{tannery.upper():^66}│")
            divider_lines.append("│                                                                  │")
            divider_lines.append(f"│{f'{len(items)} Leather Types':^66}│")
            divider_lines.append("│                                                                  │")
            divider_lines.append("│                                                                  │")
            divider_lines.append("└──────────────────────────────────────────────────────────────────┘")
            divider_lines.append("")
            divider_lines.append("")

            filename = f"{page_num:02d}_{self.sanitize_filename(tannery)}_Divider.txt"
            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                f.write('\n'.join(divider_lines))
            file_count += 1
            page_num += 1

            # Each swatch book page
            for swatch_name, info in sorted(items, key=lambda x: x[0]):
                leather_type = info['leather_type']
                colors = info['colors']

                page_lines = []
                page_lines.append("")
                page_lines.append("")
                page_lines.append("━" * 70)
                page_lines.append("")
                page_lines.append(f"    {tannery.upper()}")
                page_lines.append("")
                page_lines.append(f"    {leather_type}")
                page_lines.append("")
                page_lines.append("━" * 70)
                page_lines.append("")
                page_lines.append(f"    {len(colors)} Colors:")
                page_lines.append("")
                page_lines.append("    ┌" + "─" * 60 + "┐")

                for color in colors:
                    page_lines.append(f"    │    • {color:<54}│")

                page_lines.append("    └" + "─" * 60 + "┘")
                page_lines.append("")
                page_lines.append("")

                filename = f"{page_num:02d}_{self.sanitize_filename(tannery)}_{self.sanitize_filename(leather_type)}.txt"
                with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                    f.write('\n'.join(page_lines))
                file_count += 1
                page_num += 1

        # Summary Page
        summary_lines = []
        summary_lines.append("")
        summary_lines.append("")
        summary_lines.append("━" * 70)
        summary_lines.append("")
        summary_lines.append("                              SUMMARY")
        summary_lines.append("")
        summary_lines.append("━" * 70)
        summary_lines.append("")

        total_books = 0
        total_colors = 0

        for tannery in sorted(by_tannery.keys()):
            items = by_tannery[tannery]
            tannery_colors = sum(info['color_count'] for _, info in items)

            summary_lines.append(f"    {tannery}")
            summary_lines.append("    " + "─" * 50)

            for swatch_name, info in sorted(items, key=lambda x: x[0]):
                summary_lines.append(f"        {info['leather_type']:<40} {info['color_count']:>3} colors")
                total_books += 1
                total_colors += info['color_count']

            summary_lines.append(f"        {'─' * 44}")
            summary_lines.append(f"        {'Subtotal:':<40} {tannery_colors:>3} colors")
            summary_lines.append("")

        summary_lines.append("")
        summary_lines.append("━" * 70)
        summary_lines.append(f"    TOTAL SWATCH BOOKS:     {total_books}")
        summary_lines.append(f"    TOTAL COLOR SWATCHES:   {total_colors}")
        summary_lines.append("━" * 70)
        summary_lines.append("")

        filename = f"{page_num:02d}_Summary.txt"
        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
            f.write('\n'.join(summary_lines))
        file_count += 1

        print(f"\nGenerated {file_count} page files in: {output_dir}")
        return output_dir


def main():
    """Main entry point"""
    generator = SwatchBookGenerator()
    results = generator.run()

    if results:
        output_dir = f"swatch_book_pages_{datetime.now().strftime('%Y-%m-%d')}"
        generator.generate_separate_pages(results, output_dir)

        print("\n" + "=" * 60)
        print("COMPLETE")
        print("=" * 60)
        print(f"\nPages saved to folder: {output_dir}")

        total_books = len(results)
        total_colors = sum(info['color_count'] for info in results.values())
        print(f"Total swatch books: {total_books}")
        print(f"Total color swatches: {total_colors}")
    else:
        print("\nNo swatch book contents could be determined.")


if __name__ == "__main__":
    main()
