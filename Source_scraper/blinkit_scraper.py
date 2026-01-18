import asyncio
import re
from playwright.async_api import async_playwright, Page


def clean_price(text_line):
    matches = re.findall(r"₹\s*(\d+)", text_line)
    if not matches:
        return 0
    return min(int(p) for p in matches)


async def scrape_blinkit(page: Page, query: str):
    print(f"🟢 [Blinkit] Searching for '{query}'...")
    try:
        await page.goto(
            f"https://blinkit.com/s/?q={query}",
            wait_until="domcontentloaded"
        )

        try:
            detect_btn = page.get_by_text("Detect my location", exact=False)
            if await detect_btn.count() > 0:
                await detect_btn.first.click()
                await asyncio.sleep(2)
        except:
            pass

        try:
            await page.wait_for_selector("text=₹", timeout=6000)
        except:
            return []

        products = []
        add_buttons = await page.get_by_text("ADD", exact=True).all()

        for btn in add_buttons[:8]:
            try:
                card = btn.locator("..").locator("..").locator("..")
                text = await card.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]

                name = lines[0]
                price = clean_price(next((l for l in lines if "₹" in l), ""))

                weight = next(
                    (
                        l for l in lines
                        if re.search(r"\d+\s*(g|kg|ml|l|pc|pcs|pack)\b", l.lower())
                    ),
                    "Std Unit"
                )

                if price > 0:
                    products.append({
                        "platform": "Blinkit",
                        "name": name,
                        "price": price,
                        "weight": weight
                    })
            except:
                continue

        return list({p["name"]: p for p in products}.values())

    except:
        return []


# ------------------ RUNNER ------------------

async def main():
    user_input = input("Enter items to search on Blinkit (comma separated): ")
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
            results = await scrape_blinkit(page, item)

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
