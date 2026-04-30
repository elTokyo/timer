import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram.ext import Application
import storage
from parser import format_reminder

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def setup_scheduler(app: Application):
    scheduler.add_job(
        check_and_notify,
        trigger=IntervalTrigger(seconds=60),
        args=[app],
        id='notification_check',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started, checking every 60 seconds")


async def check_and_notify(app: Application):
    now = datetime.now()
    chat_ids = storage.get_all_chat_ids()

    for chat_id in chat_ids:
        settings = storage.load_settings(chat_id)
        predictions = storage.load_predictions(chat_id)

        for pred in predictions:
            match_time = pred.match_time
            diff_minutes = (match_time - now).total_seconds() / 60

            # 30-minute notification
            if (settings.notify_30min
                    and not pred.notified_30
                    and 29 <= diff_minutes <= 31):
                try:
                    msg = format_reminder(pred, 30)
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode='Markdown'
                    )
                    storage.update_prediction(chat_id, pred.id, notified_30=True)
                    logger.info(f"Sent 30min reminder for {pred.team1} vs {pred.team2}")
                except Exception as e:
                    logger.error(f"Failed to send 30min reminder: {e}")

            # 5-minute notification
            if (settings.notify_5min
                    and not pred.notified_5
                    and 4 <= diff_minutes <= 6):
                try:
                    msg = format_reminder(pred, 5)
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode='Markdown'
                    )
                    storage.update_prediction(chat_id, pred.id, notified_5=True)
                    logger.info(f"Sent 5min reminder for {pred.team1} vs {pred.team2}")
                except Exception as e:
                    logger.error(f"Failed to send 5min reminder: {e}")

            # Custom notification
            if (settings.notify_custom_min > 0):
                custom_window_low = settings.notify_custom_min - 1
                custom_window_high = settings.notify_custom_min + 1
                # Use notified_30 as a proxy flag — in future can add custom flag
                if custom_window_low <= diff_minutes <= custom_window_high:
                    # Only send if different from 30 and 5 min
                    if settings.notify_custom_min not in (5, 30):
                        try:
                            msg = format_reminder(pred, settings.notify_custom_min)
                            await app.bot.send_message(
                                chat_id=chat_id,
                                text=msg,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Failed to send custom reminder: {e}")
