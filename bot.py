"""
Полный бот для Bothost - ВСЕ В ОДНОМ ФАЙЛЕ
"""

import asyncio
import logging
import os
import sys
import sqlite3
import calendar
from datetime import datetime, timedelta
from contextlib import contextmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
FREE_LIMIT = 2
PREMIUM_LIMIT = 30
PREMIUM_PRICE = 25

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not set!")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# БД
DB_PATH = "data/chaos.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE,
        username TEXT, full_name TEXT, tariff TEXT DEFAULT 'free',
        premium_until DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT,
        amount REAL, billing_day INTEGER, is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def get_user(tg_id):
    with get_db() as conn:
        u = conn.execute('SELECT * FROM users WHERE telegram_id=?', (tg_id,)).fetchone()
        if not u:
            conn.execute('INSERT INTO users (telegram_id) VALUES (?)', (tg_id,))
            u = conn.execute('SELECT * FROM users WHERE telegram_id=?', (tg_id,)).fetchone()
        return u

def is_premium(tg_id):
    with get_db() as conn:
        u = conn.execute('SELECT * FROM users WHERE telegram_id=?', (tg_id,)).fetchone()
        if u and u['tariff'] == 'premium' and u['premium_until']:
            return datetime.fromisoformat(u['premium_until']) > datetime.now()
    return False

def get_subs(tg_id):
    with get_db() as conn:
        u = get_user(tg_id)
        return conn.execute('SELECT * FROM subscriptions WHERE user_id=? AND is_active=1', (u['id'],)).fetchall()

def get_count(tg_id):
    return len(get_subs(tg_id))

def get_limit(tg_id):
    return PREMIUM_LIMIT if is_premium(tg_id) else FREE_LIMIT

# Состояния
class States(StatesGroup):
    name = State()
    amount = State()
    date = State()

# Клавиатура
def main_kb(tg_id):
    count = get_count(tg_id)
    limit = get_limit(tg_id)
    status = "⭐ Premium" if is_premium(tg_id) else "🔓 Бесплатный"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои подписки", callback_data="subs")],
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add"), InlineKeyboardButton(text="❌ Удалить", callback_data="del")],
        [InlineKeyboardButton(text="📊 Финансы", callback_data="fin")],
        [InlineKeyboardButton(text=f"💳 {status} ({count}/{limit})", callback_data="tariff")],
        [InlineKeyboardButton(text="🎁 Партнерка", callback_data="ref")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

# Команды
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    get_user(message.from_user.id)
    await message.answer(
        f"👋 <b>Добро пожаловать, {message.from_user.full_name}!</b>\n\n"
        f"Я — <b>Диспетчер Хаоса</b> 🤖\n\n"
        f"Выберите действие:",
        reply_markup=main_kb(message.from_user.id)
    )

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer("📚 /start — меню\n/add — подписка\n/premium — тариф")

@dp.message(Command("cancel"))
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Отменено", reply_markup=main_kb(message.from_user.id))

# Callbacks
@dp.callback_query(F.data == "subs")
async def cb_subs(callback: types.CallbackQuery):
    subs = get_subs(callback.from_user.id)
    if not subs:
        text = "📋 Нет подписок"
    else:
        text = "📋 <b>Подписки:</b>\n\n"
        total = 0
        for s in subs:
            text += f"• <b>{s['name']}</b>: {s['amount']:.0f}₽ ({s['billing_day']} числа)\n"
            total += s['amount']
        text += f"\n💳 Итого: {total:.0f}₽/мес"
    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "add")
async def cb_add(callback: types.CallbackQuery, state: FSMContext):
    if get_count(callback.from_user.id) >= get_limit(callback.from_user.id):
        await callback.message.edit_text("❌ Лимит! Оформите Premium", reply_markup=back_kb())
        await callback.answer()
        return
    await state.set_state(States.name)
    await callback.message.edit_text("📝 Введите название подписки:")
    await callback.answer()

