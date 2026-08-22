import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    """Конфигурация бота"""
    
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "6226081631,8300113531").split(",") if x.strip()
    ])
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/chaos.db")
    
    # Stars Payment
    PREMIUM_PRICE_STARS: int = int(os.getenv("PREMIUM_PRICE_STARS", "25"))
    PREMIUM_DURATION_DAYS: int = int(os.getenv("PREMIUM_DURATION_DAYS", "30"))
    
    # Limits
    FREE_SUBSCRIPTIONS_LIMIT: int = int(os.getenv("FREE_SUBSCRIPTIONS_LIMIT", "2"))
    PREMIUM_SUBSCRIPTIONS_LIMIT: int = int(os.getenv("PREMIUM_SUBSCRIPTIONS_LIMIT", "30"))
    
    # Referral Program
    REFERRAL_REWARD_STARS: int = int(os.getenv("REFERRAL_REWARD_STARS", "5"))  # Награда за реферала
    REFERRAL_BONUS_STARS: int = int(os.getenv("REFERRAL_BONUS_STARS", "3"))  # Бонус приглашенному
    MIN_REFERRAL_PAYOUT: int = int(os.getenv("MIN_REFERRAL_PAYOUT", "25"))  # Минимум для вывода
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "data/logs/bot.log")

config = Config()
