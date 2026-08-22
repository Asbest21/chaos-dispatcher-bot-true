import asyncio
from typing import Optional, Any, List, AsyncGenerator
from contextlib import asynccontextmanager
import aiosqlite
import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from bot.config import config

# SQLAlchemy Base
Base = declarative_base()

# Настройка движка базы данных
if config.DATABASE_URL.startswith("postgresql"):
    async_engine = create_async_engine(
        config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True
    )
    sync_engine = create_engine(
        config.DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20
    )
else:
    # Для SQLite
    sqlite_path = config.DATABASE_URL.replace("sqlite:///", "")
    
    # Создаем директорию
    sqlite_dir = os.path.dirname(sqlite_path)
    if sqlite_dir:
        os.makedirs(sqlite_dir, exist_ok=True)
    
    async_engine = create_async_engine(
        f"sqlite+aiosqlite:///{sqlite_path}",
        echo=False,
        poolclass=NullPool
    )
    sync_engine = create_engine(
        config.DATABASE_URL,
        echo=False,
        poolclass=NullPool
    )

# Фабрики сессий
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

SyncSessionLocal = sessionmaker(
    sync_engine,
    expire_on_commit=False
)

@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Асинхронная сессия базы данных"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Инициализация базы данных"""
    try:
        async with async_engine.begin() as conn:
            # Импортируем модели здесь, чтобы избежать циклических импортов
            from bot.database.models import User, Subscription, Notification, Payment, ReferralReward, AuditLog
            await conn.run_sync(Base.metadata.create_all)
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        raise

async def close_db():
    """Закрытие соединений"""
    try:
        await async_engine.dispose()
        sync_engine.dispose()
        print("✅ Соединения закрыты")
    except Exception as e:
        print(f"⚠️ Ошибка при закрытии: {e}")