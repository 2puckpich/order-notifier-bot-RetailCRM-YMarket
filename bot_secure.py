"""
Secure Order Notifier Bot.

Все API-ключи вводятся через Telegram и хранятся ТОЛЬКО в оперативной памяти.
Никаких файлов с секретами на диске. При перезапуске — ввод заново.

Доступ только для авторизованного пользователя (указать в config_secure.py).
"""
import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config_secure import TG_BOT_TOKEN, TG_CHAT_ID, AUTHORIZED_USERNAME
from yandex_market import YandexMarketClient
from retailcrm import RetailCRMClient

# ---------------------------------------------------------------------------
# Настройка логирования
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("secure-order-bot")
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

SENT_ORDERS_FILE = Path(__file__).parent / "sent_orders.json"

# Conversation states
MENU = 0
WAIT_YM_KEY = 10
WAIT_YM_CAMPAIGNS = 11
WAIT_RCRM_URL = 20
WAIT_RCRM_KEY = 21
WAIT_INTERVAL = 30

# ---------------------------------------------------------------------------
# Хранилище (в памяти, не на диске)
# ---------------------------------------------------------------------------


class SecureStore:
    """Все секреты только в RAM. При перезапуске — сброс."""

    def __init__(self):
        self.ym_api_key: str = ""
        self.ym_campaign_ids: list[int] = []
        self.rcrm_url: str = ""
        self.rcrm_api_key: str = ""
        self.check_interval: int = 60
        self._running = False
        self._tasks: list[asyncio.Task] = []

    def is_configured(self) -> bool:
        return bool(self.ym_api_key or self.rcrm_api_key)

    def status_text(self) -> str:
        lines = ["🔧 <b>Текущая конфигурация</b>\n"]
        lines.append(f"⏱ Интервал проверки: {self.check_interval} сек\n")
        if self.ym_api_key:
            masked = self.ym_api_key[:6] + "..." + self.ym_api_key[-4:]
            lines.append(f"✅ Яндекс Маркет: {masked}")
            lines.append(f"   Кампании: {self.ym_campaign_ids}")
        else:
            lines.append("❌ Яндекс Маркет: не настроен")
        if self.rcrm_api_key:
            masked = self.rcrm_api_key[:6] + "..." + self.rcrm_api_key[-4:]
            lines.append(f"✅ RetailCRM: {masked}")
            lines.append(f"   URL: {self.rcrm_url}")
        else:
            lines.append("❌ RetailCRM: не настроен")
        return "\n".join(lines)


# Глобальные объекты
store = SecureStore()
app_bot: Application | None = None


# ---------------------------------------------------------------------------
# SentOrdersStore (остаётся файлом — тут нет секретов, только ID заказов)
# ---------------------------------------------------------------------------


class SentOrdersStore:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self._data: dict[str, Any] = {"ym": {}, "rcrm": {}}
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {"ym": {}, "rcrm": {}}

    def _save(self) -> None:
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Не удалось сохранить %s: %s", self.filepath, e)

    def is_sent(self, source: str, order_id: str) -> bool:
        return order_id in self._data.get(source, {})

    def mark_sent(self, source: str, order_id: str) -> None:
        if source not in self._data:
            self._data[source] = {}
        self._data[source][order_id] = datetime.now(timezone.utc).isoformat()
        self._save()

    def cleanup_old(self, source: str, max_age_hours: int = 72) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        to_remove = [
            oid for oid, ts in self._data.get(source, {}).items()
            if datetime.fromisoformat(ts) < cutoff
        ]
        for oid in to_remove:
            del self._data[source][oid]
        if to_remove:
            self._save()


order_store = SentOrdersStore(SENT_ORDERS_FILE)


# ---------------------------------------------------------------------------
# Авторизация
# ---------------------------------------------------------------------------


