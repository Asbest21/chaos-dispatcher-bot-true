"""
Главный файл бота с уведомлениями
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    try:
        from bot.config import config
        BOT_TOKEN = config.BOT_TOKEN
    except:
        pass

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    sys.exit(1)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# ============ СИСТЕМА УВЕДОМЛЕНИЙ ============

async def check_notifications():
    """Проверяет и отправляет уведомления о списаниях"""
    logger.info("🔔 Система уведомлений запущена")
    
    while True:
        try:
            from bot.database.connection import get_async_db
            from bot.database.models import Subscription, User, Notification
            from sqlalchemy import select, and_
            
            async with get_async_db() as session:
                # Находим все активные подписки
                result = await session.execute(
                    select(Subscription, User)
                    .join(User, Subscription.user_id == User.id)
                    .where(
                        and_(
                            Subscription.is_active == True,
                            User.is_blocked == False
                        )
                    )
                )
                subscriptions = result.all()
                
                today = datetime.now()
                
                for subscription, user in subscriptions:
                    # Вычисляем дату следующего списания
                    next_billing = calculate_next_billing_date(subscription.billing_day)
                    
                    # Разница в днях
                    days_left = (next_billing - today).days
                    hours_left = (next_billing - today).total_seconds() / 3600
                    
                    # Проверяем, нужно ли отправить уведомление
                    notification_type = None
                    
                    if 6 <= days_left <= 7:
                        notification_type = "7_days"
                    elif 2 <= days_left <= 3:
                        notification_type = "3_days"
                    elif 0 <= hours_left <= 1:
                        notification_type = "1_hour"
                    
                    if notification_type:
                        # Проверяем, не отправляли ли уже
                        already_sent = await session.scalar(
                            select(Notification).where(
                                and_(
                                    Notification.subscription_id == subscription.id,
                                    Notification.notification_type == notification_type,
                                    Notification.sent_at >= today - timedelta(days=1)
                                )
                            )
                        )
                        
                        if not already_sent:
                            # Отправляем уведомление
                            await send_notification(
                                bot, user.telegram_id, 
                                subscription, notification_type, next_billing
                            )
                            
                            # Сохраняем в БД
                            notification = Notification(
                                subscription_id=subscription.id,
                                notification_type=notification_type,
                                scheduled_at=datetime.now(),
                                sent_at=datetime.now(),
                                is_sent=True
                            )
                            session.add(notification)
                            await session.commit()
                            
                            logger.info(
                                f"🔔 Уведомление отправлено: {subscription.name} "
                                f"({notification_type}) для {user.telegram_id}"
                            )
            
        except Exception as e:
            logger.error(f"Ошибка в check_notifications: {e}", exc_info=True)
        
        # Проверяем каждый час
        await asyncio.sleep(3600)

def calculate_next_billing_date(billing_day: int) -> datetime:
    """Вычисляет следующую дату списания"""
    import calendar
    
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

async def send_notification(bot, user_id, subscription, notification_type, next_billing):
    """Отправляет уведомление"""
    
    messages = {
        "7_days": (
            f"⚠️ <b>Напоминание о списании</b>\n\n"
            f"Подписка: <b>{subscription.name}</b>\n"
            f"Сумма: <b>{subscription.amount:.2f} ₽</b>\n"
            f"Списание через: <b>7 дней</b>\n"
            f"Дата: <b>{next_billing.strftime('%d.%m.%Y')}</b>\n\n"
            f"<i>Проверьте баланс карты</i>"
        ),
        "3_days": (
            f"⏰ <b>Скоро списание!</b>\n\n"
            f"Подписка: <b>{subscription.name}</b>\n"
            f"Сумма: <b>{subscription.amount:.2f} ₽</b>\n"
            f"Списание через: <b>3 дня</b>\n"
            f"Дата: <b>{next_billing.strftime('%d.%m.%Y')}</b>"
        ),
        "1_hour": (
            f"🚨 <b>СРОЧНОЕ УВЕДОМЛЕНИЕ!</b>\n\n"
            f"Подписка: <b>{subscription.name}</b>\n"
            f"Сумма: <b>{subscription.amount:.2f} ₽</b>\n"
            f"Списание через: <b>1 час</b>\n\n"
            f"<b>Проверьте наличие средств!</b>"
        )
    }
    
    message_text = messages.get(notification_type, "")
    
    if message_text:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="HTML"
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")
            return False

# ============ ЗАПУСК ============

async def main():
    """Главная функция"""
    logger.info("=" * 50)
    logger.info("🚀 Запуск Диспетчера Хаоса...")
    
    # Инициализация БД
    try:
        from bot.database.connection import init_db
        await init_db()
        logger.info("✅ БД инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")
    
    # Регистрируем обработчики
    try:
        from bot.handlers import register_all_handlers
        register_all_handlers(dp)
        logger.info("✅ Обработчики зарегистрированы")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации: {e}")
        return
    
    # Запускаем систему уведомлений в фоне
    notification_task = asyncio.create_task(check_notifications())
    
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот: @{me.username}")
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Запускаем polling...")
        
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
    finally:
        notification_task.cancel()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
