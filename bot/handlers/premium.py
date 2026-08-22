from aiogram import Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, LabeledPrice, PreCheckoutQuery
)
from datetime import datetime, timedelta
from sqlalchemy import select

from bot.database.models import User, Payment
from bot.database.connection import get_async_db
from bot.services.payments import PaymentService
from bot.services.referral_service import ReferralService
from bot.keyboards.inline import get_main_keyboard
from bot.config import config
from bot.utils.logger import logger

async def cmd_premium(message: types.Message):
    """Показывает информацию о Premium"""
    user_id = message.from_user.id
    
    async with get_async_db() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        is_premium = False
        premium_until = None
        
        if user:
            is_premium = user.is_premium()
            premium_until = user.premium_until
        
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
        f"• До {config.FREE_SUBSCRIPTIONS_LIMIT} подписок\n"
        f"• Все базовые функции\n\n"
        f"<b>⭐ Premium (Контроль):</b>\n"
        f"• До {config.PREMIUM_SUBSCRIPTIONS_LIMIT} подписок\n"
        f"• Все функции без ограничений\n"
        f"• Приоритетная поддержка\n\n"
        f"💎 Стоимость: <b>{config.PREMIUM_PRICE_STARS} ⭐ Stars</b>\n"
        f"⏰ Период: {config.PREMIUM_DURATION_DAYS} дней"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    if not is_premium:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"⭐ Оплатить {config.PREMIUM_PRICE_STARS} Stars",
                callback_data="pay_stars"
            )
        ])
    else:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text="⭐ Продлить Premium",
                callback_data="pay_stars"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    ])
    
    await message.answer(text, reply_markup=keyboard)

async def process_stars_payment(callback: CallbackQuery):
    """Создает счет на оплату Stars"""
    user_id = callback.from_user.id
    
    # Создаем инвойс
    invoice_data = await PaymentService.create_stars_invoice(user_id)
    
    # Отправляем счет
    await callback.message.answer_invoice(
        title=invoice_data['title'],
        description=invoice_data['description'],
        payload=invoice_data['payload'],
        currency=invoice_data['currency'],
        prices=invoice_data['prices'],
        provider_token="",  # Для Stars не нужен
        need_email=False,
        need_phone_number=False,
        is_flexible=False
    )
    
    await callback.answer("Счет отправлен! Оплатите через Telegram.")

async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Обрабатывает предварительную проверку платежа"""
    logger.info(f"Pre-checkout query: {pre_checkout_query.currency}, amount: {pre_checkout_query.total_amount}")
    
    # Проверяем, что это Stars
    if pre_checkout_query.currency != "XTR":
        await pre_checkout_query.answer(
            ok=False,
            error_message="Принимаются только Telegram Stars"
        )
        return
    
    # Подтверждаем платеж
    await pre_checkout_query.answer(ok=True)

async def process_successful_payment(message: types.Message):
    """Обрабатывает успешный платеж Stars"""
    payment_info = message.successful_payment
    
    logger.info(f"Successful payment: {payment_info.currency}, amount: {payment_info.total_amount}")
    
    # Обрабатываем платеж
    success = await PaymentService.process_stars_payment(
        user_id=message.from_user.id,
        telegram_payment_charge_id=payment_info.telegram_payment_charge_id,
        provider_payment_charge_id=payment_info.provider_payment_charge_id,
        total_amount=payment_info.total_amount,
        currency=payment_info.currency,
        payload=payment_info.invoice_payload
    )
    
    if success:
        # Начисляем награду рефереру
        try:
            await ReferralService.reward_referrer(message.from_user.id)
        except Exception as e:
            logger.error(f"Error rewarding referrer: {e}", exc_info=True)
        
        # Получаем обновленную информацию
        async with get_async_db() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()
            
            premium_until = user.premium_until if user else None
        
        if premium_until:
            await message.answer(
                "🎉 <b>Premium успешно активирован!</b>\n\n"
                f"⏰ Действует до: <b>{premium_until.strftime('%d.%m.%Y')}</b>\n"
                f"📅 Осталось: <b>{(premium_until - datetime.now()).days} дней</b>\n"
                f"📋 Доступно подписок: <b>{config.PREMIUM_SUBSCRIPTIONS_LIMIT}</b>\n"
                f"⭐ Оплачено: <b>{config.PREMIUM_PRICE_STARS} Stars</b>\n\n"
                "Спасибо за поддержку! 💎"
            )
        else:
            await message.answer(
                "✅ <b>Оплата получена!</b>\n\n"
                "Premium будет активирован в ближайшее время.\n"
                "Если проблема сохраняется, обратитесь в поддержку."
            )
    else:
        await message.answer(
            "❌ Произошла ошибка при активации Premium.\n"
            "Пожалуйста, обратитесь в поддержку."
        )

def register_premium(dp: Dispatcher):
    """Регистрирует обработчики Premium"""
    dp.message.register(cmd_premium, Command("premium"))
    dp.callback_query.register(process_stars_payment, F.data == "pay_stars")
    
    # Обработчики платежей
    dp.pre_checkout_query.register(process_pre_checkout)
    dp.message.register(
        process_successful_payment,
        F.content_type == types.ContentType.SUCCESSFUL_PAYMENT
    )
    
    logger.info("Premium handlers registered (Stars only)")