@dp.callback_query(F.data == "del")
async def cb_del(callback: types.CallbackQuery):
    subs = get_subs(callback.from_user.id)
    if not subs:
        await callback.message.edit_text("Нет подписок", reply_markup=back_kb())
    else:
        kb = []
        for s in subs:
            kb.append([InlineKeyboardButton(text=f"❌ {s['name']}", callback_data=f"del_{s['id']}")])
        kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
        await callback.message.edit_text("🗑 Выберите:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def cb_del_confirm(callback: types.CallbackQuery):
    sid = int(callback.data.split("_")[1])
    with get_db() as conn:
        conn.execute('UPDATE subscriptions SET is_active=0 WHERE id=?', (sid,))
    await callback.message.edit_text("✅ Удалено!", reply_markup=main_kb(callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "fin")
async def cb_fin(callback: types.CallbackQuery):
    subs = get_subs(callback.from_user.id)
    total = sum(s['amount'] for s in subs) if subs else 0
    text = f"📊 <b>Финансы</b>\n\n💥 Сила удара: {total:.0f}₽\n💳 В месяц: {total:.0f}₽\n📋 Подписок: {len(subs)}"
    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "tariff")
async def cb_tariff(callback: types.CallbackQuery):
    prem = is_premium(callback.from_user.id)
    text = f"💳 <b>Тарифы</b>\n\n🔓 Бесплатный: {FREE_LIMIT}\n⭐ Premium: {PREMIUM_LIMIT}\n💎 Цена: {PREMIUM_PRICE} Stars"
    kb = []
    if not prem:
        kb.append([InlineKeyboardButton(text=f"⭐ Оплатить {PREMIUM_PRICE} Stars", callback_data="pay")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data == "ref")
async def cb_ref(callback: types.CallbackQuery):
    await callback.message.edit_text("🎁 <b>Партнерка</b>\n\nПриглашайте друзей!", reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "help")
async def cb_help(callback: types.CallbackQuery):
    await callback.message.edit_text("ℹ️ /start — меню\n/help — помощь", reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "back")
async def cb_back(callback: types.CallbackQuery):
    await callback.message.edit_text("🏠 Меню", reply_markup=main_kb(callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "pay")
async def cb_pay(callback: types.CallbackQuery):
    await callback.message.answer_invoice(
        title="Premium",
        description="Premium на 30 дней",
        payload=f"prem_{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label="Premium", amount=PREMIUM_PRICE)]
    )
    await callback.answer()

# FSM
@dp.message(States.name)
async def fsm_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(States.amount)
    await message.answer(f"💰 Сумма для <b>{message.text}</b>:")

@dp.message(States.amount)
async def fsm_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        await state.update_data(amount=amount)
        await state.set_state(States.date)
        await message.answer("📅 День списания (1-31):")
    except:
        await message.answer("❌ Неверная сумма")

@dp.message(States.date)
async def fsm_date(message: types.Message, state: FSMContext):
    try:
        day = int(message.text)
        if day < 1 or day > 31:
            raise ValueError
        data = await state.get_data()
        with get_db() as conn:
            u = get_user(message.from_user.id)
            conn.execute('INSERT INTO subscriptions (user_id, name, amount, billing_day) VALUES (?,?,?,?)',
                        (u['id'], data['name'], data['amount'], day))
        await state.clear()
        await message.answer(f"🎉 <b>{data['name']}</b> добавлена!\n💰 {data['amount']:.0f}₽\n📅 {day} числа",
                            reply_markup=main_kb(message.from_user.id))
    except:
        await message.answer("❌ Число от 1 до 31")

# Платежи
@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.content_type == types.ContentType.SUCCESSFUL_PAYMENT)
async def payment(message: types.Message):
    with get_db() as conn:
        u = get_user(message.from_user.id)
        conn.execute('UPDATE users SET tariff=?, premium_until=? WHERE id=?',
                    ('premium', (datetime.now()+timedelta(days=30)).isoformat(), u['id']))
        conn.execute('INSERT INTO payments (user_id, amount) VALUES (?,?)',
                    (u['id'], message.successful_payment.total_amount))
    await message.answer("🎉 <b>Premium активирован!</b>")

# Эхо
@dp.message()
async def echo(message: types.Message):
    await message.answer("Используйте /start", reply_markup=main_kb(message.from_user.id))

async def main():
    logger.info("🚀 Запуск...")
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
