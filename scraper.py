#!/usr/bin/env python3
"""
Web Scraper & Data Pipeline
Scrape structured data from websites, clean it, and export to CSV/JSON.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages: pip install requests beautifulsoup4")
    sys.exit(1)


class Scraper:
    """Generic web scraper with rate limiting and data extraction."""

    def __init__(self, base_url, delay=1.0, headers=None):
        self.base_url = base_url
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            headers
            or {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
            }
        )
        self.visited = set()
        self.data = []

    def fetch(self, url, params=None):
        """Fetch a page with rate limiting and error handling."""
        if url in self.visited:
            return None

        time.sleep(self.delay)
        self.visited.add(url)

        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def extract_links(self, soup, pattern=None):
        """Extract all links from a page, optionally filtering by regex pattern."""
        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(self.base_url, a["href"])
            if urlparse(href).netloc == urlparse(self.base_url).netloc:
                if pattern is None or re.search(pattern, href):
                    links.append(href)
        return list(set(links))

    def extract_table(self, soup, table_selector=None):
        """Extract data from HTML tables into list of dicts."""
        tables = (
            soup.select(table_selector)
            if table_selector
            else soup.find_all("table")
        )
        results = []

        for table in tables:
            headers = []
            for th in table.find_all("th"):
                headers.append(th.get_text(strip=True))

            if not headers:
                first_row = table.find("tr")
                if first_row:
                    headers = [
                        td.get_text(strip=True) for td in first_row.find_all("td")
                    ]

            for row in table.find_all("tr")[1 if headers else 0 :]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if cells:
                    if headers:
                        row_dict = dict(zip(headers, cells))
                    else:
                        row_dict = {f"col_{i}": c for i, c in enumerate(cells)}
                    results.append(row_dict)

        return results

    def extract_items(self, soup, container_selector, field_map):
        """
        Extract structured items from repeated page elements.

        field_map: dict mapping field names to CSS selectors or
                   (selector, attribute) tuples.
        Example:
            field_map = {
                "title": "h2.product-title",
                "price": "span.price",
                "image": ("img.product-img", "src"),
                "link":  ("a.product-link", "href"),
            }
        """
        items = []
        containers = soup.select(container_selector)

        for container in containers:
            item = {}
            for field, selector in field_map.items():
                if isinstance(selector, tuple):
                    sel, attr = selector
                    el = container.select_one(sel)
                    item[field] = el.get(attr, "").strip() if el else ""
                else:
                    el = container.select_one(selector)
                    item[field] = el.get_text(strip=True) if el else ""
            items.append(item)

        return items


class DataPipeline:
    """Clean, transform and export scraped data."""

    def __init__(self, data):
        self.data = list(data)
        self.original_count = len(self.data)

    def remove_duplicates(self, key=None):
        """Remove duplicate records, optionally by a specific key."""
        if key:
            seen = set()
            unique = []
            for item in self.data:
                val = item.get(key)
                if val not in seen:
                    seen.add(val)
                    unique.append(item)
            self.data = unique
        else:
            unique = []
            for item in self.data:
                if item not in unique:
                    unique.append(item)
            self.data = unique
        return self

    def filter_records(self, predicate):
        """Keep only records matching a predicate function."""
        self.data = [item for item in self.data if predicate(item)]
        return self

    def transform(self, field, func):
        """Apply a transformation function to a field across all records."""
        for item in self.data:
            if field in item:
                item[field] = func(item[field])
        return self

    def add_field(self, field, func):
        """Add a computed field to each record."""
        for item in self.data:
            item[field] = func(item)
        return self

    def rename_fields(self, mapping):
        """Rename fields according to a mapping dict."""
        renamed = []
        for item in self.data:
            new_item = {}
            for k, v in item.items():
                new_item[mapping.get(k, k)] = v
            renamed.append(new_item)
        self.data = renamed
        return self

    def clean_text(self, fields=None):
        """Strip whitespace and normalise spaces in text fields."""
        target_fields = fields or self._all_fields()
        for item in self.data:
            for field in target_fields:
                if field in item and isinstance(item[field], str):
                    item[field] = re.sub(r"\s+", " ", item[field]).strip()
        return self

    def clean_numbers(self, fields):
        """Parse numeric strings (remove currency symbols, commas) to floats."""
        for item in self.data:
            for field in fields:
                if field in item and isinstance(item[field], str):
                    cleaned = re.sub(r"[^\d.\-]", "", item[field])
                    try:
                        item[field] = float(cleaned) if cleaned else None
                    except ValueError:
                        item[field] = None
        return self

    def sort(self, key, reverse=False):
        """Sort records by a field."""
        self.data.sort(key=lambda x: x.get(key, ""), reverse=reverse)
        return self

    def to_csv(self, filepath):
        """Export data to CSV."""
        if not self.data:
            print("No data to export.")
            return

        fieldnames = list(self.data[0].keys())
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.data)
        print(f"Exported {len(self.data)} records to {filepath}")

    def to_json(self, filepath, indent=2):
        """Export data to JSON."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=indent, ensure_ascii=False)
        print(f"Exported {len(self.data)} records to {filepath}")

    def summary(self):
        """Print a summary of the pipeline results."""
        removed = self.original_count - len(self.data)
        print(f"\n  Pipeline Summary")
        print(f"  {'─' * 30}")
        print(f"  Records in:   {self.original_count}")
        print(f"  Records out:  {len(self.data)}")
        print(f"  Removed:      {removed}")
        if self.data:
            print(f"  Fields:       {', '.join(self.data[0].keys())}")
        return self

    def _all_fields(self):
        fields = set()
        for item in self.data:
            fields.update(item.keys())
        return fields


