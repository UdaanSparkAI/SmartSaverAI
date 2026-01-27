import json
import os
import asyncio
import pandas as pd
from datetime import datetime
from groq import AsyncGroq
from dotenv import load_dotenv
from difflib import SequenceMatcher
from .db_ingest import fetch_and_store_items
from .data_cleaner import autocorrect_query


from sqlalchemy import text
from .db_supabase import SessionLocal

load_dotenv()

# Use your specific Groq API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")

client = AsyncGroq(api_key=GROQ_API_KEY)

# ------------------ HELPERS ------------------

def get_size_bucket(qty_str):
    """
    Normalizes sizes into comparison buckets.
    """
    if not qty_str: return "unknown"
    
    qty_str = qty_str.lower().replace(" ", "")
    
    # --- VOLUME BUCKETS ---
    # Small Packs
    if "180ml" in qty_str or "200ml" in qty_str or "250ml" in qty_str: return "200-250ml"
    
    # Standard Packs
    if "450ml" in qty_str or "475ml" in qty_str or "500ml" in qty_str: return "500ml"
    
    # Large Packs
    if "900ml" in qty_str or "1l" in qty_str or "1000ml" in qty_str: return "1000ml"
    
    # --- WEIGHT BUCKETS ---
    if "280g" in qty_str: return "280g"
    if "560g" in qty_str: return "560g"
    if "pair" in qty_str: return qty_str # e.g., "3pair"
    if "set" in qty_str: return "set"
    if "roll" in qty_str: return "roll"
    if "bunch" in qty_str: return "bunch"
    
    # --- EGG BUCKETS ---
    if "6pcs" in qty_str or "6egg" in qty_str: return "6pcs"
    if "10pcs" in qty_str or "12pcs" in qty_str: return "10-12pcs"
    if "30pcs" in qty_str: return "30pcs"
    
    return qty_str

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def get_products_from_db(search_query):
    """
    Fetches products from Supabase and prepares them
    in the same structure previously returned by pandas.
    """

    db = SessionLocal()

    result = db.execute(
        text("""
            SELECT
                source,
                product_name,
                price,
                quantity_value,
                quantity_unit
            FROM products
            WHERE search_query = :q
        """),
        {"q": search_query}
    )

    rows = result.fetchall()
    db.close()

    if not rows:
        return None, None

    # Convert rows to mutable dicts
    records = []
    for r in rows:
        records.append({
            "source": r.source,
            "product_name": r.product_name,
            "price": r.price,
            "quantity_value": r.quantity_value,
            "quantity_unit": r.quantity_unit
        })

    # ---------------- NORMALIZATION (same logic, no pandas) ----------------

    for r in records:
        try:
            if r["quantity_value"] is None:
                r["norm_qty"] = 0
                r["norm_unit"] = "unknown"
                continue

            val = float(r["quantity_value"])
            unit = str(r["quantity_unit"]).lower().strip()

            if unit == "l":
                r["norm_qty"] = val * 1000
                r["norm_unit"] = "ml"
            elif unit == "kg":
                r["norm_qty"] = val * 1000
                r["norm_unit"] = "g"
            else:
                r["norm_qty"] = val
                r["norm_unit"] = unit

        except Exception:
            r["norm_qty"] = 0
            r["norm_unit"] = "unknown"

    # Size bucket generation
    for r in records:
        qty = int(r["norm_qty"]) if r["norm_qty"] else 0
        r["bucket_size"] = get_size_bucket(f"{qty}{r['norm_unit']}")

    # Split by source (same output contract as before)
    blinkit_items = [r for r in records if r["source"] == "blinkit"]
    zepto_items = [r for r in records if r["source"] == "zepto"]

    return blinkit_items, zepto_items


# ------------------ AI MATCHING LOGIC ------------------

