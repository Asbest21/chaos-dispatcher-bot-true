from aiogram import Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime

from bot.database.models import User, Subscription
from bot.database.connection import get_async_db
from bot.services.subscription_service import SubscriptionService
from bot.keyboards.inline import get_main_keyboard
from bot.utils.logger import logger
from bot.config import config
# from bot.main import bot  # ❌ УДАЛЕНО!

class SubscriptionStates(StatesGroup):
    waiting_name = State()
    waiting_amount = State()
    waiting_date = State()
    waiting_confirm = State()

async def cmd_add_subscription(message: types.Message, state: FSMContext):
    """Обработчик команды /add"""
    user_id = message.from_user.id
    
    can_add, error = await SubscriptionService.can_add_subscription(user_id)
    
    if not can_add:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Оформить Premium", callback_data="tariff_info")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
        ])
        await message.answer(f"❌ {error}", reply_markup=keyboard)
        return
    
    await state.set_state(SubscriptionStates.waiting_name)
    await message.answer(
        "📝 <b>Добавление подписки</b>\n\n"
        "Введите название подписки:\n"
        "<i>Например: Netflix, Spotify, Интернет</i>"
    )

async def process_name(message: types.Message, state: FSMContext):
    """Обрабатывает название подписки"""
    if not message.text or len(message.text) > 100:
        await message.answer("❌ Название должно быть от 1 до 100 символов")
        return
    
    await state.update_data(name=message.text.strip())
    await state.set_state(SubscriptionStates.waiting_amount)
    
    await message.answer(
        f"💰 Введите сумму списания для <b>{message.text}</b>:\n"
        "<i>Например: 299, 599.90, 1290</i>"
    )

async def process_amount(message: types.Message, state: FSMContext):
    """Обрабатывает сумму подписки"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0 or amount > 10000000:
            raise ValueError
        
        await state.update_data(amount=amount)
        await state.set_state(SubscriptionStates.waiting_date)
        
        await message.answer(
            "📅 Введите день месяца для списания (1-31):\n"
            "<i>Например: 15 — списание 15 числа каждого месяца</i>"
        )
    except ValueError:
        await message.answer("❌ Введите корректную сумму")

async def process_date(message: types.Message, state: FSMContext):
    """Обрабатывает дату списания"""
    try:
        billing_day = int(message.text)
        if billing_day < 1 or billing_day > 31:
            raise ValueError
        
        data = await state.get_data()
        await state.update_data(billing_day=billing_day)
        await state.set_state(SubscriptionStates.waiting_confirm)
        
        next_date = SubscriptionService.calculate_next_billing_date(billing_day)
        
        confirm_text = (
            "✅ <b>Проверьте данные:</b>\n\n"
            f"📝 Название: <b>{data['name']}</b>\n"
            f"💰 Сумма: <b>{data['amount']:.2f} ₽</b>\n"
            f"📅 День списания: <b>{billing_day} числа</b>\n"
            f"⏰ Следующее списание: <b>{next_date.strftime('%d.%m.%Y')}</b>\n\n"
            "Всё верно?"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_subscription"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_subscription")
            ]
        ])
        
        await message.answer(confirm_text, reply_markup=keyboard)
        
    except ValueError:
        await message.answer("❌ Введите число от 1 до 31")

async def confirm_subscription(callback: CallbackQuery, state: FSMContext):
    """Подтверждает добавление подписки"""
    data = await state.get_data()
    user_id = callback.from_user.id
    
    try:
        subscription = await SubscriptionService.add_subscription(
            user_id=user_id,
            name=data['name'],
            amount=data['amount'],
            billing_day=data['billing_day']
        )
        
        await state.clear()
        
        success_text = (
            "🎉 <b>Подписка добавлена!</b>\n\n"
            f"📝 {subscription.name}\n"
            f"💰 {subscription.amount:.2f} ₽\n"
            f"📅 Списание: {subscription.billing_day} числа\n\n"
            "⚠️ Буду напоминать:\n"
            "• За 7 дней до списания\n"
            "• За 3 дня до списания\n"
            "• За 1 час до списания"
        )
        
        await callback.message.edit_text(success_text)
        
        keyboard = await get_main_keyboard(user_id)
        await callback.message.answer(
            "Выберите следующее действие:",
            reply_markup=keyboard
        )
        
    except ValueError as e:
        await callback.message.edit_text(f"❌ {str(e)}")
    
    await callback.answer()

async def cancel_subscription(callback: CallbackQuery, state: FSMContext):
    """Отменяет добавление подписки"""
    await state.clear()
    keyboard = await get_main_keyboard(callback.from_user.id)
    await callback.message.edit_text(
        "❌ Добавление отменено",
        reply_markup=keyboard
    )
    await callback.answer()

def register_subscriptions(dp: Dispatcher):
    """Регистрирует обработчики подписок"""
    dp.message.register(cmd_add_subscription, Command("add"))
    dp.message.register(process_name, SubscriptionStates.waiting_name)
    dp.message.register(process_amount, SubscriptionStates.waiting_amount)
    dp.message.register(process_date, SubscriptionStates.waiting_date)
    dp.callback_query.register(confirm_subscription, F.data == "confirm_subscription")
    dp.callback_query.register(cancel_subscription, F.data == "cancel_subscription")
    
    logger.info("Subscription handlers registered")
