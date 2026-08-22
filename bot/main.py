"""
Главный файл бота - минимальная рабочая версия
"""

import asyncio
import sys
import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import config
from bot.database.connection import init_db, close_db

# Инициализация бота
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Диспетчер
dp = Dispatcher(storage=MemoryStorage())

# ============ БАЗОВЫЕ ОБРАБОТЧИКИ ============

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик /start"""
    logger.info(f"Received /start from {message.from_user.id}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subscriptions")],
        [InlineKeyboardButton(text="➕ Добавить подписку", callback_data="add_subscription")],
        [InlineKeyboardButton(text="💳 Тариф", callback_data="tariff_info")],
        [InlineKeyboardButton(text="🎁 Партнерская программа", callback_data="referral_program")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    
    await message.answer(
        f"👋 <b>Добро пожаловать, {message.from_user.full_name}!</b>\n\n"
        f"Я — <b>Диспетчер Хаоса</b>, ваш помощник в управлении подписками.\n\n"
        f"Выберите действие:",
        reply_markup=keyboard
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик /help"""
    await message.answer(
        "📚 <b>Помощь</b>\n\n"
        "/start — главное меню\n"
        "/add — добавить подписку\n"
        "/premium — Premium тариф\n"
        "/referral — партнерская программа\n"
        "/cancel — отменить действие"
    )

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state=None):
    """Обработчик /cancel"""
    await message.answer("✅ Действие отменено")

@dp.message()
async def echo(message: types.Message):
    """Эхо-обработчик для проверки"""
    logger.info(f"Received message: {message.text} from {message.from_user.id}")
    await message.answer(
        f"📝 Вы написали: {message.text}\n\n"
        f"Используйте /start для главного меню"
    )

# ============ CALLBACK ОБРАБОТЧИКИ ============

@dp.callback_query(F.data == "my_subscriptions")
async def cb_subscriptions(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 <b>Ваши подписки</b>\n\nПока пусто")
    await callback.answer()

@dp.callback_query(F.data == "add_subscription")
async def cb_add(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📝 <b>Добавление подписки</b>\n\n"
        "Отправьте название подписки:"
    )
    await callback.answer()

@dp.callback_query(F.data == "tariff_info")
async def cb_tariff(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💳 <b>Тарифы</b>\n\n"
        "🔓 Бесплатный: 2 подписки\n"
        "⭐ Premium: 30 подписок"
    )
    await callback.answer()

@dp.callback_query(F.data == "referral_program")
async def cb_referral(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎁 <b>Партнерская программа</b>\n\n"
        "Приглашайте друзей и получайте Stars!"
    )
    await callback.answer()

@dp.callback_query(F.data == "help")
async def cb_help(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ <b>Помощь</b>\n\n"
        "Используйте /start для главного меню"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def cb_back(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subscriptions")],
        [InlineKeyboardButton(text="➕ Добавить подписку", callback_data="add_subscription")],
        [InlineKeyboardButton(text="💳 Тариф", callback_data="tariff_info")],
        [InlineKeyboardButton(text="🎁 Партнерская программа", callback_data="referral_program")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

# ============ ЗАПУСК ============

async def main():
    """Главная функция"""
    logger.info("Запуск бота...")
    
    # Инициализация БД
    try:
        await init_db()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")
    
    # Получаем информацию о боте
    try:
        me = await bot.get_me()
        logger.info(f"Бот запущен: @{me.username}")
    except Exception as e:
        logger.error(f"Ошибка подключения: {e}")
        return
    
    logger.info("Начинаем polling...")
    
    try:
        # Запуск polling
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Ошибка polling: {e}", exc_info=True)
    finally:
        await bot.session.close()
        await close_db()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен")
    except Exception as e:
        print(f"Критическая ошибка: {e}")