import json
import os
from typing import Optional
from models import Prediction, UserSettings

DATA_DIR = os.getenv("DATA_DIR", "./data")
PREDICTIONS_FILE = os.path.join(DATA_DIR, "predictions.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

os.makedirs(DATA_DIR, exist_ok=True)


# ─── Predictions ────────────────────────────────────────────────────────────

def load_predictions(chat_id: int) -> list[Prediction]:
    try:
        with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        user_data = data.get(str(chat_id), [])
        return [Prediction.from_dict(p) for p in user_data]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_predictions(chat_id: int, predictions: list[Prediction]):
    try:
        with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data[str(chat_id)] = [p.to_dict() for p in predictions]

    with open(PREDICTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_predictions_to_storage(chat_id: int, new_predictions: list[Prediction]):
    existing = load_predictions(chat_id)
    existing.extend(new_predictions)
    # Sort by match time
    existing.sort(key=lambda p: p.match_time)
    save_predictions(chat_id, existing)


def update_prediction(chat_id: int, pred_id: str, **kwargs):
    predictions = load_predictions(chat_id)
    for pred in predictions:
        if pred.id == pred_id:
            for key, value in kwargs.items():
                setattr(pred, key, value)
    save_predictions(chat_id, predictions)


def delete_prediction_by_id(chat_id: int, pred_id: str) -> bool:
    predictions = load_predictions(chat_id)
    new_predictions = [p for p in predictions if p.id != pred_id]
    if len(new_predictions) < len(predictions):
        save_predictions(chat_id, new_predictions)
        return True
    return False


def clear_all_predictions(chat_id: int):
    save_predictions(chat_id, [])


def get_all_chat_ids() -> list[int]:
    try:
        with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [int(k) for k in data.keys()]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# ─── Settings ───────────────────────────────────────────────────────────────

def load_settings(chat_id: int) -> UserSettings:
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        user_data = data.get(str(chat_id))
        if user_data:
            return UserSettings.from_dict(user_data)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return UserSettings(chat_id=chat_id)


def save_settings(settings: UserSettings):
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data[str(settings.chat_id)] = settings.to_dict()

    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
