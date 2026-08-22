"""
Главный файл бота для Bothost.ru
Bothost запускает: python bot.py
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

# Импортируем aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Если токен не указан в env, пробуем импортировать из config
if not BOT_TOKEN:
    try:
        from bot.config import config
        BOT_TOKEN = config.BOT_TOKEN
    except:
        pass

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    logger.error("Добавьте BOT_TOKEN в переменные окружения Bothost")
    sys.exit(1)

# Инициализация
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# ============ КЛАВИАТУРЫ ============

def get_main_keyboard():
    """Главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subscriptions")],
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="add_subscription"),
            InlineKeyboardButton(text="❌ Удалить", callback_data="delete_subscription")
        ],
        [InlineKeyboardButton(text="📊 Финансовый обзор", callback_data="financial_overview")],
        [InlineKeyboardButton(text="💳 Тариф", callback_data="tariff_info")],
        [InlineKeyboardButton(text="🎁 Партнерка", callback_data="referral_program")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])

# ============ ОБРАБОТЧИКИ ============

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик /start"""
    logger.info(f"User {message.from_user.id} started")
    
    text = (
        f"👋 <b>Добро пожаловать, {message.from_user.full_name}!</b>\n\n"
        f"Я — <b>Диспетчер Хаоса</b> 🤖\n"
        f"Управляю вашими подписками.\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик /help"""
    await message.answer(
        "📚 <b>Помощь</b>\n\n"
        "/start — главное меню\n"
        "/help — помощь\n"
        "/premium — Premium\n"
        "/referral — партнерка\n"
        "/cancel — отмена"
    )

@dp.message(Command("premium"))
async def cmd_premium(message: types.Message):
    """Обработчик /premium"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить 25 Stars", callback_data="pay_premium")]
    ])
    
    await message.answer(
        "💳 <b>Premium тариф</b>\n\n"
        "• 30 подписок\n"
        "• 25 Stars/мес",
        reply_markup=keyboard
    )

@dp.message(Command("referral"))
async def cmd_referral(message: types.Message):
    """Обработчик /referral"""
    await message.answer(
        "🎁 <b>Партнерская программа</b>\n\n"
        "Приглашайте друзей и получайте Stars!"
    )

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    """Обработчик /cancel"""
    await message.answer("✅ Отменено")

# ============ CALLBACKS ============

@dp.callback_query(F.data == "my_subscriptions")
async def cb_subs(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📋 <b>Ваши подписки</b>\n\nПока пусто",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="add_subscription")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "add_subscription")
async def cb_add(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📝 Отправьте название подписки:"
    )
    await callback.answer()

@dp.callback_query(F.data == "delete_subscription")
async def cb_delete(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🗑 Выберите подписку для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "financial_overview")
async def cb_finance(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📊 <b>Финансовый обзор</b>\n\n"
        "💥 Сила удара: 0 ₽\n"
        "💳 Расходы: 0 ₽/мес",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "tariff_info")
async def cb_tariff(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💳 <b>Тарифы</b>\n\n"
        "🔓 Бесплатный: 2 подписки\n"
        "⭐ Premium: 30 подписок",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Оплатить", callback_data="pay_premium")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "referral_program")
async def cb_ref(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎁 <b>Партнерка</b>\n\n"
        "Приглашайте друзей!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "help")
async def cb_help(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ Используйте /help",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "pay_premium")
async def cb_pay(callback: types.CallbackQuery):
    await callback.answer("Оплата скоро будет доступна", show_alert=True)

@dp.callback_query(F.data == "back_to_main")
async def cb_back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

# ============ ЭХО ============

@dp.message()
async def echo(message: types.Message):
    """Обработчик всех сообщений"""
    logger.info(f"Message: {message.text}")
    await message.answer(
        f"📝 Вы написали: {message.text}",
        reply_markup=get_main_keyboard()
    )

# ============ ЗАПУСК ============

async def main():
    """Главная функция"""
    logger.info("=" * 50)
    logger.info("🚀 Запуск бота...")
    
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот: @{me.username}")
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook удален")
        
        logger.info("✅ Начинаем polling...")
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
