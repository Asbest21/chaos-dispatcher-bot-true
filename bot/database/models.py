from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, Index, Text, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from bot.database.connection import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    language = Column(String(10), default="ru")
    
    # Тариф
    tariff = Column(String(20), default="free", nullable=False)
    premium_until = Column(DateTime, nullable=True)
    
    # Статистика
    total_payments = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    is_blocked = Column(Boolean, default=False)
    
    # Реферальная система
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    referral_code = Column(String(20), unique=True, nullable=True)
    referral_balance = Column(Float, default=0.0)
    total_referrals = Column(Integer, default=0)
    active_referrals = Column(Integer, default=0)
    
    # Отношения
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    referrals = relationship("User", backref="referrer", remote_side=[id])
    
    def is_premium(self) -> bool:
        """Проверка активного Premium"""
        return (
            self.tariff == "premium" and 
            self.premium_until and 
            self.premium_until > datetime.now()
        )
    
    def get_subscription_limit(self) -> int:
        """Лимит подписок в зависимости от тарифа"""
        from bot.config import config
        if self.is_premium():
            return config.PREMIUM_SUBSCRIPTIONS_LIMIT
        return config.FREE_SUBSCRIPTIONS_LIMIT
    
    def __repr__(self):
        return f"<User {self.telegram_id}>"


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    billing_day = Column(Integer, nullable=False)  # 1-31
    currency = Column(String(10), default="RUB")
    
    # Статус
    is_active = Column(Boolean, default=True)
    paused_until = Column(DateTime, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_notified = Column(DateTime, nullable=True)
    
    # Отношения
    user = relationship("User", back_populates="subscriptions")
    notifications = relationship("Notification", back_populates="subscription", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_subscriptions_user_active", "user_id", "is_active"),
    )
    
    def __repr__(self):
        return f"<Subscription {self.name} - {self.amount}>"


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    notification_type = Column(String(20), nullable=False)  # 7_days, 3_days, 1_hour
    scheduled_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    is_sent = Column(Boolean, default=False)
    
    # Отношения
    subscription = relationship("Subscription", back_populates="notifications")
    
    __table_args__ = (
        Index("idx_notifications_scheduled", "scheduled_at", "is_sent"),
    )


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="XTR")  # XTR для Stars
    payment_type = Column(String(50), default="premium_stars")
    status = Column(String(20), default="pending")  # pending, completed, failed, refunded
    
    # Telegram Payment
    telegram_payment_id = Column(String(255), nullable=True)
    provider_payment_id = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    
    # Отношения
    user = relationship("User", back_populates="payments")
    
    __table_args__ = (
        Index("idx_payments_user_status", "user_id", "status"),
    )


class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Кто получил награду
    referred_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Кого пригласил
    amount = Column(Float, nullable=False)  # Сумма награды в Stars
    status = Column(String(20), default="pending")  # pending, paid
    created_at = Column(DateTime, server_default=func.now())
    paid_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now())