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
                # Генерируем уникальный код
                while True:
                    code = ReferralService.generate_referral_code()
                    # Проверяем уникальность
                    existing = await session.scalar(
                        select(User).where(User.referral_code == code)
                    )
                    if not existing:
                        break
                
                user.referral_code = code
                await session.commit()
            
            return user.referral_code
    
    @staticmethod
    async def process_referral(referral_code: str, new_user_id: int) -> bool:
        """Обрабатывает переход по реферальной ссылке"""
        if not referral_code:
            return False
        
        try:
            async with get_async_db() as session:
                # Находим реферера по коду
                result = await session.execute(
                    select(User).where(User.referral_code == referral_code.upper())
                )
                referrer = result.scalar_one_or_none()
                
                if not referrer:
                    logger.warning(f"Referral code not found: {referral_code}")
                    return False
                
                # Находим нового пользователя
                result = await session.execute(
                    select(User).where(User.telegram_id == new_user_id)
                )
                new_user = result.scalar_one_or_none()
                
                if not new_user:
                    logger.warning(f"New user not found: {new_user_id}")
                    return False
                
                # Проверяем, что пользователь не пригласил сам себя
                if referrer.telegram_id == new_user_id:
                    logger.warning(f"Self-referral attempt: {new_user_id}")
                    return False
                
                # Проверяем, что пользователь еще не имеет реферера
                if new_user.referrer_id:
                    logger.info(f"User {new_user_id} already has referrer")
                    return False
                
                # Устанавливаем реферера
                new_user.referrer_id = referrer.id
                referrer.total_referrals = (referrer.total_referrals or 0) + 1
                
                # Начисляем бонус новому пользователю
                new_user.referral_balance = (new_user.referral_balance or 0) + config.REFERRAL_BONUS_STARS
                
                await session.commit()
                
                logger.info(f"Referral processed: {referrer.telegram_id} -> {new_user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error processing referral: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def reward_referrer(referred_user_id: int):
        """Начисляет награду рефереру при покупке Premium"""
        try:
            async with get_async_db() as session:
                # Находим приглашенного пользователя
                result = await session.execute(
                    select(User).where(User.telegram_id == referred_user_id)
                )
                referred_user = result.scalar_one_or_none()
                
                if not referred_user or not referred_user.referrer_id:
                    return
                
                # Находим реферера
                referrer = await session.get(User, referred_user.referrer_id)
                
                if not referrer:
                    return
                
                # Начисляем награду
                referrer.referral_balance = (referrer.referral_balance or 0) + config.REFERRAL_REWARD_STARS
                referrer.active_referrals = (referrer.active_referrals or 0) + 1
                
                # Создаем запись о награде
                reward = ReferralReward(
                    user_id=referrer.id,
                    referred_user_id=referred_user.id,
                    amount=config.REFERRAL_REWARD_STARS,
                    status="paid",
                    paid_at=datetime.now()
                )
                session.add(reward)
                
                await session.commit()
                
                logger.info(
                    f"Referral reward: {config.REFERRAL_REWARD_STARS} Stars "
                    f"to {referrer.telegram_id} for {referred_user_id}"
                )
                
        except Exception as e:
            logger.error(f"Error rewarding referrer: {e}", exc_info=True)
    
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
            
            # Получаем список рефералов
            result = await session.execute(
                select(User).where(User.referrer_id == user.id)
            )
            referrals = list(result.scalars().all())
            
            # Считаем активных (с Premium)
            active_count = sum(1 for r in referrals if r.is_premium())
            
            # Формируем реферальную ссылку
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
                .where(User.active_referrals > 0)
                .order_by(User.active_referrals.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
    
    @staticmethod
    async def get_referral_rewards(user_id: int) -> List[ReferralReward]:
        """Получает историю наград пользователя"""
        async with get_async_db() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return []
            
            result = await session.execute(
                select(ReferralReward)
                .where(ReferralReward.user_id == user.id)
                .order_by(ReferralReward.created_at.desc())
            )
            return list(result.scalars().all())