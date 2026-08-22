import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, Payment
from bot.database.connection import get_async_db
from bot.config import config
from bot.utils.logger import logger

class PaymentService:
    """Сервис платежей через Telegram Stars"""
    
    @staticmethod
    async def create_stars_invoice(user_id: int) -> Dict[str, Any]:
        """Создает счет для оплаты Stars"""
        from aiogram.types import LabeledPrice
        
        prices = [LabeledPrice(
            label=f"Premium на {config.PREMIUM_DURATION_DAYS} дней",
            amount=config.PREMIUM_PRICE_STARS
        )]
        
        return {
            "title": "Диспетчер Хаоса Premium",
            "description": (
                f"⭐ Premium подписка\n"
                f"📋 До {config.PREMIUM_SUBSCRIPTIONS_LIMIT} подписок\n"
                f"⏰ На {config.PREMIUM_DURATION_DAYS} дней"
            ),
            "payload": f"premium_{user_id}_{int(datetime.now().timestamp())}",
            "currency": "XTR",
            "prices": prices
        }
    
    @staticmethod
    async def process_stars_payment(
        user_id: int,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str,
        total_amount: int,
        currency: str,
        payload: str
    ) -> bool:
        """Обрабатывает успешный платеж Stars"""
        try:
            # Извлекаем ID пользователя из payload
            payload_parts = payload.split('_')
            target_user_id = int(payload_parts[1]) if len(payload_parts) > 1 else user_id
            
            logger.info(f"Processing payment for user {target_user_id}, amount: {total_amount} {currency}")
            
            async with get_async_db() as session:
                # Находим пользователя по telegram_id
                result = await session.execute(
                    select(User).where(User.telegram_id == target_user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    # Создаем пользователя если нет
                    user = User(
                        telegram_id=target_user_id,
                        tariff="free",
                        total_payments=0.0,
                        is_blocked=False
                    )
                    session.add(user)
                    await session.flush()
                    logger.info(f"Created new user during payment: {target_user_id}")
                
                # Создаем запись о платеже
                payment = Payment(
                    user_id=user.id,
                    amount=total_amount,
                    currency="XTR",
                    payment_type="premium_stars",
                    status="completed",
                    telegram_payment_id=telegram_payment_charge_id,
                    provider_payment_id=provider_payment_charge_id,
                    completed_at=datetime.now()
                )
                session.add(payment)
                
                # Активируем Premium
                now = datetime.now()
                
                if user.premium_until and user.premium_until > now:
                    # Продлеваем от текущей даты окончания
                    user.premium_until = user.premium_until + timedelta(
                        days=config.PREMIUM_DURATION_DAYS
                    )
                else:
                    # Начинаем с сегодняшнего дня
                    user.premium_until = now + timedelta(
                        days=config.PREMIUM_DURATION_DAYS
                    )
                
                user.tariff = "premium"
                user.total_payments = (user.total_payments or 0) + total_amount
                
                await session.commit()
                
                logger.info(
                    f"Premium activated for user {target_user_id} "
                    f"until {user.premium_until}"
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error processing Stars payment: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def get_payment_stats() -> Dict[str, Any]:
        """Получает статистику платежей"""
        async with get_async_db() as session:
            total_revenue = await session.scalar(
                select(func.sum(Payment.amount)).where(
                    Payment.status == "completed"
                )
            )
            
            active_premium = await session.scalar(
                select(func.count(User.id)).where(
                    and_(
                        User.tariff == "premium",
                        User.premium_until > datetime.now()
                    )
                )
            )
            
            total_users = await session.scalar(
                select(func.count(User.id))
            )
            
            return {
                "total_revenue_stars": total_revenue or 0,
                "active_premium": active_premium or 0,
                "total_users": total_users or 0,
            }
    
    @staticmethod
    async def check_premium_expired():
        """Проверяет истекшие Premium подписки"""
        async with get_async_db() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.tariff == "premium",
                        User.premium_until < datetime.now()
                    )
                )
            )
            
            expired_users = list(result.scalars().all())
            
            for user in expired_users:
                user.tariff = "free"
                user.premium_until = None
                logger.info(f"Premium expired for user {user.telegram_id}")
            
            await session.commit()
            
            return len(expired_users)