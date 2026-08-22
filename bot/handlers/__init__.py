from aiogram import Dispatcher
from bot.utils.logger import logger

def register_all_handlers(dp: Dispatcher):
    """Регистрирует все обработчики"""
    
    # Команды
    from bot.handlers.commands import register_commands
    register_commands(dp)
    
    # Подписки
    from bot.handlers.subscriptions import register_subscriptions
    register_subscriptions(dp)
    
    # Callback
    from bot.handlers.callbacks import register_callbacks
    register_callbacks(dp)
    
    # Premium
    try:
        from bot.handlers.premium import register_premium
        register_premium(dp)
    except ImportError as e:
        logger.warning(f"Premium handlers not registered: {e}")
    
    # Реферальная программа
    try:
        from bot.handlers.referral import register_referral
        register_referral(dp)
    except ImportError as e:
        logger.warning(f"Referral handlers not registered: {e}")
    
    # Админ-панель
    try:
        from bot.handlers.admin import register_admin
        register_admin(dp)
    except ImportError as e:
        logger.warning(f"Admin handlers not registered: {e}")
    
    # Ошибки
    from bot.handlers.errors import register_errors
    register_errors(dp)
    
    logger.info("All handlers registered")