# ── Demo scrapers ──


def scrape_quotes():
    """Demo: Scrape quotes from quotes.toscrape.com."""
    print("\n  Scraping quotes.toscrape.com...")
    scraper = Scraper("https://quotes.toscrape.com", delay=0.5)

    page = 1
    while True:
        url = f"https://quotes.toscrape.com/page/{page}/"
        soup = scraper.fetch(url)
        if not soup:
            break

        quotes = scraper.extract_items(
            soup,
            "div.quote",
            {
                "text": "span.text",
                "author": "small.author",
                "tags": "div.tags",
            },
        )

        if not quotes:
            break

        scraper.data.extend(quotes)
        print(f"  Page {page}: {len(quotes)} quotes")

        next_btn = soup.select_one("li.next a")
        if not next_btn:
            break
        page += 1

    pipeline = DataPipeline(scraper.data)
    pipeline.clean_text()
    pipeline.transform("tags", lambda t: t.replace("Tags:", "").strip() if t else "")
    pipeline.add_field("scraped_at", lambda _: datetime.now().isoformat())
    pipeline.remove_duplicates(key="text")
    pipeline.summary()
    pipeline.to_csv("quotes.csv")
    pipeline.to_json("quotes.json")


def scrape_books():
    """Demo: Scrape book data from books.toscrape.com."""
    print("\n  Scraping books.toscrape.com...")
    scraper = Scraper("https://books.toscrape.com", delay=0.5)

    for page in range(1, 4):
        url = f"https://books.toscrape.com/catalogue/page-{page}.html"
        soup = scraper.fetch(url)
        if not soup:
            break

        books = scraper.extract_items(
            soup,
            "article.product_pod",
            {
                "title": ("h3 a", "title"),
                "price": "p.price_color",
                "availability": "p.instock",
                "rating": ("p.star-rating", "class"),
            },
        )

        scraper.data.extend(books)
        print(f"  Page {page}: {len(books)} books")

    rating_map = {
        "One": 1,
        "Two": 2,
        "Three": 3,
        "Four": 4,
        "Five": 5,
    }

    pipeline = DataPipeline(scraper.data)
    pipeline.clean_text(["title", "availability"])
    pipeline.clean_numbers(["price"])
    pipeline.transform(
        "rating",
        lambda r: next(
            (v for k, v in rating_map.items() if k in str(r)), 0
        ),
    )
    pipeline.transform(
        "availability", lambda a: "In stock" in a if a else False
    )
    pipeline.sort("price", reverse=True)
    pipeline.remove_duplicates(key="title")
    pipeline.summary()
    pipeline.to_csv("books.csv")
    pipeline.to_json("books.json")


def scrape_tables():
    """Demo: Scrape HTML tables from a URL."""
    print("\n  Enter a URL containing HTML tables:")
    url = input("  > ").strip()
    if not url:
        print("  No URL provided.")
        return

    scraper = Scraper(url, delay=0.5)
    soup = scraper.fetch(url)
    if not soup:
        return

    tables = scraper.extract_table(soup)
    if not tables:
        print("  No tables found on this page.")
        return

    print(f"  Found {len(tables)} rows across all tables")

    pipeline = DataPipeline(tables)
    pipeline.clean_text()
    pipeline.remove_duplicates()
    pipeline.summary()
    pipeline.to_csv("table_data.csv")
    pipeline.to_json("table_data.json")


def main():
    parser = argparse.ArgumentParser(
        description="Web Scraper & Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scraper.py --demo quotes    Scrape quotes.toscrape.com\n"
            "  python scraper.py --demo books     Scrape books.toscrape.com\n"
            "  python scraper.py --demo tables    Scrape tables from any URL\n"
        ),
    )
    parser.add_argument(
        "--demo",
        choices=["quotes", "books", "tables"],
        help="Run a demo scraper",
    )

    args = parser.parse_args()

    print("\n  ╔═══════════════════════════════════╗")
    print("  ║  Web Scraper & Data Pipeline      ║")
    print("  ╚═══════════════════════════════════╝")

    if args.demo:
        demos = {
            "quotes": scrape_quotes,
            "books": scrape_books,
            "tables": scrape_tables,
        }
        demos[args.demo]()
    else:
        print("\n  Choose a demo:")
        print("    1. Scrape quotes (quotes.toscrape.com)")
        print("    2. Scrape books  (books.toscrape.com)")
        print("    3. Scrape tables (any URL)")
        choice = input("\n  > ").strip()
        if choice == "1":
            scrape_quotes()
        elif choice == "2":
            scrape_books()
        elif choice == "3":
            scrape_tables()
        else:
            print("  Invalid choice.")


if __name__ == "__main__":
    main()
