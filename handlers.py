"""Обработчики сообщений и callback'ов."""

import asyncio
import logging
import random
import time
from typing import Dict, Deque
from collections import deque, defaultdict

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, FSInputFile
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

from services import CharacterService, SessionService, RankingService
from config import MESSAGES, CHARACTER_EMOJIS, MOTIVATIONAL_PHRASES, EVALUATION_MODES


logger = logging.getLogger(__name__)


class AdvancedFloodControl:
    """Продвинутая система защиты от флуда с скользящими окнами."""
    
    def __init__(self, requests_per_minute: int = 20, burst_limit: int = 5):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.user_requests: Dict[int, Deque[float]] = defaultdict(deque)
        self.temp_bans: Dict[int, float] = {}  # user_id -> ban_end_time
        self.warning_counts: Dict[int, int] = defaultdict(int)
    
    def is_rate_limited(self, user_id: int) -> bool:
        """Проверяет, ограничен ли пользователь по скорости запросов."""
        current_time = time.time()
        
        # Проверяем временный бан
        if user_id in self.temp_bans:
            if current_time < self.temp_bans[user_id]:
                return True
            else:
                del self.temp_bans[user_id]
                self.warning_counts[user_id] = 0
        
        # Очищаем старые запросы (старше 1 минуты)
        user_queue = self.user_requests[user_id]
        while user_queue and current_time - user_queue[0] > 60:
            user_queue.popleft()
        
        # Проверяем лимит запросов в минуту
        if len(user_queue) >= self.requests_per_minute:
            self._apply_penalty(user_id, current_time)
            return True
        
        # Проверяем burst лимит (последние 10 секунд)
        recent_requests = sum(1 for req_time in user_queue if current_time - req_time <= 10)
        if recent_requests >= self.burst_limit:
            self._apply_penalty(user_id, current_time)
            return True
        
        # Добавляем текущий запрос
        user_queue.append(current_time)
        return False
    
    def _apply_penalty(self, user_id: int, current_time: float) -> None:
        """Применяет штраф к пользователю."""
        self.warning_counts[user_id] += 1
        warnings = self.warning_counts[user_id]
        
        if warnings == 1:
            # Первое предупреждение - бан на 30 секунд
            ban_duration = 30
        elif warnings == 2:
            # Второе предупреждение - бан на 2 минуты
            ban_duration = 120
        elif warnings >= 3:
            # Третье и последующие - бан на 10 минут
            ban_duration = 600
        else:
            ban_duration = 30
        
        self.temp_bans[user_id] = current_time + ban_duration
        logger.warning(f"Пользователь {user_id} временно заблокирован на {ban_duration} секунд (предупреждение #{warnings})")
    
    def get_remaining_ban_time(self, user_id: int) -> int:
        """Возвращает оставшееся время бана в секундах."""
        if user_id not in self.temp_bans:
            return 0
        
        remaining = self.temp_bans[user_id] - time.time()
        return max(0, int(remaining))
    
    def cleanup_old_data(self) -> None:
        """Очищает старые данные для экономии памяти."""
        current_time = time.time()
        
        # Очищаем истекшие баны
        expired_bans = [uid for uid, ban_time in self.temp_bans.items() if current_time >= ban_time]
        for uid in expired_bans:
            del self.temp_bans[uid]
            self.warning_counts[uid] = 0
        
        # Очищаем старые запросы неактивных пользователей
        inactive_users = []
        for user_id, requests in self.user_requests.items():
            # Очищаем запросы старше часа
            while requests and current_time - requests[0] > 3600:
                requests.popleft()
            
            # Если пользователь неактивен более часа, удаляем его данные
            if not requests or current_time - requests[-1] > 3600:
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            if user_id in self.user_requests:
                del self.user_requests[user_id]
            if user_id in self.warning_counts:
                del self.warning_counts[user_id]
    """Класс для обработки сообщений бота."""
    
