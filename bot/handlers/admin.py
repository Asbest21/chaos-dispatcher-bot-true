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

# ЖЕСТКО УКАЖИТЕ ВАШ ID
ADMIN_IDS = [6226081631, 8300113531]

# ============ ГЛАВНАЯ АДМИН-ПАНЕЛЬ ============

async def cmd_admin(message: types.Message):
    """Главная админ-панель"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer(
            f"⛔️ <b>Недостаточно прав</b>\n\n"
            f"Ваш ID: <code>{user_id}</code>"
        )
        return
    
    text = (
        "🔐 <b>Админ-панель «Диспетчер Хаоса»</b>\n\n"
        "Выбери раздел:"
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
            InlineKeyboardButton(text="📋 Подписки", callback_data="admin_subscriptions"),
            InlineKeyboardButton(text="🎁 Рефералы", callback_data="admin_referrals")
        ],
        [
            InlineKeyboardButton(text="🔧 Действия", callback_data="admin_actions"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close_admin")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard)

# ============ СТАТИСТИКА ============

async def admin_stats_callback(callback: CallbackQuery):
    """Общая статистика"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    
    async with get_async_db() as session:
        # Основная статистика
        total_users = await session.scalar(select(func.count(User.id))) or 0
        active_premium = await session.scalar(
            select(func.count(User.id)).where(
                and_(User.tariff == "premium", User.premium_until > datetime.now())
            )
        ) or 0
        blocked_users = await session.scalar(
            select(func.count(User.id)).where(User.is_blocked == True)
        ) or 0
        
        # Подписки
        total_subs = await session.scalar(
            select(func.count(Subscription.id)).where(Subscription.is_active == True)
        ) or 0
        
        # Новые пользователи
        week_ago = datetime.now() - timedelta(days=7)
        new_users_week = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= week_ago)
        ) or 0
        
        day_ago = datetime.now() - timedelta(days=1)
        new_users_day = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= day_ago)
        ) or 0
    
    # Платежи
    payment_stats = await PaymentService.get_payment_stats()
    
    text = (
        "📊 <b>Общая статистика</b>\n\n"
        "<b>👥 Пользователи:</b>\n"
        f"• Всего: <b>{total_users}</b>\n"
        f"• Новых за 24ч: <b>{new_users_day}</b>\n"
        f"• Новых за 7 дней: <b>{new_users_week}</b>\n"
        f"• Заблокировано: <b>{blocked_users}</b>\n\n"
        "<b>⭐ Premium:</b>\n"
        f"• Активных: <b>{active_premium}</b>\n\n"
        "<b>📋 Подписки:</b>\n"
        f"• Активных: <b>{total_subs}</b>\n\n"
        "<b>💰 Финансы:</b>\n"
        f"• Всего Stars: <b>{payment_stats['total_revenue_stars']}</b>\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============ ПОЛЬЗОВАТЕЛИ ============

async def admin_users_callback(callback: CallbackQuery):
    """Список пользователей"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(30)
        )
        users = list(result.scalars().all())
    
    if not users:
        text = "👥 Нет пользователей"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
        ])
    else:
        text = f"👥 <b>Последние {len(users)} пользователей:</b>\n\n"
        
        for i, u in enumerate(users, 1):
            prem = "⭐" if u.is_premium() else "🔓"
            block = "🚫" if u.is_blocked else "✅"
            
            text += (
                f"{i}. {prem}{block} ID: <code>{u.telegram_id}</code>\n"
                f"   @{u.username or 'нет username'}\n"
                f"   📅 {u.created_at.strftime('%d.%m.%Y')}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
        ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============ БАЛАНС STARS ============

async def admin_stars_callback(callback: CallbackQuery):
    """Баланс Stars"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    stats = await PaymentService.get_payment_stats()
    
    # Статистика за 30 дней
    async with get_async_db() as session:
        month_ago = datetime.now() - timedelta(days=30)
        month_payments = await session.scalar(
            select(func.sum(Payment.amount)).where(
                and_(
                    Payment.status == "completed",
                    Payment.completed_at >= month_ago
                )
            )
        ) or 0
        
        week_ago = datetime.now() - timedelta(days=7)
        week_payments = await session.scalar(
            select(func.sum(Payment.amount)).where(
                and_(
                    Payment.status == "completed",
                    Payment.completed_at >= week_ago
                )
            )
        ) or 0
    
    text = (
        "⭐ <b>Баланс Stars</b>\n\n"
        f"💰 <b>Всего заработано:</b> {stats['total_revenue_stars']} Stars\n"
        f"📅 <b>За 30 дней:</b> {month_payments} Stars\n"
        f"📆 <b>За 7 дней:</b> {week_payments} Stars\n\n"
        f"👥 <b>Активных Premium:</b> {stats['active_premium']}\n"
        f"📊 <b>Всего пользователей:</b> {stats['total_users']}\n\n"
        f"💎 <b>Конверсия:</b> {round((stats['active_premium'] / max(stats['total_users'], 1)) * 100, 1)}%"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============ ПЛАТЕЖИ ============

async def admin_payments_callback(callback: CallbackQuery):
    """История платежей"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(Payment, User)
            .join(User, Payment.user_id == User.id)
            .order_by(Payment.created_at.desc())
            .limit(30)
        )
        payments = list(result.all())
    
    if not payments:
        text = "💰 Нет платежей"
    else:
        text = "💰 <b>Последние 30 платежей:</b>\n\n"
        
        total_amount = 0
        for i, (p, u) in enumerate(payments, 1):
            status = "✅" if p.status == "completed" else "⏳"
            text += (
                f"{i}. {status} {p.amount} {p.currency}\n"
                f"   👤 @{u.username or u.telegram_id}\n"
                f"   📅 {p.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
            total_amount += p.amount
        
        text += f"💎 <b>Итого за период:</b> {total_amount} Stars"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============ ПОДПИСКИ ============

async def admin_subscriptions_callback(callback: CallbackQuery):
    """Все подписки"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(Subscription, User)
            .join(User, Subscription.user_id == User.id)
            .where(Subscription.is_active == True)
            .order_by(Subscription.created_at.desc())
            .limit(30)
        )
        subs = list(result.all())
    
    if not subs:
        text = "📋 Нет активных подписок"
    else:
        text = f"📋 <b>Последние {len(subs)} подписок:</b>\n\n"
        
        total = 0
        for i, (s, u) in enumerate(subs, 1):
            text += (
                f"{i}. <b>{s.name}</b>\n"
                f"   💰 {s.amount:.2f} ₽ | 📅 {s.billing_day} числа\n"
                f"   👤 @{u.username or u.telegram_id}\n\n"
            )
            total += s.amount
        
        text += f"💳 <b>Всего в месяц:</b> {total:.2f} ₽"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============ РЕФЕРАЛЫ ============

async def admin_referrals_callback(callback: CallbackQuery):
    """Топ рефералов"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User)
            .where(User.total_referrals > 0)
            .order_by(User.total_referrals.desc())
            .limit(20)
        )
        referrers = list(result.scalars().all())
    
    if not referrers:
        text = "🎁 Нет рефералов"
    else:
        text = "🎁 <b>Топ рефереров:</b>\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, u in enumerate(referrers, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            text += (
                f"{medal} @{u.username or 'нет username'}\n"
                f"   👥 Рефералов: {u.total_referrals}\n"
                f"   ⭐ Активных: {u.active_referrals}\n"
                f"   💰 Баланс: {u.referral_balance} Stars\n\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============ ДЕЙСТВИЯ ============

async def admin_actions_callback(callback: CallbackQuery):
    """Меню действий"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    text = (
        "🔧 <b>Действия</b>\n\n"
        "Выберите действие:\n\n"
        "<b>Команды:</b>\n"
        "/prem [user_id] [days] — выдать Premium\n"
        "/block [user_id] — заблокировать\n"
        "/unblock [user_id] — разблокировать\n"
        "/broadcast [текст] — рассылка\n"
        "/user_info [user_id] — инфо о пользователе"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def admin_broadcast_callback(callback: CallbackQuery):
    """Информация о рассылке"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    text = (
        "📢 <b>Рассылка</b>\n\n"
        "Используйте команду:\n"
        "<code>/broadcast [текст сообщения]</code>\n\n"
        "Пример:\n"
        "<code>/broadcast Новое обновление бота!</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============ КОМАНДЫ ============

async def cmd_give_premium(message: types.Message, command: CommandObject):
    """Выдает Premium: /premium [user_id] [days]"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = command.args.split() if command.args else []
    
    if len(args) < 1:
        await message.answer(
            "📝 <b>Выдача Premium</b>\n\n"
            "Использование:\n"
            "<code>/prem [user_id] [days]</code>\n\n"
            "Пример:\n"
            "<code>/prem 123456789 30</code>"
        )
        return
    
    try:
        target_id = int(args[0])
        days = int(args[1]) if len(args) > 1 else 30
    except ValueError:
        await message.answer("❌ Неверный формат ID")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(f"❌ Пользователь {target_id} не найден")
            return
        
        if user.premium_until and user.premium_until > datetime.now():
            user.premium_until += timedelta(days=days)
        else:
            user.premium_until = datetime.now() + timedelta(days=days)
        
        user.tariff = "premium"
        await session.commit()
        
        # Уведомляем пользователя
        try:
            await message.bot.send_message(
                target_id,
                f"🎉 <b>Вам выдан Premium!</b>\n\n"
                f"⏰ До: {user.premium_until.strftime('%d.%m.%Y')}\n"
                f"📅 На {days} дней"
            )
        except:
            pass
        
        await message.answer(
            f"✅ Premium выдан пользователю {target_id}\n"
            f"⏰ До: {user.premium_until.strftime('%d.%m.%Y')}"
        )

async def cmd_block_user(message: types.Message, command: CommandObject):
    """Блокирует: /block [user_id]"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = command.args.split() if command.args else []
    
    if not args:
        await message.answer("📝 Использование: <code>/block [user_id]</code>")
        return
    
    try:
        target_id = int(args[0])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.is_blocked = True
            await session.commit()
            await message.answer(f"✅ Пользователь {target_id} заблокирован")
        else:
            await message.answer("❌ Пользователь не найден")

async def cmd_unblock_user(message: types.Message, command: CommandObject):
    """Разблокирует: /unblock [user_id]"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = command.args.split() if command.args else []
    
    if not args:
        await message.answer("📝 Использование: <code>/unblock [user_id]</code>")
        return
    
    try:
        target_id = int(args[0])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.is_blocked = False
            await session.commit()
            await message.answer(f"✅ Пользователь {target_id} разблокирован")
        else:
            await message.answer("❌ Пользователь не найден")

async def cmd_broadcast(message: types.Message, command: CommandObject):
    """Рассылка: /broadcast [текст]"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    text = command.args
    
    if not text:
        await message.answer("📝 Использование: <code>/broadcast [текст]</code>")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.is_blocked == False)
        )
        user_ids = [row[0] for row in result]
    
    success = 0
    failed = 0
    
    await message.answer(f"📢 Начинаю рассылку для {len(user_ids)} пользователей...")
    
    for user_id in user_ids:
        try:
            await message.bot.send_message(user_id, text)
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await message.answer(
        f"📤 <b>Рассылка завершена</b>\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}\n"
        f"👥 Всего: {len(user_ids)}"
    )

async def cmd_user_info(message: types.Message, command: CommandObject):
    """Информация о пользователе: /user_info [user_id]"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = command.args.split() if command.args else []
    
    if not args:
        await message.answer("📝 Использование: <code>/user_info [user_id]</code>")
        return
    
    try:
        target_id = int(args[0])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        # Подписки пользователя
        subs = await session.execute(
            select(Subscription).where(
                and_(Subscription.user_id == user.id, Subscription.is_active == True)
            )
        )
        subscriptions = list(subs.scalars().all())
        
        # Платежи
        payments = await session.execute(
            select(Payment).where(Payment.user_id == user.id)
        )
        payment_list = list(payments.scalars().all())
    
    premium_status = "⭐ Premium" if user.is_premium() else "🔓 Бесплатный"
    block_status = "🚫 Заблокирован" if user.is_blocked else "✅ Активен"
    
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"ID: <code>{user.telegram_id}</code>\n"
        f"Username: @{user.username or 'нет'}\n"
        f"Имя: {user.full_name or 'нет'}\n"
        f"Тариф: {premium_status}\n"
        f"Статус: {block_status}\n"
        f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
        f"📋 Подписок: {len(subscriptions)}\n"
        f"💰 Платежей: {len(payment_list)}\n"
        f"🎁 Рефералов: {user.total_referrals}\n"
    )
    
    if subscriptions:
        text += "\n<b>Подписки:</b>\n"
        for s in subscriptions[:10]:
            text += f"• {s.name}: {s.amount:.2f} ₽ ({s.billing_day} числа)\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚫 Блокировать", callback_data=f"block_{user.telegram_id}"),
            InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"unblock_{user.telegram_id}")
        ],
        [
            InlineKeyboardButton(text="⭐ Выдать Premium", callback_data=f"giveprem_{user.telegram_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

# ============ ДОПОЛНИТЕЛЬНЫЕ CALLBACKS ============

async def block_user_callback(callback: CallbackQuery):
    """Блокировка через кнопку"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    target_id = int(callback.data.split("_")[1])
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.is_blocked = True
            await session.commit()
    
    await callback.answer(f"Пользователь {target_id} заблокирован", show_alert=True)

async def unblock_user_callback(callback: CallbackQuery):
    """Разблокировка через кнопку"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    target_id = int(callback.data.split("_")[1])
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.is_blocked = False
            await session.commit()
    
    await callback.answer(f"Пользователь {target_id} разблокирован", show_alert=True)

async def give_premium_callback(callback: CallbackQuery):
    """Выдача Premium через кнопку"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    target_id = int(callback.data.split("_")[1])
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == target_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.tariff = "premium"
            user.premium_until = datetime.now() + timedelta(days=30)
            await session.commit()
    
    await callback.answer(f"Premium выдан на 30 дней", show_alert=True)

async def close_admin_callback(callback: CallbackQuery):
    """Закрывает админ-панель"""
    await callback.message.delete()
    await callback.answer()

async def back_to_admin_callback(callback: CallbackQuery):
    """Возврат в админ-панель"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️", show_alert=True)
        return
    
    text = "🔐 <b>Админ-панель</b>\n\nВыберите раздел:"
    
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
            InlineKeyboardButton(text="📋 Подписки", callback_data="admin_subscriptions"),
            InlineKeyboardButton(text="🎁 Рефералы", callback_data="admin_referrals")
        ],
        [
            InlineKeyboardButton(text="🔧 Действия", callback_data="admin_actions"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close_admin")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============ РЕГИСТРАЦИЯ ============

def register_admin(dp: Dispatcher):
    """Регистрирует админ-обработчики"""
    # Команды
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(cmd_give_premium, Command("prem"))
    dp.message.register(cmd_block_user, Command("block"))
    dp.message.register(cmd_unblock_user, Command("unblock"))
    dp.message.register(cmd_broadcast, Command("broadcast"))
    dp.message.register(cmd_user_info, Command("user_info"))
    
    # Callbacks
    dp.callback_query.register(admin_stats_callback, F.data == "admin_stats")
    dp.callback_query.register(admin_users_callback, F.data == "admin_users")
    dp.callback_query.register(admin_stars_callback, F.data == "admin_stars")
    dp.callback_query.register(admin_payments_callback, F.data == "admin_payments")
    dp.callback_query.register(admin_subscriptions_callback, F.data == "admin_subscriptions")
    dp.callback_query.register(admin_referrals_callback, F.data == "admin_referrals")
    dp.callback_query.register(admin_actions_callback, F.data == "admin_actions")
    dp.callback_query.register(admin_broadcast_callback, F.data == "admin_broadcast")
    dp.callback_query.register(back_to_admin_callback, F.data == "back_to_admin")
    dp.callback_query.register(close_admin_callback, F.data == "close_admin")
    dp.callback_query.register(block_user_callback, F.data.startswith("block_"))
    dp.callback_query.register(unblock_user_callback, F.data.startswith("unblock_"))
    dp.callback_query.register(give_premium_callback, F.data.startswith("giveprem_"))
    
    logger.info(f"Admin handlers registered. Admins: {ADMIN_IDS}")
