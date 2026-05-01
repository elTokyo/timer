import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from models import Prediction


def parse_predictions(text: str, user_timezone_offset: int = 3) -> list[Prediction]:
    predictions = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        pred = parse_single_line(line, user_timezone_offset)
        if pred:
            predictions.append(pred)
    return predictions


def parse_single_line(line: str, tz_offset: int = 3) -> Optional[Prediction]:
    # Strip leading "1." / "1)" numbering
    clean = re.sub(r'^\d+[\.\)]\s*', '', line).strip()

    # Find the FIRST valid time token: 11-00, 2:30, 14-45
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

    # Everything before time → label (league/sport info)
    before = clean[:time_match.start()].strip().rstrip('., ')
    # Everything after time → raw content (teams + bet), taken as-is
    after = clean[time_match.end():].strip()

    # Convert local time → UTC for storage
    user_tz = timezone(timedelta(hours=tz_offset))
    local_now = datetime.now(timezone.utc).astimezone(user_tz)
    today = local_now.date()

    try:
        local_dt = datetime(today.year, today.month, today.day, hour, minute,
                            tzinfo=user_tz)
        match_time_utc = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None

    return Prediction(
        league=before,   # everything before the time
        team1=after,     # everything after the time (teams + bet), raw
        team2='',
        bet='',
        match_time=match_time_utc,
        raw_line=line
    )


def _local_time_str(pred: Prediction, tz_offset: int) -> str:
    local_time = pred.match_time + timedelta(hours=tz_offset)
    return local_time.strftime("%H:%M")


def format_prediction_local(pred: Prediction, tz_offset: int, index: int = None) -> str:
    num = f"{index}. " if index else ""
    t = _local_time_str(pred, tz_offset)
    label = (pred.league + " ") if pred.league else ""
    content = pred.team1 if pred.team1 else ""
    return f"{num}⏰ {t} — {label}{content}"


def format_reminder(pred: Prediction, minutes_before: int, tz_offset: int = 0) -> str:
    t = _local_time_str(pred, tz_offset)
    emoji = "🔥" if minutes_before <= 5 else "⏰"
    label = (pred.league + "\n") if pred.league else ""
    content = pred.team1 if pred.team1 else ""
    return (
        f"{emoji} Через {minutes_before} мин!\n\n"
        f"🕐 {t}  {label}"
        f"{content}"
    )
