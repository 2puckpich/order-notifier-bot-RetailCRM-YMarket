"""Загрузка конфигурации из .env"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# === Telegram ===
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")

# === Яндекс Маркет ===
YM_API_KEY = os.getenv("YM_API_KEY", "")
YM_CAMPAIGN_IDS_RAW = os.getenv("YM_CAMPAIGN_IDS", "")
YM_CHECK_INTERVAL = int(os.getenv("YM_CHECK_INTERVAL", "60"))

# === RetailCRM ===
RCRM_URL = os.getenv("RCRM_URL", "").rstrip("/")
RCRM_API_KEY = os.getenv("RCRM_API_KEY", "")
RCRM_CHECK_INTERVAL = int(os.getenv("RCRM_CHECK_INTERVAL", "60"))

# Парсинг ID кампаний
YM_CAMPAIGN_IDS = [
    int(x.strip())
    for x in YM_CAMPAIGN_IDS_RAW.split(",")
    if x.strip()
]

# Файл для хранения ID отправленных заказов
SENT_ORDERS_FILE = Path(__file__).parent / "sent_orders.json"


def validate() -> list[str]:
    """Проверяет обязательные переменные окружения.
    
    Returns:
        Список ошибок конфигурации. Пустой = всё ок.
    """
    errors = []
    
    if not TG_BOT_TOKEN:
        errors.append("TG_BOT_TOKEN не задан")
    if not TG_CHAT_ID:
        errors.append("TG_CHAT_ID не задан")
    if not YM_API_KEY:
        errors.append("YM_API_KEY не задан (уведомления Яндекс Маркет будут пропущены)")
    if not YM_CAMPAIGN_IDS:
        errors.append("YM_CAMPAIGN_IDS не задан (уведомления Яндекс Маркет будут пропущены)")
    if not RCRM_URL:
        errors.append("RCRM_URL не задан (уведомления RetailCRM будут пропущены)")
    if not RCRM_API_KEY:
        errors.append("RCRM_API_KEY не задан (уведомления RetailCRM будут пропущены)")
    
    return errors
