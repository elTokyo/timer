import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram.ext import Application
import storage
from parser import format_reminder
from fonbet_scraper import get_fonbet_events, find_match_on_fonbet

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def setup_scheduler(app: Application):
    # Job 1: таймер-напоминания (каждую минуту)
    scheduler.add_job(
        check_and_notify,
        trigger=IntervalTrigger(seconds=60),
        args=[app],
        id='timer_check',
        replace_existing=True
    )
    # Job 2: проверка Фонбета prematch/live (каждые 30 секунд)
    scheduler.add_job(
        check_fonbet,
        trigger=IntervalTrigger(seconds=30),
        args=[app],
        id='fonbet_check',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler запущен: таймер каждые 60с, Фонбет каждые 30с")


# ── Таймер-напоминания ────────────────────────────────────────────────────────

async def check_and_notify(app: Application):
    now = datetime.utcnow()
    for chat_id in storage.get_all_chat_ids():
        s = storage.load_settings(chat_id)
        predictions = storage.load_predictions(chat_id)
        changed = False

        for pred in predictions:
            diff = (pred.match_time - now).total_seconds() / 60

            if s.notify_30min and not pred.notified_30 and 28 <= diff <= 32:
                try:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=format_reminder(pred, 30, s.timezone_offset)
                    )
                    pred.notified_30 = True
                    changed = True
                except Exception as e:
                    logger.error(f"[30min] {e}")

            if s.notify_5min and not pred.notified_5 and 3 <= diff <= 7:
                try:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=format_reminder(pred, 5, s.timezone_offset)
                    )
                    pred.notified_5 = True
                    changed = True
                except Exception as e:
                    logger.error(f"[5min] {e}")

            if s.notify_custom_min > 0 and not pred.notified_custom:
                low, high = s.notify_custom_min - 2, s.notify_custom_min + 2
                if low <= diff <= high and s.notify_custom_min not in (5, 30):
                    try:
                        await app.bot.send_message(
                            chat_id=chat_id,
                            text=format_reminder(pred, s.notify_custom_min, s.timezone_offset)
                        )
                        pred.notified_custom = True
                        changed = True
                    except Exception as e:
                        logger.error(f"[custom] {e}")

        if changed:
            storage.save_predictions(chat_id, predictions)


# ── Проверка Фонбета ──────────────────────────────────────────────────────────

async def check_fonbet(app: Application):
    chat_ids = storage.get_all_chat_ids()
    if not chat_ids:
        return

    # Проверяем нужна ли проверка хотя бы одному пользователю
    any_enabled = any(
        storage.load_settings(cid).fonbet_check
        for cid in chat_ids
    )
    if not any_enabled:
        return

    # Один запрос к Фонбету для всех пользователей
    fonbet_events = await get_fonbet_events()
    if not fonbet_events:
        return

    for chat_id in chat_ids:
        s = storage.load_settings(chat_id)
        if not s.fonbet_check:
            continue

        predictions = storage.load_predictions(chat_id)
        changed = False

        for pred in predictions:
            # Уже уведомляли и о prematch и о live — пропускаем
            if pred.notified_prematch and pred.notified_live:
                continue

            found = find_match_on_fonbet(pred.team1, fonbet_events)
            if not found:
                continue

            is_live = found["is_live"]
            t1 = found["team1"]
            t2 = found["team2"]
            tournament = found.get("tournament", "")

            # Уведомление: матч в прематче (первый раз)
            if not pred.notified_prematch and not is_live:
                msg = (
                    f"📋 Матч в прематче на Фонбете!\n\n"
                    f"{pred.team1}\n\n"
                    f"🏷 На сайте: {t1} — {t2}"
                    + (f"\n🏆 {tournament}" if tournament else "")
                )
                try:
                    await app.bot.send_message(chat_id=chat_id, text=msg)
                    pred.notified_prematch = True
                    changed = True
                    logger.info(f"[prematch] {t1} vs {t2}")
                except Exception as e:
                    logger.error(f"[prematch notify] {e}")

            # Уведомление: матч вышел в лайв
            if not pred.notified_live and is_live:
                msg = (
                    f"🔴 LIVE на Фонбете!\n\n"
                    f"{pred.team1}\n\n"
                    f"🏷 На сайте: {t1} — {t2}"
                    + (f"\n🏆 {tournament}" if tournament else "")
                    + "\n\n⚡ Матч начался, можно ставить!"
                )
                try:
                    await app.bot.send_message(chat_id=chat_id, text=msg)
                    pred.notified_live = True
                    pred.notified_prematch = True  # раз live — prematch тоже закрываем
                    changed = True
                    logger.info(f"[live] {t1} vs {t2}")
                except Exception as e:
                    logger.error(f"[live notify] {e}")

        if changed:
            storage.save_predictions(chat_id, predictions)
