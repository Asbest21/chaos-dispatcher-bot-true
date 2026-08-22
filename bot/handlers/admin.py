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

# ============ ОСНОВНЫЕ КОМАНДЫ ============

async def cmd_admin(message: types.Message):
    """Главная админ-панель"""
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔️ Недостаточно прав")
        return
    
    await show_admin_panel(message)

async def show_admin_panel(message: types.Message):
    """Показывает админ-панель"""
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
        ],
        [
            InlineKeyboardButton(text="🔙 Закрыть", callback_data="close_admin")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def cmd_stats(message: types.Message):
    """Показывает статистику"""
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔️ Недостаточно прав")
        return
    
    async with get_async_db() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        active_premium = await session.scalar(
            select(func.count(User.id)).where(
                and_(
                    User.tariff == "premium",
                    User.premium_until > datetime.now()
                )
            )
        ) or 0
        total_subscriptions = await session.scalar(
            select(func.count(Subscription.id)).where(Subscription.is_active == True)
        ) or 0
        blocked_users = await session.scalar(
            select(func.count(User.id)).where(User.is_blocked == True)
        ) or 0
        
        week_ago = datetime.now() - timedelta(days=7)
        new_users = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= week_ago)
        ) or 0
    
    text = (
        "📊 <b>Общая статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🆕 Новых за 7 дней: <b>{new_users}</b>\n"
        f"⭐ Активных Premium: <b>{active_premium}</b>\n"
        f"📋 Активных подписок: <b>{total_subscriptions}</b>\n"
        f"🚫 Заблокировано: <b>{blocked_users}</b>\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def cmd_stars_balance(message: types.Message):
    """Показывает баланс Stars"""
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔️ Недостаточно прав")
        return
    
    stats = await PaymentService.get_payment_stats()
    
    text = (
        "⭐ <b>Баланс Stars</b>\n\n"
        f"💰 Всего заработано: <b>{stats['total_revenue_stars']} Stars</b>\n"
        f"👥 Активных Premium: <b>{stats['active_premium']}</b>\n"
        f"📊 Всего пользователей: <b>{stats['total_users']}</b>\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def cmd_users(message: types.Message):
    """Показывает список пользователей"""
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔️ Недостаточно прав")
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
        
        for i, user in enumerate(users, 1):
            premium_status = "⭐" if user.is_premium() else "🔓"
            blocked = "🚫" if user.is_blocked else "✅"
            
            text += (
                f"{i}. {premium_status} {blocked} "
                f"ID: <code>{user.telegram_id}</code>\n"
                f"   @{user.username or 'нет username'}\n"
                f"   📅 {user.created_at.strftime('%d.%m.%Y')}\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def cmd_payments(message: types.Message):
    """Показывает последние платежи"""
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔️ Недостаточно прав")
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
        
        for i, (payment, user) in enumerate(payments, 1):
            status_emoji = "✅" if payment.status == "completed" else "⏳"
            
            text += (
                f"{i}. {status_emoji} {payment.amount} {payment.currency}\n"
                f"   👤 @{user.username or user.telegram_id}\n"
                f"   📅 {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def cmd_give_premium(message: types.Message, command: CommandObject):
    """Выдает Premium пользователю"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    args = command.args.split() if command.args else []
    
    if len(args) < 1:
        await message.answer(
            "📝 Использование:\n"
            "/premium [user_id] [days]\n"
            "Пример: /premium 123456789 30"
        )
        return
    
    try:
        target_user_id = int(args[0])
        days = int(args[1]) if len(args) > 1 else 30
    except ValueError:
        await message.answer("❌ Неверный формат ID")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if user.premium_until and user.premium_until > datetime.now():
            user.premium_until += timedelta(days=days)
        else:
            user.premium_until = datetime.now() + timedelta(days=days)
        
        user.tariff = "premium"
        await session.commit()
        
        try:
            await message.bot.send_message(
                target_user_id,
                f"🎉 <b>Вам выдан Premium!</b>\n\n"
                f"⏰ Действует до: {user.premium_until.strftime('%d.%m.%Y')}\n"
                f"📅 На {days} дней"
            )
        except:
            pass
        
        await message.answer(
            f"✅ Premium выдан пользователю {target_user_id}\n"
            f"⏰ До: {user.premium_until.strftime('%d.%m.%Y')}"
        )

async def cmd_block_user(message: types.Message, command: CommandObject):
    """Блокирует пользователя"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    args = command.args.split() if command.args else []
    
    if not args:
        await message.answer("📝 Использование: /block [user_id]")
        return
    
    try:
        target_user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.is_blocked = True
            await session.commit()
            await message.answer(f"✅ Пользователь {target_user_id} заблокирован")
        else:
            await message.answer("❌ Пользователь не найден")

async def cmd_unblock_user(message: types.Message, command: CommandObject):
    """Разблокирует пользователя"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    args = command.args.split() if command.args else []
    
    if not args:
        await message.answer("📝 Использование: /unblock [user_id]")
        return
    
    try:
        target_user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.is_blocked = False
            await session.commit()
            await message.answer(f"✅ Пользователь {target_user_id} разблокирован")
        else:
            await message.answer("❌ Пользователь не найден")

async def cmd_broadcast(message: types.Message, command: CommandObject):
    """Рассылка сообщений"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    broadcast_text = command.args
    
    if not broadcast_text:
        await message.answer("📝 Использование: /broadcast [текст сообщения]")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.is_blocked == False)
        )
        user_ids = [row[0] for row in result]
    
    success = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            await message.bot.send_message(user_id, broadcast_text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed += 1
    
    await message.answer(
        f"📤 <b>Рассылка завершена</b>\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}\n"
        f"👥 Всего: {len(user_ids)}"
    )

# ============ CALLBACK ОБРАБОТЧИКИ ============

async def admin_stats_callback(callback: CallbackQuery):
    """Обработчик кнопки Статистика"""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    
    await callback.answer()
    
    # Получаем статистику
    async with get_async_db() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        active_premium = await session.scalar(
            select(func.count(User.id)).where(
                and_(
                    User.tariff == "premium",
                    User.premium_until > datetime.now()
                )
            )
        ) or 0
        total_subscriptions = await session.scalar(
            select(func.count(Subscription.id)).where(Subscription.is_active == True)
        ) or 0
    
    text = (
        "📊 <b>Общая статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"⭐ Активных Premium: <b>{active_premium}</b>\n"
        f"📋 Активных подписок: <b>{total_subscriptions}</b>\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

async def admin_users_callback(callback: CallbackQuery):
    """Обработчик кнопки Пользователи"""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    
    await callback.answer()
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(20)
        )
        users = list(result.scalars().all())
    
    if not users:
        text = "👥 Нет пользователей"
    else:
        text = "👥 <b>Последние 20 пользователей:</b>\n\n"
        
        for i, user in enumerate(users, 1):
            premium_status = "⭐" if user.is_premium() else "🔓"
            text += (
                f"{i}. {premium_status} "
                f"ID: <code>{user.telegram_id}</code>\n"
                f"   @{user.username or 'нет username'}\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

async def admin_stars_callback(callback: CallbackQuery):
    """Обработчик кнопки Баланс Stars"""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    
    await callback.answer()
    
    stats = await PaymentService.get_payment_stats()
    
    text = (
        "⭐ <b>Баланс Stars</b>\n\n"
        f"💰 Всего заработано: <b>{stats['total_revenue_stars']} Stars</b>\n"
        f"👥 Активных Premium: <b>{stats['active_premium']}</b>\n"
        f"📊 Всего пользователей: <b>{stats['total_users']}</b>\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

async def admin_payments_callback(callback: CallbackQuery):
    """Обработчик кнопки Платежи"""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    
    await callback.answer()
    
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
        
        for i, (payment, user) in enumerate(payments, 1):
            status_emoji = "✅" if payment.status == "completed" else "⏳"
            text += (
                f"{i}. {status_emoji} {payment.amount} {payment.currency}\n"
                f"   👤 @{user.username or user.telegram_id}\n"
                f"   📅 {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

async def back_to_admin_callback(callback: CallbackQuery):
    """Возврат в админ-панель"""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    
    await callback.answer()
    
    text = "🔐 <b>Админ-панель</b>\n\nВыберите действие:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton(text="⭐ Баланс Stars", callback_data="admin_stars"),
            InlineKeyboardButton(text="💰 Платежи", callback_data="admin_payments")
        ],
        [
            InlineKeyboardButton(text="🔙 Закрыть", callback_data="close_admin")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

async def close_admin_callback(callback: CallbackQuery):
    """Закрывает админ-панель"""
    await callback.answer()
    await callback.message.delete()

# ============ РЕГИСТРАЦИЯ ============

def register_admin(dp: Dispatcher):
    """Регистрирует админ-обработчики"""
    # Команды
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(cmd_stats, Command("stats"))
    dp.message.register(cmd_stars_balance, Command("stars_balance"))
    dp.message.register(cmd_users, Command("users"))
    dp.message.register(cmd_payments, Command("payments"))
    dp.message.register(cmd_give_premium, Command("premium"))
    dp.message.register(cmd_block_user, Command("block"))
    dp.message.register(cmd_unblock_user, Command("unblock"))
    dp.message.register(cmd_broadcast, Command("broadcast"))
    
    # Callback обработчики для кнопок
    dp.callback_query.register(admin_stats_callback, F.data == "admin_stats")
    dp.callback_query.register(admin_users_callback, F.data == "admin_users")
    dp.callback_query.register(admin_stars_callback, F.data == "admin_stars")
    dp.callback_query.register(admin_payments_callback, F.data == "admin_payments")
    dp.callback_query.register(back_to_admin_callback, F.data == "back_to_admin")
    dp.callback_query.register(close_admin_callback, F.data == "close_admin")
    
    logger.info("Admin handlers registered")