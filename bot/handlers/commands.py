from aiogram import Dispatcher, types, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from sqlalchemy import select

from bot.database.models import User
from bot.database.connection import get_async_db
from bot.keyboards.inline import get_main_keyboard
from bot.services.subscription_service import SubscriptionService
from bot.services.referral_service import ReferralService
from bot.utils.logger import logger
from bot.config import config
# ❌ НЕ ИМПОРТИРУЙТЕ bot из main!
# from bot.main import bot  ← УБЕРИТЕ ЭТУ СТРОКУ

async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject = None):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    await state.clear()
    
    referral_code = None
    if command and command.args:
        referral_code = command.args.strip()
    
    user = await SubscriptionService.get_or_create_user(
        user_id=user_id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    
    if referral_code and user:
        success = await ReferralService.process_referral(referral_code, user_id)
        if success:
            await message.answer(
                f"🎁 <b>Вы присоединились по реферальной ссылке!</b>\n\n"
                f"Вам начислено: <b>{config.REFERRAL_BONUS_STARS} Stars</b>"
            )
    
    welcome_text = (
        f"👋 <b>Добро пожаловать, {message.from_user.full_name}!</b>\n\n"
        f"Я — <b>Диспетчер Хаоса</b>, ваш помощник в управлении подписками.\n\n"
        f"🔹 <b>Что я умею:</b>\n"
        f"• Отслеживать подписки и регулярные платежи\n"
        f"• Напоминать за 7 дней, 3 дня и 1 час до списания\n"
        f"• Рассчитывать «Силу удара по бюджету»\n\n"
        f"🎁 <b>Партнерская программа:</b>\n"
        f"Приглашайте друзей и получайте Stars!\n"
        f"Подробнее: /referral\n\n"
        f"💡 <b>Бесплатно: {config.FREE_SUBSCRIPTIONS_LIMIT} подписки</b>\n"
        f"⭐ Premium: до {config.PREMIUM_SUBSCRIPTIONS_LIMIT} подписок"
    )
    
    keyboard = await get_main_keyboard(user_id)
    await message.answer(welcome_text, reply_markup=keyboard)

async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "📚 <b>Помощь по использованию</b>\n\n"
        "<b>📋 Управление подписками:</b>\n"
        "• /add — добавить новую подписку\n"
        "• /subscriptions — просмотр подписок\n\n"
        "<b>📊 Финансы:</b>\n"
        "• /stats — финансовый обзор\n\n"
        "<b>💳 Тарифы:</b>\n"
        "• /premium — информация о Premium\n\n"
        "<b>🎁 Партнерская программа:</b>\n"
        "• /referral — приглашайте друзей\n\n"
        "<b>❓ Прочее:</b>\n"
        "• /cancel — отменить текущее действие\n"
        "• /support — связаться с поддержкой"
    )
    
    await message.answer(help_text)

async def cmd_cancel(message: types.Message, state: FSMContext):
    """Обработчик команды /cancel"""
    current_state = await state.get_state()
    
    if current_state:
        await state.clear()
        keyboard = await get_main_keyboard(message.from_user.id)
        await message.answer(
            "✅ Действие отменено",
            reply_markup=keyboard
        )
    else:
        await message.answer("Нет активных действий для отмены")

async def cmd_support(message: types.Message):
    """Обработчик команды /support"""
    support_text = (
        "🆘 <b>Поддержка</b>\n\n"
        "Если у вас возникли проблемы или вопросы:\n\n"
        "1️⃣ Проверьте раздел /help\n"
        "2️⃣ Напишите нам: @chaos_support\n"
        "3️⃣ Email: support@chaos-dispatcher.com\n\n"
        "<i>Мы отвечаем в течение 24 часов</i>"
    )
    
    await message.answer(support_text)

async def cmd_stats(message: types.Message):
    """Показывает финансовую статистику пользователя"""
    user_id = message.from_user.id
    
    impact_30 = await SubscriptionService.calculate_budget_impact(user_id, 30)
    impact_7 = await SubscriptionService.calculate_budget_impact(user_id, 7)
    
    subscriptions = await SubscriptionService.get_user_subscriptions(user_id)
    
    if not subscriptions:
        await message.answer("📊 У вас пока нет подписок")
        return
    
    total_monthly = sum(s.amount for s in subscriptions)
    
    stats_text = (
        "📊 <b>Ваша финансовая статистика</b>\n\n"
        f"💥 <b>Сила удара по бюджету:</b>\n"
        f"• За 7 дней: <b>{impact_7:.2f} ₽</b>\n"
        f"• За 30 дней: <b>{impact_30:.2f} ₽</b>\n\n"
        f"💳 <b>Ежемесячные расходы:</b> {total_monthly:.2f} ₽\n"
        f"📋 <b>Количество подписок:</b> {len(subscriptions)}\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Подробный обзор", callback_data="financial_overview")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    await message.answer(stats_text, reply_markup=keyboard)

def register_commands(dp: Dispatcher):
    """Регистрирует обработчики команд"""
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(cmd_support, Command("support"))
    dp.message.register(cmd_stats, Command("stats"))
    
    logger.info("Command handlers registered")
