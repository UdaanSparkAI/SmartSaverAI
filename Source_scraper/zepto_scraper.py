import asyncio
import re
from playwright.async_api import async_playwright, Page


def clean_price(text_line):
    matches = re.findall(r"₹\s*(\d+)", text_line)
    if not matches:
        return 0
    return min(int(p) for p in matches)


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

        try:
            await page.wait_for_selector("text=₹", timeout=8000)
        except:
            return []

        products = []
        parsed_count = 0

        potential_cards = await (
            page.locator("div")
            .filter(has_text=re.compile(r"₹"))
            .all()
        )

        for card in potential_cards:
            if parsed_count >= 10:
                break

            try:
                text_content = await card.inner_text()
                if len(text_content) > 300 or len(text_content) < 10:
                    continue

                lines = [l.strip() for l in text_content.split("\n") if l.strip()]

                price = 0
                for line in lines:
                    if "₹" in line:
                        p = clean_price(line)
                        if p > 10:
                            price = p
                            break

                weight = "Std Unit"
                for line in lines:
                    if re.search(r"\d+\s*(g|kg|ml|l|pc|pcs|pack)\b", line.lower()):
                        weight = line
                        break

                name = "Unknown"
                for line in lines:
                    if (
                        line != weight
                        and "₹" not in line
                        and "OFF" not in line
                        and len(line) > 3
                    ):
                        name = line
                        break

                if price > 0 and name != "Unknown":
                    if not any(p["name"] == name for p in products):
                        products.append({
                            "platform": "Zepto",
                            "name": name,
                            "price": price,
                            "weight": weight
                        })
                        parsed_count += 1

            except:
                continue

        return products

    except:
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
                    f"   {i}. ₹{pdt['price']} | {pdt['weight']} | {pdt['name'][:60]}"
                )

            print("-" * 60)

        input("\nPress Enter to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
