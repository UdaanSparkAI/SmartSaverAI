# telegram_bot/keyboards.py

from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from categories import CATEGORIES


# --------------------
# START / MAIN MENU
# --------------------
def start_keyboard():
    """
    Main entry keyboard shown on /start
    """
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
    """
    Inline keyboard for top-level categories
    """
    buttons = [
        [InlineKeyboardButton(cat, callback_data=f"cat|{cat}")]
        for cat in CATEGORIES.keys()
    ]

    # Optional back button (future UX)
    buttons.append(
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="nav|back_main")]
    )

    return InlineKeyboardMarkup(buttons)


# --------------------
# SUBCATEGORY (INLINE)
# --------------------
def subcategory_inline_keyboard(category):
    """
    Inline keyboard for subcategories inside a category
    """
    subcats = CATEGORIES.get(category)
    buttons = []

    if isinstance(subcats, dict):
        for sub in subcats.keys():
            buttons.append(
                [InlineKeyboardButton(sub, callback_data=f"subcat|{category}|{sub}")]
            )

    # Back to categories
    buttons.append(
        [InlineKeyboardButton("⬅️ Back to Categories", callback_data="nav|back_categories")]
    )

    return InlineKeyboardMarkup(buttons)


# --------------------
# ITEMS (INLINE)
# --------------------
def items_inline_keyboard(category, subcategory=None):
    """
    Inline keyboard for final item selection
    """
    if subcategory:
        items = CATEGORIES[category][subcategory]
    else:
        items = CATEGORIES[category]

    buttons = [
        [InlineKeyboardButton(item, callback_data=f"item|{item}")]
        for item in items
    ]

    # Back to subcategories
    buttons.append(
        [InlineKeyboardButton("⬅️ Back", callback_data=f"nav|back_subcat|{category}")]
    )

    return InlineKeyboardMarkup(buttons)
