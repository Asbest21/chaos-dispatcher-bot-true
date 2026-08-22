"""
Полный бот для Bothost.ru
Включает: подписки, Premium, рефералку, админку
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
import calendar

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Импорты aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, LabeledPrice, PreCheckoutQuery
)

# База данных
import sqlite3
from contextlib import contextmanager

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
FREE_LIMIT = int(os.getenv("FREE_SUBSCRIPTIONS_LIMIT", "2"))
PREMIUM_LIMIT = int(os.getenv("PREMIUM_SUBSCRIPTIONS_LIMIT", "30"))
PREMIUM_PRICE = int(os.getenv("PREMIUM_PRICE_STARS", "25"))
PREMIUM_DAYS = int(os.getenv("PREMIUM_DURATION_DAYS", "30"))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN не указан!")
    sys.exit(1)

# Инициализация
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# ============ БАЗА ДАННЫХ ============

DB_PATH = "data/chaos.db"

def init_db():
    """Инициализация базы данных"""
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            full_name TEXT,
            tariff TEXT DEFAULT 'free',
            premium_until DATETIME,
            referral_code TEXT UNIQUE,
            referral_balance REAL DEFAULT 0,
            total_referrals INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица подписок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            billing_day INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Таблица платежей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            currency TEXT DEFAULT 'XTR',
            status TEXT DEFAULT 'completed',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

@contextmanager
def get_db():
    """Контекстный менеджер для БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def get_or_create_user(telegram_id, username=None, full_name=None):
    """Получает или создает пользователя"""
    with get_db() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE telegram_id = ?', 
            (telegram_id,)
        ).fetchone()
        
        if not user:
            conn.execute(
                'INSERT INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)',
                (telegram_id, username, full_name)
            )
            user = conn.execute(
                'SELECT * FROM users WHERE telegram_id = ?', 
                (telegram_id,)
            ).fetchone()
        
        return user

def is_premium(telegram_id):
    """Проверяет Premium статус"""
    with get_db() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE telegram_id = ?',
            (telegram_id,)
        ).fetchone()
        
        if user and user['tariff'] == 'premium' and user['premium_until']:
            premium_until = datetime.fromisoformat(user['premium_until'])
            if premium_until > datetime.now():
                return True
    return False

def get_subscription_count(telegram_id):
    """Считает подписки пользователя"""
    with get_db() as conn:
        user = get_or_create_user(telegram_id)
        count = conn.execute(
            'SELECT COUNT(*) as count FROM subscriptions WHERE user_id = ? AND is_active = 1',
            (user['id'],)
        ).fetchone()['count']
        return count

def get_subscription_limit(telegram_id):
    """Возвращает лимит подписок"""
    if is_premium(telegram_id):
        return PREMIUM_LIMIT
    return FREE_LIMIT

def add_subscription_db(telegram_id, name, amount, billing_day):
    """Добавляет подписку в БД"""
    with get_db() as conn:
        user = get_or_create_user(telegram_id)
        conn.execute(
            'INSERT INTO subscriptions (user_id, name, amount, billing_day) VALUES (?, ?, ?, ?)',
            (user['id'], name, amount, billing_day)
        )
        return True

def get_subscriptions(telegram_id):
    """Получает подписки пользователя"""
    with get_db() as conn:
        user = get_or_create_user(telegram_id)
        subs = conn.execute(
            'SELECT * FROM subscriptions WHERE user_id = ? AND is_active = 1',
            (user['id'],)
        ).fetchall()
        return subs

def delete_subscription_db(telegram_id, subscription_id):
    """Удаляет подписку"""
    with get_db() as conn:
        user = get_or_create_user(telegram_id)
        conn.execute(
            'UPDATE subscriptions SET is_active = 0 WHERE id = ? AND user_id = ?',
            (subscription_id, user['id'])
        )
        return True

