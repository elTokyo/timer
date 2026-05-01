import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from models import Prediction


def parse_predictions(text: str, user_timezone_offset: int = 3) -> list[Prediction]:
    """
    Прогноз в Discord приходит блоками из нескольких строк, разделённых пустой строкой:

        Soccer. Brazil. Acreano U20. 2-00
        Santa Cruz Acre U20 — Independencia FC U20
        ф1-4,5...

    Разбиваем текст на блоки по пустым строкам, каждый блок = один прогноз.
    """
    predictions = []

    # Нормализуем переносы строк
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')

    # Разбиваем на блоки по пустым строкам
    blocks = re.split(r'\n\s*\n', normalized.strip())

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        pred = parse_block(block, user_timezone_offset)
        if pred:
            predictions.append(pred)

    return predictions


def parse_block(block: str, tz_offset: int = 3) -> Optional[Prediction]:
    """
    Склеиваем все строки блока в одну, вытаскиваем время, остальное — as-is.
    """
    # Убираем нумерацию типа "1." в начале блока
    block = re.sub(r'^\d+[\.\)]\s*', '', block.strip())

    # Склеиваем строки блока в одну через пробел
    single_line = ' '.join(
        line.strip() for line in block.split('\n') if line.strip()
    )

    # Ищем первое валидное время: 2-00, 11:00, 14-30
    time_pattern = r'\b(\d{1,2})[-:](\d{2})\b'
    hour = minute = None
    for m in re.finditer(time_pattern, single_line):
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            hour, minute = h, mn
            break

    if hour is None:
        return None

    # Конвертируем локальное время → UTC
    user_tz = timezone(timedelta(hours=tz_offset))
    local_now = datetime.now(timezone.utc).astimezone(user_tz)
    today = local_now.date()

    try:
        local_dt = datetime(today.year, today.month, today.day, hour, minute, tzinfo=user_tz)
        match_time_utc = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None

    return Prediction(
        league='',
        team1=single_line,   # весь текст as-is, склеенный в одну строку
        team2='',
        bet='',
        match_time=match_time_utc,
        raw_line=block
    )


def _local_time_str(pred: Prediction, tz_offset: int) -> str:
    return (pred.match_time + timedelta(hours=tz_offset)).strftime("%H:%M")


def format_prediction_local(pred: Prediction, tz_offset: int, index: int = None) -> str:
    num = f"{index}. " if index else ""
    return f"{num}{pred.team1}"


def format_reminder(pred: Prediction, minutes_before: int, tz_offset: int = 0) -> str:
    emoji = "🔥" if minutes_before <= 5 else "⏰"
    return f"{emoji} Через {minutes_before} мин!\n\n{pred.team1}"
