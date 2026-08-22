from aiogram import Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
from sqlalchemy import select

from bot.database.models import User
from bot.database.connection import get_async_db
from bot.services.referral_service import ReferralService
from bot.services.subscription_service import SubscriptionService
from bot.config import config
from bot.utils.logger import logger

async def cmd_referral(message: types.Message):
    """Показывает реферальную программу"""
    user_id = message.from_user.id
    
    # Создаем пользователя если его нет
    user = await SubscriptionService.get_or_create_user(
        user_id=user_id,
        username=message.from_user.username if hasattr(message.from_user, 'username') else None,
        full_name=message.from_user.full_name if hasattr(message.from_user, 'full_name') else None
    )
    
    if not user:
        # Пробуем создать напрямую
        async with get_async_db() as session:
            new_user = User(
                telegram_id=user_id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
                language="ru",
                tariff="free",
                total_payments=0.0,
                is_blocked=False
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            user = new_user
    
    # Получаем или создаем реферальный код
    code = await ReferralService.get_or_create_referral_code(user_id)
    
    if not code:
        await message.answer(
            "❌ Ошибка создания реферального кода.\n"
            "Пожалуйста, отправьте /start и попробуйте снова."
        )
        return
    
    # Получаем username бота
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    
    # Получаем статистику
    stats = await ReferralService.get_referral_stats(user_id, bot_username)
    
    referral_link = stats.get('referral_link', '')
    
    text = (
        "🎁 <b>Партнерская программа</b>\n\n"
        f"👥 Вы пригласили: <b>{stats['total_referrals']} чел.</b>\n"
        f"⭐ Активных Premium: <b>{stats['active_referrals']} чел.</b>\n"
        f"💰 Баланс: <b>{stats['balance']} Stars</b>\n\n"
        f"<b>Как это работает:</b>\n"
        f"1️⃣ Поделитесь ссылкой\n"
        f"2️⃣ Друг регистрируется по ссылке\n"
        f"3️⃣ Вы получаете <b>{config.REFERRAL_BONUS_STARS} Stars</b> за регистрацию\n"
        f"4️⃣ Когда друг покупает Premium, вы получаете <b>{config.REFERRAL_REWARD_STARS} Stars</b>\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"📝 <b>Ваш код:</b> <code>{code}</code>\n\n"
        f"💎 Минимум для вывода: {stats['min_payout']} Stars"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📤 Поделиться ссылкой",
                url=f"https://t.me/share/url?url={referral_link}&text=🎁 Попробуй Диспетчер Хаоса — управляй подписками!"
            )
        ],
        [
            InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals"),
            InlineKeyboardButton(text="📊 Топ рефереров", callback_data="top_referrals")
        ],
        [
            InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def show_my_referrals(callback: CallbackQuery):
    """Показывает список рефералов пользователя"""
    user_id = callback.from_user.id
    
    # Убедимся, что пользователь существует
    await SubscriptionService.get_or_create_user(
        user_id=user_id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name
    )
    
    referrals = await ReferralService.get_user_referrals(user_id)
    
    if not referrals:
        text = "👥 У вас пока нет рефералов\n\nПоделитесь ссылкой, чтобы пригласить друзей!"
    else:
        text = f"👥 <b>Ваши рефералы ({len(referrals)}):</b>\n\n"
        
        for i, ref in enumerate(referrals, 1):
            premium = "⭐" if ref.is_premium() else "🔓"
            text += (
                f"{i}. {premium} @{ref.username or 'нет username'}\n"
                f"   📅 {ref.created_at.strftime('%d.%m.%Y')}\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_referral")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def show_top_referrals(callback: CallbackQuery):
    """Показывает топ рефереров"""
    top_referrers = await ReferralService.get_top_referrals(10)
    
    if not top_referrers:
        text = "📊 Пока нет рефереров"
    else:
        text = "🏆 <b>Топ рефереров:</b>\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        
        for i, user in enumerate(top_referrers, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            text += (
                f"{medal} @{user.username or 'нет username'}\n"
                f"   👥 Рефералов: {user.active_referrals}\n"
                f"   💰 Заработано: {user.referral_balance} Stars\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_referral")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def back_to_referral(callback: CallbackQuery):
    """Возврат в реферальное меню"""
    await cmd_referral(callback.message)
    await callback.answer()

def register_referral(dp: Dispatcher):
    """Регистрирует обработчики реферальной программы"""
    dp.message.register(cmd_referral, Command("referral"))
    dp.message.register(cmd_referral, Command("ref"))
    
    # Callback обработчики
    dp.callback_query.register(show_my_referrals, F.data == "my_referrals")
    dp.callback_query.register(show_top_referrals, F.data == "top_referrals")
    dp.callback_query.register(back_to_referral, F.data == "back_to_referral")
    
    logger.info("Referral handlers registered")