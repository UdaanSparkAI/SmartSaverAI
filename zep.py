import asyncio
import re
from playwright.async_api import async_playwright

# --- 1. FILTERING & CLEANING ---
def filter_relevant_items(raw_items, query):
    clean_results = []
    query_words = query.lower().split()
    
    synonyms = {
        "onion": ["onion", "pyaz", "pyaaz"],
        "potato": ["potato", "aloo"],
        "tomato": ["tomato", "tamatar"],
        "milk": ["milk", "doodh", "dairy"],
        "eggs": ["egg", "anda"],
        "bread": ["bread", "loaf", "bun"],
        "chicken": ["chicken", "breast", "boneless"],
        "curd": ["curd", "dahi", "yogurt"]
    }

    for item in raw_items:
        name_lower = item['name'].lower()
        valid_keywords = []
        for word in query_words:
            valid_keywords.extend(synonyms.get(word, [word]))
            
        if any(kw in name_lower for kw in valid_keywords):
            clean_results.append(item)
            
    # Sort by Price (Cheapest first)
    clean_results.sort(key=lambda x: x['price'])
    return clean_results

def clean_price(text_line):
    matches = re.findall(r"₹\s*(\d+)", text_line)
    if not matches: return 0
    return min([int(p) for p in matches])

# --- 2. SCRAPERS ---
async def scrape_blinkit(page, query):
    print(f"   🟢 [Blinkit] Searching for '{query}'...")
    try:
        await page.goto(f"https://blinkit.com/s/?q={query}", wait_until="domcontentloaded")
        try:
            detect_btn = page.get_by_text("Detect my location", exact=False)
            if await detect_btn.count() > 0:
                await detect_btn.first.click()
                await asyncio.sleep(2)
        except: pass

        try: await page.wait_for_selector("text=₹", timeout=6000)
        except: return []

        products = []
        add_buttons = await page.get_by_text("ADD", exact=True).all()
        for btn in add_buttons[:8]:
            try:
                card = btn.locator('..').locator('..').locator('..')
                text = await card.inner_text()
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                
                name = lines[0]
                price = clean_price(next((l for l in lines if "₹" in l), ""))
                # Improved Weight Regex
                weight = next((l for l in lines if re.search(r"\d+\s*(g|kg|ml|l|pc|pcs|pack)\b", l.lower())), "Std Unit")
                
                if price > 0:
                    products.append({"platform": "Blinkit", "name": name, "price": price, "weight": weight})
            except: continue
        return list({p['name']: p for p in products}.values())
    except: return []

async def scrape_zepto(page, query):
    print(f"   🟣 [Zepto] Searching for '{query}'...")
    try:
        await page.goto(f"https://www.zepto.com/search?query={query}", wait_until="domcontentloaded")
        try:
            loc_btn = page.locator("text=Use current location")
            if await loc_btn.count() > 0:
                await loc_btn.first.click()
                await asyncio.sleep(2)
        except: pass

        try: await page.wait_for_selector("text=₹", timeout=8000)
        except: return []

        products = []
        potential_cards = await page.locator("div").filter(has_text=re.compile(r"₹")).all()
        parsed_count = 0
        for card in potential_cards:
            if parsed_count >= 10: break
            try:
                text_content = await card.inner_text()
                if len(text_content) > 300 or len(text_content) < 10: continue
                lines = [l.strip() for l in text_content.split('\n') if l.strip()]
                
                price = 0
                for line in lines:
                    if "₹" in line:
                        p = clean_price(line)
                        if p > 10: price = p; break
                
                weight = "Std Unit"
                for line in lines:
                    if re.search(r"\d+\s*(g|kg|ml|l|pc|pcs|pack)\b", line.lower()): weight = line; break

                name = "Unknown"
                for line in lines:
                    if line != weight and "₹" not in line and "OFF" not in line and len(line) > 3: name = line; break
                
                if price > 0 and name != "Unknown":
                    if not any(p['name'] == name for p in products):
                        products.append({"platform": "Zepto", "name": name, "price": price, "weight": weight})
                        parsed_count += 1
            except: continue
        return products
    except: return []

