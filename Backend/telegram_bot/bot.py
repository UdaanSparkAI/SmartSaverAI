# telegram_bot/bot.py

import os
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram import Update

from .handlers import start, text_handler, callback_handler

# --------------------
# Load environment
# --------------------
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN is missing or invalid")


# --------------------
# Global error handler
# --------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("⚠️ Telegram bot error:", context.error)

    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Something went wrong. Please try again."
            )
        except Exception:
            pass


# --------------------
# Main entry point
# --------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Error handling
    app.add_error_handler(error_handler)

    print("🤖 SmartSaver AI Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
