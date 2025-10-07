# backend/integrations/__init__.py
import os
import importlib
import threading
import logging
from database import init_db # Импортируем init_db, теперь оно безопасно

logger = logging.getLogger(__name__)

# Инициализируем БД при импорте модуля интеграций
# init_db теперь безопасна для многопоточности
init_db()

def load_and_start_integrations():
    """
    Динамически загружает и запускает интеграции из текущей папки.
    Ищет функции start_integration или run_integration в модуле.
    Запускает Telegram бота через класс в отдельном потоке.
    """
    integrations_dir = os.path.dirname(__file__)
    integration_modules = []

    # Запуск Telegram бота через класс
    from .telegram_wrapper import TelegramBot
    tg_bot = TelegramBot()
    tg_thread = threading.Thread(target=tg_bot.run, daemon=True, name="Integration-TelegramBot")
    tg_thread.start()
    logger.info(f"🚀 Запущена интеграция Telegram бота в потоке: {tg_thread.name}")
    integration_modules.append(("TelegramBot", tg_thread))

    for filename in os.listdir(integrations_dir):
        if filename.endswith('.py') and filename != '__init__.py' and filename != 'telegram_wrapper.py': # Исключаем telegram_wrapper.py
            module_name = f'integrations.{filename[:-3]}' # Убираем '.py'
            try:
                module = importlib.import_module(module_name)
                logger.info(f"✅ Импортирован модуль интеграции: {module_name}")

                start_func = getattr(module, 'start_integration', None)
                run_func = getattr(module, 'run_integration', None)

                if start_func and callable(start_func):
                    thread = threading.Thread(target=start_func, daemon=True, name=f"Integration-{module_name}")
                    thread.start()
                    logger.info(f"🚀 Запущена интеграция (start_integration) в потоке: {thread.name}")
                    integration_modules.append((module_name, thread))
                elif run_func and callable(run_func):
                     thread = threading.Thread(target=run_func, daemon=True, name=f"Integration-{module_name}")
                     thread.start()
                     logger.info(f"🚀 Запущена интеграция (run_integration) в потоке: {thread.name}")
                     integration_modules.append((module_name, thread))
                else:
                    logger.warning(f"⚠️ Модуль интеграции {module_name} не содержит start_integration или run_integration функций. Импортирован, но не запущен.")

            except ImportError as e:
                logger.error(f"❌ Ошибка импорта интеграции {module_name}: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке интеграции {module_name}: {e}")

    logger.info(f"🎉 Загружено и запущено {len(integration_modules)} интеграций (Telegram бот запущен отдельно).")
    return integration_modules

loaded_integrations = load_and_start_integrations()