# --- 3. MAIN LOGIC ---
async def main(shopping_list):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            geolocation={"latitude": 12.9716, "longitude": 77.5946}, # Bangalore
            permissions=["geolocation"]
        )

        page1 = await context.new_page()
        page2 = await context.new_page()

        # Data Structure: 
        # cart_data = { "Milk": {"Blinkit": {...}, "Zepto": {...}}, "Onion": ... }
        cart_data = {}

        print(f"🛒 STARTING SHOPPING RUN FOR: {shopping_list}\n")

        for item in shopping_list:
            print(f"🔎 Scanning for: {item.upper()}")
            cart_data[item] = {}
            
            # Scrape
            task1 = scrape_blinkit(page1, item)
            task2 = scrape_zepto(page2, item)
            res_b, res_z = await asyncio.gather(task1, task2)
            
            # Filter & Find Best Deal Per Platform
            clean_b = filter_relevant_items(res_b, item)
            clean_z = filter_relevant_items(res_z, item)
            
            # Store Best Blinkit Option
            if clean_b:
                best_b = clean_b[0] # Cheapest
                cart_data[item]["Blinkit"] = best_b
                print(f"   ✅ Blinkit: ₹{best_b['price']} ({best_b['weight']}) - {best_b['name'][:30]}...")
            else:
                cart_data[item]["Blinkit"] = None
                print("   ❌ Blinkit: Not Found")

            # Store Best Zepto Option
            if clean_z:
                best_z = clean_z[0] # Cheapest
                cart_data[item]["Zepto"] = best_z
                print(f"   ✅ Zepto : ₹{best_z['price']} ({best_z['weight']}) - {best_z['name'][:30]}...")
            else:
                cart_data[item]["Zepto"] = None
                print("   ❌ Zepto : Not Found")
                
            print("-" * 40)
            await asyncio.sleep(1)

        # --- FINAL REPORT GENERATION ---
        print("\n" + "="*80)
        print("🧾 TOTAL BASKET COMPARISON")
        print("="*80)

        platforms = ["Blinkit", "Zepto"]
        
        for platform in platforms:
            total_cost = 0
            items_found = []
            weights_str = []
            missing_items = []

            for item in shopping_list:
                product_data = cart_data.get(item, {}).get(platform)
                
                if product_data:
                    total_cost += product_data['price']
                    items_found.append(item)
                    # Format: "Milk 500ml"
                    weights_str.append(f"{item.capitalize()} {product_data['weight']}")
                else:
                    missing_items.append(item)

            # Build the output string
            # Format: zepto(milk 500ml + eggs 6pcs) = 100 rs
            
            items_summary = " + ".join(weights_str)
            if not items_summary: items_summary = "No items found"
            
            status_icon = "🟢" if platform == "Blinkit" else "🟣"
            
            print(f"{status_icon} {platform.upper()}({items_summary}) = ₹{total_cost}")
            
            if missing_items:
                print(f"   ⚠️ Missing: {', '.join(missing_items)}")
            
            print("-" * 80)

        # --- CHEAPEST MIX CALCULATION ---
        mix_total = 0
        mix_details = []
        for item in shopping_list:
            b_item = cart_data[item].get("Blinkit")
            z_item = cart_data[item].get("Zepto")
            
            b_price = b_item['price'] if b_item else float('inf')
            z_price = z_item['price'] if z_item else float('inf')
            
            if b_price == float('inf') and z_price == float('inf'):
                continue # Item not found anywhere

            if b_price < z_price:
                mix_total += b_price
                mix_details.append(f"{item} (Blinkit ₹{b_price})")
            else:
                mix_total += z_price
                mix_details.append(f"{item} (Zepto ₹{z_price})")

        print(f"🏆 CHEAPEST MIXED CART = ₹{mix_total}")
        print(f"   Build: {', '.join(mix_details)}")
        print("="*80)

        input("\nPress Enter to close browser...")
        await browser.close()

if __name__ == "__main__":
    user_input = input("Enter shopping list (comma separated): ")
    items = [x.strip() for x in user_input.split(",") if x.strip()]
    if items:
        asyncio.run(main(items))