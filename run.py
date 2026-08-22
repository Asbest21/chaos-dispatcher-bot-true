"""
Скрипт запуска бота
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    """Главная функция"""
    print("=" * 50)
    print("ЗАПУСК БОТА")
    print("=" * 50)
    
    # Проверяем .env
    from bot.config import config
    
    if not config.BOT_TOKEN:
        print("❌ BOT_TOKEN не указан в .env файле!")
        print("Создайте .env файл с BOT_TOKEN=ваш_токен")
        return
    
    print(f"✅ BOT_TOKEN: {'*' * 10}")
    print(f"✅ ADMIN_IDS: {config.ADMIN_IDS}")
    
    # Создаем директории
    Path("data").mkdir(exist_ok=True)
    Path("data/logs").mkdir(exist_ok=True)
    
    # Запускаем бота
    print("\nЗапуск бота...")
    print("Нажмите Ctrl+C для остановки\n")
    
    try:
        from bot.main import main as bot_main
        await bot_main()
    except KeyboardInterrupt:
        print("\nБот остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())