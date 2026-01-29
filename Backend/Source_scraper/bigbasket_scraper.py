import asyncio
import re
from playwright.async_api import async_playwright, Page

def clean_price(text_line):
    matches = re.findall(r"₹\s*(\d+(?:\.\d+)?)", text_line)
    if not matches:
        return 0.0
    # Convert to float to keep decimals
    return min(float(p) for p in matches)

async def scrape_bigbasket(page: Page, query: str):
    print(f"🟢 [BigBasket] Searching for '{query}'...")
    
    try:
        await page.goto(
            f"https://www.bigbasket.com/ps/?q={query}",
            wait_until="domcontentloaded"
        )

        # --- 1. HANDLE LOCATION (Standardized Logic) ---
        try:
            # BB often asks for location on fresh context. 
            # We try to use the "Select Location" button if it exists.
            loc_btn = page.get_by_text("Select Location", exact=False).first
            
            if await loc_btn.is_visible():
                print("   📍 Found 'Select Location' widget...")
                await loc_btn.click()
                
                # Type Pincode (Standard fallback for BB)
                await page.wait_for_selector("input[type='text']", timeout=3000)
                await page.locator("input[type='text']").first.fill("560001") # Bangalore Default
                await page.wait_for_timeout(1000)
                
                # Click first suggestion
                suggestion = page.locator("li").first
                if await suggestion.count() > 0:
                    await suggestion.click()
                    await page.wait_for_timeout(2000)
                else:
                    await page.keyboard.press("Enter")
        except:
            # If location flow fails or isn't needed, we continue
            pass

        # --- 2. SCROLL TO LOAD ---
        # BigBasket uses lazy loading, similar to Zepto
        await page.evaluate("window.scrollTo(0, 1000)")
        await asyncio.sleep(2)

        # --- 3. WAIT FOR RESULTS ---
        try:
            # Wait for at least one product card (li with an h3 title)
            await page.wait_for_selector("li h3", timeout=6000)
        except:
            print(f"   ⚠️ Timeout or no results for {query}")
            return []

        products = []
        
        # Target the cards
        items = await page.locator("li").filter(has=page.locator("h3")).all()

        for item in items[:12]: # Limit to 12 items like Zepto
            try:
                # --- NAME CLEANING (FIXED) ---
                raw_name = await item.locator("h3").first.inner_text()
                # 1. Replace newlines with space
                # 2. Remove multiple spaces
                name = " ".join(raw_name.replace("\n", " ").split())
                
                # B. EXTRACT PRICE
                price = 0
                # BB price is usually inside a distinct text element with ₹
                price_element = item.locator("text=₹").first
                if await price_element.count() > 0:
                    price_text = await price_element.inner_text()
                    price = clean_price(price_text)

                # C. EXTRACT WEIGHT (Robust logic ported from Zepto)
                all_text = await item.inner_text()
                lines = [l.strip() for l in all_text.split("\n") if l.strip()]
                
                weight = "Std Unit"
                found_weight = False

                # Priority 1: Brackets like (500 g)
                for line in lines:
                    if re.search(r"\(\d+.*?(g|kg|ml|l|ltr|pc|pcs|pack|pair|pairs)\)", line.lower()):
                        weight = line
                        found_weight = True
                        break
                
                # Priority 2: Standard patterns
                if not found_weight:
                    for line in lines:
                        if "₹" in line or line == name: continue
                        if re.search(r"\d+\s*(g|kg|ml|l|ltr|pc|pcs|pack|pair|pairs)\b", line.lower()):
                            weight = line
                            break

                if price > 0 and name:
                    products.append({
                        "platform": "BigBasket",
                        "name": name,
                        "price": price,
                        "weight": weight
                    })
            except:
                continue

        # Deduplicate by name
        return list({p["name"]: p for p in products}.values())

    except Exception as e:
        print(f"Error scraping BigBasket: {e}")
        return []

# ------------------ RUNNER ------------------

async def main():
    user_input = input("Enter items to search on BigBasket (comma separated): ")
    items = [x.strip() for x in user_input.split(",") if x.strip()]

    if not items:
        print("❌ No items provided.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        
        # Updated to match Zepto/Blinkit context settings
        context = await browser.new_context(
            geolocation={"latitude": 12.9716, "longitude": 77.5946},
            permissions=["geolocation"]
        )
        page = await context.new_page()

        for item in items:
            results = await scrape_bigbasket(page, item)

            print(f"\n📦 Results for '{item.upper()}':")
            if not results:
                print("   ❌ No results found")
                continue

            for i, pdt in enumerate(results, 1):
                print(
                    f"   {i}. ₹{pdt['price']} | {pdt['weight']} | {pdt['name'][:60]}"
                )

            print("-" * 60)

        input("\nPress Enter to close browser...")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())