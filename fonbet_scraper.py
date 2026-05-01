import logging
import aiohttp
from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)

# version=0 — всегда возвращает полный список событий
FONBET_API_URL = (
    "https://line-lb54-w.bk6bba-resources.com/ma/events/list"
    "?lang=ru&version=0&scopeMarket=1600"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

FUZZY_THRESHOLD = 72  # минимальный % совпадения названий команд


async def get_fonbet_events() -> list[dict]:
    """
    Возвращает все футбольные события с Фонбета (prematch + live).
    Каждый элемент: {id, team1, team2, tournament, is_live}
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                FONBET_API_URL,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Fonbet API вернул статус {resp.status}")
                    return []
                data = await resp.json(content_type=None)
    except Exception as e:
        logger.error(f"Ошибка запроса Fonbet API: {e}")
        return []

    # Строим словарь сегментов/турниров по id
    sports_map = {s["id"]: s.get("name", "") for s in data.get("sports", [])}

    results = []
    for event in data.get("events", []):
        # Пропускаем не-футбол (sportId=1 — футбол на Фонбете)
        if event.get("sportId") != 1:
            continue

        team1 = event.get("team1") or event.get("name1") or ""
        team2 = event.get("team2") or event.get("name2") or ""
        if not team1 or not team2:
            continue

        # Определяем live или prematch
        is_live = bool(event.get("live") or event.get("inLive"))

        # Название турнира
        segment_id = event.get("segmentId") or event.get("tournamentId")
        tournament = sports_map.get(segment_id, "")

        results.append({
            "id": event.get("id"),
            "team1": team1,
            "team2": team2,
            "tournament": tournament,
            "is_live": is_live,
        })

    logger.info(f"Fonbet: получено {len(results)} футбольных событий")
    return results


def find_match_on_fonbet(pred_text: str, fonbet_events: list[dict]) -> dict | None:
    """
    Ищет матч из прогноза среди событий Фонбета по нечёткому совпадению команд.
    pred_text — полная строка прогноза (team1 из Prediction).
    Возвращает найденное событие или None.
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
        p2 = pred_t2.lower()

        # Прямое совпадение
        score = (fuzz.partial_ratio(p1, live_t1) + fuzz.partial_ratio(p2, live_t2)) / 2
        # Обратное (команды могут быть переставлены)
        score_rev = (fuzz.partial_ratio(p1, live_t2) + fuzz.partial_ratio(p2, live_t1)) / 2

        best = max(score, score_rev)
        if best > best_score:
            best_score = best
            best_event = event

    if best_score >= FUZZY_THRESHOLD:
        logger.info(
            f"Найден матч [{best_score:.0f}%]: "
            f"'{pred_t1} vs {pred_t2}' → "
            f"'{best_event['team1']} vs {best_event['team2']}'"
            f" ({'LIVE' if best_event['is_live'] else 'Prematch'})"
        )
        return best_event

    return None


def _extract_teams(text: str) -> tuple[str, str]:
    """
    Вытаскивает две команды из строки прогноза.
    Ищет разделитель — или -.
    Пример: '11-00 Hurstville U20 — Central Coast Mariners U20 п2 4+'
    → ('Hurstville U20', 'Central Coast Mariners U20')
    """
    import re

    # Убираем время в начале (11-00, 2:30)
    text = re.sub(r'^\S*\d{1,2}[-:]\d{2}\S*\s*', '', text).strip()

    # Ищем разделитель команд: ' — ' или ' - '
    for sep in [' — ', '—', ' – ', ' vs ', ' - ']:
        if sep in text:
            parts = text.split(sep, 1)
            team1 = parts[0].strip()
            # Убираем ставку из второй части (последние слова типа "п2 4+")
            team2_raw = parts[1].strip()
            # Берём всё до последнего слова если оно похоже на ставку
            team2_words = team2_raw.split()
            # Ставка обычно короткая (1-3 символа) и/или содержит цифры
            while team2_words and re.match(r'^[\wфФпП]{1,4}[\d\+\-\.,]*$', team2_words[-1]):
                team2_words.pop()
            team2 = ' '.join(team2_words).strip() or team2_raw
            return team1, team2

    return text, ""
