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
    
    await SubscriptionService.get_or_create_user(
        user_id=user_id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    
    code = await ReferralService.get_or_create_referral_code(user_id)
    
    if not code:
        await message.answer("❌ Ошибка. Отправьте /start")
        return
    
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    
    stats = await ReferralService.get_referral_stats(user_id, bot_username)
    referral_link = stats.get('referral_link', '')
    balance = stats.get('balance', 0)
    premium_cost = stats.get('premium_cost', config.PREMIUM_PRICE_STARS)
    
    text = (
        "🎁 <b>Партнерская программа</b>\n\n"
        f"👥 Вы пригласили: <b>{stats['total_referrals']} чел.</b>\n"
        f"⭐ Активных Premium: <b>{stats['active_referrals']} чел.</b>\n"
        f"💰 Баланс: <b>{balance} Stars</b>\n\n"
        f"<b>Как это работает:</b>\n"
        f"1️⃣ Поделитесь ссылкой с другом\n"
        f"2️⃣ Друг регистрируется (НЕ зарегистрирован ранее)\n"
        f"3️⃣ Вы получаете <b>{config.REFERRAL_REWARD_STARS} Stars</b>\n"
        f"4️⃣ Друг получает <b>{config.REFERRAL_BONUS_STARS} Stars</b>\n"
        f"5️⃣ Когда друг покупает Premium — вы получаете еще <b>{config.REFERRAL_REWARD_STARS} Stars</b>\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"📝 <b>Код:</b> <code>{code}</code>\n\n"
        f"💎 <b>Stars можно тратить только на Premium!</b>\n"
        f"⭐ Стоимость Premium: {premium_cost} Stars\n"
        f"Вывод Stars недоступен."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📤 Поделиться ссылкой",
                url=f"https://t.me/share/url?url={referral_link}&text=🎁 Попробуй Диспетчер Хаоса! Получи {config.REFERRAL_BONUS_STARS} Stars!"
            )
        ],
        [
            InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals"),
            InlineKeyboardButton(text="📊 Топ рефереров", callback_data="top_referrals")
        ],
        [
            InlineKeyboardButton(
                text=f"⭐ Потратить Stars на Premium ({premium_cost} Stars)",
                callback_data="spend_stars"
            )
        ],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def spend_stars_callback(callback: CallbackQuery):
    """Тратит Stars на Premium"""
    user_id = callback.from_user.id
    
    success, message = await ReferralService.spend_stars_on_premium(user_id)
    
    if success:
        await callback.message.edit_text(
            f"🎉 <b>{message}</b>\n\n"
            f"Premium активирован!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_referral")]
            ])
        )
    else:
        await callback.answer(message, show_alert=True)

async def show_my_referrals(callback: CallbackQuery):
    """Показывает список рефералов"""
    user_id = callback.from_user.id
    
    referrals = await ReferralService.get_user_referrals(user_id)
    
    if not referrals:
        text = "👥 У вас пока нет рефералов\n\nПоделитесь ссылкой!"
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
                f"   👥 Рефералов: {user.total_referrals}\n"
                f"   💰 Баланс: {user.referral_balance} Stars\n\n"
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
    """Регистрирует обработчики"""
    dp.message.register(cmd_referral, Command("referral"))
    dp.message.register(cmd_referral, Command("ref"))
    dp.callback_query.register(spend_stars_callback, F.data == "spend_stars")
    dp.callback_query.register(show_my_referrals, F.data == "my_referrals")
    dp.callback_query.register(show_top_referrals, F.data == "top_referrals")
    dp.callback_query.register(back_to_referral, F.data == "back_to_referral")
    
    logger.info("Referral handlers registered")
