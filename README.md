# Web Scraper & Data Pipeline

A Python web scraper with a built-in data cleaning pipeline. Extracts structured data from websites (HTML tables, repeated elements, links) and exports clean CSV/JSON output.

## Features

- **Generic scraper** — Fetch pages with rate limiting, session persistence and custom headers
- **Table extraction** — Parse HTML tables into structured records automatically
- **Item extraction** — Define CSS-selector field maps to scrape repeated page elements
- **Link discovery** — Crawl internal links with regex filtering
- **Data pipeline** — Deduplicate, filter, transform, rename, clean and sort records
- **Export** — Output to CSV or JSON with summary statistics
- **Demo scrapers** — Ready-to-run examples against quotes.toscrape.com and books.toscrape.com

## Usage

```bash
# Interactive menu
python scraper.py

# Run a specific demo
python scraper.py --demo quotes
python scraper.py --demo books
python scraper.py --demo tables
```

## Extending

Import `Scraper` and `DataPipeline` to build your own scrapers:

```python
from scraper import Scraper, DataPipeline

scraper = Scraper("https://example.com", delay=1.0)
soup = scraper.fetch("https://example.com/products")

items = scraper.extract_items(soup, "div.product", {
    "name": "h2.title",
    "price": "span.price",
    "image": ("img", "src"),
})

pipeline = DataPipeline(items)
pipeline.clean_text().clean_numbers(["price"]).remove_duplicates(key="name")
pipeline.to_csv("products.csv")
```

## Requirements

- Python 3.8+
- requests
- beautifulsoup4

```bash
pip install requests beautifulsoup4
```

## Tech Stack

- **Python** — Core scraping and pipeline logic
- **Requests** — HTTP client with session management
- **BeautifulSoup4** — HTML parsing and CSS selector queries
