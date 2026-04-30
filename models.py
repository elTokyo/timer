from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Prediction:
    league: str
    team1: str
    team2: str
    bet: str
    match_time: datetime
    raw_line: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    notified_30: bool = False
    notified_5: bool = False

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'league': self.league,
            'team1': self.team1,
            'team2': self.team2,
            'bet': self.bet,
            'match_time': self.match_time.isoformat(),
            'raw_line': self.raw_line,
            'notified_30': self.notified_30,
            'notified_5': self.notified_5,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Prediction':
        pred = cls(
            id=data['id'],
            league=data['league'],
            team1=data['team1'],
            team2=data['team2'],
            bet=data['bet'],
            match_time=datetime.fromisoformat(data['match_time']),
            raw_line=data['raw_line'],
        )
        pred.notified_30 = data.get('notified_30', False)
        pred.notified_5 = data.get('notified_5', False)
        return pred


@dataclass
class UserSettings:
    chat_id: int
    timezone_offset: int = 3          # UTC+3 default (Moscow)
    notify_30min: bool = True
    notify_5min: bool = True
    notify_custom_min: int = 0        # 0 = disabled
    waiting_for_predictions: bool = False

    def to_dict(self) -> dict:
        return {
            'chat_id': self.chat_id,
            'timezone_offset': self.timezone_offset,
            'notify_30min': self.notify_30min,
            'notify_5min': self.notify_5min,
            'notify_custom_min': self.notify_custom_min,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UserSettings':
        return cls(
            chat_id=data['chat_id'],
            timezone_offset=data.get('timezone_offset', 3),
            notify_30min=data.get('notify_30min', True),
            notify_5min=data.get('notify_5min', True),
            notify_custom_min=data.get('notify_custom_min', 0),
        )
