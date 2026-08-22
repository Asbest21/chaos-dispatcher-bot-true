import asyncio
from aiogram import Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bot.database.models import User, Payment, Subscription
from bot.database.connection import get_async_db
from bot.config import config
from bot.utils.logger import logger
from bot.services.payments import PaymentService

# ЖЕСТКО УКАЖИТЕ ВАШ ID ЗДЕСЬ
ADMIN_IDS = [6226081631, 8300113531]  # ← ВАШИ ID

async def cmd_admin(message: types.Message):
    """Главная админ-панель"""
    user_id = message.from_user.id
    
    # Отладочная информация
    logger.info(f"Admin attempt: user_id={user_id}, admin_ids={ADMIN_IDS}")
    print(f"DEBUG: user_id={user_id}, admin_ids={ADMIN_IDS}")
    
    # Проверка прав
    if user_id not in ADMIN_IDS:
        await message.answer(
            f"⛔️ <b>Недостаточно прав</b>\n\n"
            f"Ваш ID: <code>{user_id}</code>\n"
            f"Доступные админы: <code>{ADMIN_IDS}</code>"
        )
        return
    
    # Если админ
    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="⭐ Баланс Stars", callback_data="admin_stars"),
            InlineKeyboardButton(text="💰 Платежи", callback_data="admin_payments")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def admin_stats_callback(callback: CallbackQuery):
    """Статистика"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    
    async with get_async_db() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        active_premium = await session.scalar(
            select(func.count(User.id)).where(
                and_(User.tariff == "premium", User.premium_until > datetime.now())
            )
        ) or 0
        total_subs = await session.scalar(
            select(func.count(Subscription.id)).where(Subscription.is_active == True)
        ) or 0
    
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"⭐ Premium: <b>{active_premium}</b>\n"
        f"📋 Подписок: <b>{total_subs}</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def admin_users_callback(callback: CallbackQuery):
    """Пользователи"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(20)
        )
        users = list(result.scalars().all())
    
    if not users:
        text = "👥 Нет пользователей"
    else:
        text = "👥 <b>Последние 20 пользователей:</b>\n\n"
        for i, u in enumerate(users, 1):
            prem = "⭐" if u.is_premium() else "🔓"
            text += f"{i}. {prem} ID: <code>{u.telegram_id}</code> @{u.username or '-'}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def admin_stars_callback(callback: CallbackQuery):
    """Баланс Stars"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    stats = await PaymentService.get_payment_stats()
    
    text = (
        "⭐ <b>Баланс Stars</b>\n\n"
        f"💰 Заработано: <b>{stats['total_revenue_stars']} Stars</b>\n"
        f"👥 Premium: <b>{stats['active_premium']}</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def admin_payments_callback(callback: CallbackQuery):
    """Платежи"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(Payment, User)
            .join(User, Payment.user_id == User.id)
            .order_by(Payment.created_at.desc())
            .limit(20)
        )
        payments = list(result.all())
    
    if not payments:
        text = "💰 Нет платежей"
    else:
        text = "💰 <b>Последние 20 платежей:</b>\n\n"
        for i, (p, u) in enumerate(payments, 1):
            text += f"{i}. {p.amount} XTR от @{u.username or u.telegram_id}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def back_to_admin(callback: CallbackQuery):
    """Назад в админку"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    text = "🔐 <b>Админ-панель</b>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="⭐ Баланс Stars", callback_data="admin_stars"),
            InlineKeyboardButton(text="💰 Платежи", callback_data="admin_payments")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

def register_admin(dp: Dispatcher):
    """Регистрирует админ-обработчики"""
    dp.message.register(cmd_admin, Command("admin"))
    dp.callback_query.register(admin_stats_callback, F.data == "admin_stats")
    dp.callback_query.register(admin_users_callback, F.data == "admin_users")
    dp.callback_query.register(admin_stars_callback, F.data == "admin_stars")
    dp.callback_query.register(admin_payments_callback, F.data == "admin_payments")
    dp.callback_query.register(back_to_admin, F.data == "back_to_admin")
    
    logger.info(f"Admin handlers registered. Admins: {ADMIN_IDS}")
