"""
Главный файл для Bothost.ru
Импортирует и запускает полный код из папки bot/
"""

import asyncio
import sys
import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Добавляем путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем полный код
from bot.main import main

if __name__ == "__main__":
    logger.info("🚀 Запуск через Bothost...")
    asyncio.run(main())