async def ai_find_matches(blinkit_items, zepto_items):
    # 1. Prepare Data for AI
    b_simple = [{ 'id': i, 'name': p['product_name'], 'size_hint': p['bucket_size'], 'real_qty': f"{p['norm_qty']}{p['norm_unit']}" } for i, p in enumerate(blinkit_items)]
    z_simple = [{ 'id': i, 'name': p['product_name'], 'size_hint': p['bucket_size'], 'real_qty': f"{p['norm_qty']}{p['norm_unit']}" } for i, p in enumerate(zepto_items)]

    print(f"   🔎 DEBUG: Processing {len(b_simple)} Blinkit items vs {len(z_simple)} Zepto items...")

    # 2. AI Prompt
    prompt = f"""
    You are a Grocery Matcher.
    
    List A (Blinkit): {json.dumps(b_simple)}
    List B (Zepto): {json.dumps(z_simple)}
    
    TASK: Output a JSON list of matched pairs.
    
    CRITICAL MATCHING RULES:
    1. MATCH BY 'size_hint': If 'size_hint' is same (e.g. '500ml' vs '500ml'), they MATCH, even if 'real_qty' is different (450ml vs 500ml).
    2. MATCH BY NAME: Ignore brands if comparing commodities like "Eggs" or "Onion". Match "Farm Fresh Eggs" with "White Eggs" if quantity matches.
    3. EXHAUSTIVE: Find as many pairs as possible. Match 6pcs with 6pcs, 30pcs with 30pcs.
    
    OUTPUT FORMAT:
    {{
        "pairs": [
            {{ "b_id": 0, "z_id": 1 }}
        ]
    }}
    """
    
    ai_pairs = []
    
    # 3. Call AI
    if client:
        try:
            response = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are a JSON-only assistant."}, 
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=6000
            )
            content = response.choices[0].message.content
            ai_pairs = json.loads(content).get('pairs', [])
        except Exception as e:
            print(f"   ⚠️ AI Match failed: {e}")

    # ---------------------------------------------------------
    # 4. ROBUST VALIDATION & PYTHON FALLBACK
    # ---------------------------------------------------------
    
    final_matches = []
    used_b_ids = set()
    used_z_ids = set()

    # Process AI Matches with SAFETY CHECKS
    for p in ai_pairs:
        # Check keys exist
        if 'b_id' not in p or 'z_id' not in p: continue
        
        try:
            b_id = int(p['b_id'])
            z_id = int(p['z_id'])
        except ValueError: continue

        # Check Range (Fixes IndexError crash)
        if b_id < 0 or b_id >= len(blinkit_items): continue
        if z_id < 0 or z_id >= len(zepto_items): continue

        b_item = blinkit_items[b_id]
        z_item = zepto_items[z_id]

        # --- NUMERIC GUARD: Reject if sizes are mathematically incompatible ---
        # 1. Unit Check
        if b_item['norm_unit'] != z_item['norm_unit']: continue
        
        # 2. Difference Calculation
        b_q = float(b_item['norm_qty'])
        z_q = float(z_item['norm_qty'])
        diff = abs(b_q - z_q)
        
        # 3. Tolerance Logic
        is_compatible = False
        if b_q < 300: # Small items (e.g. 200ml)
            if diff <= 60: is_compatible = True # Allow 200 vs 250
        else: # Large items (e.g. 500ml)
            if diff <= 150: is_compatible = True # Allow 450 vs 500
        
        if not is_compatible: continue 
        # ----------------------------------------------------------------------

        final_matches.append((b_item, z_item))
        used_b_ids.add(b_id)
        used_z_ids.add(z_id)

    # Fallback Loop: Check purely on 'bucket_size' match for missed items
    print(f"   🤖 AI found {len(final_matches)} valid pairs. Checking for missed size matches...")

    for i, b_item in enumerate(blinkit_items):
        if i in used_b_ids: continue
        
        for j, z_item in enumerate(zepto_items):
            if j in used_z_ids: continue

            # Strict Bucket Match for Fallback
            if b_item['bucket_size'] == z_item['bucket_size']:
                
                # Similarity Check (> 30%)
                name_sim = similar(b_item['product_name'].lower(), z_item['product_name'].lower())
                
                if name_sim > 0.3: 
                    final_matches.append((b_item, z_item))
                    used_b_ids.add(i)
                    used_z_ids.add(j)
                    break 

    # 5. Format Output
    structured_results = []
    
    for b_item, z_item in final_matches:
        # Calculate Unit Price
        b_qty = float(b_item['norm_qty']) if b_item['norm_qty'] > 0 else 1
        z_qty = float(z_item['norm_qty']) if z_item['norm_qty'] > 0 else 1
        
        b_unit = float(b_item['price']) / b_qty
        z_unit = float(z_item['price']) / z_qty
        
        # Strict Winner Logic
        if b_unit < z_unit:
            winner = "Blinkit"
        elif z_unit < b_unit:
            winner = "Zepto"
        else:
            winner = "Tie"
            
        structured_results.append({
            "product_name": b_item['product_name'], # Display Name
            "variant": b_item['bucket_size'],   
            "b_name": b_item['product_name'],  
            "z_name": z_item['product_name'], 
            "real_qty_b": f"{int(b_item['norm_qty'])}{b_item['norm_unit']}",
            "real_qty_z": f"{int(z_item['norm_qty'])}{z_item['norm_unit']}",
            "b_price": b_item['price'],
            "z_price": z_item['price'],
            "winner": winner
        })

    return structured_results

