import asyncio
import re
from playwright.async_api import async_playwright, Page

def clean_price(text_line):
    # Extracts the first valid integer after a ₹ symbol
    matches = re.findall(r"₹\s*(\d+(?:\.\d+)?)", text_line)
    if not matches:
        return 0.0
    # Convert to float to keep decimals
    return min(float(p) for p in matches)

async def scrape_zepto(page: Page, query: str):
    print(f"🟣 [Zepto] Searching for '{query}'...")
    try:
        await page.goto(
            f"https://www.zepto.com/search?query={query}",
            wait_until="domcontentloaded"
        )

        try:
            loc_btn = page.locator("text=Use current location")
            if await loc_btn.count() > 0:
                await loc_btn.first.click()
                await asyncio.sleep(2)
        except:
            pass

        # --- 1. SCROLL TO LOAD ---
        print("   📜 Scrolling to load items...")
        await page.evaluate("window.scrollTo(0, 1000)")
        await asyncio.sleep(2) 

        # --- 2. FIND CARDS USING THE NAME TAG ---
        # We look for the specific Product Name element you found.
        # Then we go up to the main card container (ancestor) to find the price/weight.
        try:
            await page.wait_for_selector('[data-slot-id="ProductName"]', timeout=8000)
        except:
            print(f"   ⚠️ Timeout: No products found for {query}")
            return []

        # Find all name elements first
        name_elements = await page.locator('[data-slot-id="ProductName"]').all()
        
        print(f"   🔍 DEBUG: Found {len(name_elements)} products.")
        
        products = []

        for name_el in name_elements[:12]:
            try:
                # A. EXTRACT NAME (Directly from the element you identified)
                name = await name_el.inner_text()
                name = name.strip()

                # B. FIND CONTAINER (Go up to find the card that holds Price/Weight)
                # We assume the card is a few levels up. 
                # We search up for a DIV that contains an Image to ensure we are in the main card.
                card = name_el.locator("xpath=./ancestor::div[contains(., '₹')][1]")
                
                # Validation: If we can't find a parent with a price, skip
                if await card.count() == 0:
                    continue
                
                # Get all text from the card to parse Price/Weight
                text_content = await card.inner_text()
                lines = [l.strip() for l in text_content.split("\n") if l.strip()]

                # C. EXTRACT PRICE
                price = 0
                price_line = next((l for l in lines if "₹" in l), "")
                if price_line:
                    price = clean_price(price_line)

                # D. EXTRACT WEIGHT
                weight = "Std Unit"
                found_weight = False
                
                # Priority 1: Brackets (500 g)
                for line in lines:
                    if re.search(r"\(\d+.*?(g|gm|kg|ml|l|pc|pcs)\)", line.lower()):
                        weight = line
                        found_weight = True
                        break
                
                # Priority 2: Look for 'Pack' or 'gm' lines that are NOT the name
                if not found_weight:
                    for line in lines:
                        if line == name or "₹" in line: continue
                        # Added 'gm' and '/' support based on your log "1 Pack / 900 -1000 gm"
                        if re.search(r"\d+\s*(g|gm|kg|ml|l|pc|pcs|pack|pair|pairs)\b", line.lower()):
                            weight = line
                            break

                if price > 0 and name:
                    # Deduplicate
                    if not any(p["name"] == name for p in products):
                        products.append({
                            "platform": "Zepto",
                            "name": name,
                            "price": price,
                            "weight": weight
                        })

            except Exception as e:
                # print(f"Card error: {e}")
                continue

        return products

    except Exception as e:
        print(f"Error scraping Zepto: {e}")
        return []

# ------------------ RUNNER ------------------

async def main():
    user_input = input("Enter items to search on Zepto (comma separated): ")
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
        page = await context.new_page()

        for item in items:
            results = await scrape_zepto(page, item)

            print(f"\n📦 Results for '{item.upper()}':")
            if not results:
                print("   ❌ No results found")
                continue

            for i, pdt in enumerate(results, 1):
                print(
                    f"   {i}. ₹{pdt['price']} | {pdt['weight']} | {pdt['name']}"
                )

            print("-" * 60)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())