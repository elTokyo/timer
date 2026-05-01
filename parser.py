import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from models import Prediction


def parse_predictions(text: str, user_timezone_offset: int = 3) -> list[Prediction]:
    predictions = []
    # Normalize all newline variants (\r\n, \r, \n) and split on any of them
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    for line in normalized.split('\n'):
        line = line.strip()
        if not line:
            continue
        pred = parse_single_line(line, user_timezone_offset)
        if pred:
            predictions.append(pred)
    return predictions


def parse_single_line(line: str, tz_offset: int = 3) -> Optional[Prediction]:
    clean = re.sub(r'^\d+[\.\)]\s*', '', line).strip()

    # Extract first valid time token (only for scheduling)
    time_pattern = r'\b(\d{1,2})[-:](\d{2})\b'
    time_match = None
    hour = minute = 0
    for m in re.finditer(time_pattern, clean):
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            time_match = m
            hour, minute = h, mn
            break

    if not time_match:
        return None

    # Convert local time → UTC for storage
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
        team1=clean,        # полная строка без номера — без изменений
        team2='',
        bet='',
        match_time=match_time_utc,
        raw_line=line
    )


def _local_time_str(pred: Prediction, tz_offset: int) -> str:
    return (pred.match_time + timedelta(hours=tz_offset)).strftime("%H:%M")


def format_prediction_local(pred: Prediction, tz_offset: int, index: int = None) -> str:
    num = f"{index}. " if index else ""
    return f"{num}{pred.team1}"


def format_reminder(pred: Prediction, minutes_before: int, tz_offset: int = 0) -> str:
    emoji = "🔥" if minutes_before <= 5 else "⏰"
    return f"{emoji} Через {minutes_before} мин!\n\n{pred.team1}"
