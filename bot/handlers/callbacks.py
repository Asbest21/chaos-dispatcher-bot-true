from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from sqlalchemy import select, func

from bot.database.models import User, Subscription
from bot.database.connection import get_async_db
from bot.services.subscription_service import SubscriptionService
from bot.keyboards.inline import get_main_keyboard
from bot.utils.logger import logger
from bot.config import config

async def show_subscriptions(callback: CallbackQuery):
    """Показывает подписки пользователя"""
    user_id = callback.from_user.id
    
    subscriptions = await SubscriptionService.get_user_subscriptions(user_id)
    
    if not subscriptions:
        text = "📋 <b>У вас пока нет подписок</b>\n\nНажмите «➕ Добавить», чтобы начать"
    else:
        text = "📋 <b>Ваши подписки:</b>\n\n"
        total = 0
        
        for i, sub in enumerate(subscriptions, 1):
            next_date = SubscriptionService.calculate_next_billing_date(sub.billing_day)
            days_left = (next_date - datetime.now()).days
            
            text += (
                f"{i}. <b>{sub.name}</b>\n"
                f"   💰 {sub.amount:.2f} ₽ | 📅 {sub.billing_day} числа\n"
                f"   ⏰ Через {days_left} дн. ({next_date.strftime('%d.%m')})\n\n"
            )
            total += sub.amount
        
        text += f"💳 <b>Итого в месяц: {total:.2f} ₽</b>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="add_subscription"),
            InlineKeyboardButton(text="❌ Удалить", callback_data="delete_subscription")
        ],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def show_financial_overview(callback: CallbackQuery):
    """Показывает финансовый обзор"""
    user_id = callback.from_user.id
    
    impact_30 = await SubscriptionService.calculate_budget_impact(user_id, 30)
    impact_7 = await SubscriptionService.calculate_budget_impact(user_id, 7)
    
    subscriptions = await SubscriptionService.get_user_subscriptions(user_id)
    
    if not subscriptions:
        text = "📊 <b>Финансовый обзор</b>\n\nУ вас пока нет подписок"
    else:
        total_monthly = sum(s.amount for s in subscriptions)
        
        text = (
            "📊 <b>Финансовый обзор</b>\n\n"
            f"💥 <b>Сила удара по бюджету:</b>\n"
            f"• За 7 дней: <b>{impact_7:.2f} ₽</b>\n"
            f"• За 30 дней: <b>{impact_30:.2f} ₽</b>\n\n"
            f"💳 <b>Ежемесячные расходы:</b> {total_monthly:.2f} ₽\n"
            f"📋 <b>Количество подписок:</b> {len(subscriptions)}\n\n"
            "<b>Ближайшие списания:</b>\n"
        )
        
        sorted_subs = sorted(
            subscriptions,
            key=lambda s: SubscriptionService.calculate_next_billing_date(s.billing_day)
        )
        
        for sub in sorted_subs[:5]:
            next_date = SubscriptionService.calculate_next_billing_date(sub.billing_day)
            days_left = (next_date - datetime.now()).days
            text += f"• {sub.name}: {sub.amount:.2f} ₽ (через {days_left} дн.)\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def show_tariff_info(callback: CallbackQuery):
    """Показывает информацию о тарифе"""
    user_id = callback.from_user.id
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        is_premium = user.is_premium() if user else False
        premium_until = user.premium_until if user else None
    
    if is_premium and premium_until:
        days_left = (premium_until - datetime.now()).days
        status = (
            f"✅ Premium активен\n"
            f"⏰ Действует до: {premium_until.strftime('%d.%m.%Y')}\n"
            f"📅 Осталось: {days_left} дней"
        )
    else:
        status = "🔓 Бесплатный тариф"
    
    text = (
        f"💳 <b>Тарифы</b>\n\n"
        f"Текущий статус:\n{status}\n\n"
        f"<b>🔓 Бесплатный:</b>\n"
        f"• {config.FREE_SUBSCRIPTIONS_LIMIT} подписки\n\n"
        f"<b>⭐ Premium:</b>\n"
        f"• {config.PREMIUM_SUBSCRIPTIONS_LIMIT} подписок\n"
        f"• {config.PREMIUM_PRICE_STARS} Stars / {config.PREMIUM_DURATION_DAYS} дней\n\n"
    )
    
    keyboard = []
    if not is_premium:
        keyboard.append([
            InlineKeyboardButton(
                text=f"⭐ Оплатить {config.PREMIUM_PRICE_STARS} Stars",
                callback_data="pay_stars"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text="⭐ Продлить Premium",
                callback_data="pay_stars"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

async def delete_subscription_menu(callback: CallbackQuery):
    """Показывает меню удаления подписок"""
    user_id = callback.from_user.id
    
    subscriptions = await SubscriptionService.get_user_subscriptions(user_id)
    
    if not subscriptions:
        keyboard = await get_main_keyboard(user_id)
        await callback.message.edit_text(
            "📋 У вас нет подписок для удаления",
            reply_markup=keyboard
        )
    else:
        text = "🗑 <b>Выберите подписку для удаления:</b>\n\n"
        keyboard = []
        
        for i, sub in enumerate(subscriptions, 1):
            text += f"{i}. {sub.name} - {sub.amount:.2f} ₽\n"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ {sub.name}",
                    callback_data=f"confirm_delete_{sub.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    
    await callback.answer()

async def confirm_delete(callback: CallbackQuery):
    """Подтверждает удаление подписки"""
    subscription_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    success = await SubscriptionService.delete_subscription(user_id, subscription_id)
    
    if success:
        keyboard = await get_main_keyboard(user_id)
        await callback.message.edit_text(
            "✅ Подписка удалена!",
            reply_markup=keyboard
        )
    else:
        await callback.answer("Ошибка удаления", show_alert=True)
    
    await callback.answer()

async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    keyboard = await get_main_keyboard(callback.from_user.id)
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

async def show_help(callback: CallbackQuery):
    """Показывает помощь"""
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "<b>📋 Добавление подписки:</b>\n"
        "1. Нажмите «➕ Добавить»\n"
        "2. Введите название\n"
        "3. Укажите сумму\n"
        "4. Выберите дату списания\n\n"
        "<b>⚠️ Уведомления:</b>\n"
        "• За 7 дней\n"
        "• За 3 дня\n"
        "• За 1 час\n\n"
        "<b>💥 Сила удара:</b>\n"
        "Сумма всех списаний за период\n\n"
        "<b>💳 Тарифы:</b>\n"
        f"• Бесплатный: {config.FREE_SUBSCRIPTIONS_LIMIT} подписки\n"
        f"• Premium: {config.PREMIUM_SUBSCRIPTIONS_LIMIT} подписок\n\n"
        "<b>🎁 Партнерская программа:</b>\n"
        "Приглашайте друзей и получайте Stars!\n"
        "Подробнее: /referral"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def show_referral_program(callback: CallbackQuery):
    """Показывает реферальную программу"""
    from bot.services.subscription_service import SubscriptionService
    from bot.services.referral_service import ReferralService
    
    user_id = callback.from_user.id
    
    # Создаем пользователя если его нет
    await SubscriptionService.get_or_create_user(
        user_id=user_id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name
    )
    
    # Получаем или создаем реферальный код
    code = await ReferralService.get_or_create_referral_code(user_id)
    
    if not code:
        await callback.message.edit_text(
            "❌ Ошибка. Пожалуйста, отправьте /start и попробуйте снова.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return
    
    # Получаем username бота
    bot_info = await callback.message.bot.get_me()
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
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

async def add_subscription_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки добавления подписки"""
    from bot.handlers.subscriptions import SubscriptionStates
    
    user_id = callback.from_user.id
    
    # Проверяем возможность добавления
    can_add, error = await SubscriptionService.can_add_subscription(user_id)
    
    if not can_add:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Оформить Premium", callback_data="tariff_info")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
        ])
        await callback.message.edit_text(f"❌ {error}", reply_markup=keyboard)
        await callback.answer()
        return
    
    await state.set_state(SubscriptionStates.waiting_name)
    await callback.message.edit_text(
        "📝 <b>Добавление подписки</b>\n\n"
        "Введите название подписки:\n"
        "<i>Например: Netflix, Spotify, Интернет</i>"
    )
    await callback.answer()

def register_callbacks(dp: Dispatcher):
    """Регистрирует обработчики callback-запросов"""
    # Основные кнопки меню
    dp.callback_query.register(show_subscriptions, F.data == "my_subscriptions")
    dp.callback_query.register(show_financial_overview, F.data == "financial_overview")
    dp.callback_query.register(show_tariff_info, F.data == "tariff_info")
    dp.callback_query.register(delete_subscription_menu, F.data == "delete_subscription")
    dp.callback_query.register(back_to_main, F.data == "back_to_main")
    dp.callback_query.register(show_help, F.data == "help")
    
    # Кнопка добавления подписки
    dp.callback_query.register(add_subscription_callback, F.data == "add_subscription")
    
    # Кнопка реферальной программы
    dp.callback_query.register(show_referral_program, F.data == "referral_program")
    
    # Удаление подписки
    dp.callback_query.register(confirm_delete, F.data.startswith("confirm_delete_"))
    
    logger.info("Callback handlers registered")