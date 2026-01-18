import asyncio
import sqlite3
import re
from datetime import datetime
from playwright.async_api import async_playwright

from Source_scraper.blinkit_scraper import scrape_blinkit
from Source_scraper.zepto_scraper import scrape_zepto


DB_PATH = "data/smartsaver.db"


# ------------------ DB SETUP ------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            search_query TEXT NOT NULL,
            product_name TEXT NOT NULL,
            brand TEXT,
            price INTEGER NOT NULL,
            raw_quantity TEXT,
            quantity_value REAL,
            quantity_unit TEXT,
            scraped_at TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ------------------ HELPERS ------------------

def extract_brand(product_name: str):
    """Simple heuristic: first word as brand"""
    return product_name.split()[0]


def parse_quantity(raw_qty: str):
    """
    Extracts quantity value and unit from strings like:
    - '1 pack (500 ml)'
    - '250 g'
    - '12 x 70 g'  -> (70, 'g') [NOT normalized yet]
    """
    if not raw_qty:
        return None, None

    match = re.search(r"(\d+(?:\.\d+)?)\s*(ml|l|g|kg|pcs|pc)", raw_qty.lower())
    if match:
        return float(match.group(1)), match.group(2)

    return None, None


def insert_product(conn, data):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (
            source,
            search_query,
            product_name,
            brand,
            price,
            raw_quantity,
            quantity_value,
            quantity_unit,
            scraped_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["source"],
        data["search_query"],
        data["product_name"],
        data["brand"],
        data["price"],
        data["raw_quantity"],
        data["quantity_value"],
        data["quantity_unit"],
        data["scraped_at"]
    ))
    conn.commit()


# ------------------ MAIN PIPELINE ------------------

async def main():
    init_db()
    conn = sqlite3.connect(DB_PATH)

    user_input = input("Enter items to search (comma separated): ")
    items = [x.strip() for x in user_input.split(",") if x.strip()]

    if not items:
        print("❌ No items provided.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            geolocation={"latitude": 12.9716, "longitude": 77.5946},
            permissions=["geolocation"]
        )

        page_blinkit = await context.new_page()
        page_zepto = await context.new_page()

        for item in items:
            print(f"\n🔎 Processing '{item.upper()}'")

            # --- SCRAPE ---
            blinkit_results, zepto_results = await asyncio.gather(
                scrape_blinkit(page_blinkit, item),
                scrape_zepto(page_zepto, item)
            )

            all_results = [
                ("blinkit", blinkit_results),
                ("zepto", zepto_results)
            ]

            for source, results in all_results:
                for r in results:
                    qty_val, qty_unit = parse_quantity(r.get("weight"))

                    record = {
                        "source": source,
                        "search_query": item,
                        "product_name": r["name"],
                        "brand": extract_brand(r["name"]),
                        "price": r["price"],
                        "raw_quantity": r.get("weight"),
                        "quantity_value": qty_val,
                        "quantity_unit": qty_unit,
                        "scraped_at": datetime.utcnow()
                    }

                    insert_product(conn, record)

            print(f"   ✅ Stored {len(blinkit_results) + len(zepto_results)} records")

        await browser.close()
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
