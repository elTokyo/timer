import logging
import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from handlers import (
    check_fonbet_now,
    start, add_predictions, list_predictions, clear_predictions,
    settings, button_callback, delete_prediction, handle_text
)
from scheduler import setup_scheduler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_predictions))
    app.add_handler(CommandHandler("list", list_predictions))
    app.add_handler(CommandHandler("clear", clear_predictions))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("delete", delete_prediction))
    app.add_handler(CommandHandler("checkfonbet", check_fonbet_now))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    setup_scheduler(app)

    logger.info("Bot started!")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
