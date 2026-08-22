"""Диспетчер Хаоса - Telegram бот для управления подписками"""

__version__ = "1.0.0"
__author__ = "Chaos Dispatcher Team"

from bot.config import config
from bot.utils.logger import logger

logger.info(f"Chaos Dispatcher v{__version__} initialized")