"""
Telegram-бот для уведомлений о новых заказах.

Источники:
- Яндекс Маркет (BODY KULT) — через API партнёра
- RetailCRM (BUTONI) — через API v5

Алгоритм:
1. Периодический опрос API каждого источника
2. Проверка на дубликаты через локальное хранилище
3. Отправка уведомлений в Telegram
"""
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from telegram import Bot
from telegram.constants import ParseMode

import config
from yandex_market import YandexMarketClient
from retailcrm import RetailCRMClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("order-bot")

# Подавляем шум от библиотек
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


class SentOrdersStore:
    """Хранилище ID отправленных заказов (чтобы не дублировать уведомления)."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self._data: dict[str, Any] = {"ym": {}, "rcrm": {}}
        self._load()

    def _load(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Не удалось загрузить %s: %s", self.filepath, e)
                self._data = {"ym": {}, "rcrm": {}}

    def _save(self) -> None:
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error("Не удалось сохранить %s: %s", self.filepath, e)

    def is_sent(self, source: str, order_id: str) -> bool:
        """Проверить, отправлялось ли уже уведомление по этому заказу."""
        return order_id in self._data.get(source, {})

    def mark_sent(self, source: str, order_id: str) -> None:
        """Отметить заказ как отправленный."""
        if source not in self._data:
            self._data[source] = {}
        self._data[source][order_id] = datetime.now(timezone.utc).isoformat()
        self._save()

    def cleanup_old(self, source: str, max_age_hours: int = 72) -> None:
        """Удалить старые записи, чтобы файл не рос бесконечно."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        to_remove = [
            oid for oid, ts in self._data.get(source, {}).items()
            if datetime.fromisoformat(ts) < cutoff
        ]
        for oid in to_remove:
            del self._data[source][oid]
        if to_remove:
            self._save()
            logger.info("Очищено %d старых записей из %s", len(to_remove), source)


class OrderNotifierBot:
    """Основной класс бота."""

    def __init__(self):
        self.bot = Bot(token=config.TG_BOT_TOKEN)
        self.chat_id = config.TG_CHAT_ID
        self.store = SentOrdersStore(config.SENT_ORDERS_FILE)

        # Клиенты API
        self.ym_client: YandexMarketClient | None = None
        if config.YM_API_KEY and config.YM_CAMPAIGN_IDS:
            self.ym_client = YandexMarketClient(
                api_key=config.YM_API_KEY,
                campaign_ids=config.YM_CAMPAIGN_IDS,
            )

        self.rcrm_client: RetailCRMClient | None = None
        if config.RCRM_URL and config.RCRM_API_KEY:
            self.rcrm_client = RetailCRMClient(
                crm_url=config.RCRM_URL,
                api_key=config.RCRM_API_KEY,
            )

        self._running = True

    async def send_notification(self, text: str) -> None:
        """Отправить уведомление в Telegram."""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text[:4096],  # лимит Telegram
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error("Ошибка отправки в Telegram: %s", e)

    async def check_yandex_market(self) -> None:
        """Проверить новые заказы в Яндекс Маркете."""
        if not self.ym_client:
            return

        try:
            # Получаем заказы за последние N минут + буфер
            since = datetime.now(timezone.utc) - timedelta(
                minutes=config.YM_CHECK_INTERVAL // 60 + 5
            )
            orders = await self.ym_client.get_new_orders(since=since)

            new_count = 0
            for order in orders:
                order_id = str(order.get("id", ""))
                if not order_id or self.store.is_sent("ym", order_id):
                    continue

                message = self.ym_client.format_order_message(order)
                await self.send_notification(message)
                self.store.mark_sent("ym", order_id)
                new_count += 1
                # Небольшая задержка между сообщениями
                await asyncio.sleep(0.5)

            if new_count > 0:
                logger.info("YM | Отправлено уведомлений: %d", new_count)
            else:
                logger.debug("YM | Новых заказов нет")

        except Exception as e:
            logger.error("YM | Ошибка при проверке: %s", e)

    async def check_retailcrm(self) -> None:
        """Проверить новые заказы в RetailCRM."""
        if not self.rcrm_client:
            return

        try:
            # Получаем заказы за последние N минут + буфер
            since = datetime.now(timezone.utc) - timedelta(
                minutes=config.RCRM_CHECK_INTERVAL // 60 + 5
            )
            orders = await self.rcrm_client.get_new_orders(since=since)

            new_count = 0
            for order in orders:
                order_id = str(order.get("id", ""))
                if not order_id or self.store.is_sent("rcrm", order_id):
                    continue

                message = self.rcrm_client.format_order_message(order)
                await self.send_notification(message)
                self.store.mark_sent("rcrm", order_id)
                new_count += 1
                await asyncio.sleep(0.5)

            if new_count > 0:
                logger.info("RCRM | Отправлено уведомлений: %d", new_count)
            else:
                logger.debug("RCRM | Новых заказов нет")

        except Exception as e:
            logger.error("RCRM | Ошибка при проверке: %s", e)

    async def cleanup_task(self) -> None:
        """Периодическая очистка старых записей."""
        while self._running:
            await asyncio.sleep(3600 * 6)  # каждые 6 часов
            self.store.cleanup_old("ym")
            self.store.cleanup_old("rcrm")

    async def ym_polling_task(self) -> None:
        """Фоновая задача опроса Яндекс Маркета."""
        while self._running:
            await self.check_yandex_market()
            await asyncio.sleep(config.YM_CHECK_INTERVAL)

    async def rcrm_polling_task(self) -> None:
        """Фоновая задача опроса RetailCRM."""
        while self._running:
            await self.check_retailcrm()
            await asyncio.sleep(config.RCRM_CHECK_INTERVAL)

    async def run(self) -> None:
        """Запустить бота."""
        # Проверка конфигурации
        errors = config.validate()
        if errors:
            logger.error("❌ Ошибки конфигурации:")
            for err in errors:
                logger.error("  - %s", err)
            if all(e.endswith("(уведомления будут пропущены)") for e in errors):
                logger.warning("⚠️ Все источники отключены, бот не имеет смысла")
                return
            logger.info("Продолжаем работу с доступными источниками...")

        # Тестовое сообщение при старте
        sources = []
        if self.ym_client:
            sources.append("Яндекс Маркет (BODY KULT)")
        if self.rcrm_client:
            sources.append("RetailCRM (BUTONI)")
        
        start_msg = (
            f"✅ <b>Бот запущен</b>\n"
            f"Источники: {', '.join(sources) if sources else 'нет'}\n"
            f"Проверка каждые {config.YM_CHECK_INTERVAL // 60} мин"
        )
        await self.send_notification(start_msg)
        logger.info("Бот запущен. Источники: %s", sources)

        # Запускаем задачи
        tasks = []
        if self.ym_client:
            tasks.append(asyncio.create_task(self.ym_polling_task()))
        if self.rcrm_client:
            tasks.append(asyncio.create_task(self.rcrm_polling_task()))
        tasks.append(asyncio.create_task(self.cleanup_task()))

        # Ожидаем завершения (или сигнала)
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self.bot.send_message(
                chat_id=self.chat_id, text="⛔ <b>Бот остановлен</b>"
            )
            await self.bot.session.close()

    def stop(self) -> None:
        """Остановить бота."""
        self._running = False


def main() -> None:
    bot = OrderNotifierBot()

    def handle_signal(sig, frame):
        logger.info("Получен сигнал %s, останавливаем...", sig)
        bot.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    finally:
        logger.info("Бот завершил работу")


if __name__ == "__main__":
    main()
