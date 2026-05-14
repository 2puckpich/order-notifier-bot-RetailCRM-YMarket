"""Клиент для API RetailCRM v5"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

import config

logger = logging.getLogger(__name__)


class RetailCRMClient:
    """Асинхронный клиент для получения заказов из RetailCRM."""

    def __init__(self, crm_url: str, api_key: str):
        self.crm_url = crm_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_new_orders(
        self,
        since: datetime | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Получить заказы из RetailCRM, созданные после указанной даты.

        Args:
            since: Дата создания заказа (от). Если None — за последние 24 часа.
            session: Внешняя aiohttp сессия (опционально)

        Returns:
            Список заказов
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        url = f"{self.crm_url}/api/v5/orders"
        
        # RetailCRM ожидает дату в формате Y-m-d
        date_str = since.strftime("%Y-%m-%d")
        
        params = {
            "filter[createdAtFrom]": date_str,
            "limit": 100,
            "page": 1,
        }

        all_orders = []
        should_close = session is None

        try:
            if session is None:
                session = aiohttp.ClientSession()

            while True:
                try:
                    async with session.get(
                        url,
                        headers=self.headers,
                        params=params,
                        timeout=30,
                    ) as resp:
                        if resp.status == 401:
                            logger.error("RCRM | Неверный API-ключ")
                            break
                        if resp.status == 403:
                            logger.error("RCRM | Нет доступа к API")
                            break
                        if resp.status != 200:
                            text = await resp.text()
                            logger.error(
                                "RCRM | Ошибка %s: %s", resp.status, text[:200]
                            )
                            break

                        data = await resp.json()
                        orders = data.get("orders", [])
                        if not orders:
                            break

                        all_orders.extend(orders)

                        # Пагинация
                        pagination = data.get("pagination", {})
                        current_page = pagination.get("currentPage", 1)
                        total_pages = pagination.get("totalPageCount", 1)
                        
                        if current_page >= total_pages:
                            break
                        params["page"] = current_page + 1

                except asyncio.TimeoutError:
                    logger.error("RCRM | Таймаут запроса")
                    break
                except Exception as e:
                    logger.error("RCRM | Ошибка запроса: %s", e)
                    break

        finally:
            if should_close and session is not None:
                await session.close()

        return all_orders

    @staticmethod
    def format_order_message(order: dict[str, Any]) -> str:
        """Формирует текст уведомления о заказе RetailCRM.

        Args:
            order: Данные заказа из API

        Returns:
            Текст сообщения для Telegram
        """
        order_id = order.get("id", "?")
        order_number = order.get("number", order_id)
        status = order.get("status", "?")
        status_text = order.get("status", "?")
        created_at = order.get("createdAt", "?")
        total_sum = order.get("summ", 0)
        
        # Покупатель
        customer = order.get("customer", {})
        customer_first = customer.get("firstName", "")
        customer_last = customer.get("lastName", "")
        customer_phone = ""
        if customer.get("phones"):
            customer_phone = customer["phones"][0].get("number", "")
        customer_email = customer.get("email", "")
        customer_name = f"{customer_first} {customer_last}".strip() or "Не указан"
        
        # Доставка
        delivery = order.get("delivery", {})
        delivery_type = delivery.get("service", {}).get("name", "")
        delivery_address = delivery.get("address", {}).get("text", "")
        delivery_cost = delivery.get("cost", 0)
        
        # Товары
        items = order.get("items", [])
        items_text = []
        for item in items:
            name = item.get("offer", {}).get("displayName", item.get("offerName", item.get("name", "Товар")))
            quantity = item.get("quantity", item.get("count", 1))
            initial_price = item.get("initialPrice", 0)
            items_text.append(f"  • {name} x{quantity} — {initial_price} ₽")
        
        items_str = "\n".join(items_text) if items_text else "  • (информация о товарах недоступна)"
        
        # Способ оплаты
        payments = order.get("payments", [])
        payment_type = ""
        if payments:
            payment_type = payments[0].get("type", "")

        message = (
            f"🛒 <b>НОВЫЙ ЗАКАЗ RetailCRM</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🆔 Номер: <code>{order_number}</code>\n"
            f"📊 Статус: {status_text}\n"
            f"💰 Сумма: {total_sum} ₽\n"
            f"🕐 Создан: {created_at}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 Покупатель: {customer_name}\n"
            f"📞 Телефон: {customer_phone or 'не указан'}\n"
            f"📧 Email: {customer_email or 'не указан'}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🚚 Доставка: {delivery_type or 'не указана'}\n"
            f"📍 Адрес: {delivery_address or 'не указан'}\n"
            f"💵 Стоимость доставки: {delivery_cost} ₽\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💳 Оплата: {payment_type or 'не указана'}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🛍 Товары:\n{items_str}"
        )
        
        return message
