import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import calendar

from bot.database.models import User, Subscription, Notification
from bot.database.connection import get_async_db
from bot.config import config
from bot.utils.logger import logger

class SubscriptionService:
    """Сервис управления подписками"""
    
    @staticmethod
    def calculate_next_billing_date(billing_day: int, from_date: datetime = None) -> datetime:
        """Вычисляет следующую дату списания"""
        if from_date is None:
            from_date = datetime.now()
        
        year = from_date.year
        month = from_date.month
        
        # Обработка месяцев с меньшим количеством дней
        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(billing_day, max_day)
        
        next_date = datetime(year, month, actual_day)
        
        if next_date.date() < from_date.date():
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            max_day = calendar.monthrange(year, month)[1]
            actual_day = min(billing_day, max_day)
            next_date = datetime(year, month, actual_day)
        
        return next_date
    
    @staticmethod
    async def get_or_create_user(user_id: int, username: str = None, full_name: str = None) -> Optional[User]:
        """Получает или создает пользователя"""
        async with get_async_db() as session:
            # Ищем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # Создаем нового пользователя
                user = User(
                    telegram_id=user_id,
                    username=username,
                    full_name=full_name,
                    language="ru",
                    tariff="free",
                    total_payments=0.0,
                    is_blocked=False
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                
                logger.info(f"Created new user: {user_id}")
            
            return user
    
    @staticmethod
    async def can_add_subscription(user_id: int) -> Tuple[bool, str]:
        """Проверяет возможность добавления подписки"""
        async with get_async_db() as session:
            # Получаем или создаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # Создаем пользователя
                user = User(
                    telegram_id=user_id,
                    tariff="free",
                    total_payments=0.0,
                    is_blocked=False
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            if user.is_blocked:
                return False, "Аккаунт заблокирован"
            
            # Считаем активные подписки
            count = await session.scalar(
                select(func.count(Subscription.id)).where(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.is_active == True
                    )
                )
            ) or 0
            
            limit = user.get_subscription_limit()
            
            if count >= limit:
                if user.is_premium():
                    return False, f"Достигнут лимит Premium ({limit} подписок)"
                else:
                    return False, f"Бесплатный лимит исчерпан ({limit} подписки). Оформите Premium!"
            
            return True, ""
    
    @staticmethod
    async def add_subscription(
        user_id: int, 
        name: str, 
        amount: float, 
        billing_day: int
    ) -> Optional[Subscription]:
        """Добавление новой подписки"""
        # Проверяем возможность
        can_add, error = await SubscriptionService.can_add_subscription(user_id)
        if not can_add:
            raise ValueError(error)
        
        async with get_async_db() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError("Пользователь не найден")
            
            # Создаем подписку
            subscription = Subscription(
                user_id=user.id,
                name=name,
                amount=amount,
                billing_day=billing_day,
                is_active=True
            )
            session.add(subscription)
            await session.commit()
            await session.refresh(subscription)
            
            logger.info(f"Subscription added: {name} for user {user_id}")
            
            # Создаем уведомления
            await SubscriptionService.create_notifications(subscription)
            
            return subscription
    
    @staticmethod
    async def create_notifications(subscription: Subscription):
        """Создает уведомления для подписки"""
        next_billing = SubscriptionService.calculate_next_billing_date(
            subscription.billing_day
        )
        
        notification_schedule = [
            (next_billing - timedelta(days=7), "7_days"),
            (next_billing - timedelta(days=3), "3_days"),
            (next_billing - timedelta(hours=1), "1_hour")
        ]
        
        async with get_async_db() as session:
            for scheduled_at, notif_type in notification_schedule:
                if scheduled_at > datetime.now():
                    notification = Notification(
                        subscription_id=subscription.id,
                        notification_type=notif_type,
                        scheduled_at=scheduled_at,
                        is_sent=False
                    )
                    session.add(notification)
            
            await session.commit()
    
    @staticmethod
    async def get_user_subscriptions(user_id: int, active_only: bool = True) -> List[Subscription]:
        """Получает подписки пользователя"""
        async with get_async_db() as session:
            # Находим пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return []
            
            # Получаем подписки
            query = select(Subscription).where(Subscription.user_id == user.id)
            if active_only:
                query = query.where(Subscription.is_active == True)
            query = query.order_by(Subscription.billing_day)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    @staticmethod
    async def delete_subscription(user_id: int, subscription_id: int) -> bool:
        """Удаляет подписку"""
        async with get_async_db() as session:
            # Находим пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            # Находим подписку
            subscription = await session.get(Subscription, subscription_id)
            if subscription and subscription.user_id == user.id:
                # Удаляем будущие уведомления
                await session.execute(
                    select(Notification).where(
                        and_(
                            Notification.subscription_id == subscription_id,
                            Notification.is_sent == False
                        )
                    )
                )
                
                # Помечаем как неактивную
                subscription.is_active = False
                await session.commit()
                
                logger.info(f"Subscription deleted: {subscription.name}")
                return True
            return False
    
    @staticmethod
    async def calculate_budget_impact(user_id: int, days: int = 30) -> float:
        """Рассчитывает силу удара по бюджету"""
        subscriptions = await SubscriptionService.get_user_subscriptions(user_id)
        total = 0.0
        today = datetime.now()
        end_date = today + timedelta(days=days)
        
        for sub in subscriptions:
            next_date = SubscriptionService.calculate_next_billing_date(sub.billing_day)
            
            if today <= next_date <= end_date:
                total += sub.amount
            else:
                next_month = SubscriptionService.calculate_next_billing_date(
                    sub.billing_day, 
                    next_date + timedelta(days=1)
                )
                if today <= next_month <= end_date:
                    total += sub.amount
        
        return round(total, 2)