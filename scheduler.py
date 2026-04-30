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
        changed = False

        for pred in predictions:
            match_time = pred.match_time
            diff_minutes = (match_time - now).total_seconds() / 60

            # 30-minute notification — wide window: between 28 and 32 min
            if (settings.notify_30min
                    and not pred.notified_30
                    and 28 <= diff_minutes <= 32):
                try:
                    msg = format_reminder(pred, 30)
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode='Markdown'
                    )
                    pred.notified_30 = True
                    changed = True
                    logger.info(f"Sent 30min reminder for {pred.team1} vs {pred.team2}")
                except Exception as e:
                    logger.error(f"Failed to send 30min reminder: {e}")

            # 5-minute notification — wide window: between 3 and 7 min
            if (settings.notify_5min
                    and not pred.notified_5
                    and 3 <= diff_minutes <= 7):
                try:
                    msg = format_reminder(pred, 5)
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode='Markdown'
                    )
                    pred.notified_5 = True
                    changed = True
                    logger.info(f"Sent 5min reminder for {pred.team1} vs {pred.team2}")
                except Exception as e:
                    logger.error(f"Failed to send 5min reminder: {e}")

            # Custom notification — wide window: ±2 min
            if settings.notify_custom_min > 0 and not pred.notified_custom:
                low = settings.notify_custom_min - 2
                high = settings.notify_custom_min + 2
                if low <= diff_minutes <= high and settings.notify_custom_min not in (5, 30):
                    try:
                        msg = format_reminder(pred, settings.notify_custom_min)
                        await app.bot.send_message(
                            chat_id=chat_id,
                            text=msg,
                            parse_mode='Markdown'
                        )
                        pred.notified_custom = True
                        changed = True
                        logger.info(f"Sent custom {settings.notify_custom_min}min reminder")
                    except Exception as e:
                        logger.error(f"Failed to send custom reminder: {e}")

        # Save all changes in one write instead of one write per notification
        if changed:
            storage.save_predictions(chat_id, predictions)
