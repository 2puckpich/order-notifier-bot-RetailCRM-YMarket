# 📦 Order Notifier Bot

Telegram-бот для мгновенных уведомлений о новых заказах из **Яндекс Маркета** и **RetailCRM**.

> 🇷🇺 Русский | [English version below](#english-version)

---

## 🚀 Возможности

- 🔴 **Мгновенные уведомления** в Telegram при каждом новом заказе
- 🏪 **Несколько магазинов** — поддержка 2+ магазинов Яндекс Маркета
- 📊 **Детальная информация** — товары, сумма, покупатель, адрес, телефон
- 🔄 **Без дублей** — умное отслеживание отправленных уведомлений
- ☁️ **24/7 на Render.com** — бесплатный хостинг (инструкция ниже)
- 🐍 **Простой Python** — легко модифицировать под свои нужды

---

## 🔒 Безопасная версия (Secure)

Если вы не хотите хранить API-ключи магазинов на чужих серверах — используйте **`bot_secure.py`**:

- ✅ **API-ключи вводятся через Telegram** (`/setup`)
- ✅ **Хранятся только в RAM** — при перезапуске исчезают
- ✅ **Доступ только по username** — жёсткая авторизация
- ✅ **Никаких файлов с секретами** на диске

```bash
python bot_secure.py
# В Telegram: /setup → ввести ключи → /run
```

Подробнее: [`SECURITY.md`](./SECURITY.md) | [`config_secure.py`](./config_secure.py)

---

## 📋 Структура проекта

```
order-notifier-bot/
├── bot.py              # Главный файл — запуск бота
├── config.py           # Загрузка конфигурации из .env
├── yandex_market.py    # Клиент API Яндекс Маркета
├── retailcrm.py        # Клиент API RetailCRM v5
├── requirements.txt    # Зависимости Python
├── .env                # Переменные окружения (не пушить!)
├── .env.example        # Шаблон .env
├── .gitignore          # Что не пушить в git
├── README.md           # Этот файл
└── sent_orders.json    # База отправленных заказов (создаётся автоматически)
```

---

## ⚡ Быстрый старт (локально)

### 1. Клонирование

```bash
git clone https://github.com/USERNAME/order-notifier-bot.git
cd order-notifier-bot
```

### 2. Установка зависимостей

```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Получение API-ключей

#### Telegram
1. Напишите `@BotFather` → `/newbot`
2. Придумайте имя и username для бота
3. **Скопируйте токен** — это `TG_BOT_TOKEN`

#### Свой Chat ID
1. Напишите `@userinfobot` — он покажет ваш ID
2. Зайдите в своего бота, нажмите `/start`

#### Яндекс Маркет
1. [Личный кабинет продавца](https://partner.market.yandex.ru/) → Настройки → API и модули
2. Вкладка **"Отправка запросов Маркету"**
3. **Авторизационный токен** → `YM_API_KEY`
4. **Идентификатор кампании** → `YM_CAMPAIGN_IDS` (через запятую для нескольких)

#### RetailCRM
1. Ваша CRM → Настройки → Интеграция → Ключи доступа к API
2. Создайте ключ с правами `orders_read`

### 4. Конфигурация

```bash
cp .env.example .env
# Отредактируйте .env, вставьте свои ключи
```

### 5. Запуск

```bash
python bot.py
```

Вы получите сообщение в Telegram: **"✅ Бот запущен"**

---

## ☁️ Запуск на Render.com (24/7, бесплатно)

[Полный пошаговый гайд → RENDER_GUIDE.md](./RENDER_GUIDE.md)

Кратко:
1. Залейте код на **GitHub**
2. Создайте аккаунт на [render.com](https://render.com)
3. New Web Service → Connect GitHub repo
4. Укажите Start Command: `python bot.py`
5. Добавьте Environment Variables из `.env`
6. Deploy

---

## 🔧 Переменные окружения

| Переменная | Описание | Пример |
|---|---|---|
| `TG_BOT_TOKEN` | Токен бота от @BotFather | `123456:ABC...` |
| `TG_CHAT_ID` | Ваш Telegram ID | `123456789` |
| `YM_API_KEY` | API-ключ Яндекс Маркета | `AQVNxxxx...` |
| `YM_CAMPAIGN_IDS` | ID кампаний через запятую | `12345678,87654321` |
| `YM_CHECK_INTERVAL` | Период проверки YM (сек) | `60` |
| `RCRM_URL` | URL вашей RetailCRM | `https://your-shop.retailcrm.ru` |
| `RCRM_API_KEY` | API-ключ RetailCRM | `abc123...` |
| `RCRM_CHECK_INTERVAL` | Период проверки CRM (сек) | `60` |

---

## 📱 Пример уведомления

### Яндекс Маркет
```
📦 НОВЫЙ ЗАКАЗ Яндекс Маркет
🏪 Магазин: Яндекс Маркет (кампания 12345678)
━━━━━━━━━━━━━━━
🆔 Номер: 123456789
📊 Статус: PROCESSING
💰 Сумма: 4580 ₽
📅 Дата доставки: 2024-01-15
━━━━━━━━━━━━━━━
👤 Покупатель: Иван Петров
📞 Телефон: +79001234567
📍 Адрес: Москва, Ленина, 10, 25
━━━━━━━━━━━━━━━
🛍 Товары:
  • Крем для тела x2 — 2290 ₽
```

### RetailCRM
```
🛒 НОВЫЙ ЗАКАЗ RetailCRM
━━━━━━━━━━━━━━━
🆔 Номер: A-1234
📊 Статус: new
💰 Сумма: 3200 ₽
🕐 Создан: 2024-01-15 14:30:00
━━━━━━━━━━━━━━━
👤 Покупатель: Анна Смирнова
📞 Телефон: +79109876543
📧 Email: anna@mail.ru
━━━━━━━━━━━━━━━
🚚 Доставка: СДЭК
📍 Адрес: г Москва, ул Пушкина, д 5
💵 Стоимость доставки: 350 ₽
━━━━━━━━━━━━━━━
🛍 Товары:
  • Платье Summer x1 — 3200 ₽
```

---

## 🛡 Безопасность

- Файл `.env` с токенами **не попадает в Git** (добавлен в `.gitignore`)
- `sent_orders.json` хранится локально и тоже игнорируется Git
- При компрометации токена — сразу перевыпустите в соответствующем сервисе

---

## 🐛 Отладка

```bash
# Уровень логирования DEBUG
export LOG_LEVEL=DEBUG  # Linux/Mac
set LOG_LEVEL=DEBUG     # Windows
python bot.py
```

---

## 📄 Лицензия

MIT — свободное использование.

---

## English Version

A Telegram bot for instant notifications about new orders from **Yandex Market** and **RetailCRM**.

### Features
- Instant Telegram notifications for each new order
- Multiple Yandex Market store support
- Detailed info: items, total, buyer, address, phone
- Smart deduplication
- Free 24/7 hosting on Render.com

### Quick Start
```bash
git clone https://github.com/USERNAME/order-notifier-bot.git
cd order-notifier-bot
cp .env.example .env
# Edit .env with your API keys
pip install -r requirements.txt
python bot.py
```

See [RENDER_GUIDE.md](./RENDER_GUIDE.md) for Render.com deployment guide.