def is_authorized(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    # Проверяем username (без @)
    username = (user.username or "").lower()
    return username == AUTHORIZED_USERNAME.lower()


async def check_auth(update: Update) -> bool:
    if not is_authorized(update):
        await update.message.reply_text(
            "🚫 <b>Доступ запрещён</b>\nЭтот бот личный.",
            parse_mode=ParseMode.HTML,
        )
        logger.warning(
            "Попытка доступа от @%s (id=%s)",
            update.effective_user.username if update.effective_user else "?",
            update.effective_user.id if update.effective_user else "?",
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Команды бота
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    await update.message.reply_text(
        f"👋 Привет, <b>@{AUTHORIZED_USERNAME}</b>!\n\n"
        f"Это безопасный бот уведомлений о заказах.\n"
        f"Все API-ключи хранятся только в памяти и сбрасываются при перезапуске.\n\n"
        f"<b>Команды:</b>\n"
        f"/setup — настроить API-ключи\n"
        f"/status — проверить конфигурацию\n"
        f"/run — запустить проверку заказов\n"
        f"/stop — остановить проверку\n"
        f"/interval — сменить интервал проверки\n"
        f"/clear — стереть все ключи из памяти\n"
        f"/help — справка",
        parse_mode=ParseMode.HTML,
    )
    return ConversationHandler.END


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    await update.message.reply_text(
        "<b>📖 Справка</b>\n\n"
        "<b>/setup</b> — пошаговая настройка API-ключей через Telegram\n"
        "<b>/status</b> — текущая конфигурация (ключи маскированы)\n"
        "<b>/run</b> — начать проверку заказов\n"
        "<b>/stop</b> — остановить проверку\n"
        "<b>/interval</b> — изменить период проверки (по умолчанию 60 сек)\n"
        "<b>/clear</b> — удалить все API-ключи из памяти\n\n"
        "⚠️ <b>Важно:</b> API-ключи хранятся только в RAM. "
        "При перезапуске бота нужно будет ввести их заново.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    status = store.status_text()
    if store._running:
        status += "\n\n🟢 <b>Проверка активна</b>"
    else:
        status += "\n\n🔴 <b>Проверка остановлена</b>"
    await update.message.reply_text(status, parse_mode=ParseMode.HTML)


# ---- SETUP: пошаговый ввод ключей ----


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    kb = [
        ["Яндекс Маркет"],
        ["RetailCRM"],
        ["Готово — в меню"],
    ]
    await update.message.reply_text(
        "🔧 <b>Настройка API-ключей</b>\n\n"
        "Все ключи будут храниться только в памяти (RAM).\n"
        "Выбери источник:",
        parse_mode=ParseMode.HTML,
        reply_markup={"keyboard": kb, "resize_keyboard": True, "one_time_keyboard": True},
    )
    return MENU


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    text = update.message.text
    if text == "Яндекс Маркет":
        await update.message.reply_text(
            "Отправь API-ключ Яндекс Маркета:\n"
            "(его можно найти: ЛК → Настройки → API и модули → Токен)\n\n"
            "Для отмены отправь /cancel",
            reply_markup={"remove_keyboard": True},
        )
        return WAIT_YM_KEY
    elif text == "RetailCRM":
        await update.message.reply_text(
            "Отправь URL RetailCRM (например: https://your-shop.retailcrm.ru):\n\n"
            "Для отмены отправь /cancel",
            reply_markup={"remove_keyboard": True},
        )
        return WAIT_RCRM_URL
    elif text in ("Готово — в меню", "/cancel"):
        await update.message.reply_text(
            "✅ Настройка завершена. Используй /status или /run",
            reply_markup={"remove_keyboard": True},
        )
        return ConversationHandler.END
    return MENU


# --- Яндекс Маркет flow ---


async def receive_ym_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    key = update.message.text.strip()
    if key == "/cancel":
        await update.message.reply_text("Отменено.", reply_markup={"remove_keyboard": True})
        return ConversationHandler.END
    context.user_data["_tmp_ym_key"] = key
    await update.message.reply_text(
        "Теперь отправь ID кампаний (магазинов) через запятую:\n"
        "(например: <code>12345678,87654321</code>)\n\n"
        "Найти: ЛК → Настройки → API → Идентификатор кампании",
        parse_mode=ParseMode.HTML,
    )
    return WAIT_YM_CAMPAIGNS


async def receive_ym_campaigns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text("Отменено.", reply_markup={"remove_keyboard": True})
        return ConversationHandler.END
    try:
        campaign_ids = [int(x.strip()) for x in text.split(",") if x.strip()]
        if not campaign_ids:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Отправь числа через запятую (например: 12345678,87654321)"
        )
        return WAIT_YM_CAMPAIGNS
    store.ym_api_key = context.user_data.pop("_tmp_ym_key", "")
    store.ym_campaign_ids = campaign_ids
    await update.message.reply_text(
        f"✅ Яндекс Маркет настроен!\n"
        f"Ключ: <code>{store.ym_api_key[:6]}...{store.ym_api_key[-4:]}</code>\n"
        f"Кампании: {store.ym_campaign_ids}",
        parse_mode=ParseMode.HTML,
    )
    return await cmd_setup(update, context)


# --- RetailCRM flow ---


async def receive_rcrm_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    url = update.message.text.strip().rstrip("/")
    if url == "/cancel":
        await update.message.reply_text("Отменено.", reply_markup={"remove_keyboard": True})
        return ConversationHandler.END
    if not url.startswith("https://"):
        await update.message.reply_text("❌ URL должен начинаться с https://")
        return WAIT_RCRM_URL
    context.user_data["_tmp_rcrm_url"] = url
    await update.message.reply_text(
        "Отправь API-ключ RetailCRM:\n"
        "(Настройки → Интеграция → Ключи доступа к API)\n\n"
        "Для отмены отправь /cancel"
    )
    return WAIT_RCRM_KEY


async def receive_rcrm_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    key = update.message.text.strip()
    if key == "/cancel":
        await update.message.reply_text("Отменено.", reply_markup={"remove_keyboard": True})
        return ConversationHandler.END
    store.rcrm_url = context.user_data.pop("_tmp_rcrm_url", "")
    store.rcrm_api_key = key
    await update.message.reply_text(
        f"✅ RetailCRM настроен!\n"
        f"URL: {store.rcrm_url}\n"
        f"Ключ: <code>{store.rcrm_api_key[:6]}...{store.rcrm_api_key[-4:]}</code>",
        parse_mode=ParseMode.HTML,
    )
    return await cmd_setup(update, context)


# ---- RUN / STOP ----


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    if store._running:
        await update.message.reply_text("🟢 Проверка уже запущена. /status")
        return
    if not store.is_configured():
        await update.message.reply_text(
            "❌ Сначала настрой API-ключи командой /setup"
        )
        return

    store._running = True
    await update.message.reply_text("🚀 Запускаю проверку заказов...")

    # Запускаем фоновые задачи
    tasks = []
    if store.ym_api_key and store.ym_campaign_ids:
        tasks.append(asyncio.create_task(poll_yandex_market(context)))
    if store.rcrm_api_key and store.rcrm_url:
        tasks.append(asyncio.create_task(poll_retailcrm(context)))
    tasks.append(asyncio.create_task(cleanup_loop(context)))
    store._tasks = tasks

    sources = []
    if store.ym_api_key:
        sources.append("Яндекс Маркет")
    if store.rcrm_api_key:
        sources.append("RetailCRM")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"✅ <b>Бот запущен</b>\n"
            f"Источники: {', '.join(sources)}\n"
            f"Интервал: {store.check_interval} сек"
        ),
        parse_mode=ParseMode.HTML,
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    if not store._running:
        await update.message.reply_text("🔴 Проверка уже остановлена.")
        return
    store._running = False
    for t in store._tasks:
        t.cancel()
    store._tasks = []
    await update.message.reply_text("⛔ <b>Проверка остановлена</b>", parse_mode=ParseMode.HTML)


# ---- INTERVAL ----


async def cmd_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    await update.message.reply_text(
        f"Текущий интервал: <b>{store.check_interval}</b> сек\n"
        f"Отправь новое значение (в секундах, минимум 30):\n\n"
        f"Для отмены отправь /cancel",
        parse_mode=ParseMode.HTML,
    )
    return WAIT_INTERVAL


async def receive_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    text = update.message.text.strip()
    if text == "/cancel":
        await update.message.reply_text("Отменено.")
        return ConversationHandler.END
    try:
        val = int(text)
        if val < 30:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи число от 30 и больше.")
        return WAIT_INTERVAL
    store.check_interval = val
    await update.message.reply_text(f"✅ Интервал установлен: {val} сек")
    return ConversationHandler.END


# ---- CLEAR ----


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_auth(update):
        return
    # Останавливаем если запущено
    if store._running:
        store._running = False
        for t in store._tasks:
            t.cancel()
        store._tasks = []
    # Чистим память
    store.ym_api_key = ""
    store.ym_campaign_ids = []
    store.rcrm_url = ""
    store.rcrm_api_key = ""
    await update.message.reply_text(
        "🧹 <b>Все API-ключи удалены из памяти.</b>\n"
        "При перезапуске бота нужно будет настроить заново.\n\n"
        "Используй /setup для повторной настройки.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_auth(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "Отменено.", reply_markup={"remove_keyboard": True}
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Фоновые задачи проверки заказов
# ---------------------------------------------------------------------------


async def poll_yandex_market(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Цикл проверки Яндекс Маркета."""
    client = YandexMarketClient(
        api_key=store.ym_api_key,
        campaign_ids=store.ym_campaign_ids,
    )
    while store._running:
        try:
            since = datetime.now(timezone.utc) - timedelta(
                minutes=store.check_interval // 60 + 5
            )
            orders = await client.get_new_orders(since=since)
            for order in orders:
                order_id = str(order.get("id", ""))
                if not order_id or order_store.is_sent("ym", order_id):
                    continue
                msg = client.format_order_message(order)
                await send_to_owner(context.bot, msg)
                order_store.mark_sent("ym", order_id)
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error("YM poll error: %s", e)
        await asyncio.sleep(store.check_interval)


async def poll_retailcrm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Цикл проверки RetailCRM."""
    client = RetailCRMClient(
        crm_url=store.rcrm_url,
        api_key=store.rcrm_api_key,
    )
    while store._running:
        try:
            since = datetime.now(timezone.utc) - timedelta(
                minutes=store.check_interval // 60 + 5
            )
            orders = await client.get_new_orders(since=since)
            for order in orders:
                order_id = str(order.get("id", ""))
                if not order_id or order_store.is_sent("rcrm", order_id):
                    continue
                msg = client.format_order_message(order)
                await send_to_owner(context.bot, msg)
                order_store.mark_sent("rcrm", order_id)
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error("RCRM poll error: %s", e)
        await asyncio.sleep(store.check_interval)


async def cleanup_loop(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очистка старых записей."""
    while store._running:
        await asyncio.sleep(3600 * 6)  # каждые 6 часов
        order_store.cleanup_old("ym")
        order_store.cleanup_old("rcrm")


async def send_to_owner(bot: Bot, text: str) -> None:
    """Отправить сообщение владельцу."""
    try:
        chat_id = TG_CHAT_ID
        if not chat_id:
            logger.error("TG_CHAT_ID не задан, не могу отправить уведомление")
            return
        await bot.send_message(
            chat_id=chat_id,
            text=text[:4096],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("Ошибка отправки: %s", e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if not TG_BOT_TOKEN:
        logger.error("TG_BOT_TOKEN не задан! Отредактируй config_secure.py и впиши токен.")
        return

    application = Application.builder().token(TG_BOT_TOKEN).build()
    global app_bot
    app_bot = application

    # Conversation: setup
    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("setup", cmd_setup)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)],
            WAIT_YM_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ym_key)],
            WAIT_YM_CAMPAIGNS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ym_campaigns)
            ],
            WAIT_RCRM_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rcrm_url)],
            WAIT_RCRM_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rcrm_key)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    # Conversation: interval
    interval_conv = ConversationHandler(
        entry_points=[CommandHandler("interval", cmd_interval)],
        states={
            WAIT_INTERVAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_interval)
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    application.add_handler(setup_conv)
    application.add_handler(interval_conv)
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("run", cmd_run))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler("clear", cmd_clear))

    logger.info("Секьюрный бот запущен. Ожидаю команды...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
