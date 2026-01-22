import sqlite3
import json
import os
import pandas as pd
import asyncio
from datetime import datetime
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# CONFIGURATION
DB_PATH = "/Users/jiteshvijaykumar/Downloads/SmartSaver/SmartSaverAI/data/smartsave.db"


AZURE_OPENAI_API_VERSION=os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_API_KEY= os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT= os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME= os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Initialize Azure Client
client = AsyncAzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

def get_products_from_db(search_query):
    """
    Synchronous DB fetch. Since SQLite is local and fast, 
    we keep this sync to avoid complexity, but run it inside async wrapper.
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT source, product_name, price, quantity_value, quantity_unit FROM products WHERE search_query = ?",
        conn,
        params=(search_query,)
    )
    conn.close()
    
    if df.empty:
        return None, None

    def normalize(row):
        try:
            val = float(row['quantity_value'])
            unit = str(row['quantity_unit']).lower().strip()
            if unit == 'l': return val * 1000, 'ml'
            if unit == 'kg': return val * 1000, 'g'
            return val, unit
        except:
            return 0, 'unknown'

    df[['norm_qty', 'norm_unit']] = df.apply(normalize, axis=1, result_type='expand')

    # Deduplicate: Keep lowest price per unique item
    df_clean = df.groupby(['source', 'product_name', 'norm_qty', 'norm_unit'], as_index=False)['price'].min()

    blinkit_items = df_clean[df_clean['source'] == 'blinkit'].to_dict(orient='records')
    zepto_items = df_clean[df_clean['source'] == 'zepto'].to_dict(orient='records')
    
    return blinkit_items, zepto_items

async def ai_find_matches(blinkit_items, zepto_items):
    """
    Async function to call Azure OpenAI
    """
    prompt = f"""
    You are an expert Frugal Shopper.
    
    List A (Blinkit):
    {json.dumps([{ 'id': i, 'name': p['product_name'], 'qty': p['norm_qty'], 'unit': p['norm_unit'], 'price': p['price']} for i, p in enumerate(blinkit_items)])}
    
    List B (Zepto):
    {json.dumps([{ 'id': i, 'name': p['product_name'], 'qty': p['norm_qty'], 'unit': p['norm_unit'], 'price': p['price']} for i, p in enumerate(zepto_items)])}
    
    YOUR GOAL:
    Find matches based on "Value for Money".
    
    RULES:
    1. EXACT MATCH: Same Brand + Same Weight.
    2. COMMODITY MATCH: Generic items (Eggs, Onion) -> Same Weight, different brand is OK.
    3. BULK WIN: If one sells MORE quantity for LESS price, match them.
       
    OUTPUT FORMAT:
    Strictly Return the below JSON object.
    {{
        "matches": [
            {{ 
                "blinkit_id": <id>, 
                "zepto_id": <id>, 
                "winner": "blinkit" | "zepto" | "tie",
                "reason": "Brief reason" 
            }}
        ]
    }}
    """
    
    if client:
        try:
            # CHANGED: await client.chat.completions.create
            response = await client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."}, 
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" }
            )
            content = response.choices[0].message.content
            matches = json.loads(content)['matches']
            return matches
        except Exception as e:
            # print(f"⚠️ AI Error: {e}") # Optional: suppress print to keep console clean
            return []
    return []

async def process_item_logic(search_query):
    """
    1. Fetches data (Sync)
    2. Calls AI (Async)
    3. Calculates Best Deal (CPU)
    Returns a DATA DICTIONARY (Does not print)
    """

    # Run DB fetch in a separate thread if needed, but direct call is usually fine for SQLite
    # blinkit_items, zepto_items = get_products_from_db(search_query)
    blinkit_items, zepto_items = await asyncio.to_thread(get_products_from_db, search_query)
    
    if not blinkit_items or not zepto_items:
        return {"status": "error", "query": search_query, "msg": "Insufficient data"}

    # 1. AI Comparison (Async)
    matches = await ai_find_matches(blinkit_items, zepto_items)

    # 2. FIND BEST VALUE ITEM FOR BASKET CALCULATION
    def get_unit_price(item):
        try:
            return float(item['price']) / float(item['norm_qty'])
        except: return float('inf')

    best_b_opt = min(blinkit_items, key=get_unit_price, default=None)
    best_z_opt = min(zepto_items, key=get_unit_price, default=None)

    return {
        "status": "success",
        "query": search_query,
        "matches": matches,
        "blinkit_items": blinkit_items,
        "zepto_items": zepto_items,
        "best_b": best_b_opt,
        "best_z": best_z_opt
    }

def print_item_report(data):
    """
    Handles all the printing logic sequentially after data is ready.
    """
    search_query = data["query"]
    
    print(f"\n📊 Generating Savings Report for: {search_query.upper()}")

    if data["status"] == "error":
        print(f"   ❌ {data['msg']}")
        return

    blinkit_items = data["blinkit_items"]
    zepto_items = data["zepto_items"]
    matches = data["matches"]
    
    # Print Debug Info
    # print("matches found from AI --", matches) 
    
    if matches:
        print(f"   ✅ Found {len(matches)} smart value comparisons.\n")
        print(f"{'PRODUCT (BLINKIT vs ZEPTO)':<55} | {'PRICE B':<9} | {'PRICE Z':<9} | {'ANALYSIS'}")
        print("-" * 120)
        
        for m in matches:
            b_name = "N/A"
            b_price = "---"
            z_name = "N/A"
            z_price = "---"
            
            # SAFE ACCESS: Only get Blinkit data if ID exists
            if m.get('blinkit_id') is not None:
                b_item = blinkit_items[m['blinkit_id']]
                b_name = f"{b_item['product_name'][:22]} ({int(b_item['norm_qty'])}{b_item['norm_unit']})"
                b_price = f"₹{b_item['price']}"

            # SAFE ACCESS: Only get Zepto data if ID exists
            if m.get('zepto_id') is not None:
                z_item = zepto_items[m['zepto_id']]
                z_name = f"{z_item['product_name'][:22]} ({int(z_item['norm_qty'])}{z_item['norm_unit']})"
                z_price = f"₹{z_item['price']}"
            
            # Format the verdict color
            winner = m.get('winner', 'tie').lower()
            reason = m.get('reason', '')
            
            if winner == 'blinkit':
                verdict = f"🟢 Blinkit Wins"
            elif winner == 'zepto':
                verdict = f"🟣 Zepto Wins"
            else:
                verdict = "⚪ Tie"
            
            # Print the row safely
            print(f"{b_name:<30} vs {z_name:<30} | {str(b_price):<8} | {str(z_price):<8} | {verdict} | {reason}")
        print("-" * 120)

    # Print Best Deal Summary
    best_b_opt = data["best_b"]
    best_z_opt = data["best_z"]

    if best_b_opt and best_z_opt:
        # Simple recalc of score for display logic
        def get_score(item):
            try: return float(item['price']) / float(item['norm_qty'])
            except: return float('inf')
            
        b_score = get_score(best_b_opt)
        z_score = get_score(best_z_opt)
        
        print(f"🏆 BEST DEAL FOR '{search_query.upper()}':")
        if z_score < b_score:
            print(f"   🥇 Zepto:   {best_z_opt['product_name']} (₹{best_z_opt['price']})")
        else:
            print(f"   🥇 Blinkit: {best_b_opt['product_name']} (₹{best_b_opt['price']})")


async def main():
    user_input = input("Enter items to analyze (comma separated): ")
    items = [x.strip() for x in user_input.split(",") if x.strip()]
    
    print(f"\n🚀 Analyzing {len(items)} items in PARALLEL (this will be fast)...")
    
    # 1. LAUNCH ALL TASKS IN PARALLEL
    tasks = [process_item_logic(item) for item in items]
    results = await asyncio.gather(*tasks)

    # 2. PROCESS RESULTS SEQUENTIALLY (Printing & Totals)
    basket_blinkit_total = 0
    basket_zepto_total = 0
    basket_details = []

    for res in results:
        # Print the detailed table for this item
        print_item_report(res)

        # Basket Logic
        if res["status"] == "success":
            best_b = res["best_b"]
            best_z = res["best_z"]
            
            b_price = best_b['price'] if best_b else 0
            z_price = best_z['price'] if best_z else 0
            
            basket_blinkit_total += b_price
            basket_zepto_total += z_price
            
            basket_details.append({
                "item": res["query"],
                "blinkit_item": best_b['product_name'] if best_b else "Not Found",
                "blinkit_price": b_price,
                "zepto_item": best_z['product_name'] if best_z else "Not Found",
                "zepto_price": z_price
            })

    # --- FINAL BASKET RECEIPT ---
    print("\n\n" + "="*80)
    print("🧾 FINAL BASKET RECEIPT")
    print("="*80)
    print(f"{'ITEM':<15} | {'BLINKIT BEST OPTION':<30} | {'ZEPTO BEST OPTION':<30}")
    print("-" * 80)

    for entry in basket_details:
        b_str = f"{entry['blinkit_item'][:50]}.. (₹{entry['blinkit_price']})"
        z_str = f"{entry['zepto_item'][:50]}.. (₹{entry['zepto_price']})"
        print(f"{entry['item'].upper():<15} | {b_str:<30} | {z_str:<30}")

    print("-" * 80)
    print(f"🟢 TOTAL BLINKIT BASKET: ₹{basket_blinkit_total}")
    print(f"🟣 TOTAL ZEPTO BASKET:   ₹{basket_zepto_total}")
    print("="*80)

    if basket_zepto_total < basket_blinkit_total:
        save = basket_blinkit_total - basket_zepto_total
        print(f"🎉 RECOMMENDATION: Buy from ZEPTO to save ₹{save}!")
    elif basket_blinkit_total < basket_zepto_total:
        save = basket_zepto_total - basket_blinkit_total
        print(f"🎉 RECOMMENDATION: Buy from BLINKIT to save ₹{save}!")
    else:
        print("⚖️ Both platforms cost the same.")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())