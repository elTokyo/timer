import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from parser import parse_predictions, format_prediction
import storage

logger = logging.getLogger(__name__)

# Track users waiting to paste predictions
WAITING_FOR_INPUT = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Ensure default settings exist
    settings = storage.load_settings(chat_id)
    storage.save_settings(settings)

    text = (
        "⚽ *Бот для прогнозов на матчи*\n\n"
        "Команды:\n"
        "📥 /add — добавить прогнозы\n"
        "📋 /list — список на сегодня\n"
        "🗑 /clear — очистить все\n"
        "⚙️ /settings — настройки уведомлений\n\n"
        "Поддерживаемый формат:\n"
        "`1. Soccer. Brazil. Acreano U20. 2-00 Santa Cruz — Independencia ф1-4,5`\n\n"
        "Бот пришлёт напоминание за 30 и 5 минут до матча 🔔"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def add_predictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    WAITING_FOR_INPUT[chat_id] = True

    await update.message.reply_text(
        "📥 *Вставь прогнозы* — каждый с новой строки.\n\n"
        "Формат:\n"
        "`1. Soccer. Brazil. Liga. 14-00 Команда1 — Команда2 Ставка`\n\n"
        "Можно вставить сразу весь список из Discord:",
        parse_mode='Markdown'
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mode = WAITING_FOR_INPUT.get(chat_id)

    if not mode:
        await update.message.reply_text(
            "Используй /add чтобы добавить прогнозы, или /list чтобы посмотреть список."
        )
        return

    WAITING_FOR_INPUT[chat_id] = False
    text = update.message.text.strip()

    # ── Handle timezone input ──────────────────────────────────────────────
    if mode == "timezone":
        try:
            offset = int(text.replace("+", ""))
            if not -12 <= offset <= 14:
                raise ValueError
            s = storage.load_settings(chat_id)
            s.timezone_offset = offset
            storage.save_settings(s)
            await update.message.reply_text(
                f"✅ Часовой пояс установлен: UTC+{offset}",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Введи число от -12 до 14, например `3`", parse_mode='Markdown')
        return

    # ── Handle custom notification time ───────────────────────────────────
    if mode == "custom_time":
        try:
            minutes = int(text)
            if minutes < 0:
                raise ValueError
            s = storage.load_settings(chat_id)
            s.notify_custom_min = minutes
            storage.save_settings(s)
            msg = f"✅ Уведомление за *{minutes} минут* включено." if minutes > 0 else "✅ Своё время уведомления отключено."
            await update.message.reply_text(msg, parse_mode='Markdown')
        except ValueError:
            await update.message.reply_text("❌ Введи целое число минут, например `15`", parse_mode='Markdown')
        return

    # ── Handle predictions input ───────────────────────────────────────────
    s = storage.load_settings(chat_id)
    predictions = parse_predictions(text, s.timezone_offset)

    if not predictions:
        await update.message.reply_text(
            "❌ Не удалось распознать прогнозы.\n\n"
            "Проверь формат:\n"
            "`1. Soccer. Brazil. Liga. 14-00 Команда1 — Команда2 Ставка`",
            parse_mode='Markdown'
        )
        return

    storage.add_predictions_to_storage(chat_id, predictions)

    lines = [f"✅ *Добавлено {len(predictions)} прогнозов:*\n"]
    for i, pred in enumerate(predictions, 1):
        lines.append(format_prediction(pred, i))
        lines.append("")

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def list_predictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    predictions = storage.load_predictions(chat_id)

    if not predictions:
        await update.message.reply_text(
            "📋 Список прогнозов пуст.\n\nДобавь через /add"
        )
        return

    lines = ["📋 *Прогнозы на сегодня:*\n"]
    for i, pred in enumerate(predictions, 1):
        status = ""
        if pred.notified_5:
            status = " ✅"
        elif pred.notified_30:
            status = " 🔔"
        lines.append(format_prediction(pred, i) + status)
        lines.append(f"🆔 `{pred.id}`\n")

    lines.append("\nДля удаления: `/delete <id>`")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def delete_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "Укажи ID прогноза: `/delete abc12345`\n"
            "ID видны в /list",
            parse_mode='Markdown'
        )
        return

    pred_id = context.args[0]
    success = storage.delete_prediction_by_id(chat_id, pred_id)

    if success:
        await update.message.reply_text(f"🗑 Прогноз `{pred_id}` удалён.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Прогноз с ID `{pred_id}` не найден.", parse_mode='Markdown')


async def clear_predictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear"),
    ]]
    await update.message.reply_text(
        "⚠️ Очистить все прогнозы?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    s = storage.load_settings(chat_id)

    def toggle(val): return "✅" if val else "☐"

    keyboard = [
        [InlineKeyboardButton(f"{toggle(s.notify_30min)} За 30 минут", callback_data="toggle_30")],
        [InlineKeyboardButton(f"{toggle(s.notify_5min)} За 5 минут", callback_data="toggle_5")],
        [InlineKeyboardButton(
            f"⏱ Своё время: {s.notify_custom_min} мин" if s.notify_custom_min else "⏱ Добавить своё время",
            callback_data="set_custom"
        )],
        [InlineKeyboardButton(f"🌐 UTC+{s.timezone_offset}", callback_data="set_tz")],
    ]
    await update.message.reply_text(
        "⚙️ *Настройки уведомлений*\n\nВыбери что включить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    data = query.data
    await query.answer()

    if data == "confirm_clear":
        storage.clear_all_predictions(chat_id)
        await query.edit_message_text("🗑 Все прогнозы удалены.")

    elif data == "cancel_clear":
        await query.edit_message_text("Отмена.")

    elif data == "toggle_30":
        s = storage.load_settings(chat_id)
        s.notify_30min = not s.notify_30min
        storage.save_settings(s)
        await _update_settings_message(query, s)

    elif data == "toggle_5":
        s = storage.load_settings(chat_id)
        s.notify_5min = not s.notify_5min
        storage.save_settings(s)
        await _update_settings_message(query, s)

    elif data == "set_custom":
        WAITING_FOR_INPUT[chat_id] = "custom_time"
        await query.edit_message_text(
            "⏱ Введи своё время уведомления в минутах (например: `15`).\n"
            "Введи `0` чтобы отключить.",
            parse_mode='Markdown'
        )

    elif data == "set_tz":
        WAITING_FOR_INPUT[chat_id] = "timezone"
        await query.edit_message_text(
            "🌐 Введи смещение часового пояса (UTC+N).\n"
            "Примеры: `3` для Москвы, `5` для Екатеринбурга, `0` для UTC",
            parse_mode='Markdown'
        )


async def _update_settings_message(query, s):
    def toggle(val): return "✅" if val else "☐"
    keyboard = [
        [InlineKeyboardButton(f"{toggle(s.notify_30min)} За 30 минут", callback_data="toggle_30")],
        [InlineKeyboardButton(f"{toggle(s.notify_5min)} За 5 минут", callback_data="toggle_5")],
        [InlineKeyboardButton(
            f"⏱ Своё время: {s.notify_custom_min} мин" if s.notify_custom_min else "⏱ Добавить своё время",
            callback_data="set_custom"
        )],
        [InlineKeyboardButton(f"🌐 UTC+{s.timezone_offset}", callback_data="set_tz")],
    ]
    await query.edit_message_text(
        "⚙️ *Настройки уведомлений*\n\nВыбери что включить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