def calculate_next_billing(billing_day):
    """Вычисляет следующую дату списания"""
    today = datetime.now()
    year = today.year
    month = today.month
    
    max_day = calendar.monthrange(year, month)[1]
    actual_day = min(billing_day, max_day)
    
    next_date = datetime(year, month, actual_day)
    if next_date < today:
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(billing_day, max_day)
        next_date = datetime(year, month, actual_day)
    
    return next_date

# ============ СОСТОЯНИЯ FSM ============

class SubscriptionStates(StatesGroup):
    waiting_name = State()
    waiting_amount = State()
    waiting_date = State()

# ============ КЛАВИАТУРЫ ============

def get_main_keyboard(telegram_id):
    """Главное меню"""
    count = get_subscription_count(telegram_id)
    limit = get_subscription_limit(telegram_id)
    premium = "⭐ Premium" if is_premium(telegram_id) else "🔓 Бесплатный"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subscriptions")],
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="add_subscription"),
            InlineKeyboardButton(text="❌ Удалить", callback_data="delete_subscription")
        ],
        [InlineKeyboardButton(text="📊 Финансовый обзор", callback_data="financial_overview")],
        [InlineKeyboardButton(text=f"💳 Тариф: {premium} ({count}/{limit})", callback_data="tariff_info")],
        [InlineKeyboardButton(text="🎁 Партнерская программа", callback_data="referral_program")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])

