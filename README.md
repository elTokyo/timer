# ⚽ Betting Reminder Bot

Telegram-бот для напоминаний о матчах по прогнозам из Discord.

## Быстрый старт

### 1. Получи токен бота
- Напиши [@BotFather](https://t.me/BotFather) в Telegram
- Создай нового бота: `/newbot`
- Скопируй токен

### 2. Деплой на Railway (бесплатно, 5 минут)

1. Зайди на [railway.app](https://railway.app) → войди через GitHub
2. New Project → Deploy from GitHub repo
3. Загрузи все файлы в репозиторий GitHub
4. В Railway: Variables → добавь переменную:
   ```
   BOT_TOKEN = твой_токен_от_BotFather
   ```
5. Деплой запустится автоматически

### 3. Локальный запуск (для теста)

```bash
# Установи зависимости
pip install -r requirements.txt

# Запусти
BOT_TOKEN=твой_токен python bot.py
```

---

## Формат прогнозов

Вставляй прогнозы в таком формате (как в твоём Discord):

```
1. Soccer. Brazil. Acreano U20. 2-00 Santa Cruz Acre U20 — Independencia FC U20 ф1-4,5.
2. Soccer. Australia. NPL Victoria. 9-00 Altona Magic — Heidelberg United ТБ2.5
3. Soccer. Kazakhstan. Premier League. 14-30 Kairat — Astana П2
```

**Поддерживаемые форматы времени:** `2-00`, `14:30`, `9-00`

**Поддерживаемые типы ставок:** ф1, ф2, ТБ, ТМ, П1, П2, 1X, X2, 12 и др.

---

## Команды бота

| Команда | Действие |
|---------|----------|
| `/add` | Добавить прогнозы (вставить список) |
| `/list` | Показать все прогнозы на сегодня |
| `/delete <id>` | Удалить конкретный прогноз по ID |
| `/clear` | Очистить все прогнозы |
| `/settings` | Настройки уведомлений |

---

## Настройки уведомлений

В `/settings` можно включить/выключить:
- ✅ Уведомление за **30 минут** до матча
- ✅ Уведомление за **5 минут** до матча  
- ⏱ Своё произвольное время (например за 15 минут)
- 🌐 Часовой пояс (UTC+N)

---

## Структура файлов

```
bet_bot/
├── bot.py          # Точка входа
├── handlers.py     # Обработчики команд
├── parser.py       # Парсинг прогнозов
├── scheduler.py    # Планировщик уведомлений
├── storage.py      # Хранение данных (JSON)
├── models.py       # Модели данных
├── requirements.txt
├── Dockerfile
└── data/           # Создаётся автоматически
    ├── predictions.json
    └── settings.json
```
