# data_cleaner.py

def keyword_filter(items, query):
    """
    Filters out items that do not contain the search terms.
    """
    print(f"   🧹 Running Keyword Filter for '{query}'...")
    
    # EXPANDED DICTIONARY FOR INDIAN GROCERIES
    synonyms = {
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
    
    query_lower = query.lower()
    
    # FALLBACK: If query is not in dict, strictly match the query word itself
    valid_keywords = synonyms.get(query_lower, [query_lower])
    
    clean_list = []
    discarded_count = 0

    for item in items:
        name_lower = item['name'].lower()
        
        # LOGIC: Item must match at least one keyword
        if any(kw in name_lower for kw in valid_keywords):
            clean_list.append(item)
        else:
            discarded_count += 1
            
    if discarded_count > 0:
        print(f"      ❌ Removed {discarded_count} irrelevant items.")
        
    return clean_list