def get_back_keyboard():
    """Клавиатура назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])

# ============ ОБРАБОТЧИКИ КОМАНД ============

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик /start"""
    await state.clear()
    
    user = get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )
    
    text = (
        f"👋 <b>Добро пожаловать, {message.from_user.full_name}!</b>\n\n"
        f"Я — <b>Диспетчер Хаоса</b> 🤖\n"
        f"Ваш помощник в управлении подписками.\n\n"
        f"🔹 <b>Что я умею:</b>\n"
        f"• Отслеживать подписки и платежи\n"
        f"• Напоминать о списаниях\n"
        f"• Рассчитывать расходы\n\n"
        f"💡 <b>Бесплатно:</b> {FREE_LIMIT} подписки\n"
        f"⭐ <b>Premium:</b> {PREMIUM_LIMIT} подписок\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(text, reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик /help"""
    text = (
        "📚 <b>Помощь</b>\n\n"
        "<b>📋 Подписки:</b>\n"
        "• Нажмите «➕ Добавить» для новой подписки\n"
        "• Укажите название, сумму и дату\n\n"
        "<b>💳 Тарифы:</b>\n"
        f"• Бесплатный: {FREE_LIMIT} подписки\n"
        f"• Premium: {PREMIUM_LIMIT} подписок\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/help — помощь\n"
        "/cancel — отмена"
    )
    await message.answer(text)

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Обработчик /cancel"""
    await state.clear()
    await message.answer(
        "✅ Отменено",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

# ============ CALLBACK ОБРАБОТЧИКИ ============

@dp.callback_query(F.data == "my_subscriptions")
async def cb_subscriptions(callback: CallbackQuery):
    """Показывает подписки"""
    subs = get_subscriptions(callback.from_user.id)
    
    if not subs:
        text = "📋 <b>У вас пока нет подписок</b>\n\nНажмите «➕ Добавить»"
    else:
        text = "📋 <b>Ваши подписки:</b>\n\n"
        total = 0
        
        for i, sub in enumerate(subs, 1):
            next_date = calculate_next_billing(sub['billing_day'])
            days_left = (next_date - datetime.now()).days
            text += (
                f"{i}. <b>{sub['name']}</b>\n"
                f"   💰 {sub['amount']:.2f} ₽ | 📅 {sub['billing_day']} числа\n"
                f"   ⏰ Через {days_left} дн.\n\n"
            )
            total += sub['amount']
        
        text += f"💳 <b>Итого: {total:.2f} ₽/мес</b>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_subscription")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "add_subscription")
async def cb_add_subscription(callback: CallbackQuery, state: FSMContext):
    """Начинает добавление подписки"""
    count = get_subscription_count(callback.from_user.id)
    limit = get_subscription_limit(callback.from_user.id)
    
    if count >= limit:
        await callback.message.edit_text(
            f"❌ <b>Лимит исчерпан!</b>\n\n"
            f"У вас {count} из {limit} подписок.\n"
            f"Оформите Premium для {PREMIUM_LIMIT} подписок!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ Premium", callback_data="tariff_info")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return
    
    await state.set_state(SubscriptionStates.waiting_name)
    await callback.message.edit_text(
        "📝 <b>Добавление подписки</b>\n\n"
        "Введите название:\n"
        "<i>Например: Netflix, Spotify</i>"
    )
    await callback.answer()

@dp.callback_query(F.data == "delete_subscription")
async def cb_delete_subscription(callback: CallbackQuery):
    """Показывает меню удаления"""
    subs = get_subscriptions(callback.from_user.id)
    
    if not subs:
        await callback.message.edit_text(
            "📋 Нет подписок для удаления",
            reply_markup=get_back_keyboard()
        )
    else:
        text = "🗑 <b>Выберите подписку:</b>\n\n"
        keyboard = []
        
        for sub in subs:
            text += f"• {sub['name']} - {sub['amount']:.2f} ₽\n"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ {sub['name']}",
                    callback_data=f"del_{sub['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def cb_confirm_delete(callback: CallbackQuery):
    """Подтверждает удаление"""
    sub_id = int(callback.data.split("_")[1])
    delete_subscription_db(callback.from_user.id, sub_id)
    
    await callback.message.edit_text(
        "✅ Подписка удалена!",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )
    await callback.answer()

@dp.callback_query(F.data == "financial_overview")
async def cb_financial(callback: CallbackQuery):
    """Финансовый обзор"""
    subs = get_subscriptions(callback.from_user.id)
    
    if not subs:
        text = "📊 <b>Финансовый обзор</b>\n\nНет подписок"
    else:
        total = sum(s['amount'] for s in subs)
        impact_30 = total  # Упрощенно
        
        text = (
            "📊 <b>Финансовый обзор</b>\n\n"
            f"💥 Сила удара: <b>{impact_30:.2f} ₽</b>\n"
            f"💳 Ежемесячно: <b>{total:.2f} ₽</b>\n"
            f"📋 Подписок: <b>{len(subs)}</b>\n\n"
            "<b>Ближайшие списания:</b>\n"
        )
        
        for sub in subs[:5]:
            next_date = calculate_next_billing(sub['billing_day'])
            days = (next_date - datetime.now()).days
            text += f"• {sub['name']}: {sub['amount']:.2f} ₽ (через {days} дн.)\n"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "tariff_info")
async def cb_tariff(callback: CallbackQuery):
    """Информация о тарифе"""
    premium = is_premium(callback.from_user.id)
    
    if premium:
        status = "✅ Premium активен"
    else:
        status = "🔓 Бесплатный"
    
    text = (
        f"💳 <b>Тарифы</b>\n\n"
        f"Статус: {status}\n\n"
        f"🔓 <b>Бесплатный:</b> {FREE_LIMIT} подписки\n"
        f"⭐ <b>Premium:</b> {PREMIUM_LIMIT} подписок\n"
        f"💎 Цена: {PREMIUM_PRICE} Stars/{PREMIUM_DAYS} дн."
    )
    
    keyboard = []
    if not premium:
        keyboard.append([
            InlineKeyboardButton(
                text=f"⭐ Оплатить {PREMIUM_PRICE} Stars",
                callback_data="pay_premium"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@dp.callback_query(F.data == "referral_program")
async def cb_referral(callback: CallbackQuery):
    """Партнерская программа"""
    text = (
        "🎁 <b>Партнерская программа</b>\n\n"
        "Приглашайте друзей и получайте Stars!\n\n"
        "Скоро будет доступно!"
    )
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    """Помощь"""
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "• /start — главное меню\n"
        "• /help — помощь\n"
        "• /cancel — отмена"
    )
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def cb_back(callback: CallbackQuery):
    """Возврат в меню"""
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )
    await callback.answer()

@dp.callback_query(F.data == "pay_premium")
async def cb_pay(callback: CallbackQuery):
    """Оплата Premium"""
    prices = [LabeledPrice(label="Premium", amount=PREMIUM_PRICE)]
    
    await callback.message.answer_invoice(
        title="Диспетчер Хаоса Premium",
        description=f"Premium на {PREMIUM_DAYS} дней",
        payload=f"premium_{callback.from_user.id}",
        currency="XTR",
        prices=prices
    )
    await callback.answer()

# ============ FSM ОБРАБОТЧИКИ ============

@dp.message(SubscriptionStates.waiting_name)
async def process_name(message: types.Message, state: FSMContext):
    """Обрабатывает название"""
    if not message.text:
        await message.answer("❌ Введите текст")
        return
    
    await state.update_data(name=message.text)
    await state.set_state(SubscriptionStates.waiting_amount)
    await message.answer(f"💰 Введите сумму для <b>{message.text}</b>:")

@dp.message(SubscriptionStates.waiting_amount)
async def process_amount(message: types.Message, state: FSMContext):
    """Обрабатывает сумму"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
        
        await state.update_data(amount=amount)
        await state.set_state(SubscriptionStates.waiting_date)
        await message.answer("📅 Введите день списания (1-31):")
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму")

@dp.message(SubscriptionStates.waiting_date)
async def process_date(message: types.Message, state: FSMContext):
    """Обрабатывает дату"""
    try:
        billing_day = int(message.text)
        if billing_day < 1 or billing_day > 31:
            raise ValueError
        
        data = await state.get_data()
        add_subscription_db(
            message.from_user.id,
            data['name'],
            data['amount'],
            billing_day
        )
        
        await state.clear()
        
        text = (
            f"🎉 <b>Подписка добавлена!</b>\n\n"
            f"📝 {data['name']}\n"
            f"💰 {data['amount']:.2f} ₽\n"
            f"📅 {billing_day} числа\n\n"
            f"Буду напоминать о списаниях!"
        )
        
        await message.answer(text, reply_markup=get_main_keyboard(message.from_user.id))
        
    except ValueError:
        await message.answer("❌ Введите число от 1 до 31")

# ============ ПЛАТЕЖИ ============

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    """Проверка платежа"""
    await query.answer(ok=True)

@dp.message(F.content_type == types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    """Успешный платеж"""
    with get_db() as conn:
        user = get_or_create_user(message.from_user.id)
        conn.execute(
            'UPDATE users SET tariff = ?, premium_until = ? WHERE telegram_id = ?',
            ('premium', (datetime.now() + timedelta(days=PREMIUM_DAYS)).isoformat(), message.from_user.id)
        )
        conn.execute(
            'INSERT INTO payments (user_id, amount, currency) VALUES (?, ?, ?)',
            (user['id'], message.successful_payment.total_amount, 'XTR')
        )
    
    await message.answer(
        f"🎉 <b>Premium активирован!</b>\n\n"
        f"⏰ До: {(datetime.now() + timedelta(days=PREMIUM_DAYS)).strftime('%d.%m.%Y')}"
    )

# ============ ЭХО ============

@dp.message()
async def echo(message: types.Message):
    """Обработчик остальных сообщений"""
    await message.answer(
        "Используйте /start для главного меню",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

# ============ ЗАПУСК ============

async def main():
    """Главная функция"""
    logger.info("=" * 50)
    logger.info("🚀 Запуск Диспетчера Хаоса...")
    
    # Инициализация БД
    init_db()
    
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот: @{me.username}")
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Запускаем polling...")
        
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
