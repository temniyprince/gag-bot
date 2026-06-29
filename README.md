# 🌱 Grow a Garden — Telegram-бот раздачи (Roblox)

Telegram-бот для раздачи доступа к приватным серверам Roblox (игра **Grow a Garden**).
Пользователь получает бесплатную попытку, крутит «рулетку» (25% шанс выигрыша),
при проигрыше может подписаться на канал за дополнительную попытку.

**Стек:** Python 3.12 · aiogram 3.x · SQLite (aiosqlite) · python-dotenv

---

## ✨ Возможности

### Для пользователя
- `/start` — старт и автоматическая выдача **одной бесплатной попытки** новым пользователям.
- Кнопка «🎁 Использовать попытку» — случайный исход:
  - 🎉 **Выигрыш (25%)** — бот присылает ссылку на приватный сервер Roblox.
  - 😔 **Проигрыш (75%)** — предложение подписаться на канал за +1 попытку.
- Кнопка «✅ Проверить подписку» — **настоящая** проверка через `getChatMember`:
  - не подписан → «❌ Вы ещё не подписались»;
  - подписан и бонус не выдавался → **+1 попытка** (один раз);
  - подписан, но бонус уже получен → «Вы уже получили бонусную попытку».
- После использования всех попыток → «У вас закончились попытки».

### Для администратора (`/admin`)
- 📊 **Статистика** — количество пользователей и победителей, число ссылок на сервер.
- 🔗 **Изменить ссылку** — смена ссылок на сервер **без изменения кода**
  (поддерживается несколько ссылок через запятую — победителю выдаётся случайная).
- 📣 **Рассылка** — отправка сообщения всем пользователям с отчётом о доставке.

---

## 📁 Структура проекта

```
gag-bot/
├── main.py              # точка входа: запуск polling, error-handling, переподключение
├── config.py            # загрузка и валидация настроек из .env
├── database.py          # асинхронный слой данных (SQLite/aiosqlite)
├── requirements.txt     # зависимости
├── .env.example         # пример переменных окружения
├── .gitignore
├── README.md
├── handlers/            # обработчики aiogram (роутеры)
│   ├── __init__.py      # register_all_routers()
│   ├── user.py          # /start, игра, проверка подписки
│   └── admin.py         # админ-панель
├── keyboards/           # inline-клавиатуры
│   ├── user.py
│   └── admin.py
├── services/            # бизнес-логика (не привязана к Telegram)
│   ├── game.py          # расчёт выигрыша, выбор случайной ссылки
│   ├── subscription.py  # проверка подписки через Telegram API
│   └── settings.py      # ссылки на сервер (БД + откат к .env)
├── middlewares/         # инъекция db/config в хендлеры
│   └── services.py
├── filters/             # кастомные фильтры (IsAdmin)
│   └── filters.py
├── states/              # FSM-состояния админ-панели
│   └── admin.py
└── utils/               # утилиты
    ├── callbacks.py     # типизированные CallbackData
    ├── messages.py      # шаблоны текстов
    └── helpers.py       # безопасная отправка, рассылка
```

---

## 🚀 Запуск локально

### 1. Клонирование
```bash
git clone https://github.com/<твой-юзер>/gag-bot.git
cd gag-bot
```

