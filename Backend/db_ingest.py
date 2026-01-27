import asyncio
import re
from datetime import datetime

from playwright.async_api import async_playwright
from sqlalchemy import text

from data_cleaner import keyword_filter, autocorrect_query
from Source_scraper.blinkit_scraper import scrape_blinkit
from Source_scraper.zepto_scraper import scrape_zepto
from db_supabase import SessionLocal


# ------------------ HELPERS ------------------

def extract_brand(product_name: str):
    """Simple heuristic: first word as brand"""
    if not product_name:
        return None
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

    raw_qty = raw_qty.lower().strip()

    # --- SPECIAL MAPPINGS (Normalization) ---
    # Convert specific words to standard units immediately
    if "dozen" in raw_qty:
        # "1 dozen" -> 12 pcs
        match_doz = re.search(r"(\d+)\s*dozen", raw_qty)
        val = float(match_doz.group(1)) * 12 if match_doz else 12
        return val, "pcs"
    
    if "bunch" in raw_qty or "bundle" in raw_qty:
        return 1.0, "bunch"

    # --- PRIORITY 1: Inside Parentheses (The most accurate source) ---
    # Looks for "(3 pairs)", "(500 g)", "(10 sheets)"
    match_inside = re.search(r"\(\s*(\d+(?:\.\d+)?)\s*(pair|pairs|set|sets|roll|rolls|sheet|sheets|tablet|tablets|sachet|sachets|ml|l|g|kg|gm|pc|pcs)\s*\)", raw_qty)
    if match_inside:
        val = float(match_inside.group(1))
        unit = match_inside.group(2)
        # Normalize plurals
        if unit in ['pairs', 'sets', 'rolls', 'sheets', 'tablets', 'sachets']:
            unit = unit[:-1] # Remove 's'
        return val, unit

    # --- PRIORITY 2: Standard Units anywhere ---
    # Extended regex for all new units
    match_std = re.search(r"(\d+(?:\.\d+)?)\s*(pair|pairs|set|sets|roll|rolls|sheet|sheets|tablet|tablets|sachet|sachets|ml|l|g|kg|gm|pc|pcs)", raw_qty)
    if match_std:
        val = float(match_std.group(1))
        unit = match_std.group(2)
        if unit in ['pairs', 'sets', 'rolls', 'sheets', 'tablets', 'sachets']:
            unit = unit[:-1]
        if unit == 'gm': unit = 'g' # Normalize gm -> g
        return val, unit

    # --- PRIORITY 3: "Pack" Logic ---
    # If it says "1 pack" but NO other unit, treat it as 1 unit (or 1 pc)
    # But if it says "Pack of 3", treat it as 3 pcs
    match_pack_of = re.search(r"pack of\s*(\d+)", raw_qty)
    if match_pack_of:
        return float(match_pack_of.group(1)), "pcs"

    match_pack_simple = re.search(r"(\d+)\s*pack", raw_qty)
    if match_pack_simple:
        return float(match_pack_simple.group(1)), "pack"

    return None, None


# ------------------ DB OPERATIONS (SUPABASE) ------------------

def remove_old_entries(db, search_query: str):
    """
    Deletes old rows for a given search query
    to avoid stale / duplicate data.
    """
    db.execute(
        text("DELETE FROM products WHERE search_query = :q"),
        {"q": search_query}
    )
    db.commit()
    print(f"   🧹 Cleared old records for '{search_query}'")


def insert_product(db, data: dict):
    """
    Inserts a single cleaned product row into Supabase.
    """
    db.execute(
        text("""
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
            VALUES (
                :source,
                :search_query,
                :product_name,
                :brand,
                :price,
                :raw_quantity,
                :quantity_value,
                :quantity_unit,
                :scraped_at
            )
        """),
        data
    )


# ------------------ MAIN PIPELINE ------------------

async def fetch_and_store_items(items):
    """
    Scrapes the provided items from all sources
    and stores them in Supabase (PostgreSQL).
    """

    db = SessionLocal()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            geolocation={"latitude": 12.9716, "longitude": 77.5946},
            permissions=["geolocation"]
        )

        page_blinkit = await context.new_page()
        page_zepto = await context.new_page()

        for raw_item in items:
            item = autocorrect_query(raw_item)
            if item != raw_item:
                print(f"   ✨ Corrected '{raw_item}' -> '{item}' for scraping.")
            # ------------------------------

            print(f"\n🌍 Live Scraping for '{item.upper()}'...")

            # 1. Scrape Parallel
            blinkit_results, zepto_results = await asyncio.gather(
                scrape_blinkit(page_blinkit, item),
                scrape_zepto(page_zepto, item)
            )

            print("blinkit_results -->", blinkit_results)
            print("zepto_results -->", zepto_results)

            # 2. Tag Source
            raw_items = []
            for p in blinkit_results:
                p['source'] = 'blinkit'
                raw_items.append(p)
            for p in zepto_results:
                p['source'] = 'zepto'
                raw_items.append(p)

            total_found = len(raw_items)
            
            if total_found > 0:
                # 3. Clean & Filter
                clean_items = keyword_filter(raw_items, item)

                print("Cleaned items",clean_items)

                if clean_items:
                    # 4. Refresh DB Data
                    remove_old_entries(db, item)
                    
                    for r in clean_items:
                        qty_val, qty_unit = parse_quantity(r.get("weight"))
                        insert_product(db, {
                            "source": r["source"],
                            "search_query": item,
                            "product_name": r["name"],
                            "brand": extract_brand(r["name"]),
                            "price": r["price"],
                            "raw_quantity": r.get("weight"),
                            "quantity_value": qty_val,
                            "quantity_unit": qty_unit,
                            "scraped_at": datetime.utcnow()
                        })
                    print(f"   ✅ Saved {len(clean_items)} new items to DB.")
                else:
                    print(f"   ⚠️ Items found but filtered out by keyword cleaner.")
            else:
                print(f"   ❌ No items found on any platform for '{item}'.")

            db.commit()
            print(f"   ✅ Saved {len(clean_items)} new items to Supabase.")

        await browser.close()

    db.close()


# ------------------ CLI RUNNER ------------------

if __name__ == "__main__":
    user_input = input("Enter items to search (comma separated): ")
    items = [x.strip() for x in user_input.split(",") if x.strip()]

    if items:
        asyncio.run(fetch_and_store_items(items))
