import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    """Конфигурация бота"""
    
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # ЖЕСТКО УКАЗАННЫЕ АДМИНЫ (замените на свои ID)
    ADMIN_IDS: List[int] = field(default_factory=lambda: [6226081631, 8300113531])
    
    # Остальные настройки
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/chaos.db")
    PREMIUM_PRICE_STARS: int = int(os.getenv("PREMIUM_PRICE_STARS", "25"))
    PREMIUM_DURATION_DAYS: int = int(os.getenv("PREMIUM_DURATION_DAYS", "30"))
    FREE_SUBSCRIPTIONS_LIMIT: int = int(os.getenv("FREE_SUBSCRIPTIONS_LIMIT", "2"))
    PREMIUM_SUBSCRIPTIONS_LIMIT: int = int(os.getenv("PREMIUM_SUBSCRIPTIONS_LIMIT", "30"))
    REFERRAL_REWARD_STARS: int = int(os.getenv("REFERRAL_REWARD_STARS", "5"))
    REFERRAL_BONUS_STARS: int = int(os.getenv("REFERRAL_BONUS_STARS", "3"))
    MIN_REFERRAL_PAYOUT: int = int(os.getenv("MIN_REFERRAL_PAYOUT", "25"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "data/logs/bot.log")

config = Config()

# Вывод для отладки
print(f"DEBUG: ADMIN_IDS = {config.ADMIN_IDS}")