class BotHandlers:
    """Класс для обработки сообщений бота."""
    
    def __init__(
        self,
        character_service: CharacterService,
        session_service: SessionService,
        ranking_service: RankingService,
        flood_delay: float = 0.5
    ):
        self.character_service = character_service
        self.session_service = session_service
        self.ranking_service = ranking_service
        
        # Новая продвинутая система защиты от флуда
        self._flood_control = AdvancedFloodControl(requests_per_minute=20, burst_limit=5)
        
        # Старая система для обратной совместимости
        self._last_action_time: Dict[int, float] = {}
        self._flood_delay = flood_delay
        
        # Вспомогательные клавиатуры
        # Компактное главное меню (более сбалансированное расположение)
        self._main_menu = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Создать рейтинг", callback_data="start_ranking"),
             InlineKeyboardButton(text="🌍 Глобальный топ", callback_data="show_global_top")],
            [InlineKeyboardButton(text="📊 Мой рейтинг", callback_data="show_my_rating")]
        ])
        
        # Компактное меню после результатов
        self._post_result_menu = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Пересоздать", callback_data="start_ranking"),
             InlineKeyboardButton(text="📊 Мой топ", callback_data="show_my_rating")],
            [InlineKeyboardButton(text="🌍 Общий топ", callback_data="show_global_top"),
             InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
    
    def _check_flood_control(self, user_id: int) -> bool:
        """Проверяет, не слишком ли быстро пользователь выполняет действия."""
        # Используем новую продвинутую систему
        is_limited = self._flood_control.is_rate_limited(user_id)
        
        if is_limited:
            # Периодическая очистка старых данных
            if random.random() < 0.1:  # 10% вероятность
                self._flood_control.cleanup_old_data()
        
        return not is_limited
    
    def _get_flood_warning(self, user_id: int) -> str:
        """Возвращает предупреждение о слишком быстрых действиях."""
        remaining_ban = self._flood_control.get_remaining_ban_time(user_id)
        if remaining_ban > 0:
            minutes = remaining_ban // 60
            seconds = remaining_ban % 60
            if minutes > 0:
                return f"⏱️ Вы временно ограничены. Осталось: {minutes}м {seconds}с"
            else:
                return f"⏱️ Вы временно ограничены. Осталось: {seconds}с"
        return MESSAGES["flood_warning"]
    
    async def handle_start_message(self, message: types.Message, bot) -> None:
        """Обрабатывает начальное сообщение."""
        user_id = message.from_user.id
        
        try:
            # Сохраняем информацию о пользователе для отслеживания блокировок
            user_info = {
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name
            }
            
            # Проверяем антифлуд
            if not self._check_flood_control(user_id):
                await self._send_message_safe(bot, message.chat.id, self._get_flood_warning(user_id))
                return
            
            # Проверяем наличие файлов персонажей (предупреждение, но не блокировка)
            missing_files = self.character_service.validate_character_files()
            if missing_files:
                logger.warning(f"Отсутствуют файлы персонажей: {missing_files}")
                # Не блокируем пользователя, но уведомляем в лог
            
            # Проверяем, есть ли незавершенная сессия
            session = self.session_service.get_session(user_id)
            if session and not session.is_completed:
                # Показываем сообщение о восстановлении сессии
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Продолжить оценку", callback_data="continue_session")],
                    [InlineKeyboardButton(text="🆕 Начать заново", callback_data="start_ranking")],
                    [InlineKeyboardButton(text="📊 Мой рейтинг", callback_data="show_my_rating")],
                    [InlineKeyboardButton(text="🌍 Глобальный топ", callback_data="show_global_top")],
                ])
                await self._send_message_safe(
                    bot, 
                    message.chat.id,
                    "🔄 **У вас есть незавершенная сессия оценки!**\n\nХотите продолжить с того места, где остановились, или начать заново?",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                return
            
            # Создаем главное меню
            await message.reply(MESSAGES["start"], reply_markup=self._main_menu)
            
        except TelegramAPIError as e:
            logger.error(f"Ошибка Telegram API при обработке стартового сообщения: {e}")
            await message.reply(MESSAGES["error_network"])
        except Exception as e:
            logger.error(f"Ошибка при обработке стартового сообщения: {e}")
            await message.reply(MESSAGES["error_generic"])

    async def handle_help_command(self, message: types.Message, bot) -> None:
        """Обрабатывает команду /help."""
        try:
            await message.reply(MESSAGES["help"], parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка при обработке команды help: {e}")
            await message.reply(MESSAGES["error_generic"])

    async def handle_reload_characters(self, message: types.Message, bot) -> None:
        """Горячая перезагрузка персонажей из папки без рестарта бота (админ)."""
        admin_ids = [6480088003]
        if message.from_user.id not in admin_ids:
            await message.reply("У вас нет прав для выполнения этой команды.")
            return
        try:
            # Получаем список новых персонажей до перезагрузки
            newly_discovered_before = self.character_service.get_newly_discovered_characters()
            
            count = self.character_service.reload_characters()
            
            # Получаем список новых персонажей после перезагрузки
            newly_discovered_after = self.character_service.get_newly_discovered_characters()
            
            response = f"🔄 Персонажи перезагружены: {count}"
            
            # Показываем информацию о новых персонажах
            if newly_discovered_after:
                response += f"\n\n🆕 Обнаружены новые персонажи:"
                for i, name in enumerate(newly_discovered_after[:10]):  # Максимум 10
                    response += f"\n• {name}"
                
                if len(newly_discovered_after) > 10:
                    response += f"\n... и ещё {len(newly_discovered_after) - 10}"
                    
                response += "\n\nℹ️ Новые персонажи автоматически доступны в боте!"
            
            await message.reply(response)
        except Exception as e:
            logger.error(f"Ошибка перезагрузки персонажей: {e}")
            await message.reply("Не удалось перезагрузить персонажей")
    
    async def handle_add_characters_command(self, message: types.Message, bot) -> None:
        """Обрабатывает команду /add_characters для добавления новых персонажей."""
        # Проверяем, что это администратор (можно настроить список админов)
        admin_ids = [6480088003]  # Замените на реальные ID администраторов
        
        if message.from_user.id not in admin_ids:
            await message.reply("У вас нет прав для выполнения этой команды.")
            return
        
        try:
            # Парсим имена персонажей из сообщения
            text = message.text.replace('/add_characters', '').strip()
            if not text:
                await message.reply("Использование: /add_characters Персонаж1, Персонаж2, Персонаж3")
                return
            
            character_names = [name.strip() for name in text.split(',')]
            
            # Перечитываем список персонажей из папки перед валидацией
            try:
                self.character_service.reload_characters()
            except Exception as e:
                logger.error(f"Ошибка при перезагрузке персонажей: {e}")
                await message.reply("Ошибка при обновлении списка персонажей.")
                return

            # Проверяем, что все персонажи существуют
            existing_characters = [char.name for char in self.character_service.characters]
            valid_characters = []
            invalid_characters = []
            
            for name in character_names:
                if name in existing_characters:
                    valid_characters.append(name)
                else:
                    invalid_characters.append(name)
            
            if invalid_characters:
                await message.reply(f"Не найдены персонажи: {', '.join(invalid_characters)}")
                return
            
            if not valid_characters:
                await message.reply("Не указаны валидные имена персонажей.")
                return
            
            # Добавляем новых персонажей (в файле new_characters.json)
            self.session_service.add_new_characters(valid_characters)
            # Горячая перезагрузка списка персонажей
            reloaded = self.character_service.reload_characters()
            
            # Отправляем уведомления всем пользователям
            self.session_service.notify_all_users_about_new_characters(bot)
            
            await message.reply(
                f"✅ Добавлены новые персонажи: {', '.join(valid_characters)}\n"
                f"Персонажи перезагружены (всего: {reloaded}).\n"
                f"Уведомления отправлены всем пользователям с рейтингами."
            )
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении персонажей: {e}")
            await message.reply("Произошла ошибка при добавлении персонажей.")

    async def handle_show_new_characters_info(self, message: types.Message, bot) -> None:
        """Показывает информацию о новых персонажах (админ)."""
        admin_ids = [6480088003]
        if message.from_user.id not in admin_ids:
            await message.reply("У вас нет прав для выполнения этой команды.")
            return
        
        try:
            from config import CHARACTER_NAMES
            
            all_characters = [c.name for c in self.character_service.characters]
            newly_discovered = self.character_service.get_newly_discovered_characters()
            
            response = f"📁 **Информация о персонажах:**\n\n"
            response += f"📂 **Всего персонажей:** {len(all_characters)}\n"
            response += f"⚙️ **В config.py:** {len(CHARACTER_NAMES)}\n"
            response += f"🆕 **Новых обнаружено:** {len(newly_discovered)}\n\n"
            
            if newly_discovered:
                response += f"🎆 **Новые персонажи:**\n"
                for name in newly_discovered[:15]:  # Максимум 15
                    response += f"• {name}\n"
                
                if len(newly_discovered) > 15:
                    response += f"... и ещё {len(newly_discovered) - 15}\n"
                    
                response += "\nℹ️ **Новые персонажи автоматически работают в боте!**\n"
                response += "✍️ Не нужно вручную обновлять config.py"
            else:
                response += "✅ **Все персонажи синхронизированы**"
            
            await message.reply(response, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о персонажах: {e}")
            await message.reply("Произошла ошибка при получении информации.")


    async def _send_message_safe(self, bot, chat_id: int, text: str, **kwargs) -> bool:
        """Безопасная отправка сообщения."""
        try:
            await bot.send_message(chat_id, text, **kwargs)
            return True
            
        except TelegramAPIError as e:
            # Просто логируем ошибку без отслеживания блокировок
            if "blocked by the user" in str(e).lower() or "bot was blocked" in str(e).lower():
                logger.warning(f"🚫 Пользователь {chat_id} заблокировал бота: {e}")
            else:
                logger.error(f"Ошибка Telegram API: {e}")
            
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка отправки сообщения: {e}")
            return False
    

    async def handle_start_ranking(self, callback_query, bot):
        """Начинает процесс построения рейтинга с выбором режима."""
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        try:
            # Компактная клавиатура для выбора режима (2 строки вместо 3)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡ Быстрый (5мин)", callback_data="mode_quick"),
                 InlineKeyboardButton(text="🎯 Средний (10мин)", callback_data="mode_medium")],
                [InlineKeyboardButton(text="🏆 Точный (20мин)", callback_data="mode_precise"),
                 InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ])
            
            await callback_query.message.answer(MESSAGES["mode_selection"], reply_markup=keyboard, parse_mode="Markdown")
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Ошибка при выборе режима: {e}")
            await callback_query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)
    
    async def handle_mode_selection(self, callback_query, bot):
        """Обрабатывает выбор режима оценки."""
        user_id = callback_query.from_user.id
        mode_key = callback_query.data.replace('mode_', '')
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        if mode_key not in EVALUATION_MODES:
            await callback_query.answer("Некорректный режим", show_alert=True)
            return
        
        try:
            mode_info = EVALUATION_MODES[mode_key]
            
            # Создаем новую сессию с выбранным режимом
            session = self.session_service.create_session(
                user_id, 
                len(self.character_service.characters),
                max_comparisons=mode_info['max_comparisons']
            )
            
            # Отправляем сообщение о начале оценки
            start_message = (
                f"{mode_info['emoji']} **Режим: {mode_info['name']}**\n\n"
                f"🕰️ **Время:** {mode_info['estimated_time']}\n"
                f"🎯 **Точность:** {mode_info['accuracy']}\n"
                f"🏆 **Топ-3 точность:** {mode_info['top3_accuracy']}\n\n"
                f"{mode_info['description']}\n\n"
                f"🎆 **Начинаем оценку!**"
            )
            
            await callback_query.message.answer(start_message, parse_mode="Markdown")
            await self._send_next_pair(callback_query.message.chat.id, user_id, bot)
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Ошибка при создании сессии: {e}")
            await callback_query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)
    
    async def handle_back_to_menu(self, callback_query, bot):
        """Возвращает к главному меню."""
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        try:
            await callback_query.message.answer(MESSAGES["start"], reply_markup=self._main_menu)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Ошибка при возврате к меню: {e}")
            await callback_query.answer("Произошла ошибка", show_alert=True)
            
        except Exception as e:
            logger.error(f"Ошибка при начале построения рейтинга: {e}")
            await callback_query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)
    
    async def handle_choice_callback(self, callback_query: types.CallbackQuery, bot) -> None:
        """Обрабатывает выбор пользователя."""
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        session = self.session_service.get_session(user_id)
        
        if not session:
            await callback_query.answer(MESSAGES["session_expired"])
            return
        
        try:
            # Парсим данные callback'а
            _, a_str, b_str, choice = callback_query.data.split(':')
            a, b = int(a_str), int(b_str)
            winner = a if choice == "a" else b
            
            # Записываем выбор
            self.session_service.record_choice(user_id, (a, b), winner)
            
            await callback_query.answer(MESSAGES["choice_accepted"])
            await self._send_next_pair(callback_query.message.chat.id, user_id, bot)
            
        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка при парсинге callback данных: {e}")
            await callback_query.answer("Ошибка обработки выбора")
        except Exception as e:
            logger.error(f"Ошибка при обработке выбора: {e}")
            await callback_query.answer("Произошла ошибка")
    
    async def _send_next_pair(self, chat_id: int, user_id: int, bot) -> None:
        """Отправляет следующую пару персонажей или показывает рейтинг."""
        session = self.session_service.get_session(user_id)
        if not session:
            return
        
        # Проверяем, завершена ли сессия
        if session.is_completed:
            await self._show_ranking(chat_id, user_id, bot)
            return
        
        current_pair = session.get_current_pair()
        
        if not current_pair:
            await self._show_ranking(chat_id, user_id, bot)
            return
        
        a, b = current_pair
        
        # Получаем персонажей
        char_a = self.character_service.get_character_by_index(a)
        char_b = self.character_service.get_character_by_index(b)
        
        if not char_a or not char_b:
            logger.error(f"Не найдены персонажи с индексами {a} или {b}")
            await bot.send_message(chat_id, "Ошибка: персонаж не найден")
            return
        
        try:
            # Компактное сообщение с парой персонажей
            char_a_emoji = CHARACTER_EMOJIS.get(char_a.name, "🎭")
            char_b_emoji = CHARACTER_EMOJIS.get(char_b.name, "🎭")
            
            # Прогресс-бар
            total_results = len(session.results)
            progress_percent = min(100, int((total_results / session.total_pairs) * 100))
            progress_bar_filled = int(progress_percent / 10)  # 10 сегментов
            progress_bar = "🟫" * progress_bar_filled + "⬜" * (10 - progress_bar_filled)
            
            # Мотивирующая фраза каждые 5 сравнений
            motivational_text = ""
            if total_results > 0 and total_results % 5 == 0:
                motivational_text = f"\n✨ {random.choice(MOTIVATIONAL_PHRASES)}"
            
            # Пробуем отправить изображения
            import os
            if os.path.exists(char_a.image_path) and os.path.exists(char_b.image_path):
                try:
                    # Отправляем изображения с подписями
                    first_caption = f"**{char_a.name}**\n\n🤔 **Кто тебе больше нравится?**\n📊 {progress_bar} {progress_percent}%{motivational_text}"
                    media = [
                        InputMediaPhoto(media=FSInputFile(char_a.image_path), caption=first_caption, parse_mode="Markdown"),
                        InputMediaPhoto(media=FSInputFile(char_b.image_path), caption=f"**{char_b.name}**", parse_mode="Markdown")
                    ]
                    
                    # Компактная клавиатура (2 кнопки в строке)
                    keyboard_buttons = [
                        [
                            InlineKeyboardButton(
                                text=f"{char_a_emoji} {char_a.name}", 
                                callback_data=f"choose:{a}:{b}:a"
                            ),
                            InlineKeyboardButton(
                                text=f"{char_b_emoji} {char_b.name}", 
                                callback_data=f"choose:{a}:{b}:b"
                            )
                        ]
                    ]
                    
                    # Дополнительные кнопки (если есть история)
                    if session.choice_history:
                        keyboard_buttons.append([
                            InlineKeyboardButton(text="⬅️ Отменить", callback_data="go_back"),
                            InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")
                        ])
                    else:
                        keyboard_buttons.append([
                            InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")
                        ])
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                    
                    # Отправляем медиа-группу с изображениями
                    await bot.send_media_group(chat_id, media)
                    # Отправляем кнопки отдельным сообщением
                    await bot.send_message(
                        chat_id,
                        "👇 **Выбери, кто больше нравится:**",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                    return
                    
                except Exception as img_error:
                    logger.warning(f"Ошибка отправки изображений: {img_error}. Используем текстовый режим.")
            
            # Fallback: текстовый режим (если изображения недоступны)
            # Основное сообщение
            comparison_text = (
                f"🤔 **Кто тебе больше нравится?**\n\n"
                f"{char_a_emoji} **{char_a.name}**  🆚  {char_b_emoji} **{char_b.name}**\n\n"
                f"📊 {progress_bar} {progress_percent}%{motivational_text}"
            )
            
            # Компактная клавиатура (2 кнопки в строке)
            keyboard_buttons = [
                [
                    InlineKeyboardButton(
                        text=f"{char_a_emoji} {char_a.name}", 
                        callback_data=f"choose:{a}:{b}:a"
                    ),
                    InlineKeyboardButton(
                        text=f"{char_b_emoji} {char_b.name}", 
                        callback_data=f"choose:{a}:{b}:b"
                    )
                ]
            ]
            
            # Дополнительные кнопки (если есть история)
            if session.choice_history:
                keyboard_buttons.append([
                    InlineKeyboardButton(text="⬅️ Отменить", callback_data="go_back"),
                    InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")
                ])
            else:
                keyboard_buttons.append([
                    InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")
                ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            # Отправляем текстовое сообщение с клавиатурой
            await bot.send_message(
                chat_id,
                comparison_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при отправке пары персонажей: {e}")
            await bot.send_message(
                chat_id, 
                MESSAGES["file_not_found"].format(
                    path_a=char_a.image_path, 
                    path_b=char_b.image_path
                )
            )
    
    async def _show_ranking(self, chat_id: int, user_id: int, bot) -> None:
        """Показывает рейтинг пользователя."""
        session = self.session_service.get_session(user_id)
        if not session:
            return
        try:
            # Генерируем рейтинг
            ranking = self.ranking_service.generate_ranking(session)
            
            # Определяем использованный режим по количеству сравнений
            mode_info = None
            comparisons_made = len(session.results)
            
            for mode_key, mode_data in EVALUATION_MODES.items():
                if abs(comparisons_made - mode_data['max_comparisons']) <= 5:  # Допуск 5 сравнений
                    mode_info = mode_data
                    break
            
            # Показываем только топ-5 с информацией о точности
            top5_ranking = self.ranking_service.format_ranking_text(ranking[:5])
            
            # Добавляем информацию о точности
            if mode_info:
                accuracy_info = (
                    f"\n\n🎯 **Точность оценки:**\n"
                    f"• Общая: {mode_info['accuracy']}\n"
                    f"• Топ-3: {mode_info['top3_accuracy']}\n"
                    f"• Сравнений: {comparisons_made}\n"
                    f"• Режим: {mode_info['name']}"
                )
                top5_ranking += accuracy_info
            # Сохраняем весь рейтинг пользователя (все имена) с бэкапом
            all_names = [entry.character_name for entry in ranking]
            self.session_service.update_user_ranking_with_backup(user_id, all_names)
            
            # Если это была сессия новых персонажей, отмечаем их как оцененные
            if session.new_characters_only and session.new_character_indices:
                new_character_names = []
                for idx in session.new_character_indices:
                    char = self.character_service.get_character_by_index(idx)
                    if char:
                        new_character_names.append(char.name)
                
                if new_character_names:
                    self.session_service.mark_characters_as_rated(user_id, new_character_names)
                    logger.info(f"Персонажи {new_character_names} отмечены как оцененные для пользователя {user_id}")
            
            # Показываем только топ-5
            top5_ranking = self.ranking_service.format_ranking_text(ranking[:5])
            
            # Компактные кнопки навигации после результатов (без кнопки "новые герои")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Полный рейтинг", callback_data="show_full_ranking"),
                 InlineKeyboardButton(text="🌍 Глобальный топ", callback_data="show_global_top")],
                [InlineKeyboardButton(text="🔄 Новый рейтинг", callback_data="start_ranking"),
                 InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")]
            ])
            
            # Компактное сообщение о завершении
            completion_message = (
                f"🎉 **Рейтинг готов!** 🎉\n\n"
                f"✨ Выше топ-5, но можно посмотреть полный список!"
            )
            
            await asyncio.gather(
                bot.send_message(chat_id, top5_ranking, reply_markup=keyboard, parse_mode="Markdown"),
                bot.send_message(chat_id, completion_message, parse_mode="Markdown"),
                bot.send_message(chat_id, MESSAGES["restart"])
            )
            # Сохраняем обучение и удаляем сессию
            session.save_learning()
            self.session_service.remove_session(user_id)
        except Exception as e:
            logger.error(f"Ошибка при показе рейтинга: {e}")
            await bot.send_message(chat_id, "❌ Ошибка при формировании рейтинга")

    # --- Новые обработчики для кнопок ---
    async def handle_show_my_rating(self, callback_query, bot):
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        last_ranking = self.session_service.get_last_user_ranking(user_id)
        logger.info(f"Попытка загрузки рейтинга для пользователя {user_id}: {'успешно' if last_ranking else 'не найден'}")
        if not last_ranking:
            await callback_query.answer(MESSAGES["no_rating"], show_alert=True)
            return
        
        # Показываем только топ-5
        top5_text = "🏆 **Твой топ-5 персонажей:**\n\n"
        for i, name in enumerate(last_ranking[:5]):
            emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
            top5_text += f"{emoji} **{i+1}.** {name}\n"

        # Компактная клавиатура для навигации
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Полный рейтинг", callback_data="show_full_ranking"),
             InlineKeyboardButton(text="🌍 Глобальный", callback_data="show_global_top")],
            [InlineKeyboardButton(text="🔄 Новый", callback_data="start_ranking"),
             InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu")]
        ])
        await callback_query.message.answer(top5_text, parse_mode="Markdown", reply_markup=keyboard)
        await callback_query.answer()

    async def handle_show_full_ranking(self, callback_query, bot):
        """Показывает полный рейтинг пользователя."""
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        last_ranking = self.session_service.get_last_user_ranking(user_id)
        if not last_ranking:
            await callback_query.answer(MESSAGES["no_rating"], show_alert=True)
            return
        
        # Формируем текст полного рейтинга
        text = "🏆 **Твой полный рейтинг:**\n\n"
        for i, name in enumerate(last_ranking):
            if i < 3:
                emoji = ["🥇", "🥈", "🥉"][i]
            elif i < 10:
                emoji = "⭐"
            else:
                emoji = "🔸"
            text += f"{emoji} **{i+1}.** {name}\n"

        # Клавиатура для удобной навигации
        await callback_query.message.answer(text, parse_mode="Markdown", reply_markup=self._post_result_menu)
        await callback_query.answer()

    async def handle_show_global_top(self, callback_query, bot):
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        top = self.session_service.get_global_top_characters(top_n=5)
        if not top:
            await callback_query.answer(MESSAGES["no_global_top"], show_alert=True)
            return
        
        text = "🌍 **Глобальный ТОП-5 персонажей:**\n\n"
        for i, name in enumerate(top):
            emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
            text += f"{emoji} **{i+1}.** {name}\n"

        await callback_query.message.answer(text, parse_mode="Markdown", reply_markup=self._post_result_menu)
        await callback_query.answer()

    async def handle_rate_new_characters(self, callback_query, bot):
        """Обрабатывает запрос на оценку новых персонажей."""
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        # Проверяем, есть ли новые персонажи
        if not self.session_service.has_new_characters(user_id):
            await callback_query.answer("У тебя нет новых персонажей для оценки!", show_alert=True)
            return
        
        try:
            # Получаем список новых персонажей
            new_characters = self.session_service.get_new_characters_for_user(user_id)
            
            # Создаем сессию для новых персонажей
            session = self.session_service.create_new_characters_session(user_id)
            
            if not session:
                await callback_query.answer("Ошибка создания сессии для новых персонажей", show_alert=True)
                return
            
            await callback_query.message.answer(
                f"🎯 **Оценка новых персонажей:**\n\n"
                f"Сейчас ты будешь сравнивать новых персонажей:\n"
                f"{', '.join(new_characters)}\n\n"
                f"Это поможет добавить их в твой рейтинг!"
            )
            await self._send_next_pair(callback_query.message.chat.id, user_id, bot)
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Ошибка при начале оценки новых персонажей: {e}")
            await callback_query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)

    async def handle_go_back(self, callback_query, bot):
        """Обрабатывает отмену последнего выбора."""
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        session = self.session_service.get_session(user_id)
        if not session:
            await callback_query.answer("Сессия не найдена", show_alert=True)
            return
        
        # Узнаем последнюю пару до отмены
        last_pair = session.peek_last_pair()
        if not last_pair:
            await callback_query.answer("❌ Нечего отменять", show_alert=True)
            return
        
        # Отменяем последний выбор
        if self.session_service.undo_last_choice(user_id):
            await callback_query.answer("✅ Последний выбор отменен")
            # Отправляем ровно эту же пару снова
            a, b = last_pair
            # Принудительно отправляем указанную пару, минуя выбор новой
            # Получаем персонажей
            char_a = self.character_service.get_character_by_index(a)
            char_b = self.character_service.get_character_by_index(b)
            if not char_a or not char_b:
                await self._send_next_pair(callback_query.message.chat.id, user_id, bot)
                return
            try:
                first_caption = f"**{char_a.name}**\n\n👆 **Выбери, кто тебе больше нравится:**"
                media = [
                    InputMediaPhoto(media=FSInputFile(char_a.image_path), caption=first_caption, parse_mode="Markdown"),
                    InputMediaPhoto(media=FSInputFile(char_b.image_path), caption=f"**{char_b.name}**", parse_mode="Markdown")
                ]
                keyboard_buttons = [
                    [
                        InlineKeyboardButton(text=f"❤️ {char_a.name}", callback_data=f"choose:{a}:{b}:a"),
                        InlineKeyboardButton(text=f"{char_b.name} ❤️", callback_data=f"choose:{a}:{b}:b"),
                    ]
                ]
                if session.choice_history:
                    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="go_back")])
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                await bot.send_media_group(callback_query.message.chat.id, media)
                await bot.send_message(
                    callback_query.message.chat.id,
                    "👇 Выбери вариант:",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except TelegramAPIError as e:
                logger.error(f"Ошибка Telegram API при отправке медиа: {e}")
                await self._send_next_pair(callback_query.message.chat.id, user_id, bot)
            except Exception as e:
                logger.error(f"Неожиданная ошибка при отправке медиа: {e}")
                await self._send_next_pair(callback_query.message.chat.id, user_id, bot)
        else:
            await callback_query.answer("❌ Нечего отменять", show_alert=True)
    
    async def handle_continue_session(self, callback_query: types.CallbackQuery, bot) -> None:
        """Продолжает незавершенную сессию пользователя."""
        user_id = callback_query.from_user.id
        
        # Проверяем антифлуд
        if not self._check_flood_control(user_id):
            await callback_query.answer(self._get_flood_warning(user_id), show_alert=True)
            return
        
        session = self.session_service.get_session(user_id)
        
        if not session or session.is_completed:
            await callback_query.answer("❌ Нет активной сессии для продолжения", show_alert=True)
            return
        
        try:
            await callback_query.answer("🔄 Продолжаем оценку...")
            await self._send_next_pair(callback_query.message.chat.id, user_id, bot)
        except Exception as e:
            logger.error(f"Ошибка при продолжении сессии: {e}")
            await callback_query.answer("Произошла ошибка при продолжении сессии")
