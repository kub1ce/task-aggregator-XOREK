# backend/integrations/telegram_wrapper.py
import os
import logging
import asyncio
from pyrogram import Client, filters
from dotenv import load_dotenv
from database import save_message_to_db, Notification
from services.notification_processor import calculate_importance

load_dotenv()
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.api_id = int(os.getenv("TELEGRAM_API_ID"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.session_name = os.getenv("SESSION_NAME", "my_session")
        self.target_chat_id = int(os.getenv("TARGET_CHAT_ID", 0))
        # Создаём клиента *здесь*, но не регистрируем обработчики до _run_bot
        # Это может быть важно, если обработчики регистрируются в контексте loop'а
        # Но для Pyrogram Client это обычно не так. Оставим как есть.
        self.client = Client(self.session_name, api_id=self.api_id, api_hash=self.api_hash)

        # Регистрируем обработчики *внутри* асинхронной функции _run_bot
        # Это гарантирует, что они зарегистрированы в правильном loop'е
        # НЕТ, это не сработает, потому что @self.client.on_message декоратор
        # применяется при создании класса, а не в _run_bot

        # Правильный способ - зарегистрировать внутри _run_bot
        # Используем метод add_handler
        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует обработчики. Вызывается в контексте класса, но обработчик будет использован в loop'е."""
        # Декоратор @self.client.on_message применяется при выполнении этой строки
        # Он создает функцию-обработчик и добавляет её в клиент Pyrogram
        # Важно, чтобы клиент был инициализирован (app.start() вызван) до обработки сообщений
        @self.client.on_message(filters.private)
        async def handle_private_message(client, message):
            await self._process_message(message)

    async def _process_message(self, message):
        """Обрабатывает входящее сообщение."""
        logger.info(f"Получено сообщение от {message.from_user.id if message.from_user else 'Unknown'} с ID {message.id}")
        if not message.from_user:
            logger.warning("Сообщение без пользователя, пропущено.")
            return

        # --- КОНВЕРТАЦИЯ Pyrogram Message в нашу модель Notification (как раньше) ---
        from_user = message.from_user
        chat = message.chat

        first_name = from_user.first_name or ""
        last_name = from_user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()

        if chat.title:
            chat_title = chat.title
        elif chat.first_name:
            chat_title = f"{chat.first_name} {chat.last_name or ''}".strip()
        else:
            chat_title = str(chat.id)

        text_content = message.text or message.caption or ""
        media_type = None
        if message.photo: media_type = "photo"
        elif message.document: media_type = "document"
        elif message.video: media_type = "video"
        elif message.voice: media_type = "voice"
        elif message.audio: media_type = "audio"
        elif message.sticker: media_type = "sticker"
        elif message.animation: media_type = "animation"

        msg_date = message.date.isoformat()

        notification = Notification(
            source='telegram',
            from_user_id=from_user.id,
            from_name=full_name,
            chat_id=chat.id,
            chat_title=chat_title,
            text_content=text_content,
            media_type=media_type,
            date=msg_date,
            message_id=str(message.id), # Преобразуем в строку
            raw_message=str(message)[:1000]
        )

        notification.importance = calculate_importance(notification)
        notification.status = 'unread'
        # --- КОНЕЦ КОНВЕРТАЦИИ ---

        # --- ОТЛАДКА: Выводим информацию о подготовленном уведомлении ---
        logger.info(f"Подготовка к сохранению уведомления от {notification.from_name} (TG)")
        logger.debug(f"Объект Notification: {notification}") # Выводим весь объект (может быть много информации)
        # Или, если debug слишком много, используем info с ключевыми полями:
        logger.info(f"  - ID: {notification.id} (ожидается None)")
        logger.info(f"  - Source: {notification.source}")
        logger.info(f"  - From User ID: {notification.from_user_id}")
        logger.info(f"  - From Name: {notification.from_name}")
        logger.info(f"  - Chat ID: {notification.chat_id}")
        logger.info(f"  - Chat Title: {notification.chat_title}")
        logger.info(f"  - Text Content: '{notification.text_content}'")
        logger.info(f"  - Media Type: {notification.media_type}")
        logger.info(f"  - Date: {notification.date}")
        logger.info(f"  - Message ID: {notification.message_id}")
        logger.info(f"  - Importance: {notification.importance}")
        logger.info(f"  - Status: {notification.status}")
        # --- КОНЕЦ ОТЛАДКИ ---

        notification_id = save_message_to_db(notification)
        if notification_id:
            logger.info(f"✅ Уведомление от {notification.from_name} (TG) сохранено в БД с ID {notification_id}")
        else:
            logger.error(f"❌ Ошибка при сохранении уведомления от TG от {from_user.id}. Text: '{text_content}'")

    def run(self):
        """Запускает бота в новом asyncio event loop в текущем потоке."""
        return
        logger.info("🤖 Подготовка к запуску Telegram бота в новом loop'е...")
        try:
            # Создаём новый asyncio loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logger.info("✅ Новый asyncio loop создан и установлен для потока бота.")
            # Запускаем асинхронную функцию _run_bot в этом loop
            # run_until_complete блокирует выполнение *внутри этого потока* до завершения _run_bot
            # _run_bot вызывает app.start() и app.idle(), что позволяет боту работать
            loop.run_until_complete(self._run_bot())
            # loop.run_until_complete(self._run_bot())
            loop.close()
            logger.info("✅ asyncio loop для бота закрыт.")
        except KeyboardInterrupt:
            logger.info("Telegram бот остановлен пользователем (внутри run).")
        except Exception as e:
            logger.error(f"Ошибка в Telegram боте (внутри run): {e}")
            if not loop.is_closed():
                 loop.close()

    async def _run_bot(self):
        return
        """Внутренняя асинхронная функция для запуска бота."""
        logger.info("🤖 Асинхронный запуск Telegram бота...")
        try:
            # Регистрация обработчиков происходит при создании класса, но
            # они будут использоваться в loop'е, созданном в run()
            # Это должно работать, так как @self.client.on_message связывает
            # функцию с клиентом, и клиент запускается в нужном loop'е
            await self.client.start() # Запускаем клиента
            logger.info("✅ Telegram бот успешно запущен.")
            # Используем app.idle() чтобы бот начал *обрабатывать* сообщения
            # idle() блокирует выполнение до остановки
            await self.client.idle()
            # Если idle() завершится (например, через сигнал), продолжаем
        finally:
            logger.info("🤖 Остановка Telegram бота...")
            await self.client.stop() # Останавливаем клиента
            logger.info("✅ Telegram бот остановлен корректно.")
