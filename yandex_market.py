"""Клиент для API Яндекс Маркета (FBS/FBY заказы)"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.partner.market.yandex.ru"


class YandexMarketClient:
    """Асинхронный клиент для получения заказов из Яндекс Маркета."""

    def __init__(self, api_key: str, campaign_ids: list[int]):
        self.api_key = api_key
        self.campaign_ids = campaign_ids
        self.headers = {
            "Api-Key": api_key,
            "Accept": "application/json",
        }

    async def _get_orders(
        self,
        session: aiohttp.ClientSession,
        campaign_id: int,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        """Получить заказы кампании за указанный период.

        Args:
            session: aiohttp сессия
            campaign_id: ID кампании (магазина)
            from_date: начало периода
            to_date: конец периода

        Returns:
            Список заказов
        """
        url = f"{BASE_URL}/v2/campaigns/{campaign_id}/orders.json"
        
        # Формат даты для Яндекс Маркета: YYYY-MM-DD
        params = {
            "fromDate": from_date.strftime("%Y-%m-%d"),
            "toDate": to_date.strftime("%Y-%m-%d"),
        }

        orders = []
        page = 1
        page_size = 50

        while True:
            params["page"] = page
            params["page_size"] = page_size

            try:
                async with session.get(
                    url, headers=self.headers, params=params, timeout=30
                ) as resp:
                    if resp.status == 401:
                        logger.error(
                            "YM | Неверный API-ключ для кампании %s", campaign_id
                        )
                        break
                    if resp.status == 403:
                        logger.error(
                            "YM | Нет доступа к кампании %s", campaign_id
                        )
                        break
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(
                            "YM | Ошибка %s для кампании %s: %s",
                            resp.status,
                            campaign_id,
                            text[:200],
                        )
                        break

                    data = await resp.json()
                    page_orders = data.get("orders", [])
                    if not page_orders:
                        break

                    orders.extend(page_orders)
                    
                    # Пагинация
                    pager = data.get("pager", {})
                    total = pager.get("total", 0)
                    if page * page_size >= total:
                        break
                    page += 1

            except asyncio.TimeoutError:
                logger.error("YM | Таймаут запроса для кампании %s", campaign_id)
                break
            except Exception as e:
                logger.error(
                    "YM | Ошибка запроса для кампании %s: %s", campaign_id, e
                )
                break

        return orders

    async def get_new_orders(
        self, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Получить новые заказы из всех кампаний.

        Args:
            since: Дата, с которой искать заказы. Если None — за последние 24 часа.

        Returns:
            Список всех заказов из всех кампаний
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        to_date = datetime.now(timezone.utc) + timedelta(days=1)
        all_orders = []

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._get_orders(session, cid, since, to_date)
                for cid in self.campaign_ids
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "YM | Ошибка получения заказов кампании %s: %s",
                        self.campaign_ids[i],
                        result,
                    )
                    continue
                for order in result:
                    order["_campaign_id"] = self.campaign_ids[i]
                all_orders.extend(result)

        return all_orders

    @staticmethod
    def format_order_message(order: dict[str, Any]) -> str:
        """Формирует текст уведомления о заказе.

        Args:
            order: Данные заказа из API

        Returns:
            Текст сообщения для Telegram
        """
        order_id = order.get("id", "?")
        status = order.get("status", "?")
        campaign_id = order.get("_campaign_id", "?")
        
        # Покупатель
        delivery = order.get("delivery", {})
        buyer = delivery.get("buyer", {})
        buyer_name = buyer.get("firstName", "")
        buyer_last = buyer.get("lastName", "")
        buyer_phone = buyer.get("phone", "")
        buyer_full = f"{buyer_name} {buyer_last}".strip() or "Не указан"
        
        # Адрес доставки
        address = delivery.get("address", {})
        address_parts = [
            address.get("city", ""),
            address.get("street", ""),
            address.get("house", ""),
            address.get("apartment", ""),
        ]
        address_str = ", ".join(p for p in address_parts if p) or "Не указан"
        
        # Дата доставки
        delivery_date = delivery.get("dates", {}).get("fromDate", "?")
        
        # Товары
        items = order.get("items", [])
        items_text = []
        total_sum = 0
        for item in items:
            name = item.get("offerName", item.get("offerId", "Товар"))
            count = item.get("count", 1)
            price = item.get("price", 0)
            total_sum += price * count
            items_text.append(f"  • {name} x{count} — {price} ₽")
        
        items_str = "\n".join(items_text) if items_text else "  • (информация о товарах недоступна)"

        message = (
            f"📦 <b>НОВЫЙ ЗАКАЗ Яндекс Маркет</b>\n"
            f"🏪 Магазин: BODY KULT (кампания {campaign_id})\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🆔 Номер: <code>{order_id}</code>\n"
            f"📊 Статус: {status}\n"
            f"💰 Сумма: {total_sum} ₽\n"
            f"📅 Дата доставки: {delivery_date}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 Покупатель: {buyer_full}\n"
            f"📞 Телефон: {buyer_phone or 'не указан'}\n"
            f"📍 Адрес: {address_str}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🛍 Товары:\n{items_str}"
        )
        
        return message
