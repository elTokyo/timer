import logging
import aiohttp
from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)

# Рабочий URL — lang=en чтобы названия команд были на латинице (лучше для матчинга)
FONBET_API_URL = (
    "https://line-lb61-w.bk6bba-resources.com/ma/events/listBase"
    "?lang=en&scopeMarket=1600"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

FUZZY_THRESHOLD = 70


async def get_fonbet_events() -> list[dict]:
    """
    Запрашивает Fonbet и возвращает все футбольные события (prematch + live).
    Формат каждого элемента: {id, team1, team2, tournament, is_live}
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                FONBET_API_URL,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Fonbet API статус: {resp.status}")
                    return []
                data = await resp.json(content_type=None)
    except Exception as e:
        logger.error(f"Fonbet API ошибка: {e}")
        return []

    # Строим карту турниров: segmentId → название
    sports_map = {}
    for s in data.get("sports", []):
        sports_map[s["id"]] = s.get("name", "")

    results = []
    for event in data.get("events", []):
        # Только футбол: sportId=1
        if event.get("sportId") != 1:
            continue

        team1 = event.get("team1") or event.get("name1") or ""
        team2 = event.get("team2") or event.get("name2") or ""
        if not team1 or not team2:
            continue

        is_live = bool(event.get("live") or event.get("inLive"))

        segment_id = event.get("segmentId") or event.get("tournamentId")
        tournament = sports_map.get(segment_id, "")

        results.append({
            "id": event.get("id"),
            "team1": team1,
            "team2": team2,
            "tournament": tournament,
            "is_live": is_live,
        })

    logger.info(f"Fonbet: {len(results)} футбольных событий получено")
    return results


def find_match_on_fonbet(pred_text: str, fonbet_events: list[dict]) -> dict | None:
    """
    Ищет матч из прогноза среди событий Фонбета.
    Использует нечёткое сравнение названий команд.
    """
    pred_t1, pred_t2 = _extract_teams(pred_text)
    if not pred_t1:
        return None

    best_score = 0
    best_event = None

    for event in fonbet_events:
        live_t1 = event["team1"].lower()
        live_t2 = event["team2"].lower()
        p1 = pred_t1.lower()
        p2 = pred_t2.lower() if pred_t2 else ""

        # Прямое совпадение
        if p2:
            score = (fuzz.partial_ratio(p1, live_t1) + fuzz.partial_ratio(p2, live_t2)) / 2
            score_rev = (fuzz.partial_ratio(p1, live_t2) + fuzz.partial_ratio(p2, live_t1)) / 2
            score = max(score, score_rev)
        else:
            score = fuzz.partial_ratio(p1, live_t1)

        if score > best_score:
            best_score = score
            best_event = event

    if best_score >= FUZZY_THRESHOLD:
        logger.info(
            f"Матч найден [{best_score:.0f}%]: "
            f"'{pred_t1} vs {pred_t2}' → "
            f"'{best_event['team1']} vs {best_event['team2']}'"
            f" ({'LIVE' if best_event['is_live'] else 'Prematch'})"
        )
        return best_event

    logger.debug(f"Матч не найден [{best_score:.0f}%]: '{pred_t1} vs {pred_t2}'")
    return None


def _extract_teams(text: str) -> tuple[str, str]:
    """
    Извлекает названия команд из строки прогноза.
    Пример: 'Soccer. Australia. 11-00 Hurstville U20 — Central Coast Mariners U20 п2 4+'
    → ('Hurstville U20', 'Central Coast Mariners U20')
    """
    import re

    # Убираем префикс до времени включительно: 'Soccer. Australia. 11-00 '
    text = re.sub(r'^.*?\d{1,2}[-:]\d{2}\s*', '', text).strip()

    # Ищем разделитель команд
    for sep in [' — ', '—', ' – ', ' vs ', ' - ']:
        if sep in text:
            parts = text.split(sep, 1)
            team1 = parts[0].strip()
            team2_raw = parts[1].strip()

            # Убираем ставку с конца второй команды
            # Ставка: короткое слово с буквами/цифрами типа "п2", "4+", "ТБ2.5"
            team2_words = team2_raw.split()
            while team2_words and re.match(
                r'^[а-яёa-zА-ЯЁA-ZфФпП]{0,3}[\d\+\-\.,]+$',
                team2_words[-1], re.IGNORECASE
            ):
                team2_words.pop()
            team2 = ' '.join(team2_words).strip() or team2_raw

            return team1, team2

    # Нет разделителя — возвращаем весь текст как первую команду
    return text, ""
