import asyncio
import sqlite3
import re
from datetime import datetime
from playwright.async_api import async_playwright
from data_cleaner import keyword_filter

from Source_scraper.blinkit_scraper import scrape_blinkit
from Source_scraper.zepto_scraper import scrape_zepto


DB_PATH = "/Users/jiteshvijaykumar/Downloads/SmartSaver/SmartSaverAI/data/smartsave.db"


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

def remove_old_entries(conn, search_query):
    """
    Deletes entries for a specific search query to prevent duplicate/stale data.
    Example: If updating 'Milk', remove all old 'Milk' rows first.
    """
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE search_query = ?", (search_query,))
    conn.commit()
    print(f"   🧹 Cleared old records for '{search_query}'")


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
            raw_items = []
            for p in blinkit_results:
                p['source'] = 'blinkit'
                raw_items.append(p)
            
            for p in zepto_results:
                p['source'] = 'zepto'
                raw_items.append(p)

            total_found = len(raw_items)

            if total_found > 0:
                # 3. APPLY KEYWORD FILTER
                clean_items = keyword_filter(raw_items, item)

                if clean_items:
                    # 4. DELETE OLD DATA (Only if we have valid new data)
                    remove_old_entries(conn, item)

                    # 5. INSERT CLEAN DATA
                    for r in clean_items:
                        qty_val, qty_unit = parse_quantity(r.get("weight"))

                        record = {
                            "source": r["source"], # Uses the tag we added above
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
                    
                    print(f"   ✅ Successfully inserted {len(clean_items)} records (filtered from {total_found}).")
                else:
                    print(f"   ⚠️ Scraper found items, but ALL were filtered out as irrelevant.")
            else:
                print(f"   ⚠️ Scraper returned 0 results for '{item}'. Keeping old data.")    

        await browser.close()
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
