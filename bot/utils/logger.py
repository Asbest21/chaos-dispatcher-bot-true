import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
import os
from datetime import datetime

# Используем loguru
from loguru import logger

from bot.config import config

class InterceptHandler(logging.Handler):
    """Перехватчик стандартных логов для loguru"""
    
    def emit(self, record):
        # Получаем соответствующий уровень loguru
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        
        # Находим вызывающую функцию
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logger():
    """Настройка логирования"""
    # Удаляем стандартные обработчики
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Настраиваем loguru
    logger.remove()  # Удаляем стандартный обработчик
    
    # Создаем директорию для логов
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Простой формат логов (без timestamp в format_map)
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Вывод в консоль
    logger.add(
        sys.stdout,
        format=log_format,
        level=config.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # Вывод в файл
    logger.add(
        "data/logs/bot.log",
        format=log_format,
        level=config.LOG_LEVEL,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )
    
    # Отдельный файл для ошибок
    logger.add(
        "data/logs/errors.log",
        format=log_format,
        level="ERROR",
        rotation="5 MB",
        retention="90 days",
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )
    
    return logger

# Создаем глобальный логгер
logger = setup_logger()