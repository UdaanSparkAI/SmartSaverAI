# telegram_bot/keyboards.py

from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from Backend.categories import CATEGORIES


# --------------------
# START / MAIN MENU
# --------------------
def start_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📂 Browse Categories", "🔍 Search Item Manually"]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


# --------------------
# CATEGORY (INLINE)
# --------------------
def category_inline_keyboard():
    buttons = [
        [InlineKeyboardButton(cat, callback_data=f"cat|{cat}")]
        for cat in CATEGORIES.keys()
    ]

    buttons.append(
        [InlineKeyboardButton("🧺 View Basket", callback_data="basket|view")]
    )

    return InlineKeyboardMarkup(buttons)


# --------------------
# SUBCATEGORY (INLINE)
# --------------------
def subcategory_inline_keyboard(category):
    subcats = CATEGORIES.get(category)
    buttons = []

    if isinstance(subcats, dict):
        for sub in subcats.keys():
            buttons.append(
                [InlineKeyboardButton(sub, callback_data=f"subcat|{category}|{sub}")]
            )

    buttons.append(
        [InlineKeyboardButton("🧺 View Basket", callback_data="basket|view")]
    )

    return InlineKeyboardMarkup(buttons)


# --------------------
# ITEMS (INLINE)
# --------------------
def items_inline_keyboard(category, subcategory=None):
    if subcategory:
        items = CATEGORIES[category][subcategory]
    else:
        items = CATEGORIES[category]

    buttons = [
        [InlineKeyboardButton(f"➕ {item}", callback_data=f"item|{item}")]
        for item in items
    ]

    buttons.extend([
        [InlineKeyboardButton("➕ Add More Items", callback_data="basket|add_more")],
        [InlineKeyboardButton("🧺 View Basket", callback_data="basket|view")],
        [InlineKeyboardButton("🔍 Compare Basket", callback_data="basket|compare")]
    ])

    return InlineKeyboardMarkup(buttons)

