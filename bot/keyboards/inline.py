from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, func

from bot.database.models import User, Subscription
from bot.database.connection import get_async_db
from bot.config import config

async def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Главное меню"""
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        is_premium = False
        count = 0
        limit = config.FREE_SUBSCRIPTIONS_LIMIT
        
        if user:
            is_premium = user.is_premium()
            limit = user.get_subscription_limit()
            
            count = await session.scalar(
                select(func.count(Subscription.id)).where(
                    Subscription.user_id == user.id,
                    Subscription.is_active == True
                )
            ) or 0
    
    if is_premium:
        tariff_text = f"⭐ Premium ({count}/{limit})"
    else:
        tariff_text = f"🔓 Бесплатный ({count}/{limit})"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📋 Мои подписки", 
                callback_data="my_subscriptions"
            )
        ],
        [
            InlineKeyboardButton(
                text="➕ Добавить", 
                callback_data="add_subscription"
            ),
            InlineKeyboardButton(
                text="❌ Удалить", 
                callback_data="delete_subscription"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Финансовый обзор", 
                callback_data="financial_overview"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"💳 Тариф: {tariff_text}", 
                callback_data="tariff_info"
            )
        ],
        [
            InlineKeyboardButton(
                text="🎁 Партнерская программа", 
                callback_data="referral_program"
            )
        ],
        [
            InlineKeyboardButton(
                text="ℹ️ Помощь", 
                callback_data="help"
            )
        ]
    ])
    
    return keyboard