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
    # Must look like a time: hour 0-23, minute 0-59
    time_pattern = r'\b(\d{1,2})[-:](\d{2})\b'
    for m in re.finditer(time_pattern, clean):
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            time_match = m
            hour, minute = h, mn
            break
    else:
        return None  # no valid time found

    # Everything before time → label (league/sport info)
    before = clean[:time_match.start()].strip().rstrip('.,')
    # Everything after time → raw content (teams + bet)
    after = clean[time_match.end():].strip()

    # Build full display text: just concat label + after, keep it natural
    # We store them separately so format functions can use them
    label = before if before else ''
    content = after if after else ''

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
        league=label,       # repurposed: everything before the time
        team1=content,      # repurposed: everything after the time (teams + bet)
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
    # Reconstruct the original-style line: label + time + content
    parts = []
    if pred.league:
        parts.append(pred.league)
    parts.append(t)
    if pred.team1:
        parts.append(pred.team1)
    full_text = ' '.join(parts)
    return f"{num}⏰ `{t}` — {pred.league + ' ' if pred.league else ''}{pred.team1}"


def format_reminder(pred: Prediction, minutes_before: int, tz_offset: int = 0) -> str:
    t = _local_time_str(pred, tz_offset)
    emoji = "🔥" if minutes_before <= 5 else "⏰"
    label = f"{pred.league} " if pred.league else ""
    return (
        f"{emoji} *Через {minutes_before} мин!*\n\n"
        f"🕐 *{t}*  {label}\n"
        f"{pred.team1}"
    )
