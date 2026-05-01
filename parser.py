import re
from datetime import datetime, date, timezone, timedelta
from typing import Optional
from models import Prediction


def parse_predictions(text: str, user_timezone_offset: int = 3) -> list[Prediction]:
    """
    Parses predictions in format:
    1. Soccer. Brazil. Acreano U20. 2-00 Santa Cruz Acre U20 — Independencia FC U20 ф1-4,5.

    Supports:
    - Time formats: 2-00, 2:00, 14:30
    - Separator: — or -
    - Bet at end after team names
    """
    predictions = []
    lines = text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        pred = parse_single_line(line, user_timezone_offset)
        if pred:
            predictions.append(pred)

    return predictions


def parse_single_line(line: str, tz_offset: int = 3) -> Optional[Prediction]:
    """Parse a single prediction line"""

    # Remove leading number like "1." or "1)"
    line = re.sub(r'^\d+[\.\)]\s*', '', line)

    # Find time pattern: 2-00 or 14:30 or 2:00
    time_pattern = r'\b(\d{1,2})[-:](\d{2})\b'
    time_match = re.search(time_pattern, line)
    if not time_match:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2))

    if hour > 23 or minute > 59:
        return None

    # Everything before time = league info
    time_start = time_match.start()
    league_part = line[:time_start].strip().rstrip('.')
    league_parts = [p.strip() for p in league_part.split('.') if p.strip()]
    league = ' › '.join(league_parts) if league_parts else 'Unknown'

    # Everything after time = teams + bet
    after_time = line[time_match.end():].strip()

    bet = ''
    teams_part = after_time

    # Bet patterns at end of line
    bet_pattern = r'\s+((?:[фФ]|[ТтTt][БбМм]|[П][12Х]|[12Х]{1,2}|[xXхХ][\d]?)[\d\+\-\.,]*(?:\d+)?\.?)$'
    bet_match = re.search(bet_pattern, teams_part)

    if bet_match:
        bet = bet_match.group(1).strip().rstrip('.')
        teams_part = teams_part[:bet_match.start()].strip()
    else:
        words = teams_part.split()
        if words:
            last_word = words[-1].rstrip('.')
            if re.match(r'^[фФТтПXх12]{1,3}[\d\+\-\.,]*$', last_word):
                bet = last_word
                teams_part = ' '.join(words[:-1]).strip()

    # Split team names
    team1, team2 = '', ''
    for sep in [' — ', '—', ' – ', ' - ']:
        if sep in teams_part:
            parts = teams_part.split(sep, 1)
            team1 = parts[0].strip()
            team2 = parts[1].strip()
            break

    if not team1:
        team1 = teams_part
        team2 = 'TBD'

    # ── Convert user local time → UTC for storage ──────────────────────────
    # Server may run in UTC; user enters time in their local timezone.
    # We store everything as UTC so scheduler comparisons are correct.
    user_tz = timezone(timedelta(hours=tz_offset))
    utc_now = datetime.now(timezone.utc)
    local_now = utc_now.astimezone(user_tz)
    today = local_now.date()

    try:
        local_dt = datetime(today.year, today.month, today.day, hour, minute,
                            tzinfo=user_tz)
        # Store as naive UTC
        match_time_utc = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None

    return Prediction(
        league=league,
        team1=team1,
        team2=team2,
        bet=bet,
        match_time=match_time_utc,
        raw_line=line
    )


def format_prediction(pred: Prediction, index: int = None) -> str:
    """Format prediction for display — show time in UTC (server time)"""
    num = f"{index}. " if index else ""
    time_str = pred.match_time.strftime("%H:%M")
    bet_str = f"  📊 *{pred.bet}*" if pred.bet else ""
    return (
        f"{num}🏟 *{pred.team1} vs {pred.team2}*\n"
        f"🏆 {pred.league}\n"
        f"⏰ {time_str} UTC{bet_str}"
    )


def format_prediction_local(pred: Prediction, tz_offset: int, index: int = None) -> str:
    """Format prediction showing time in user's local timezone"""
    num = f"{index}. " if index else ""
    local_time = pred.match_time + timedelta(hours=tz_offset)
    time_str = local_time.strftime("%H:%M")
    bet_str = f"  📊 *{pred.bet}*" if pred.bet else ""
    return (
        f"{num}🏟 *{pred.team1} vs {pred.team2}*\n"
        f"🏆 {pred.league}\n"
        f"⏰ {time_str}{bet_str}"
    )


def format_reminder(pred: Prediction, minutes_before: int, tz_offset: int = 0) -> str:
    """Format reminder notification showing local time"""
    local_time = pred.match_time + timedelta(hours=tz_offset)
    time_str = local_time.strftime("%H:%M")
    bet_str = f"\n📊 Ставка: *{pred.bet}*" if pred.bet else ""
    emoji = "🔥" if minutes_before <= 5 else "⏰"
    return (
        f"{emoji} *Через {minutes_before} минут!*\n\n"
        f"🏟 *{pred.team1}* vs *{pred.team2}*\n"
        f"🏆 {pred.league}\n"
        f"🕐 Старт: {time_str}"
        f"{bet_str}"
    )
