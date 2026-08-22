"""
Главный файл бота
Работает и локально, и на Bothost
"""

import asyncio
import logging
import os
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Добавляем путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Получаем токен
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Если нет в env, пробуем из config
if not BOT_TOKEN:
    try:
        from bot.config import config
        BOT_TOKEN = config.BOT_TOKEN
    except:
        pass

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    sys.exit(1)

# Инициализация
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# Регистрируем обработчики
try:
    from bot.handlers import register_all_handlers
    register_all_handlers(dp)
    logger.info("✅ Все обработчики зарегистрированы")
except Exception as e:
    logger.error(f"❌ Ошибка регистрации: {e}")
    sys.exit(1)

async def main():
    """Главная функция"""
    logger.info("=" * 50)
    logger.info("🚀 Запуск бота...")
    
    # Инициализация БД
    try:
        from bot.database.connection import init_db
        await init_db()
        logger.info("✅ БД инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")
    
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот: @{me.username}")
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Запускаем polling...")
        
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
