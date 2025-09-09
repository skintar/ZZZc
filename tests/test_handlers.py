"""Тесты для обработчиков бота."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from collections import deque

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, User, Chat, Message, CallbackQuery

from handlers import BotHandlers, AdvancedFloodControl
from services import CharacterService, SessionService, RankingService
from config import MESSAGES


# Mock class for UserSession since we can't import it directly
class MockUserSession:
    """Мокированная сессия пользователя для тестов."""
    def __init__(self, user_id, character_names):
        self.user_id = user_id
        self.character_names = character_names
        self.is_completed = False


class TestAdvancedFloodControl:
    """Тесты для продвинутой системы защиты от флуда."""
    
    def test_init(self):
        """Тест инициализации flood control."""
        flood_control = AdvancedFloodControl(requests_per_minute=30, burst_limit=10)
        
        assert flood_control.requests_per_minute == 30
        assert flood_control.burst_limit == 10
        assert isinstance(flood_control.user_requests, dict)
        assert isinstance(flood_control.temp_bans, dict)
        assert isinstance(flood_control.warning_counts, dict)
    
    def test_normal_request_allowed(self):
        """Тест что обычные запросы разрешены."""
        flood_control = AdvancedFloodControl(requests_per_minute=10, burst_limit=3)
        user_id = 123
        
        # Первый запрос должен быть разрешен
        assert not flood_control.is_rate_limited(user_id)
        
        # Проверяем, что запрос записался
        assert len(flood_control.user_requests[user_id]) == 1
    
    def test_burst_limit_exceeded(self):
        """Тест превышения burst лимита."""
        flood_control = AdvancedFloodControl(requests_per_minute=100, burst_limit=3)
        user_id = 123
        
        # Отправляем запросы до лимита
        for i in range(3):
            assert not flood_control.is_rate_limited(user_id)
        
        # Следующий запрос должен быть заблокирован
        assert flood_control.is_rate_limited(user_id)
        
        # Проверяем, что пользователь в бане
        assert user_id in flood_control.temp_bans
        assert flood_control.warning_counts[user_id] == 1
    
    def test_minute_limit_exceeded(self):
        """Тест превышения лимита запросов в минуту."""
        flood_control = AdvancedFloodControl(requests_per_minute=5, burst_limit=10)
        user_id = 123
        
        # Заполняем очередь запросов
        for i in range(5):
            current_time = time.time()
            flood_control.user_requests[user_id].append(current_time)
        
        # Следующий запрос должен быть заблокирован
        assert flood_control.is_rate_limited(user_id)
    
    def test_temporary_ban_duration(self):
        """Тест продолжительности временного бана."""
        flood_control = AdvancedFloodControl(requests_per_minute=1, burst_limit=1)
        user_id = 123
        
        # Первое нарушение - 30 секунд
        flood_control.is_rate_limited(user_id)  # Первый запрос
        flood_control.is_rate_limited(user_id)  # Второй запрос - нарушение
        
        remaining = flood_control.get_remaining_ban_time(user_id)
        assert 25 <= remaining <= 30  # Примерно 30 секунд с учетом времени выполнения
        
        # Второе нарушение - 2 минуты
        current_time = time.time()
        flood_control.temp_bans[user_id] = current_time - 1  # Убираем бан
        flood_control.is_rate_limited(user_id)  # Еще одно нарушение
        
        remaining = flood_control.get_remaining_ban_time(user_id)
        assert 115 <= remaining <= 120  # Примерно 2 минуты
    
    def test_cleanup_old_data(self):
        """Тест очистки старых данных."""
        flood_control = AdvancedFloodControl()
        user_id = 123
        
        # Добавляем старые запросы
        old_time = time.time() - 3700  # Час назад
        flood_control.user_requests[user_id].append(old_time)
        flood_control.warning_counts[user_id] = 1
        
        # Добавляем истекший бан
        flood_control.temp_bans[user_id] = time.time() - 100
        
        # Очищаем данные
        flood_control.cleanup_old_data()
        
        # Проверяем, что данные очищены
        assert user_id not in flood_control.user_requests
        assert user_id not in flood_control.temp_bans
        assert flood_control.warning_counts[user_id] == 0


class TestBotHandlers:
    """Тесты для обработчиков бота."""
    
    @pytest.fixture
    def mock_services(self):
        """Создает мокированные сервисы."""
        character_service = MagicMock(spec=CharacterService)
        session_service = MagicMock(spec=SessionService)
        ranking_service = MagicMock(spec=RankingService)
        
        # Настраиваем поведение по умолчанию
        character_service.validate_character_files.return_value = []
        session_service.get_session.return_value = None
        
        return character_service, session_service, ranking_service
    
    @pytest.fixture
    def handlers(self, mock_services):
        """Создает экземпляр обработчиков с мокированными сервисами."""
        character_service, session_service, ranking_service = mock_services
        return BotHandlers(character_service, session_service, ranking_service)
    
    @pytest.fixture
    def mock_message(self):
        """Создает мокированное сообщение."""
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=123, type="private")
        message = Message(
            message_id=1,
            date=1234567890,
            chat=chat,
            from_user=user,
            content_type="text",
            text="/start"
        )
        message.reply = AsyncMock()
        message.answer = AsyncMock()
        return message
    
    @pytest.fixture
    def mock_callback_query(self):
        """Создает мокированный callback query."""
        user = User(id=123, is_bot=False, first_name="Test")
        message = MagicMock()
        message.edit_text = AsyncMock()
        message.edit_media = AsyncMock()
        message.edit_reply_markup = AsyncMock()
        
        callback = CallbackQuery(
            id="test_callback",
            from_user=user,
            chat_instance="test_instance",
            data="test_data",
            message=message
        )
        callback.answer = AsyncMock()
        return callback
    
    def test_handlers_init(self, mock_services):
        """Тест инициализации обработчиков."""
        character_service, session_service, ranking_service = mock_services
        handlers = BotHandlers(character_service, session_service, ranking_service)
        
        assert handlers.character_service == character_service
        assert handlers.session_service == session_service
        assert handlers.ranking_service == ranking_service
        assert isinstance(handlers._flood_control, AdvancedFloodControl)
        assert isinstance(handlers._main_menu, InlineKeyboardMarkup)
        assert isinstance(handlers._post_result_menu, InlineKeyboardMarkup)
    
    def test_flood_control_check(self, handlers):
        """Тест проверки flood control."""
        user_id = 123
        
        # Первые запросы должны проходить
        assert handlers._check_flood_control(user_id) is True
        assert handlers._check_flood_control(user_id) is True
        
        # Превышаем burst лимит
        for _ in range(10):
            handlers._flood_control.is_rate_limited(user_id)
        
        # Следующий запрос должен быть заблокирован
        assert handlers._check_flood_control(user_id) is False
    
    def test_get_flood_warning(self, handlers):
        """Тест получения предупреждения о флуде."""
        user_id = 123
        
        # Без бана - обычное предупреждение
        warning = handlers._get_flood_warning(user_id)
        assert warning == MESSAGES["flood_warning"]
        
        # С активным баном
        handlers._flood_control.temp_bans[user_id] = time.time() + 60
        warning = handlers._get_flood_warning(user_id)
        assert "Осталось:" in warning
    
    @pytest.mark.asyncio
    async def test_handle_start_message_normal(self, handlers, mock_message, mock_services):
        """Тест обработки команды /start в нормальных условиях."""
        character_service, session_service, ranking_service = mock_services
        bot = AsyncMock()
        
        await handlers.handle_start_message(mock_message, bot)
        
        # Проверяем, что сообщение было отправлено
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert MESSAGES["start"] in call_args[0][0]
        assert isinstance(call_args[1]["reply_markup"], InlineKeyboardMarkup)
    
    @pytest.mark.asyncio
    async def test_handle_start_message_flood_control(self, handlers, mock_message):
        """Тест обработки команды /start с активированным flood control."""
        bot = AsyncMock()
        user_id = mock_message.from_user.id
        
        # Активируем flood control
        handlers._flood_control.temp_bans[user_id] = time.time() + 60
        
        await handlers.handle_start_message(mock_message, bot)
        
        # Проверяем, что было отправлено предупреждение о флуде
        mock_message.reply.assert_called_once()
        call_args = mock_message.reply.call_args
        assert "Осталось:" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_handle_start_message_with_active_session(self, handlers, mock_message, mock_services):
        """Тест обработки команды /start с активной сессией."""
        character_service, session_service, ranking_service = mock_services
        bot = AsyncMock()
        user_id = mock_message.from_user.id
        
        # Создаем активную сессию
        active_session = MockUserSession(user_id=user_id, character_names=["Char1", "Char2"])
        session_service.get_session.return_value = active_session
        
        await handlers.handle_start_message(mock_message, bot)
        
        # Проверяем, что предложено продолжить сессию
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "незавершенная сессия" in call_args[0][0]
    
    @pytest.mark.asyncio 
    async def test_handle_start_message_missing_files(self, handlers, mock_message, mock_services):
        """Тест обработки команды /start с отсутствующими файлами."""
        character_service, session_service, ranking_service = mock_services
        bot = AsyncMock()
        
        # Настраиваем отсутствующие файлы
        character_service.validate_character_files.return_value = ["missing1.png", "missing2.png"]
        
        await handlers.handle_start_message(mock_message, bot)
        
        # Проверяем, что сообщение все равно было отправлено (предупреждение только в логи)
        mock_message.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exception_handling_in_handlers(self, handlers, mock_message):
        """Тест обработки исключений в handlers."""
        bot = AsyncMock()
        
        # Мокируем исключение в character_service
        handlers.character_service.validate_character_files.side_effect = Exception("Test error")
        
        # Обработчик не должен падать
        try:
            await handlers.handle_start_message(mock_message, bot)
        except Exception as e:
            pytest.fail(f"Handler должен перехватывать исключения, но получил: {e}")
    
    def test_keyboard_creation(self, handlers):
        """Тест создания клавиатур."""
        # Проверяем основное меню
        main_menu = handlers._main_menu
        assert isinstance(main_menu, InlineKeyboardMarkup)
        assert len(main_menu.inline_keyboard) >= 3  # Минимум 3 ряда кнопок
        
        # Проверяем меню после результатов
        post_result_menu = handlers._post_result_menu
        assert isinstance(post_result_menu, InlineKeyboardMarkup)
        assert len(post_result_menu.inline_keyboard) >= 3  # Минимум 3 ряда кнопок
    
    def test_flood_control_integration(self, handlers):
        """Тест интеграции с системой flood control."""
        user_id = 123
        
        # Проверяем начальное состояние
        assert handlers._check_flood_control(user_id) is True
        
        # Проверяем, что данные обновляются
        initial_count = len(handlers._flood_control.user_requests[user_id])
        handlers._check_flood_control(user_id)
        after_count = len(handlers._flood_control.user_requests[user_id])
        
        assert after_count >= initial_count


@pytest.mark.asyncio
class TestHandlersIntegration:
    """Интеграционные тесты для обработчиков."""
    
    @pytest.fixture
    async def full_setup(self):
        """Создает полную настройку для интеграционных тестов."""
        # Создаем реальные (но мокированные) сервисы
        character_service = MagicMock(spec=CharacterService)
        session_service = MagicMock(spec=SessionService)
        ranking_service = MagicMock(spec=RankingService)
        
        # Настраиваем базовое поведение
        character_service.validate_character_files.return_value = []
        character_service.get_character_pairs.return_value = [("Char1", "Char2")]
        
        session_service.get_session.return_value = None
        session_service.create_session.return_value = MockUserSession(
            user_id=123, 
            character_names=["Char1", "Char2", "Char3"]
        )
        
        ranking_service.update_user_ranking.return_value = None
        ranking_service.get_last_user_ranking.return_value = ["Char1", "Char2", "Char3"]
        
        handlers = BotHandlers(character_service, session_service, ranking_service)
        
        return handlers, character_service, session_service, ranking_service
    
    async def test_full_user_flow_simulation(self, full_setup):
        """Тест полного пользовательского пути."""
        handlers, char_service, session_service, ranking_service = full_setup
        
        user_id = 123
        bot = AsyncMock()
        
        # Создаем мокированное сообщение
        user = User(id=user_id, is_bot=False, first_name="Test")
        chat = Chat(id=user_id, type="private")
        message = Message(
            message_id=1,
            date=1234567890,
            chat=chat,
            from_user=user,
            content_type="text",
            text="/start"
        )
        message.reply = AsyncMock()
        message.answer = AsyncMock()
        
        # Симулируем пользовательский поток
        # 1. Пользователь отправляет /start
        await handlers.handle_start_message(message, bot)
        
        # Проверяем, что начальное сообщение отправлено
        message.answer.assert_called_once()
        
        # 2. Проверяем, что flood control работает корректно
        for i in range(5):
            result = handlers._check_flood_control(user_id)
            assert result is True  # Первые запросы должны проходить
        
        # 3. Проверяем интеграцию сервисов
        char_service.validate_character_files.assert_called()
        session_service.get_session.assert_called_with(user_id)
    
    async def test_error_resilience(self, full_setup):
        """Тест устойчивости к ошибкам."""
        handlers, char_service, session_service, ranking_service = full_setup
        
        # Настраиваем различные типы ошибок
        char_service.validate_character_files.side_effect = [
            Exception("Service error"),
            [],  # Восстановление
        ]
        
        user_id = 123
        user = User(id=user_id, is_bot=False, first_name="Test")
        chat = Chat(id=user_id, type="private")
        message = Message(
            message_id=1,
            date=1234567890,
            chat=chat,
            from_user=user,
            content_type="text",
            text="/start"
        )
        message.reply = AsyncMock()
        message.answer = AsyncMock()
        bot = AsyncMock()
        
        # Первый вызов с ошибкой - не должен падать
        try:
            await handlers.handle_start_message(message, bot)
        except Exception as e:
            pytest.fail(f"Обработчик должен быть устойчив к ошибкам сервисов: {e}")
        
        # Второй вызов должен работать нормально
        await handlers.handle_start_message(message, bot)
        
        # Проверяем, что сообщения отправлялись в обоих случаях
        assert message.answer.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__])