async def process_item_logic(search_query):

    corrected_query = autocorrect_query(search_query)
    if corrected_query != search_query.lower():
        print(f"   ✨ Auto-corrected '{search_query}' -> '{corrected_query}'")
    
    search_query = corrected_query
    blinkit_items, zepto_items = await asyncio.to_thread(get_products_from_db, search_query)
    
    if not blinkit_items and not zepto_items:
        print(f"⚠️ No data found in DB for '{search_query}'. Initiating Live Scrape...")
        
        # CALL THE SCRAPER (This will open browser, scrape, and save to DB)
        await fetch_and_store_items([search_query])
        
        # 3. Second Attempt: Re-check DB after scraping
        blinkit_items, zepto_items = await asyncio.to_thread(get_products_from_db, search_query)
    
    # 4. If STILL empty, then it's a real failure
    if not blinkit_items or not zepto_items:
        return {"status": "error", "query": search_query, "msg": "Insufficient data even after scraping."}

    # 5. Run AI Matching
    matches = await ai_find_matches(blinkit_items, zepto_items)

    return {
        "status": "success",
        "query": search_query,
        "matches": matches
    }

def print_item_report(data):
    search_query = data["query"]
    print(f"\n📊 COMPARISON FOR: {search_query.upper()}")

    if data["status"] == "error":
        print(f"   ❌ {data['msg']}")
        return

    matches = data["matches"]
    
    if matches:
        # Header with Product Names
        # We allot 25 characters for names to keep the table readable
        print(f"{'SIZE':<8} | {'BLINKIT ITEM':<25} | {'ZEPTO ITEM':<25} | {'BLINKIT':<8} | {'ZEPTO':<8} | {'WINNER'}")
        print("-" * 110)
        
        for m in matches:
            bucket = m['variant']
            
            # Truncate names to 23 chars + '..'
            b_name = (m['b_name'][:23] + '..') if len(m['b_name']) > 23 else m['b_name']
            z_name = (m['z_name'][:23] + '..') if len(m['z_name']) > 23 else m['z_name']
            
            # Combine Price & Real Qty for compact view: "₹44(140g)"
            b_details = f"₹{m['b_price']} ({m['real_qty_b']})"
            z_details = f"₹{m['z_price']} ({m['real_qty_z']})"
            
            winner = m['winner']
            
            if winner == "Blinkit":
                win_str = "🟢 Blinkit"
            elif winner == "Zepto":
                win_str = "🟣 Zepto"
            else:
                win_str = "⚪ Tie"
                
            print(f"{bucket:<8} | {b_name:<25} | {z_name:<25} | {b_details:<12} | {z_details:<12} | {win_str}")
        print("-" * 110)

        print(f"\n📱 TELEGRAM PREVIEW FOR: {data['query'].upper()}")
        print("-" * 40)
        
        # Ensure 'format_for_telegram' function is defined in your script before calling it
        telegram_msg = format_for_telegram(matches) 
        print(telegram_msg)
        print("-" * 40)
    else:
        print("   ⚠️ No matching products found to compare.")

