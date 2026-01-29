import asyncio
import os
import json
import re
from groq import AsyncGroq
from dotenv import load_dotenv
from difflib import SequenceMatcher
from sqlalchemy import text
from .db_ingest import fetch_and_store_items
from .data_cleaner import autocorrect_query
from .db_supabase import SessionLocal

load_dotenv()

# Use your specific Groq API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=GROQ_API_KEY)

# ------------------ 1. DATA PREPARATION ------------------

def normalize_weight(qty_val, unit):
    if not unit or qty_val == 0: return "Other"
    unit = unit.lower().strip()
    
    if unit == 'g' or unit == 'gm':
        if qty_val >= 1000: return f"{int(qty_val/1000)}kg"
        return f"{int(qty_val)}g"
    
    if unit == 'ml':
        if qty_val >= 1000: return f"{int(qty_val/1000)}l"
        return f"{int(qty_val)}ml"
        
    if unit in ['kg', 'l', 'ltr']:
        return f"{int(qty_val) if qty_val % 1 == 0 else qty_val}{unit.replace('ltr', 'l')}"
        
    return f"{int(qty_val)}{unit}"

def get_products_from_db(search_query):
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT source, product_name, price, quantity_value, quantity_unit 
                FROM test_products WHERE search_query = :q
            """),
            {"q": search_query}
        )
        rows = result.fetchall()
        
        items = []
        for r in rows:
            q_val = float(r.quantity_value) if r.quantity_value else 0
            q_unit = str(r.quantity_unit).lower() if r.quantity_unit else "unit"

            clean_name = r.product_name.replace("\n", " ").strip()
            clean_name = " ".join(clean_name.split()) 
            
            weight_label = normalize_weight(q_val, q_unit)

            items.append({
                "source": r.source,
                "name": clean_name,
                "price": float(r.price),
                "weight": weight_label,
                "raw_val": q_val 
            })
        return items
    finally:
        db.close()

# ------------------ 2. NEW: SEMANTIC INTENT FILTER ------------------

async def semantic_filter(query, items):
    """
    Uses AI to filter out irrelevant products (e.g. 'Onion Pakoda' when searching 'Onion').
    """
    if not items: return []

    # Prepare a simple numbered list for the AI
    item_list_str = "\n".join([f"{i}: {item['name']}" for i, item in enumerate(items)])

    print(f"\n🧠 [DEBUG] Running Semantic Filter on {len(items)} items...")

    prompt = f"""
    User Query: "{query}"
    
    Task: Identify which products in the list below are IRRELEVANT to the user's intent.
    
    STRICT FILTERING RULES:
    1. **Processed/Cooked:** If user asks for a raw ingredient (e.g. "Onion", "Chicken"), REMOVE cooked dishes (e.g. "Onion Pakoda", "Butter Chicken", "Chips").
    2. **Distinct Varieties:** If user asks for a generic item (e.g. "Onion"), REMOVE distinct biological varieties that usually require specific queries (e.g. remove "Spring Onion" or "Leeks"). 
       *Exception:* Keep subtypes like "Red Onion", "White Onion", "Baby Onion" as they are still core "Onions".
    3. **Derivatives:** Remove pastes, powders, oils, and ketchups unless explicitly asked for.
    4. **Accessories:** Remove peelers, choppers, or seeds.

    Items:
    {item_list_str}

    OUTPUT JSON FORMAT ONLY:
    {{
        "keep_indices": [0, 2, 5, ...] 
    }}
    (Return ONLY the indices of items that match the user intent).
    """

    try:
        response = await client.chat.completions.create(
            model=os.getenv("GROQ_MODEL"),
            messages=[
                {"role": "system", "content": "You are a strict data cleaning assistant. JSON output only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0, # Deterministic
            max_tokens=1000,
            response_format={"type": "json_object"} # Force JSON
        )
        
        result = json.loads(response.choices[0].message.content)
        keep_indices = set(result.get("keep_indices", []))
        
        # Filter the original list
        filtered_items = [item for i, item in enumerate(items) if i in keep_indices]
        
        print(f"   ✂️  Filtered {len(items)} -> {len(filtered_items)} items.")
        return filtered_items

    except Exception as e:
        print(f"   ⚠️ Semantic Filter Failed: {e}. Proceeding with full list.")
        return items # Fallback to full list if AI fails

# ------------------ 3. ALIGNMENT & ANALYSIS ------------------

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def align_products(all_items):
    grouped_by_weight = {}

    for item in all_items:
        w = item['weight']
        if w not in grouped_by_weight:
            grouped_by_weight[w] = []
        
        found_match = False
        for row in grouped_by_weight[w]:
            if similar(row['name'], item['name']) > 0.5: 
                row[item['source']] = item['price']
                if len(item['name']) > len(row['name']):
                    row['name'] = item['name']
                found_match = True
                break
        
        if not found_match:
            new_row = {
                "name": item['name'],
                "blinkit": None,
                "zepto": None,
                "bigbasket": None
            }
            new_row[item['source']] = item['price']
            grouped_by_weight[w].append(new_row)

    return grouped_by_weight

async def get_ai_recommendation(query, inventory_data):
    ai_payload = []

    for weight, products in inventory_data.items():
        all_options = []
        for p in products:
            for store in ['blinkit', 'zepto', 'bigbasket']:
                if p[store] is not None:
                    all_options.append({
                        "store": store,
                        "price": p[store],
                        "product_name": p['name'], 
                        "is_brand": any(x in p['name'].lower() for x in ["amul", "nandini", "heritage", "tata", "nestle", "fortune", "organic","premium"])
                    })
        
        if not all_options: continue

        # 1. Sort & Pick Winner
        all_options.sort(key=lambda x: x['price'])
        winner = all_options[0]
        other_options = all_options[1:] # Exclude winner
        
        competitor_best_prices = {} 
        
        for opt in other_options:
            store = opt['store']
            price = opt['price']
            
            # CRITICAL FIX: Only calculate savings against DIFFERENT stores
            if store == winner['store']:
                continue
            
            # Keep only the lowest price per competitor to avoid spamming
            if store not in competitor_best_prices or price < competitor_best_prices[store]:
                competitor_best_prices[store] = price
        
        savings_parts = []
        if competitor_best_prices:
            for store, price in competitor_best_prices.items():
                diff = int(price - winner['price'])
                if diff > 0:
                    savings_parts.append(f"Save ₹{diff} vs {store.title()}")
                else:
                    savings_parts.append(f"Price Match with {store.title()}")
        else:
            # If no competitors (only same store options), say this:
            savings_parts.append("Lowest price across platforms")

        # 4. JSON Payload
        group_data = {
            "size": weight,
            "best_deal": {
                "winner_store": winner['store'].title(),
                "price": int(winner['price']),
                "item": winner['product_name'], 
                "savings_analysis": ", ".join(savings_parts) 
            },
            "other_options": other_options # <-- This list still contains same-store items for the AI to check brands
        }
        ai_payload.append(group_data)

    json_context = json.dumps(ai_payload, indent=2, ensure_ascii=False)

    print(json_context)
    
    # --- FEW SHOT PROMPT ---
    prompt = f"""
    You are a Smart Shopping Assistant.
    
    INPUT DATA (JSON):
    {json_context}
    
    YOUR TASK:
    Convert this JSON into a clean Telegram buying guide.
    
    --------------------------------------------------------
    FEW-SHOT EXAMPLES (Follow these patterns strictly):

    Example 1: (Generic Winner, Premium Alternative exists)
    Input: {{
        "size": "1kg",
        "best_deal": {{ "winner_store": "BigBasket", "price": 30, "item": "fresho! Onion", "savings_analysis": "Save ₹10 vs Blinkit" }},
        "other_options": [ {{ "store": "blinkit", "price": 40, "product_name": "Organic Onion", "is_brand": true }} ]
    }}
    Output:
    🔹 1kg
       🏆 BigBasket • fresho! Onion • ₹30
       📉 Save ₹10 vs Blinkit
       Tip: Upgrade to Organic Onion for ₹40 (Blinkit)

    Example 2: (Brand Winner, Multiple Comparisons)
    Input: {{
        "size": "500ml",
        "best_deal": {{ "winner_store": "Zepto", "price": 24, "item": "Nandini GoodLife", "savings_analysis": "Save ₹2 vs Blinkit, Save ₹4 vs BigBasket" }},
        "other_options": [ 
             {{ "store": "blinkit", "price": 26, "product_name": "Amul Taaza", "is_brand": true }},
             {{ "store": "bigbasket", "price": 28, "product_name": "Nandini GoodLife", "is_brand": true }}
        ]
    }}
    Output:
    🔹 500ml
       🏆 Zepto • Nandini GoodLife • ₹24
       📉 Save ₹2 vs Blinkit, Save ₹4 vs BigBasket
       Tip: Upgrade to Amul Taaza for ₹26 (Blinkit)

    Example 3: (Single Option)
    Input: {{
        "size": "200g",
        "best_deal": {{ "winner_store": "Blinkit", "price": 100, "item": "Milky Mist Paneer", "savings_analysis": "Lowest price" }},
        "other_options": []
    }}
    Output:
    🔹 200g
       🏆 **Blinkit** • Milky Mist Paneer • ₹100
       📉 Lowest price
    --------------------------------------------------------

    FORMATTING RULES:
    1. **Winner Line:** 🏆 [Store] • [Brand + Product Name] • ₹[Price]
    2. **Savings:** Use the 'savings_analysis' string directly from JSON.
    3. **Tips:** CHECK 'other_options'. If there is a PREMIUM BRAND (Amul, Tata, etc.) available, mention it in the 💡 tip.
    
    OUTPUT:
    📊 Best Prices for  {query.upper()}
    """

    try:
        response = await client.chat.completions.create(
            model=os.getenv("GROQ_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI Analysis failed: {e}"

# ------------------ 4. PIPELINE ------------------

async def process_item_logic(search_query):
    corrected_query = autocorrect_query(search_query)
    search_query = corrected_query
    
    # 1. Fetch
    all_items = await asyncio.to_thread(get_products_from_db, search_query)
    
    # 2. Scrape if needed
    if not all_items:
        print(f"⚠️ No data. Scraping '{search_query}'...")
        await fetch_and_store_items([search_query])
        all_items = await asyncio.to_thread(get_products_from_db, search_query)
    
    if not all_items:
        return {"status": "error", "query": search_query, "msg": "No items found."}

    # --- 3. NEW: SEMANTIC FILTER ---
    # This removes "Pakoda", "Spring Onion" etc. BEFORE alignment
    filtered_items = await semantic_filter(search_query, all_items)
    
    if not filtered_items:
        return {"status": "error", "query": search_query, "msg": "No relevant items found after filtering."}

    # 4. Align (Python)
    aligned_data = align_products(filtered_items)
    
    # 5. Analyze (AI with JSON)
    ai_report = await get_ai_recommendation(search_query, aligned_data)

    return {
        "status": "success",
        "query": search_query,
        "report": ai_report
    }

# ------------------ MAIN ------------------

async def main():
    user_input = input("Enter items: ")
    items = [x.strip() for x in user_input.split(",") if x.strip()]
    
    for item in items:
        print(f"\n🚀 Processing '{item.upper()}'...")
        res = await process_item_logic(item)
        
        if res['status'] == 'success':
            print(res['report'])
        else:
            print(res['msg'])
        
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())