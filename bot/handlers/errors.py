from aiogram import Dispatcher, types
from aiogram.exceptions import TelegramAPIError
import traceback

from bot.utils.logger import logger

async def error_handler(event: types.ErrorEvent, exception: Exception):
    """Обработчик ошибок для dispatcher"""
    logger.error(f"Update caused error: {exception}", exc_info=True)
    
    # Получаем update из event
    update = event.update if hasattr(event, 'update') else None
    
    # Отправляем сообщение пользователю
    if update:
        if update.message:
            try:
                await update.message.answer(
                    "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз."
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
        elif update.callback_query:
            try:
                await update.callback_query.answer(
                    "Произошла ошибка",
                    show_alert=True
                )
            except Exception as e:
                logger.error(f"Failed to send callback error: {e}")
    
    return True

def register_errors(dp: Dispatcher):
    """Регистрирует обработчики ошибок"""
    dp.errors.register(error_handler)
    
    logger.info("Error handlers registered")