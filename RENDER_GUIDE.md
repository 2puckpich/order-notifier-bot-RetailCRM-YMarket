# ☁️ Гайд: Запуск бота на Render.com (24/7, бесплатно)

> Этот гайд проведёт тебя от кода на GitHub до работающего бота шаг за шагом.

---

## Что такое Render.com?

**Render** — это облачный хостинг, который позволяет запускать код бесплатно 24/7. Он сам:
- Устанавливает зависимости
- Запускает бот
- Перезапускает при падениях
- Показывает логи в реальном времени

---

## Шаг 1: Загрузить код на GitHub

### 1.1 Создать репозиторий на GitHub

1. Зайди на [github.com](https://github.com) и войди в аккаунт (или зарегистрируйся)
2. Нажми зелёную кнопку **"New"** (или "+" → "New repository")
3. Заполни:
   - **Repository name:** `order-notifier-bot`
   - **Description:** `Telegram bot for Yandex Market & RetailCRM order notifications`
   - **Visibility:** `Public` (или Private — тоже работает)
   - **☑ Initialize this repository with a README** — сними галочку
   - **☑ Add .gitignore** — сними галочку
   - **☑ Choose a license** — сними галочку
4. Нажми **"Create repository"**

Ты увидишь страницу с инструкцией. Скопируй URL репозитория, например:
```
https://github.com/ТВОЙ_НИК/order-notifier-bot.git
```

### 1.2 Загрузить файлы через терминал (Git)

Открой терминал (Windows: `cmd` или PowerShell, Mac: Terminal, Linux: Terminal) и выполни:

```bash
# Перейди в папку проекта
cd путь/до/order-notifier-bot

# Инициализировать Git (если ещё не инициализирован)
git init

# Добавить все файлы
git add .

# Сделать первый коммит
git commit -m "Initial commit: order notifier bot"

# Подключить удалённый репозиторий (вставь СВОЙ URL)
git remote add origin https://github.com/ТВОЙ_НИК/order-notifier-bot.git

# Отправить код на GitHub
git branch -M main
git push -u origin main
```

**Готово!** Код на GitHub. Проверь: зайди на страницу репозитория и убедись, что все файлы на месте.

> ⚠️ **Важно:** файлы `.env` и `sent_orders.json` не должны быть в репозитории (они указаны в `.gitignore`). Если случайно попали — пиши, помогу удалить.

---

## Шаг 2: Зарегистрироваться на Render

1. Открой [render.com](https://render.com)
2. Нажми **"Get Started for Free"** или **"Sign Up"**
3. Зарегистрируйся (можно через **GitHub** — самый удобный способ)
4. Подтверди email

---

## Шаг 3: Создать Web Service

1. На дашборде Render нажми **"New +"** → **"Web Service"**

   ![Шаг 1](https://i.imgur.com/placeholder1.png)

2. **Connect a repository** — найди свой репозиторий `order-notifier-bot` и нажми **"Connect"**

   Если репозитория нет в списке → нажми **"Configure account"** → дай Render доступ к репозиториям

3. Заполни настройки:

   | Поле | Значение |
   |------|----------|
   | **Name** | `order-notifier-bot` (или своё) |
   | **Region** | `Frankfurt (EU Central)` (ближе к России) |
   | **Branch** | `main` |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `python bot.py` |
   | **Plan** | `Free` |

   Вот как это выглядит:

   ```
   Name: order-notifier-bot
   Region: Frankfurt (EU Central)
   Branch: main
   
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python bot.py
   
   Instance Type: Free
   ```

4. Прокрути вниз и нажми **"Advanced"** → **"Add Environment Variable"**

---

## Шаг 4: Добавить переменные окружения

Это самый важный шаг! Здесь ты вводишь все свои секретные ключи.

Нажми **"Add Environment Variable"** и добавь по одной:

| Key | Value | Описание |
|-----|-------|----------|
| `TG_BOT_TOKEN` | `123456789:ABCdefGHI...` | Токен от @BotFather |
| `TG_CHAT_ID` | `123456789` | Твой Telegram ID от @userinfobot |
| `YM_API_KEY` | `AQVNxxxx...` | API-ключ Яндекс Маркета |
| `YM_CAMPAIGN_IDS` | `12345678,87654321` | ID магазинов через запятую |
| `YM_CHECK_INTERVAL` | `60` | Проверка каждую минуту |
| `RCRM_URL` | `https://your-shop.retailcrm.ru` | URL твоей CRM |
| `RCRM_API_KEY` | `abc123def456...` | API-ключ RetailCRM |
| `RCRM_CHECK_INTERVAL` | `60` | Проверка каждую минуту |

Вот пример заполненного блока:

```
Environment Variables:
  TG_BOT_TOKEN=741234567:AAFxxxxxx...
  TG_CHAT_ID=123456789
  YM_API_KEY=AQVN0B_xxxx...
  YM_CAMPAIGN_IDS=12345678,87654321
  YM_CHECK_INTERVAL=60
  RCRM_URL=https://your-shop.retailcrm.ru
  RCRM_API_KEY=abc123def456...
  RCRM_CHECK_INTERVAL=60
```

Нажми **"Create Web Service"** внизу страницы.

---

## Шаг 5: Деплой и проверка

1. Render начнёт автоматическую сборку:
   - Установит Python
   - Запустит `pip install -r requirements.txt`
   - Выполнит `python bot.py`

2. Следи за логами в реальном времени (вкладка **"Logs"** на странице сервиса):

   ```
   ==> Running 'python bot.py'
   14:30:01 | INFO | order-bot | Бот запущен. Источники: ['Яндекс Маркет', 'RetailCRM']
   ```

3. Проверь Telegram — должен прийти запускающий бота сообщение:
   > ✅ **Бот запущен**
   > Источники: Яндекс Маркет, RetailCRM

---

## Шаг 6: Проверка работы

### Тест Яндекс Маркет
Дождись нового заказа (или создай тестовый) — уведомление придёт в Telegram.

### Тест RetailCRM
Создай тестовый заказ в CRM → проверь Telegram.

### Если что-то не работает
1. Открой вкладку **"Logs"** на Render
2. Ищи ошибки:
   - `401` — неверный API-ключ
   - `403` — нет доступа
   - `YM | Ошибка` — проблема с Яндекс Маркетом
   - `RCRM | Ошибка` — проблема с RetailCRM
3. Исправь переменные окружения → **Settings** → **Environment**

---

## 📊 Управление сервисом

### Где находится
[Dashboard Render](https://dashboard.render.com) → твой сервис `order-notifier-bot`

### Полезные кнопки
- **Logs** — смотреть логи в реальном времени
- **Settings** — изменить переменные окружения
- **Events** — история деплоев
- **Manual Deploy** → **Deploy latest commit** — перезапустить вручную

### Перезапуск
Если изменил код на GitHub:
1. Запушь изменения: `git push origin main`
2. На Render нажми **Manual Deploy** → **Deploy latest commit**
3. Или подключи **Auto-Deploy** (в Settings) — тогда обновится автоматически

### Остановка
Чтобы остановить бота:
1. На странице сервиса нажми **Settings**
2. Прокрути вниз → **Delete Service**
3. Или просто удали все переменные окружения — бот не запустится

---

## 💡 Частые проблемы

### "Build failed"
Проверь `requirements.txt` — все ли библиотеки на месте.

### "Module not found"
Убедись, что `Build Command` написан правильно:
```
pip install -r requirements.txt
```

### "Нет уведомлений в Telegram"
1. Проверь логи Render на ошибки
2. Убедись, что ты написал боту `/start`
3. Проверь `TG_CHAT_ID` — должен быть твой ID, не ID бота

### "Free plan limitations"
- Бесплатный инстанс засыпает после 15 минут без активности
- **Но!** Если бот постоянно делает запросы (каждую минуту) — он не засыпает
- Если засыпнет — проснётся при следующем запросе (задержка ~30 сек)
- Для критичных кейсов рассмотри paid plan ($7/мес)

---

## 🔗 Полезные ссылки

- [Render Dashboard](https://dashboard.render.com)
- [Render Docs](https://docs.render.com)
- [GitHub Desktop](https://desktop.github.com/) — если не любишь терминал
- [@BotFather](https://t.me/BotFather) — создание Telegram бота
- [@userinfobot](https://t.me/userinfobot) — узнать свой ID

---

## Готово! 🎉

Твой бот теперь работает 24/7 в облаке и присылает уведомления о заказах прямо в Telegram.

Если остались вопросы — открывай Issue в репозитории или пиши в Telegram.
