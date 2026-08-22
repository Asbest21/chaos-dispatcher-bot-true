import asyncio
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_, update

from bot.database.models import Notification, Subscription, User
from bot.database.connection import get_async_db
from bot.services.subscription_service import SubscriptionService
from bot.utils.logger import logger

class NotificationService:
    """Сервис уведомлений"""
    
    @staticmethod
    async def send_notification(
        notification: Notification,
        subscription: Subscription,
        user: User,
        bot_instance
    ):
        """Отправляет уведомление пользователю"""
        try:
            next_date = SubscriptionService.calculate_next_billing_date(
                subscription.billing_day
            )
            
            messages = {
                "7_days": (
                    f"⚠️ <b>Напоминание о списании</b>\n\n"
                    f"Подписка: <b>{subscription.name}</b>\n"
                    f"Сумма: <b>{subscription.amount:.2f} ₽</b>\n"
                    f"Списание через: <b>7 дней</b>\n"
                    f"Дата: <b>{next_date.strftime('%d.%m.%Y')}</b>"
                ),
                "3_days": (
                    f"⏰ <b>Скоро списание!</b>\n\n"
                    f"Подписка: <b>{subscription.name}</b>\n"
                    f"Сумма: <b>{subscription.amount:.2f} ₽</b>\n"
                    f"Списание через: <b>3 дня</b>"
                ),
                "1_hour": (
                    f"🚨 <b>СРОЧНО!</b>\n\n"
                    f"Подписка: <b>{subscription.name}</b>\n"
                    f"Сумма: <b>{subscription.amount:.2f} ₽</b>\n"
                    f"Списание через: <b>1 час</b>"
                )
            }
            
            message_text = messages.get(notification.notification_type, "")
            
            if message_text and bot_instance:
                await bot_instance.send_message(
                    chat_id=user.telegram_id,
                    text=message_text,
                    parse_mode="HTML"
                )
                
                async with get_async_db() as session:
                    await session.execute(
                        update(Notification)
                        .where(Notification.id == notification.id)
                        .values(is_sent=True, sent_at=datetime.now())
                    )
                
                logger.info(f"Notification sent to {user.telegram_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to send notification: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def check_due_notifications(bot_instance=None):
        """Проверяет и отправляет просроченные уведомления"""
        while True:
            try:
                if bot_instance is None:
                    from bot.main import bot as bot_instance
                
                async with get_async_db() as session:
                    result = await session.execute(
                        select(Notification, Subscription, User)
                        .join(Subscription, Notification.subscription_id == Subscription.id)
                        .join(User, Subscription.user_id == User.id)
                        .where(
                            and_(
                                Notification.is_sent == False,
                                Notification.scheduled_at <= datetime.now(),
                                Subscription.is_active == True,
                                User.is_blocked == False
                            )
                        )
                        .limit(50)
                    )
                    
                    notifications = result.all()
                    
                    for notification, subscription, user in notifications:
                        await NotificationService.send_notification(
                            notification, subscription, user, bot_instance
                        )
                        
            except Exception as e:
                logger.error(f"Error in check_due_notifications: {e}", exc_info=True)
            
            await asyncio.sleep(60)
