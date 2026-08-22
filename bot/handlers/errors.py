from aiogram import Dispatcher, types
import traceback

from bot.utils.logger import logger

async def error_handler(event, exception):
    """Обработчик ошибок"""
    logger.error(f"Error: {exception}", exc_info=True)
    
    if hasattr(event, 'message') and event.message:
        try:
            await event.message.answer(
                "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз."
            )
        except:
            pass
    elif hasattr(event, 'callback_query') and event.callback_query:
        try:
            await event.callback_query.answer(
                "Произошла ошибка",
                show_alert=True
            )
        except:
            pass
    
    return True

def register_errors(dp: Dispatcher):
    """Регистрирует обработчики ошибок"""
    dp.errors.register(error_handler)
    logger.info("Error handlers registered")
