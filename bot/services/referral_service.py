import asyncio
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, ReferralReward, Payment
from bot.database.connection import get_async_db
from bot.config import config
from bot.utils.logger import logger

class ReferralService:
    """Сервис реферальной программы"""
    
    @staticmethod
    def generate_referral_code(length: int = 8) -> str:
        """Генерирует уникальный реферальный код"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))
    
    @staticmethod
    async def get_or_create_referral_code(user_id: int) -> str:
        """Получает или создает реферальный код"""
        async with get_async_db() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return ""
            
            if not user.referral_code:
                while True:
                    code = ReferralService.generate_referral_code()
                    existing = await session.scalar(
                        select(User).where(User.referral_code == code)
                    )
                    if not existing:
                        break
                
                user.referral_code = code
                await session.commit()
            
            return user.referral_code
    
    @staticmethod
    async def process_referral(referral_code: str, new_user_id: int) -> Tuple[bool, str]:
        """
        Обрабатывает переход по реферальной ссылке
        Возвращает: (успех, сообщение)
        """
        if not referral_code:
            return False, "Код не указан"
        
        try:
            async with get_async_db() as session:
                # Находим реферера по коду
                result = await session.execute(
                    select(User).where(User.referral_code == referral_code.upper())
                )
                referrer = result.scalar_one_or_none()
                
                if not referrer:
                    logger.warning(f"Referral code not found: {referral_code}")
                    return False, "Код не найден"
                
                # Находим нового пользователя
                result = await session.execute(
                    select(User).where(User.telegram_id == new_user_id)
                )
                new_user = result.scalar_one_or_none()
                
                if not new_user:
                    return False, "Пользователь не найден"
                
                # Проверка: не приглашает ли сам себя
                if referrer.telegram_id == new_user_id:
                    return False, "Нельзя приглашать самого себя"
                
                # Проверка: уже есть реферер
                if new_user.referrer_id:
                    return False, "Вы уже зарегистрированы по реферальной ссылке"
                
                # Проверка: пользователь недавно зарегистрирован
                # Если created_at старше 5 минут - значит уже был зарегистрирован
                if new_user.created_at:
                    created_time = new_user.created_at
                    if isinstance(created_time, str):
                        created_time = datetime.fromisoformat(created_time)
                    
                    time_since_creation = datetime.now() - created_time
                    if time_since_creation > timedelta(minutes=5):
                        return False, "Пользователь уже был зарегистрирован ранее"
                
                # Устанавливаем реферера
                new_user.referrer_id = referrer.id
                referrer.total_referrals = (referrer.total_referrals or 0) + 1
                
                # Начисляем бонусы
                new_user.referral_balance = (new_user.referral_balance or 0) + config.REFERRAL_BONUS_STARS
                referrer.referral_balance = (referrer.referral_balance or 0) + config.REFERRAL_REWARD_STARS
                
                # Создаем запись о награде
                reward = ReferralReward(
                    user_id=referrer.id,
                    referred_user_id=new_user.id,
                    amount=config.REFERRAL_REWARD_STARS,
                    status="paid",
                    paid_at=datetime.now()
                )
                session.add(reward)
                
                await session.commit()
                
                logger.info(
                    f"Referral processed: {referrer.telegram_id} -> {new_user_id}. "
                    f"Referrer +{config.REFERRAL_REWARD_STARS}, New user +{config.REFERRAL_BONUS_STARS}"
                )
                
                return True, f"Начислено {config.REFERRAL_REWARD_STARS} Stars рефереру и {config.REFERRAL_BONUS_STARS} Stars новому пользователю"
                
        except Exception as e:
            logger.error(f"Error processing referral: {e}", exc_info=True)
            return False, "Ошибка обработки"
    
    @staticmethod
    async def reward_referrer_for_premium(referred_user_id: int):
        """Начисляет награду рефереру при покупке Premium"""
        try:
            async with get_async_db() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == referred_user_id)
                )
                referred_user = result.scalar_one_or_none()
                
                if not referred_user or not referred_user.referrer_id:
                    return False
                
                referrer = await session.get(User, referred_user.referrer_id)
                
                if not referrer:
                    return False
                
                # Начисляем награду
                referrer.referral_balance = (referrer.referral_balance or 0) + config.REFERRAL_REWARD_STARS
                referrer.active_referrals = (referrer.active_referrals or 0) + 1
                
                # Создаем запись
                reward = ReferralReward(
                    user_id=referrer.id,
                    referred_user_id=referred_user.id,
                    amount=config.REFERRAL_REWARD_STARS,
                    status="paid",
                    paid_at=datetime.now()
                )
                session.add(reward)
                
                await session.commit()
                
                logger.info(f"Premium reward: +{config.REFERRAL_REWARD_STARS} to {referrer.telegram_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error rewarding referrer: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def spend_stars_on_premium(user_id: int) -> Tuple[bool, str]:
        """
        Тратит Stars на покупку Premium
        Stars НЕЛЬЗЯ вывести, только потратить на Premium
        """
        async with get_async_db() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False, "Пользователь не найден"
            
            balance = user.referral_balance or 0
            premium_cost = config.PREMIUM_PRICE_STARS
            
            if balance < premium_cost:
                return False, f"Недостаточно Stars. Нужно {premium_cost}, у вас {balance}"
            
            # Списываем Stars
            user.referral_balance = balance - premium_cost
            
            # Активируем Premium
            if user.premium_until and user.premium_until > datetime.now():
                user.premium_until += timedelta(days=config.PREMIUM_DURATION_DAYS)
            else:
                user.premium_until = datetime.now() + timedelta(days=config.PREMIUM_DURATION_DAYS)
            
            user.tariff = "premium"
            
            # Создаем запись о платеже
            payment = Payment(
                user_id=user.id,
                amount=premium_cost,
                currency="XTR",
                payment_type="referral_spend",
                status="completed",
                completed_at=datetime.now()
            )
            session.add(payment)
            
            await session.commit()
            
            logger.info(f"User {user_id} spent {premium_cost} Stars on Premium")
            return True, f"Premium активирован! Потрачено {premium_cost} Stars"
    
    @staticmethod
    async def get_referral_stats(user_id: int, bot_username: str = None) -> Dict:
        """Получает статистику реферальной программы"""
        async with get_async_db() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {}
            
            result = await session.execute(
                select(User).where(User.referrer_id == user.id)
            )
            referrals = list(result.scalars().all())
            
            active_count = sum(1 for r in referrals if r.is_premium())
            
            referral_link = ""
            if user.referral_code and bot_username:
                referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"
            
            return {
                "referral_code": user.referral_code or "",
                "referral_link": referral_link,
                "total_referrals": user.total_referrals or 0,
                "active_referrals": active_count,
                "balance": user.referral_balance or 0,
                "min_payout": config.MIN_REFERRAL_PAYOUT,
                "reward_per_referral": config.REFERRAL_REWARD_STARS,
                "bonus_for_new": config.REFERRAL_BONUS_STARS,
                "premium_cost": config.PREMIUM_PRICE_STARS,
            }
    
    @staticmethod
    async def get_user_referrals(user_id: int) -> List[User]:
        """Получает список рефералов пользователя"""
        async with get_async_db() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return []
            
            result = await session.execute(
                select(User)
                .where(User.referrer_id == user.id)
                .order_by(User.created_at.desc())
            )
            return list(result.scalars().all())
    
    @staticmethod
    async def get_top_referrals(limit: int = 10) -> List[User]:
        """Получает топ рефереров"""
        async with get_async_db() as session:
            result = await session.execute(
                select(User)
                .where(User.total_referrals > 0)
                .order_by(User.total_referrals.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
