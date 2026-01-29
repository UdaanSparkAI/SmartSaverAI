# telegram_bot/handlers.py

from telegram import Update
from telegram.ext import ContextTypes

from Backend.ai_reco import get_telegram_message
from Backend.categories import CATEGORIES

from .keyboards import (
    start_keyboard,
    category_inline_keyboard,
    subcategory_inline_keyboard,
    items_inline_keyboard
)

# --------------------
# /start command
# --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "👋 Welcome to *SmartSaverAI Groceries*\n\n"
        "How would you like to search?\n\n"
        "👉 Choose an option below ⬇️",
        reply_markup=start_keyboard(),
        parse_mode="Markdown"
    )


# --------------------
# Text message handler
# --------------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # OPTION 1: Browse Categories
    if text == "📂 Browse Categories":
        context.user_data.pop("mode", None)

        await update.message.reply_text(
            "📦 Select a category:",
            reply_markup=category_inline_keyboard()
        )

    # OPTION 2: Manual search
    elif text == "🔍 Search Item Manually":
        context.user_data["mode"] = "manual"

        await update.message.reply_text(
            "✍️ Enter item names (comma-separated)\n"
            "e.g. Milk, Onion"
        )

    # Back to main menu
    elif text == "⬅️ Back":
        context.user_data.clear()

        await update.message.reply_text(
            "Main menu:",
            reply_markup=start_keyboard()
        )

    # Manual search input (supports multiple items)
    else:
        if context.user_data.get("mode") == "manual":
            items = [i.strip() for i in text.split(",") if i.strip()]

            for item in items:
                await update.message.reply_text(
                    f"🔎 Analyzing *{item}*...",
                    parse_mode="Markdown"
                )

                msg = await get_telegram_message(item)
                await update.message.reply_text(msg, parse_mode="Markdown")


# --------------------
# Inline button handler
# --------------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")

    # --------------------
    # CATEGORY CLICK
    # callback_data = cat|Staples & Grains
    # --------------------
    if data[0] == "cat":
        category = data[1]
        category_data = CATEGORIES.get(category)

        # CASE 1: Category has subcategories
        if isinstance(category_data, dict):
            await query.message.reply_text(
                f"📂 *{category}*\nChoose a sub-category:",
                reply_markup=subcategory_inline_keyboard(category),
                parse_mode="Markdown"
            )

        # CASE 2: Category has items directly
        elif isinstance(category_data, list):
            await query.message.reply_text(
                f"🛒 *{category}* items:",
                reply_markup=items_inline_keyboard(category),
                parse_mode="Markdown"
            )

    # --------------------
    # SUBCATEGORY CLICK
    # callback_data = subcat|Fruits & Vegetables|Vegetables
    # --------------------
    elif data[0] == "subcat":
        _, category, subcategory = data

        await query.message.reply_text(
            f"🛒 *{subcategory}* items:",
            reply_markup=items_inline_keyboard(category, subcategory),
            parse_mode="Markdown"
        )

    # --------------------
    # ITEM CLICK → AI SEARCH
    # callback_data = item|Onion
    # --------------------
    elif data[0] == "item":
        item = data[1]

        await query.message.reply_text(
            f"🔎 Analyzing *{item}*...",
            parse_mode="Markdown"
        )

        msg = await get_telegram_message(item)
        await query.message.reply_text(msg, parse_mode="Markdown")

    # --------------------
    # NAVIGATION (future use)
    # --------------------
    elif data[0] == "nav":
        return