### 2. Виртуальное окружение
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# или на Windows:
# venv\Scripts\activate
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка `.env`
```bash
cp .env.example .env
```
Открой `.env` и заполни переменные (см. раздел [Переменные окружения](#-переменные-окружения)).

> **Где взять значения:**
> - `BOT_TOKEN` — у [@BotFather](https://t.me/BotFather) (команда `/newbot`).
> - `ADMIN_ID` — свой Telegram ID узнаётся у [@userinfobot](https://t.me/userinfobot).
> - `CHANNEL_ID` — `@username` публичного канала или числовой ID приватного.
> - `SERVER_LINK` — ссылка(и) на приватный сервер Roblox (можно несколько через запятую).

### 5. Подготовка канала
Бот должен быть **администратором канала** с правом читать список участников —
иначе `getChatMember` не сможет проверить подписку.

### 6. Запуск
```bash
python main.py
```
При первом запуске автоматически создадутся папка `data/` и база `data/bot.db`.

---

## 🔧 Переменные окружения

| Переменная       | Обяз. | Описание                                                                 |
|------------------|:-----:|--------------------------------------------------------------------------|
| `BOT_TOKEN`      |  ✅   | Токен бота от @BotFather.                                               |
| `ADMIN_ID`       |  ✅   | ID администратора(ов). Несколько — через запятую: `111,222,333`.        |
| `CHANNEL_ID`     |  ✅   | Канал подписки: `@username` или числовой ID (`-1001234567890`).         |
| `SERVER_LINK`    |  ✅   | Ссылка(и) на сервер. Несколько — через запятую (выдаётся случайная).    |
| `CHANNEL_LINK`   |  ➖   | Публичная ссылка на канал для кнопки «Подписаться».                     |
| `WIN_CHANCE`     |  ➖   | Шанс выигрыша, `0..1`. По умолчанию `0.25` (25%).                       |
| `FREE_ATTEMPTS`  |  ➖   | Бесплатных попыток новому пользователю. По умолчанию `1`.               |

Пример `.env`:
```dotenv
BOT_TOKEN=7123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_ID=123456789
CHANNEL_ID=@my_garden_channel
SERVER_LINK=https://www.roblox.com/share?code=abc123, https://www.roblox.com/share?code=def456
CHANNEL_LINK=https://t.me/my_garden_channel
WIN_CHANCE=0.25
FREE_ATTEMPTS=1
```

---

## ☁️ Деплой

### Вариант A. Деплой через GitHub + Render

**Render** (https://render.com) — бесплатный Web Service с поддержкой фоновых процессов.

1. **Залей код на GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Grow a Garden bot"
   git branch -M main
   git remote add origin https://github.com/<твой-юзер>/gag-bot.git
   git push -u origin main
   ```
   > `.env` и `data/` не попадут в репозиторий (они в `.gitignore`).

2. **Создай Web Service на Render:**
   - New → **Web Service** → подключи GitHub-репозиторий.
   - Settings:
     - **Environment:** `Python 3`.
     - **Build Command:** `pip install -r requirements.txt`.
     - **Start Command:** `python main.py`.
     - **Instance Type:** Free.

3. **Переменные окружения** (вкладка Environment на Render):
   добавь все переменные из `.env` (`BOT_TOKEN`, `ADMIN_ID`, `CHANNEL_ID`,
   `SERVER_LINK` и т.д.).

4. **Важно про SQLite на Render:** бесплатные сервисы используют эфемерную
   файловую систему — база обнуляется при каждом перезапуске/deploy.
   Для продакшена лучше подключить бесплатный PostgreSQL-адаптер
   (потребуется заменить `database.py` на `asyncpg`), либо использовать
   Render Disk (платный). Для тестирования/небольшой нагрузки SQLite подойдёт.

5. **Deploy** → Render сам поднимет сервис и будет держать его запущенным.

### Вариант B. Деплой на Koyeb

**Koyeb** (https://www.koyeb.com) — бесплатныйtier с Docker/процесс-сервисами.

1. Залей код на GitHub (как в варианте A, шаг 1).
2. На Koyeb: **Create Service** → **GitHub** → выбери репозиторий.
3. **Build settings:**
   - Builder: `Buildpack`.
   - Build command: `pip install -r requirements.txt`.
   - Run command: `python main.py`.
4. **Environment variables:** добавь переменные из `.env`.
5. **Deploy.**

> ⚠️ Те же ограничения по эфемерному диску, что и на Render (см. шаг 4 выше).

### Вариант C. Любой VPS (Linux)

```bash
git clone https://github.com/<твой-юзер>/gag-bot.git
cd gag-bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env   # заполни

# через systemd (рекомендуется для постоянной работы):
# создай /etc/systemd/system/gag-bot.service:
```
```ini
[Unit]
Description=Grow a Garden Telegram Bot
After=network.target

[Service]
Type=simple
User=<твой-пользователь>
WorkingDirectory=/home/<user>/gag-bot
ExecStart=/home/<user>/gag-bot/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gag-bot
sudo journalctl -u gag-bot -f   # смотреть логи
```
На VPS SQLite сохраняется между перезапусками — это лучший вариант для постоянной работы.

---

## 🔒 Безопасность

- Все секреты — **только** в `.env` (в `.gitignore`, в репозиторий не попадает).
- В коде нет хардкода токенов и абсолютных путей.
- Перед коммитом проверь, что `.env` не отслеживается: `git status` не должен показывать `.env`.

---

## 🛠️ Технические особенности

- **Авто-переподключение:** `Dispatcher.start_polling()` использует встроенный
  backoff при временных ошибках Telegram API (сеть, 5xx, flood).
- **Устойчивость к ошибкам:** глобальный error-handler логирует исключения в
  хендлерах и не даёт боту упасть; при `TelegramRetryAfter` бот ждёт указанное время.
- **FSM** — для пошагового ввода в админ-панели (смена ссылки, рассылка).
- **Типизированные `CallbackData`** — защита от опечаток в `callback_data`.
- **Логирование** в консоль с временными метками.
- **Авто-создание** директорий и таблиц БД при первом запуске.

---

## ❓ Частые вопросы

**Бот пишет «❌ Вы ещё не подписались», хотя я подписан.**
Проверь, что бот — **администратор канала** с правом чтения участников, и что
`CHANNEL_ID` указан верно (`@username` для публичного, числовой ID для приватного).

**Хочу несколько серверов.**
Укажи ссылки в `SERVER_LINK` через запятую — победителю выдаётся случайная.
Менять можно и через админку (`/admin` → «Изменить ссылку»).

**Победителю не приходит ссылка.**
Скорее всего, список ссылок пуст. Задай их в `.env` (`SERVER_LINK`) или через
админ-панель — тогда выпадение выигрыша будет показывать ссылку.
