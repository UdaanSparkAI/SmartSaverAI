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
    context.user_data["basket"] = []

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

    if text == "📂 Browse Categories":
        context.user_data.pop("mode", None)
        context.user_data.setdefault("basket", [])

        await update.message.reply_text(
            "📦 Select a category:",
            reply_markup=category_inline_keyboard()
        )

    elif text == "🔍 Search Item Manually":
        context.user_data["mode"] = "manual"

        await update.message.reply_text(
            "✍️ Enter item names (comma-separated)\n"
            "e.g. Milk, Onion"
        )

    elif text == "⬅️ Back":
        context.user_data.clear()
        context.user_data["basket"] = []

        await update.message.reply_text(
            "Main menu:",
            reply_markup=start_keyboard()
        )

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
    context.user_data.setdefault("basket", [])

    # --------------------
    # CATEGORY CLICK
    # --------------------
    if data[0] == "cat":
        category = data[1]
        category_data = CATEGORIES.get(category)

        if isinstance(category_data, dict):
            await query.message.reply_text(
                f"📂 *{category}*\nChoose a sub-category:",
                reply_markup=subcategory_inline_keyboard(category),
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(
                f"🛒 *{category}* items:",
                reply_markup=items_inline_keyboard(category),
                parse_mode="Markdown"
            )

    # --------------------
    # SUBCATEGORY CLICK
    # --------------------
    elif data[0] == "subcat":
        _, category, subcategory = data

        await query.message.reply_text(
            f"🛒 *{subcategory}* items:",
            reply_markup=items_inline_keyboard(category, subcategory),
            parse_mode="Markdown"
        )

    # --------------------
    # ITEM CLICK → ADD TO BASKET
    # --------------------
    elif data[0] == "item":
        item = data[1]

        if item not in context.user_data["basket"]:
            context.user_data["basket"].append(item)

        await query.message.reply_text(
            f"✅ *{item}* added to basket\n"
            f"🧺 Basket: {', '.join(context.user_data['basket'])}",
            parse_mode="Markdown"
        )

    # --------------------
    # VIEW BASKET
    # --------------------
    elif data[0] == "basket" and data[1] == "view":
        basket = context.user_data.get("basket", [])

        if not basket:
            await query.message.reply_text("🧺 Your basket is empty.")
        else:
            await query.message.reply_text(
                "🧺 *Your Basket:*\n" + "\n".join(f"• {i}" for i in basket),
                parse_mode="Markdown"
            )

    # --------------------
    # COMPARE BASKET
    # --------------------
    elif data[0] == "basket" and data[1] == "compare":
        basket = context.user_data.get("basket", [])

        if not basket:
            await query.message.reply_text("🧺 Basket is empty.")
            return

        await query.message.reply_text(
            "🔍 Comparing basket items...",
            parse_mode="Markdown"
        )

        for item in basket:
            msg = await get_telegram_message(item)
            await query.message.reply_text(msg, parse_mode="Markdown")

        context.user_data["basket"] = []
        
    elif data[0] == "basket" and data[1] == "add_more":
        await query.message.reply_text(
            "📦 Select a category:",
            reply_markup=category_inline_keyboard()
        )


    # --------------------
    # NAV (future)
    # --------------------
    elif data[0] == "nav":
        return
