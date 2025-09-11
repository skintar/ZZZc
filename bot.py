"""Основной класс бота."""

import logging
import asyncio
import signal
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand

from config import BotConfig, MESSAGES
from services import CharacterService, SessionService, RankingService
from handlers import BotHandlers


logger = logging.getLogger(__name__)


class CharacterBot:
    """Основной класс Telegram бота для выбора персонажей."""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.handlers: Optional[BotHandlers] = None
        self._shutdown_event = asyncio.Event()
        self._backup_task: Optional[asyncio.Task] = None
        
        # Инициализируем сервисы
        self.character_service = CharacterService(config.characters_dir)
        self.session_service = SessionService(self.character_service)
        self.ranking_service = RankingService(self.character_service)
        
        self._setup_logging()
        self._setup_bot()
        self._setup_handlers()
        self._setup_signal_handlers()
    
    def _setup_logging(self) -> None:
        """Настраивает логирование."""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('bot.log', encoding='utf-8')
            ]
        )
    
    def _setup_bot(self) -> None:
        """Настраивает бота и диспетчер."""
        self.bot = Bot(
            self.config.api_token,
            default=DefaultBotProperties(parse_mode="Markdown")
        )
        self.dp = Dispatcher()
        
        # Регистрируем список команд бота для Telegram-клиентов
        async def set_commands():
            try:
                await self.bot.set_my_commands([
                    BotCommand(command="start", description="Главное меню"),
                    BotCommand(command="help", description="Помощь"),
                    BotCommand(command="menu", description="Показать меню"),
                    BotCommand(command="reload_characters", description="Перезагрузить персонажей (админ)"),
                    BotCommand(command="add_characters", description="Добавить новых персонажей (админ)"),
                ])
            except Exception:
                pass
        
        # Настраиваем TMA
        async def setup_tma():
            try:
                from aiogram.types import MenuButtonWebApp, WebAppInfo
                # Для локальной разработки используем http, для продакшена - https
                if self.config.tma_domain.startswith('localhost'):
                    web_app_url = f"http://{self.config.tma_domain}/web/simple-tma.html"
                else:
                    web_app_url = f"https://{self.config.tma_domain}/web/simple-tma.html"
                await self.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(text="🏆 Рейтинг персонажей", web_app=WebAppInfo(url=web_app_url))
                )
                logger.info(f"TMA настроен: {web_app_url}")
            except ImportError:
                logger.warning("TMA не поддерживается в этой версии aiogram")
            except Exception as e:
                logger.error(f"Ошибка настройки TMA: {e}")
        
        # Вызовем асинхронно после инициализации
        asyncio.create_task(set_commands())
        asyncio.create_task(setup_tma())
    
    def _setup_handlers(self) -> None:
        """Настраивает обработчики сообщений."""
        self.handlers = BotHandlers(
            self.character_service,
            self.session_service,
            self.ranking_service,
            self.config.flood_delay
        )
        
        # Регистрируем обработчики
        @self.dp.message(CommandStart())
        async def handle_start(message):
            await self.handlers.handle_start_message(message, self.bot)
        
        @self.dp.message(Command("help"))
        async def handle_help(message):
            await self.handlers.handle_help_command(message, self.bot)
        
        @self.dp.message(Command("menu"))
        async def handle_menu(message):
            await self.handlers.handle_start_message(message, self.bot)
        
        @self.dp.message(Command("add_characters"))
        async def handle_add_characters(message):
            await self.handlers.handle_add_characters_command(message, self.bot)
        
        @self.dp.message(Command("reload_characters"))
        async def handle_reload_characters(message):
            await self.handlers.handle_reload_characters(message, self.bot)
        
        @self.dp.message()
        async def handle_message(message):
            await self.handlers.handle_start_message(message, self.bot)
        
        @self.dp.callback_query(lambda c: c.data and c.data.startswith('choose:'))
        async def handle_callback(callback_query):
            await self.handlers.handle_choice_callback(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data == 'show_my_rating')
        async def handle_show_my_rating(callback_query):
            await self.handlers.handle_show_my_rating(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data == 'show_global_top')
        async def handle_show_global_top(callback_query):
            await self.handlers.handle_show_global_top(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data == 'start_ranking')
        async def handle_start_ranking(callback_query):
            await self.handlers.handle_start_ranking(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data and c.data.startswith('mode_'))
        async def handle_mode_selection(callback_query):
            await self.handlers.handle_mode_selection(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data == 'back_to_menu')
        async def handle_back_to_menu(callback_query):
            await self.handlers.handle_back_to_menu(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data == 'rate_new_characters')
        async def handle_rate_new_characters(callback_query):
            await self.handlers.handle_rate_new_characters(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data == 'show_full_ranking')
        async def handle_show_full_ranking(callback_query):
            await self.handlers.handle_show_full_ranking(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data == 'go_back')
        async def handle_go_back(callback_query):
            await self.handlers.handle_go_back(callback_query, self.bot)
        
        @self.dp.callback_query(lambda c: c.data == 'continue_session')
        async def handle_continue_session(callback_query):
            await self.handlers.handle_continue_session(callback_query, self.bot)
    
    def _setup_signal_handlers(self) -> None:
        """Настраивает обработчики сигналов для graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Получен сигнал {signum}, начинаем graceful shutdown...")
            self._shutdown_event.set()
        
        try:
            signal.signal(signal.SIGINT, signal_handler)
        except Exception as e:
            logger.debug(f"Не удалось зарегистрировать SIGINT: {e}")
        # На некоторых платформах SIGTERM может отсутствовать
        try:
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, signal_handler)
        except Exception as e:
            logger.debug(f"Не удалось зарегистрировать SIGTERM: {e}")
    
    def _start_backup_task(self) -> None:
        """Запускает периодическое создание бэкапов в рамках активного цикла."""
        async def backup_task():
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(self.config.backup_interval)
                    if not self._shutdown_event.is_set():
                        logger.debug("Запуск периодического бэкапа")
                        self.session_service.create_backup()
                        # Очищаем завершенные сессии
                        self.session_service.cleanup_completed_sessions()
                        logger.debug("Периодический бэкап завершен")
                except asyncio.CancelledError:
                    logger.debug("Задача бэкапа отменена")
                    break
                except Exception as e:
                    logger.error(f"Ошибка в задаче бэкапа: {e}")
                    # Продолжаем работу на следующий цикл
                    
        try:
            self._backup_task = asyncio.create_task(backup_task())
            logger.debug("Задача бэкапа запущена")
        except RuntimeError as e:
            # Нет активного цикла — запустим позже в start()
            logger.debug(f"Не удалось запустить задачу бэкапа: {e}")

    async def _stop_backup_task(self) -> None:
        """Останавливает задачу бэкапа, если она запущена."""
        if self._backup_task is not None:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
            finally:
                self._backup_task = None
    
    def validate_setup(self) -> bool:
        """Проверяет корректность настройки бота."""
        try:
            # Проверяем директорию с персонажами
            if not self.character_service.validate_characters_directory():
                logger.error(
                    MESSAGES["characters_dir_missing"].format(
                        dir=self.config.characters_dir
                    )
                )
                return False
            
            # Проверяем файлы персонажей
            missing_files = self.character_service.validate_character_files()
            if missing_files:
                logger.error(f"Отсутствуют файлы персонажей: {missing_files}")
                return False
            
            logger.info(f"Загружено {len(self.character_service.characters)} персонажей")
            return True
        except Exception as e:
            logger.error(f"Ошибка валидации: {e}")
            return False
    
    async def start(self) -> None:
        """Запускает бота."""
        if not self.validate_setup():
            logger.error("Ошибка валидации настроек бота")
            return
        
        logger.info(MESSAGES["bot_started"])
        
        try:
            # Подготовка бэкапов: очистка старых и запуск периодической задачи
            self.session_service.cleanup_old_backups(self.config.max_backups)
            self._start_backup_task()
            # Запускаем бота в отдельной задаче и ожидаем сигнала завершения
            polling_task = asyncio.create_task(self.dp.start_polling(self.bot))
            shutdown_waiter = asyncio.create_task(self._shutdown_event.wait())
            done, pending = await asyncio.wait({polling_task, shutdown_waiter}, return_when=asyncio.FIRST_COMPLETED)
            # Если получили сигнал завершения — останавливаем поллинг
            if shutdown_waiter in done and not polling_task.done():
                try:
                    # В aiogram 3 есть метод остановки поллинга
                    if hasattr(self.dp, "stop_polling"):
                        await self.dp.stop_polling()
                except Exception as e:
                    logger.debug(f"Ошибка при остановке поллинга: {e}")
                finally:
                    polling_task.cancel()
                    try:
                        await polling_task
                    except asyncio.CancelledError:
                        pass
        except TelegramAPIError as e:
            logger.error(f"Ошибка Telegram API: {e}")
            raise
        except KeyboardInterrupt:
            logger.info("Получен KeyboardInterrupt, останавливаем бота...")
            self._shutdown_event.set()
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """Очищает ресурсы при завершении работы с улучшенным graceful shutdown."""
        logger.info("🛑 Начинаем graceful shutdown...")
        
        try:
            # Шаг 1: Прекращаем принимать новые запросы
            logger.info("🚨 Останавливаем прием новых запросов...")
            self._shutdown_event.set()
            
            # Шаг 2: Ждем завершения текущих операций (максимум 2 секунды)
            logger.info("⏳ Ожидаем завершения текущих операций...")
            await asyncio.sleep(2)  # Даем время для завершения активных обработчиков
            
            # Шаг 3: Сохраняем все активные сессии
            logger.info("💾 Сохраняем активные сессии...")
            try:
                active_sessions = len([s for s in self.session_service._sessions.values() if not s.is_completed])
                if active_sessions > 0:
                    logger.info(f"💾 Найдено {active_sessions} активных сессий для сохранения")
            except Exception as e:
                logger.error(f"Ошибка при подсчете сессий: {e}")
            
            # Шаг 4: Принудительно сохраняем данные с бэкапом
            logger.info("💾 Сохраняем глобальные данные...")
            self.session_service.force_save_with_backup()
            logger.info("✅ Глобальные данные сохранены")
            
        except Exception as e:
            logger.error(f"🚨 Ошибка при сохранении данных при завершении: {e}")
        
        # Шаг 5: Останавливаем задачу бэкапа
        try:
            logger.info("🔄 Останавливаем задачу бэкапа...")
            await self._stop_backup_task()
            logger.info("✅ Задача бэкапа остановлена")
        except Exception as e:
            logger.error(f"🚨 Ошибка при остановке задачи бэкапа: {e}")

        # Шаг 6: Закрываем соединения с Telegram
        if self.bot:
            try:
                logger.info("🔌 Закрываем соединение с Telegram...")
                await self.bot.session.close()
                logger.info("✅ Соединение с Telegram закрыто")
            except Exception as e:
                logger.error(f"🚨 Ошибка при закрытии соединения: {e}")
        
        logger.info("✅ Graceful shutdown завершен успешно!")


async def create_and_run_bot(config: BotConfig) -> None:
    """Создает и запускает бота."""
    bot = CharacterBot(config)
    await bot.start()