def format_for_telegram(matches):
    if not matches:
        return "⚠️ No matches found."

    # 1. Group by Variant (Size)
    # We want to find the CHEAPEST product for each size on both platforms
    # Structure: { "500ml": { "b_min": {price, name}, "z_min": {price, name} } }
    
    analysis = {}
    
    for m in matches:
        variant = m['variant']
        
        if variant not in analysis:
            analysis[variant] = {
                "b_best": None,
                "z_best": None
            }
        
        # Check Blinkit Price
        b_price = float(m['b_price'])
        if analysis[variant]['b_best'] is None or b_price < analysis[variant]['b_best']['price']:
            analysis[variant]['b_best'] = { 'price': b_price, 'name': m['b_name'] }
            
        # Check Zepto Price
        z_price = float(m['z_price'])
        if analysis[variant]['z_best'] is None or z_price < analysis[variant]['z_best']['price']:
            analysis[variant]['z_best'] = { 'price': z_price, 'name': m['z_name'] }

    # 2. Build the Message String
    msg_lines = []
    
    # Sort variants to keep logic (e.g. 6pcs, then 30pcs) - simple string sort for now
    for variant in sorted(analysis.keys()):
        data = analysis[variant]
        b_data = data['b_best']
        z_data = data['z_best']
        
        if not b_data or not z_data: continue # Skip partial data
        
        b_price = b_data['price']
        z_price = z_data['price']
        
        # Determine Winner
        if b_price < z_price:
            winner_icon = "🟢"
            winner_name = "Blinkit"
            win_price = b_price
            lose_price = z_price
            save_amt = int(lose_price - win_price)
        elif z_price < b_price:
            winner_icon = "🟣"
            winner_name = "Zepto"
            win_price = z_price
            lose_price = b_price
            save_amt = int(lose_price - win_price)
        else:
            winner_icon = "⚪"
            winner_name = "Tie"
            win_price = b_price
            lose_price = b_price
            save_amt = 0

        # FORMATTING THE CARD
        msg_lines.append(f"🔹 **{variant}**")
        
        if winner_name == "Tie":
             msg_lines.append(f"   🤝 **It's a Tie!** (₹{int(win_price)})")
        else:
            msg_lines.append(f"   🏆 {winner_icon} **{winner_name} Wins!**")
            msg_lines.append(f"   💰 **₹{int(win_price)}** vs ~₹{int(lose_price)}~ (Save ₹{save_amt})")
            
            # Optional: Show product names if needed
            # msg_lines.append(f"   Items: {b_data['name'][:15]}.. vs {z_data['name'][:15]}..")
        
        msg_lines.append("") # Empty line for spacing

    return "\n".join(msg_lines)

async def main():
    user_input = input("Enter items (e.g. Milk, Eggs): ")
    items = [x.strip() for x in user_input.split(",") if x.strip()]
    
    print(f"\n🚀 analyzing...")
    tasks = [process_item_logic(item) for item in items]
    results = await asyncio.gather(*tasks)

    for res in results:
        print_item_report(res)

async def get_telegram_message(search_query: str) -> str:
    """
    Entry point for Telegram bot.
    Returns formatted Telegram-ready message.
    """
    result = await process_item_logic(search_query)

    if result["status"] != "success":
        return f"❌ No sufficient data for {search_query}."

    matches = result["matches"]

    if not matches:
        return f"⚠️ No comparable items found for {search_query}."

    msg = f"📱 PRICE COMPARISON: {search_query.upper()}\n"
    msg += "----------------------------------------\n"
    msg += format_for_telegram(matches)

    return msg

if __name__ == "__main__":
    asyncio.run(main())