import difflib

# 1. MOVED TO MODULE LEVEL (So Auto-Correct can use it)
# Master list of all valid grocery terms we know about
SYNONYMS = {
    # VEGETABLES
    "onion": ["onion", "pyaz", "pyaaz"],
    "potato": ["potato", "aloo", "batata"],
    "tomato": ["tomato", "tamatar"],
    "coriander": ["coriander", "dhaniya", "cilantro"],
    "chilli": ["chilli", "mirch", "pepper", "paprika"],
    "ginger": ["ginger", "adrak"],
    "garlic": ["garlic", "lehsun"],
    "lemon": ["lemon", "nimbu", "lime"],
    "cucumber": ["cucumber", "kheera", "kakdi"],
    "carrot": ["carrot", "gajar"],
    "cauliflower": ["cauliflower", "gobi", "gobhi"],
    "cabbage": ["cabbage", "patta gobhi"],
    "peas": ["peas", "matar"],
    "spinach": ["spinach", "palak"],
    "lady finger": ["lady finger", "bhindi", "okra"],
    "brinjal": ["brinjal", "baingan", "eggplant"],
    "capsicum": ["capsicum", "shimla mirch", "bell pepper"],

    # DAIRY & BREAKFAST
    "milk": ["milk", "doodh", "dairy"],
    "curd": ["curd", "dahi", "yogurt"],
    "paneer": ["paneer", "cottage cheese"],
    "butter": ["butter", "maska"],
    "cheese": ["cheese", "cheddar", "mozzarella"],
    "bread": ["bread", "bun", "pav", "loaf"],
    "egg": ["egg", "anda", "eggs"],
    "coffee": ["coffee", "nescafe", "bru"],
    "tea": ["tea", "chai", "tata tea"],
    
    # STAPLES
    "rice": ["rice", "chawal", "basmati"],
    "flour": ["flour", "atta", "maida", "besan"],
    "sugar": ["sugar", "cheeni", "shakkar"],
    "salt": ["salt", "namak"],
    "oil": ["oil", "tel", "sunflower", "mustard", "ghee"],
    "dal": ["dal", "lentil", "pulse", "toor", "moong", "urad"],

    # FRUITS
    "apple": ["apple", "seb"],
    "banana": ["banana", "kela"],
    "mango": ["mango", "aam"],
    "papaya": ["papaya", "papita"]
}

# Flatten all known words into a single list for checking
# This creates a list like ['onion', 'pyaz', 'potato', 'aloo', 'milk'...]
ALL_VALID_WORDS = set()
for key, values in SYNONYMS.items():
    ALL_VALID_WORDS.add(key)
    for v in values:
        ALL_VALID_WORDS.add(v)


def autocorrect_query(user_query):
    """
    Corrects 'milks' -> 'milk', 'tomat' -> 'tomato'
    using the known grocery dictionary.
    """
    user_query = user_query.lower().strip()
    
    # 1. Exact match? Return immediately
    if user_query in ALL_VALID_WORDS:
        return user_query
    
    # 2. Fuzzy match (Find closest word in our list)
    # cutoff=0.8 means it must be 80% similar (prevents wild guesses)
    matches = difflib.get_close_matches(user_query, ALL_VALID_WORDS, n=1, cutoff=0.8)
    
    if matches:
        suggestion = matches[0]
        print(f"   🪄 Auto-corrected '{user_query}' -> '{suggestion}'")
        return suggestion
    
    # 3. No close match? Return original (maybe it's a new item not in our list)
    return user_query


def keyword_filter(items, query):
    """
    Filters out items that do not contain the search terms.
    """
    print(f"   🧹 Running Keyword Filter for '{query}'...")
    
    query_lower = query.lower()
    
    # Use the global SYNONYMS dict now
    valid_keywords = SYNONYMS.get(query_lower, [query_lower])
    
    clean_list = []
    discarded_count = 0

    for item in items:
        name_lower = item['name'].lower()
        if any(kw in name_lower for kw in valid_keywords):
            clean_list.append(item)
        else:
            discarded_count += 1
            
    if discarded_count > 0:
        print(f"      ❌ Removed {discarded_count} irrelevant items.")
        
    return clean_list