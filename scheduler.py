import logging
from datetime import datetime, timezone
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
    # Always compare in UTC — predictions are stored as naive UTC datetimes
    now = datetime.utcnow()
    chat_ids = storage.get_all_chat_ids()

    for chat_id in chat_ids:
        s = storage.load_settings(chat_id)
        predictions = storage.load_predictions(chat_id)
        changed = False

        for pred in predictions:
            diff_minutes = (pred.match_time - now).total_seconds() / 60

            # ── 30-minute window: 28..32 ──────────────────────────────────
            if s.notify_30min and not pred.notified_30 and 28 <= diff_minutes <= 32:
                try:
                    msg = format_reminder(pred, 30, s.timezone_offset)
                    await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
                    pred.notified_30 = True
                    changed = True
                    logger.info(f"[30min] {pred.team1} vs {pred.team2} | diff={diff_minutes:.1f}min")
                except Exception as e:
                    logger.error(f"[30min] send failed: {e}")

            # ── 5-minute window: 3..7 ─────────────────────────────────────
            if s.notify_5min and not pred.notified_5 and 3 <= diff_minutes <= 7:
                try:
                    msg = format_reminder(pred, 5, s.timezone_offset)
                    await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
                    pred.notified_5 = True
                    changed = True
                    logger.info(f"[5min] {pred.team1} vs {pred.team2} | diff={diff_minutes:.1f}min")
                except Exception as e:
                    logger.error(f"[5min] send failed: {e}")

            # ── Custom window: notify_custom_min ± 2 ─────────────────────
            if s.notify_custom_min > 0 and not pred.notified_custom:
                low = s.notify_custom_min - 2
                high = s.notify_custom_min + 2
                if low <= diff_minutes <= high and s.notify_custom_min not in (5, 30):
                    try:
                        msg = format_reminder(pred, s.notify_custom_min, s.timezone_offset)
                        await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
                        pred.notified_custom = True
                        changed = True
                        logger.info(f"[custom {s.notify_custom_min}min] {pred.team1} vs {pred.team2}")
                    except Exception as e:
                        logger.error(f"[custom] send failed: {e}")

        if changed:
            storage.save_predictions(chat_id, predictions)
