"""Тесты для основного класса бота."""

import pytest
import asyncio
import logging
import signal
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from bot import CharacterBot, create_and_run_bot
from config import BotConfig
from services import CharacterService, SessionService, RankingService
from handlers import BotHandlers


class TestCharacterBot:
    """Тесты для основного класса бота."""
    
    @pytest.fixture
    def mock_config(self):
        """Создает мокированную конфигурацию."""
        config = MagicMock(spec=BotConfig)
        config.api_token = "test_token:123456789"
        config.characters_dir = "test_characters"
        config.log_level = "INFO"
        config.flood_delay = 0.5
        config.backup_interval = 3600
        config.tma_domain = "localhost:8080"
        return config
    
    @pytest.fixture
    def bot_instance(self, mock_config):
        """Создает экземпляр бота с мокированной конфигурацией."""
        with patch('bot.CharacterService'), \
             patch('bot.SessionService'), \
             patch('bot.RankingService'), \
             patch('bot.BotHandlers'):
            return CharacterBot(mock_config)
    
    def test_bot_initialization(self, mock_config):
        """Тест инициализации бота."""
        with patch('bot.CharacterService') as mock_char_service, \
             patch('bot.SessionService') as mock_session_service, \
             patch('bot.RankingService') as mock_ranking_service, \
             patch('bot.BotHandlers') as mock_handlers:
            
            bot = CharacterBot(mock_config)
            
            # Проверяем, что конфигурация сохранена
            assert bot.config == mock_config
            
            # Проверяем, что сервисы инициализированы
            mock_char_service.assert_called_once_with(mock_config.characters_dir)
            mock_session_service.assert_called_once()
            mock_ranking_service.assert_called_once()
            
            # Проверяем начальные значения
            assert bot._shutdown_event is not None
            assert isinstance(bot._shutdown_event, asyncio.Event)
            assert bot._backup_task is None
    
    def test_setup_logging(self, bot_instance):
        """Тест настройки логирования."""
        with patch('logging.basicConfig') as mock_basic_config:
            bot_instance._setup_logging()
            
            # Проверяем, что basicConfig был вызван
            mock_basic_config.assert_called_once()
            call_args = mock_basic_config.call_args[1]
            
            # Проверяем параметры логирования
            assert call_args['level'] == logging.INFO
            assert 'format' in call_args
            assert 'handlers' in call_args
            assert len(call_args['handlers']) == 2  # StreamHandler и FileHandler
    
    def test_setup_bot(self, bot_instance):
        """Тест настройки бота и диспетчера."""
        with patch('aiogram.Bot') as mock_bot_class, \
             patch('aiogram.Dispatcher') as mock_dispatcher_class:
            
            mock_bot = MagicMock()
            mock_dispatcher = MagicMock()
            mock_bot_class.return_value = mock_bot
            mock_dispatcher_class.return_value = mock_dispatcher
            
            bot_instance._setup_bot()
            
            # Проверяем, что Bot и Dispatcher созданы
            mock_bot_class.assert_called_once()
            mock_dispatcher_class.assert_called_once()
            
            assert bot_instance.bot == mock_bot
            assert bot_instance.dp == mock_dispatcher
    
    def test_setup_handlers(self, bot_instance):
        """Тест настройки обработчиков."""
        # Мокируем BotHandlers
        with patch.object(bot_instance, 'handlers') as mock_handlers:
            mock_dp = MagicMock()
            bot_instance.dp = mock_dp
            
            bot_instance._setup_handlers()
            
            # Проверяем, что обработчики зарегистрированы
            assert mock_dp.message.called
            assert mock_dp.callback_query.called
    
    def test_setup_signal_handlers(self, bot_instance):
        """Тест настройки обработчиков сигналов."""
        with patch('signal.signal') as mock_signal:
            bot_instance._setup_signal_handlers()
            
            # Проверяем, что сигналы зарегистрированы
            assert mock_signal.called
            
            # Проверяем обработку SIGINT
            calls = mock_signal.call_args_list
            sigint_registered = any(call[0][0] == signal.SIGINT for call in calls)
            assert sigint_registered
    
    def test_signal_handler_sets_shutdown_event(self, bot_instance):
        """Тест что обработчик сигнала устанавливает событие завершения."""
        # Проверяем начальное состояние
        assert not bot_instance._shutdown_event.is_set()
        
        # Симулируем получение сигнала
        with patch('signal.signal') as mock_signal:
            bot_instance._setup_signal_handlers()
            
            # Получаем зарегистрированный обработчик сигнала
            signal_handler = None
            for call in mock_signal.call_args_list:
                if call[0][0] == signal.SIGINT:
                    signal_handler = call[0][1]
                    break
            
            assert signal_handler is not None
            
            # Вызываем обработчик
            signal_handler(signal.SIGINT, None)
            
            # Проверяем, что событие установлено
            assert bot_instance._shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_start_backup_task(self, bot_instance):
        """Тест запуска задачи бэкапа."""
        # Мокируем методы сервиса
        bot_instance.session_service.create_backup = MagicMock()
        bot_instance.session_service.cleanup_completed_sessions = MagicMock()
        
        # Настраиваем короткий интервал для теста
        bot_instance.config.backup_interval = 0.1
        
        # Запускаем задачу бэкапа
        bot_instance._start_backup_task()
        
        # Проверяем, что задача создана
        assert bot_instance._backup_task is not None
        assert isinstance(bot_instance._backup_task, asyncio.Task)
        
        # Ждем короткое время для выполнения бэкапа
        await asyncio.sleep(0.2)
        
        # Останавливаем задачу
        bot_instance._shutdown_event.set()
        
        try:
            await asyncio.wait_for(bot_instance._backup_task, timeout=1.0)
        except asyncio.TimeoutError:
            bot_instance._backup_task.cancel()
        
        # Проверяем, что методы бэкапа вызывались
        assert bot_instance.session_service.create_backup.called
        assert bot_instance.session_service.cleanup_completed_sessions.called
    
    def test_stop_backup_task(self, bot_instance):
        """Тест остановки задачи бэкапа."""
        # Создаем мокированную задачу
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        bot_instance._backup_task = mock_task
        
        bot_instance._stop_backup_task()
        
        # Проверяем, что задача отменена
        mock_task.cancel.assert_called_once()
        assert bot_instance._backup_task is None
    
    def test_stop_backup_task_no_task(self, bot_instance):
        """Тест остановки бэкапа когда задача не запущена."""
        # Убеждаемся, что задачи нет
        bot_instance._backup_task = None
        
        # Не должно вызывать исключение
        try:
            bot_instance._stop_backup_task()
        except Exception as e:
            pytest.fail(f"Остановка бэкапа без активной задачи не должна вызывать ошибку: {e}")
    
    def test_validate_setup(self, bot_instance):
        """Тест валидации настройки бота."""
        # Мокируем сервисы для успешной валидации
        bot_instance.character_service.validate_character_files = MagicMock(return_value=[])
        bot_instance.bot = MagicMock()
        bot_instance.dp = MagicMock()
        bot_instance.handlers = MagicMock()
        
        # Валидация должна пройти успешно
        try:
            is_valid = bot_instance.validate_setup()
            assert is_valid is True
        except Exception as e:
            pytest.fail(f"Валидация не должна вызывать исключение при корректной настройке: {e}")
    
    def test_validate_setup_missing_characters(self, bot_instance):
        """Тест валидации с отсутствующими персонажами."""
        # Настраиваем отсутствующие файлы персонажей
        bot_instance.character_service.validate_character_files = MagicMock(
            return_value=["missing1.png", "missing2.png"]
        )
        bot_instance.bot = MagicMock()
        bot_instance.dp = MagicMock()
        bot_instance.handlers = MagicMock()
        
        # Валидация должна пройти с предупреждением
        is_valid = bot_instance.validate_setup()
        assert is_valid is True  # Отсутствующие файлы не блокируют запуск
    
    def test_validate_setup_missing_components(self, bot_instance):
        """Тест валидации с отсутствующими компонентами."""
        # Убираем критические компоненты
        bot_instance.bot = None
        
        is_valid = bot_instance.validate_setup()
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_cleanup(self, bot_instance):
        """Тест очистки ресурсов бота."""
        # Настраиваем мокированные компоненты
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        
        mock_bot = MagicMock()
        mock_bot.session = mock_session
        mock_bot.close = AsyncMock()
        
        bot_instance.bot = mock_bot
        bot_instance.session_service.force_save_with_backup = MagicMock()
        
        # Создаем задачу бэкапа
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        bot_instance._backup_task = mock_task
        
        await bot_instance.cleanup()
        
        # Проверяем, что ресурсы очищены
        bot_instance.session_service.force_save_with_backup.assert_called_once()
        mock_task.cancel.assert_called_once()
        mock_bot.close.assert_called_once()


class TestBotUtilityFunctions:
    """Тесты для вспомогательных функций бота."""
    
    @pytest.mark.asyncio
    async def test_create_and_run_bot(self):
        """Тест функции создания и запуска бота."""
        mock_config = MagicMock(spec=BotConfig)
        mock_config.api_token = "test_token"
        
        with patch('bot.CharacterBot') as mock_bot_class:
            mock_bot_instance = MagicMock()
            mock_bot_instance.start = AsyncMock()
            mock_bot_class.return_value = mock_bot_instance
            
            await create_and_run_bot(mock_config)
            
            # Проверяем, что бот создан и запущен
            mock_bot_class.assert_called_once_with(mock_config)
            mock_bot_instance.start.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])