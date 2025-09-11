"""Сервисы для работы с данными."""

import os
import json
import logging
import asyncio
import threading
import hashlib
import time
from typing import List, Dict, Optional
from collections import defaultdict

from models import Character, SimpleTransitiveSession as UserSession, RankingEntry
from config import CHARACTER_NAMES, MESSAGES

# Импортируем менеджер базы данных
try:
    from database import DatabaseManager
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    DatabaseManager = None

logger = logging.getLogger(__name__)


class CharacterService:
    """Сервис для работы с персонажами."""
    
    def __init__(self, characters_dir: str):
        self.characters_dir = characters_dir
        self._characters: Optional[List[Character]] = None
        self._name_to_index: Optional[Dict[str, int]] = None
    
    @property
    def characters(self) -> List[Character]:
        """Возвращает список персонажей."""
        if self._characters is None:
            self._characters = self._load_characters()
            # Построим быстрый индекс имя -> индекс
            self._name_to_index = {c.name: i for i, c in enumerate(self._characters)}
        return self._characters
    
    def _load_characters(self) -> List[Character]:
        """Загружает персонажей: сначала из папки, иначе из списка по умолчанию."""
        characters: List[Character] = []
        
        try:
            if os.path.isdir(self.characters_dir):
                # Читаем все .png как имена персонажей
                try:
                    files = [f for f in os.listdir(self.characters_dir) if f.lower().endswith('.png')]
                    names = [os.path.splitext(f)[0] for f in files]
                    names.sort()
                    
                    for name in names:
                        if not name.strip():  # Пропускаем пустые имена
                            continue
                        image_path = os.path.join(self.characters_dir, f"{name}.png")
                        if os.path.exists(image_path):  # Проверяем существование файла
                            characters.append(Character(name=name, image_path=image_path))
                            
                    # Автоматически обновляем эмодзи для новых персонажей
                    self._update_missing_emojis(names)
                    
                except (OSError, PermissionError) as e:
                    logger.error(f"Ошибка чтения директории {self.characters_dir}: {e}")
            
            # Фолбэк на статический список, если папка пуста или недоступна
            if not characters:
                logger.warning(f"Папка {self.characters_dir} пуста или недоступна, используем список по умолчанию")
                for name in CHARACTER_NAMES:
                    image_path = os.path.join(self.characters_dir, f"{name}.png")
                    characters.append(Character(name=name, image_path=image_path))
                    
        except Exception as e:
            logger.error(f"Критическая ошибка загрузки персонажей: {e}")
            # Критическая ошибка - создаем минимальный список
            characters = [Character(name="Неизвестный", image_path="unknown.png")]
        
        logger.info(f"Загружено {len(characters)} персонажей")
        return characters
    
    def _update_missing_emojis(self, character_names: List[str]) -> None:
        """Обновляет эмодзи для новых персонажей, которых нет в CHARACTER_EMOJIS."""
        try:
            from config import CHARACTER_EMOJIS
            
            # Добавляем эмодзи для новых персонажей
            default_emojis = ["🎭", "🎪", "💫", "✨", "🌟", "🔥", "⚡", "🌈", "🌍", "🎆"]
            emoji_index = 0
            
            missing_characters = []
            for name in character_names:
                if name not in CHARACTER_EMOJIS:
                    # Добавляем случайный эмодзи в рантайме
                    emoji = default_emojis[emoji_index % len(default_emojis)]
                    CHARACTER_EMOJIS[name] = emoji
                    emoji_index += 1
                    missing_characters.append(name)
            
            if missing_characters:
                logger.info(f"Добавлены эмодзи для новых персонажей: {missing_characters}")
                
        except Exception as e:
            logger.warning(f"Ошибка обновления эмодзи: {e}")

    def reload_characters(self) -> int:
        """Перечитывает список персонажей из папки. Возвращает количество."""
        self._characters = None
        loaded = len(self.characters)
        logger.info(f"Персонажи перезагружены: {loaded}")
        return loaded

    def get_index_by_name(self, name: str) -> Optional[int]:
        """Возвращает индекс персонажа по имени за O(1)."""
        # Убедимся, что индекс построен
        if self._name_to_index is None and self._characters is not None:
            self._name_to_index = {c.name: i for i, c in enumerate(self._characters)}
        if self._name_to_index is None:
            # Триггерим загрузку
            _ = self.characters
        return self._name_to_index.get(name) if self._name_to_index else None
    
    def validate_characters_directory(self) -> bool:
        """Проверяет существование директории с персонажами."""
        return os.path.exists(self.characters_dir)
    
    def validate_character_files(self) -> List[str]:
        """Проверяет существование файлов персонажей и возвращает список отсутствующих."""
        missing_files = []
        for character in self.characters:
            if not os.path.exists(character.image_path):
                missing_files.append(character.image_path)
        
        if missing_files:
            logger.warning(f"Отсутствуют файлы: {missing_files}")
        
        return missing_files
    
    def get_character_by_index(self, index: int) -> Optional[Character]:
        """Возвращает персонажа по индексу."""
        if 0 <= index < len(self.characters):
            return self.characters[index]
        return None
    
    def get_characters_count(self) -> int:
        """Возвращает количество персонажей."""
        return len(self.characters)
    
    def get_newly_discovered_characters(self) -> List[str]:
        """Возвращает список персонажей, которые были обнаружены в папке, но не в config.py."""
        try:
            from config import CHARACTER_NAMES
            current_names = [c.name for c in self.characters]
            newly_discovered = [name for name in current_names if name not in CHARACTER_NAMES]
            return newly_discovered
        except Exception as e:
            logger.error(f"Ошибка при получении новых персонажей: {e}")
            return []


class SessionService:
    """Сервис для работы с сессиями пользователей с транзитивным ранжированием."""
    
    def __init__(self, character_service: Optional['CharacterService'] = None, use_database: bool = True, database_path: str = "character_bot.db"):
        self._sessions: Dict[int, UserSession] = {}
        self.character_service = character_service
        self._file_lock = threading.Lock()
        self._last_backup_hash: Optional[str] = None
        
        # Параметры базы данных
        self.use_database = use_database and DATABASE_AVAILABLE
        self.db_manager = None
        
        if self.use_database:
            try:
                self.db_manager = DatabaseManager(database_path)
                logger.info(f"💾 Используем базу данных: {database_path}")
                self._load_sessions_from_database()
            except Exception as e:
                logger.error(f"⚠️ Ошибка инициализации базы данных: {e}")
                logger.info("📁 Переходим на файловое хранение")
                self.use_database = False
        
        if not self.use_database:
            # Файловое хранение (старый метод)
            self._global_stats_file = "global_stats.json"
            self._global_stats = self._load_global_stats()
            self._save_counter = 0
            self._new_characters_file = "new_characters.json"
            self._new_characters = self._load_new_characters()
            self._sessions_file = "active_sessions.json"
            self._load_sessions()

    def _load_global_stats(self) -> Dict[int, List[str]]:
        """Загружает глобальную статистику из файла с улучшенной обработкой ошибок."""
        if not os.path.exists(self._global_stats_file):
            return {}
            
        try:
            with open(self._global_stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Проверяем и конвертируем ключи в int
            result = {}
            for uid, top in data.items():
                try:
                    user_id = int(uid)
                    if isinstance(top, list) and all(isinstance(item, str) for item in top):
                        result[user_id] = top
                    else:
                        logger.warning(f"Некорректные данные для пользователя {uid}")
                except (ValueError, TypeError):
                    logger.warning(f"Некорректные данные для пользователя {uid}")
                    continue
                    
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON в {self._global_stats_file}: {e}")
            # Пытаемся создать бэкап поврежденного файла
            try:
                backup_path = f"{self._global_stats_file}.corrupted.{int(time.time())}"
                import shutil
                shutil.copy2(self._global_stats_file, backup_path)
                logger.info(f"Поврежденный файл сохранен как {backup_path}")
            except (IOError, OSError) as e:
                logger.error(f"Ошибка создания бэкапа поврежденного файла: {e}")
            return {}
        except (IOError, OSError) as e:
            logger.error(f"Ошибка чтения {self._global_stats_file}: {e}")
            return {}

    def _save_global_stats(self) -> None:
        """Сохраняет глобальную статистику в файл."""
        try:
            # Сохраняем новые данные
            with self._file_lock:
                with open(self._global_stats_file, "w", encoding="utf-8") as f:
                    json.dump(self._global_stats, f, ensure_ascii=False, indent=2)
            
            self._save_counter += 1
            logger.debug(f"Глобальная статистика сохранена ({len(self._global_stats)} пользователей, сохранение #{self._save_counter})")
            
            # Создаем бэкап при необходимости
            self.create_backup_if_needed()
        except Exception as e:
            logger.error(f"Ошибка сохранения глобальной статистики: {e}")

    def _normalize_full_ranking(self, top_characters: List[str]) -> List[str]:
        """Гарантирует, что сохраняется ПОЛНЫЙ порядок всех персонажей."""
        if not self.character_service:
            return top_characters[:50] if len(top_characters) > 50 else top_characters  # Ограничиваем длину
            
        try:
            all_names = [c.name for c in self.character_service.characters]
            if not all_names:
                logger.warning("Нет загруженных персонажей для нормализации")
                return top_characters
                
            # Удаляем несуществующие персонажей из списка
            valid_top = [name for name in top_characters if name in all_names]
            
            if len(valid_top) >= len(all_names):
                return valid_top[:len(all_names)]
                
            # Добавляем недостающие персонажи в детерминированном порядке
            remaining = [name for name in all_names if name not in valid_top]
            return valid_top + remaining
            
        except Exception as e:
            logger.error(f"Ошибка нормализации полного рейтинга: {e}")
            return top_characters

    def create_backup(self) -> None:
        """Создает резервную копию глобальной статистики."""
        try:
            if os.path.exists(self._global_stats_file):
                current_hash = self._calculate_file_hash(self._global_stats_file)
                if self._last_backup_hash == current_hash:
                    logger.debug("Пропуск бэкапа: данные не изменились с последнего бэкапа")
                    return
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{self._global_stats_file}.{timestamp}"
                import shutil
                with self._file_lock:
                    shutil.copy2(self._global_stats_file, backup_file)
                self._last_backup_hash = current_hash
                logger.info(f"Создан периодический бэкап: {backup_file}")
                # Подчищаем старые бэкапы, оставляем последние 5
                self.cleanup_old_backups(keep_count=5)
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа: {e}")
    
    def create_backup_if_needed(self) -> None:
        """Создает бэкап только если было много изменений."""
        if self._save_counter >= 10:  # Создаем бэкап каждые 10 сохранений
            try:
                if os.path.exists(self._global_stats_file):
                    current_hash = self._calculate_file_hash(self._global_stats_file)
                    if self._last_backup_hash != current_hash:
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_file = f"{self._global_stats_file}.{timestamp}"
                        import shutil
                        with self._file_lock:
                            shutil.copy2(self._global_stats_file, backup_file)
                        self._last_backup_hash = current_hash
                        logger.info(f"Создан бэкап по необходимости: {backup_file}")
                        # Подчищаем старые бэкапы
                        self.cleanup_old_backups(keep_count=5)
                    else:
                        logger.debug("Пропуск бэкапа по необходимости: данные не изменились")
                    self._save_counter = 0  # Сбрасываем счетчик
            except Exception as e:
                logger.error(f"Ошибка создания бэкапа: {e}")

    def cleanup_old_backups(self, keep_count: int = 5) -> None:
        """Удаляет старые бэкапы, оставляя только последние keep_count."""
        try:
            import glob
            backup_files = glob.glob(f"{self._global_stats_file}.*")
            backup_files.sort(reverse=True)  # Сортируем по дате (новые первыми)
            
            # Удаляем старые бэкапы
            for old_backup in backup_files[keep_count:]:
                os.remove(old_backup)
                logger.info(f"Удален старый бэкап: {old_backup}")
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")

    def update_user_ranking(self, user_id: int, top_characters: List[str]) -> None:
        """Обновляет топ пользователя с валидацией."""
        if not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Некорректный user_id: {user_id}")
            return
            
        if not isinstance(top_characters, list):
            logger.error(f"Некорректные данные top_characters: {type(top_characters)}")
            return
            
        # Гарантируем сохранение полного рейтинга
        top_characters = self._normalize_full_ranking(top_characters)
        
        # Проверяем, изменился ли рейтинг
        old_ranking = self._global_stats.get(user_id)
        if old_ranking != top_characters:
            self._global_stats[user_id] = top_characters
            self._save_global_stats()
            logger.info(f"Рейтинг пользователя {user_id} обновлен")
        else:
            logger.debug(f"Рейтинг пользователя {user_id} не изменился, пропускаем сохранение")
    
    def update_user_ranking_with_backup(self, user_id: int, top_characters: List[str]) -> None:
        """Обновляет топ пользователя с созданием бэкапа (для завершения рейтинга)."""
        # Гарантируем сохранение полного рейтинга
        top_characters = self._normalize_full_ranking(top_characters)
        old_ranking = self._global_stats.get(user_id)
        if old_ranking != top_characters:
            self._global_stats[user_id] = top_characters
            # Создаем бэкап перед сохранением
            if os.path.exists(self._global_stats_file):
                with self._file_lock:
                    backup_file = f"{self._global_stats_file}.backup"
                    import shutil
                    shutil.copy2(self._global_stats_file, backup_file)
            
            self._save_global_stats()
            logger.info(f"Рейтинг пользователя {user_id} обновлен с бэкапом")
        else:
            logger.debug(f"Рейтинг пользователя {user_id} не изменился, пропускаем сохранение")

    def get_last_user_ranking(self, user_id: int) -> Optional[List[str]]:
        """Возвращает последний топ пользователя (имена персонажей)."""
        ranking = self._global_stats.get(user_id)
        if ranking:
            logger.info(f"Загружен рейтинг для пользователя {user_id}: {len(ranking)} персонажей")
        else:
            logger.warning(f"Рейтинг для пользователя {user_id} не найден")
        return ranking

    def get_global_top_characters(self, top_n: int = 5) -> List[str]:
        """Возвращает топ-N самых популярных персонажей по последним результатам всех пользователей."""
        from collections import Counter
        all_tops = list(self._global_stats.values())
        # Считаем, сколько раз каждый персонаж встречается на первом месте, втором и т.д.
        counter = Counter()
        for top in all_tops:
            for name in top[:top_n]:
                counter[name] += 1
        # Берём top_n самых популярных
        most_common = counter.most_common(top_n)
        return [name for name, _ in most_common]

    
    def remove_session(self, user_id: int) -> None:
        """Удаляет сессию пользователя."""
        if user_id in self._sessions:
            del self._sessions[user_id]
            self._save_sessions()  # Сохраняем после удаления
            logger.info(f"Сессия пользователя {user_id} удалена")
    
    def should_continue_session(self, session: UserSession) -> bool:
        """Определяет, стоит ли продолжать сессию для более точного ранжирования."""
        # Проверяем достигнут ли максимум сравнений (если установлен)
        if session.max_comparisons is not None and len(session.results) >= session.max_comparisons:
            return False
            
        # Ищем следующую оптимальную пару
        next_pair = session.get_next_pair()
        return next_pair is not None
    
    def has_sufficient_data(self, session: UserSession) -> bool:
        """Проверяет, достаточно ли данных для создания качественного рейтинга."""
        # Минимум 15-20 сравнений для получения базового понимания предпочтений
        return len(session.results) >= 15
    
    def force_save_with_backup(self) -> None:
        """Принудительно сохраняет данные с бэкапом (для завершения работы)."""
        try:
            if os.path.exists(self._global_stats_file):
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{self._global_stats_file}.{timestamp}"
                import shutil
                with self._file_lock:
                    shutil.copy2(self._global_stats_file, backup_file)
                logger.info(f"Создан финальный бэкап: {backup_file}")
            
            # Принудительно сохраняем
            with self._file_lock:
                with open(self._global_stats_file, "w", encoding="utf-8") as f:
                    json.dump(self._global_stats, f, ensure_ascii=False, indent=2)
            
            # Обновляем хеш последнего бэкапа и подчищаем старые
            if os.path.exists(self._global_stats_file):
                self._last_backup_hash = self._calculate_file_hash(self._global_stats_file)
            self.cleanup_old_backups(keep_count=5)

            logger.info("Принудительное сохранение завершено")
        except Exception as e:
            logger.error(f"Ошибка принудительного сохранения: {e}")

    def _calculate_file_hash(self, path: str) -> Optional[str]:
        """Возвращает MD5-хеш файла для проверки изменений."""
        try:
            md5 = hashlib.md5()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    md5.update(chunk)
            return md5.hexdigest()
        except (IOError, OSError) as e:
            logger.error(f"Ошибка чтения файла для хэша: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при вычислении хэша: {e}")
            return None
    
    def _load_new_characters(self) -> Dict[str, List[str]]:
        """Загружает информацию о новых персонажах."""
        if os.path.exists(self._new_characters_file):
            try:
                with open(self._new_characters_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки новых персонажей: {e}")
                return {}
        return {}
    
    def _save_new_characters(self) -> None:
        """Сохраняет информацию о новых персонажах."""
        try:
            with open(self._new_characters_file, "w", encoding="utf-8") as f:
                json.dump(self._new_characters, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения новых персонажей: {e}")
    
    def add_new_characters(self, character_names: List[str]) -> None:
        """Добавляет новых персонажей и отмечает их как новые для всех пользователей."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Добавляем новых персонажей в список
        if timestamp not in self._new_characters:
            self._new_characters[timestamp] = character_names
        else:
            self._new_characters[timestamp].extend(character_names)
        
        self._save_new_characters()
        logger.info(f"Добавлены новые персонажи: {character_names}")
    
    def get_new_characters_for_user(self, user_id: int) -> List[str]:
        """Возвращает список новых персонажей для пользователя."""
        user_ranking = self._global_stats.get(user_id, [])
        all_new_characters = []
        
        # Собираем всех новых персонажей
        for timestamp, characters in self._new_characters.items():
            all_new_characters.extend(characters)
        
        # Возвращаем только тех, кого нет в рейтинге пользователя
        return [char for char in all_new_characters if char not in user_ranking]
    
    def mark_characters_as_rated(self, user_id: int, character_names: List[str]) -> None:
        """Отмечает персонажей как оцененных пользователем."""
        # Удаляем персонажей из списка новых для этого пользователя
        for timestamp in list(self._new_characters.keys()):
            self._new_characters[timestamp] = [
                char for char in self._new_characters[timestamp] 
                if char not in character_names
            ]
        
        # Удаляем пустые записи
        self._new_characters = {
            timestamp: chars for timestamp, chars in self._new_characters.items() 
            if chars
        }
        
        self._save_new_characters()
        logger.info(f"Персонажи {character_names} отмечены как оцененные для пользователя {user_id}")
    
    def get_users_with_ratings(self) -> List[int]:
        """Возвращает список пользователей, у которых есть рейтинги."""
        return list(self._global_stats.keys())
    
    def has_new_characters(self, user_id: int) -> bool:
        """Проверяет, есть ли у пользователя новые персонажи для оценки."""
        return len(self.get_new_characters_for_user(user_id)) > 0
    
    def notify_all_users_about_new_characters(self, bot) -> None:
        """Отправляет уведомления всем пользователям с рейтингами о новых персонажах."""
        users_with_ratings = self.get_users_with_ratings()
        
        for user_id in users_with_ratings:
            if self.has_new_characters(user_id):
                try:
                    new_chars = self.get_new_characters_for_user(user_id)
                    message = (
                        f"🎉 **Мы добавили новых персонажей!** 🎉\n\n"
                        f"Новые персонажи:\n"
                        f"{', '.join(new_chars)}\n\n"
                        f"Создайте новый рейтинг, чтобы включить их в оценку!"
                    )
                    
                    # Отправляем уведомление без дополнительных кнопок (асинхронно, но без await)
                    asyncio.create_task(
                        bot.send_message(user_id, message, parse_mode="Markdown")
                    )
                    
                    logger.info(f"Отправлено уведомление о новых персонажах пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")


    
    def _load_sessions(self) -> None:
        """Загружает активные сессии из файла."""
        if not os.path.exists(self._sessions_file):
            return
        
        try:
            with open(self._sessions_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for user_id_str, session_data in data.items():
                user_id = int(user_id_str)
                # Восстанавливаем сессию из сохраненных данных
                session = UserSession(
                    characters_count=session_data["characters_count"],
                    max_comparisons=session_data.get("max_comparisons"),
                    new_characters_only=session_data.get("new_characters_only", False),
                    new_character_indices=session_data.get("new_character_indices", [])
                )
                
                # Восстанавливаем состояние сессии
                session.comparisons_made = session_data.get("comparisons_made", 0)
                session.results = session_data.get("results", {})
                session.wins = session_data.get("wins", {})
                session.choice_history = session_data.get("choice_history", [])
                session.learned_preferences = session_data.get("learned_preferences", {})
                
                # Восстанавливаем транзитивные отношения
                if hasattr(session, '_recalculate_transitivity'):
                    session._recalculate_transitivity()
                
                self._sessions[user_id] = session
                logger.info(f"Восстановлена сессия для пользователя {user_id}")
                
        except Exception as e:
            logger.error(f"Ошибка загрузки сессий: {e}")
    
    def _save_sessions(self) -> None:
        """Сохраняет активные сессии в файл."""
        try:
            sessions_data = {}
            for user_id, session in self._sessions.items():
                if not session.is_completed:  # Сохраняем только незавершенные сессии
                    sessions_data[str(user_id)] = {
                        "characters_count": session.characters_count,
                        "max_comparisons": session.max_comparisons,
                        "new_characters_only": session.new_characters_only,
                        "new_character_indices": session.new_character_indices,
                        "comparisons_made": session.comparisons_made,
                        "results": session.results,
                        "wins": session.wins,
                        "choice_history": session.choice_history,
                        "learned_preferences": session.learned_preferences
                    }
            
            with open(self._sessions_file, "w", encoding="utf-8") as f:
                json.dump(sessions_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения сессий: {e}")
    
    def get_session(self, user_id: int) -> Optional[UserSession]:
        """Получает сессию пользователя."""
        return self._sessions.get(user_id)
    
    def record_choice(self, user_id: int, pair: tuple, winner: int) -> None:
        """Записывает выбор пользователя с отложенным сохранением."""
        session = self._sessions.get(user_id)
        if session:
            session.record_choice(pair, winner)
            # Отложенное сохранение - сохраняем только каждые 5 выборов или при завершении
            if session.comparisons_made % 5 == 0 or session.is_completed:
                self._save_sessions()
            else:
                # Помечаем как измененное для отложенного сохранения
                if not hasattr(self, '_dirty_sessions'):
                    self._dirty_sessions = set()
                self._dirty_sessions.add(user_id)
    
    def undo_last_choice(self, user_id: int) -> bool:
        """Отменяет последний выбор пользователя с отложенным сохранением."""
        session = self._sessions.get(user_id)
        if session and session.undo_last_choice():
            # Отложенное сохранение
            if not hasattr(self, '_dirty_sessions'):
                self._dirty_sessions = set()
            self._dirty_sessions.add(user_id)
            return True
        return False
    
    def cleanup_completed_sessions(self, max_age_hours: int = 24) -> int:
        """Очищает завершенные и старые сессии для экономии памяти."""
        if not hasattr(self, '_sessions'):
            return 0
            
        current_time = time.time()
        sessions_to_remove = []
        
        for user_id, session in self._sessions.items():
            should_remove = False
            
            # Удаляем завершенные сессии
            if session.is_completed:
                should_remove = True
                logger.debug(f"Отмечаем завершенную сессию {user_id} для удаления")
            
            # Проверяем возраст сессии (если есть информация о последней активности)
            elif hasattr(session, 'choice_history') and session.choice_history:
                # Последний выбор содержит временную метку?
                # Пока просто проверяем количество сравнений
                if len(session.choice_history) == 0:
                    # Пустая сессия старше 1 часа - удаляем
                    should_remove = True
                    logger.debug(f"Отмечаем пустую сессию {user_id} для удаления")
            
            if should_remove:
                sessions_to_remove.append(user_id)
        
        # Удаляем отмеченные сессии
        removed_count = 0
        for user_id in sessions_to_remove:
            if user_id in self._sessions:
                del self._sessions[user_id]
                removed_count += 1
                logger.info(f"Завершенная сессия пользователя {user_id} удалена")
        
        if removed_count > 0:
            logger.info(f"Очищено {removed_count} неактивных сессий")
            self._save_sessions()  # Сохраняем изменения
        
        return removed_count
    
    def flush_dirty_sessions(self) -> None:
        """Сохраняет все отложенные сессии."""
        if hasattr(self, '_dirty_sessions') and self._dirty_sessions:
            logger.debug(f"Сохраняем {len(self._dirty_sessions)} отложенных сессий")
            self._save_sessions()
            self._dirty_sessions.clear()
    
    def force_save_with_backup(self) -> None:
        """Принудительно сохраняет все данные с созданием бэкапа."""
        try:
            # Сохраняем отложенные сессии
            self.flush_dirty_sessions()
            
            # Сохраняем сессии
            self._save_sessions()
            
            # Сохраняем глобальную статистику
            self.ranking_service._save_global_stats()
            
            # Создаем бэкап
            self.create_backup()
            
            logger.info("Успешно сохранены все данные с бэкапом")
        except Exception as e:
            logger.error(f"Ошибка при принудительном сохранении: {e}")

    def create_session(self, user_id: int, characters_count: int = None, max_comparisons: int = None) -> Optional[UserSession]:
        """Создает новую сессию для пользователя с валидацией."""
        if not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Некорректный user_id: {user_id}")
            return None
            
        if characters_count is None:
            characters_count = self.character_service.get_characters_count() if self.character_service else 1
            
        if not isinstance(characters_count, int) or characters_count < 2:
            logger.error(f"Некорректное количество персонажей: {characters_count}")
            return None
            
        if max_comparisons is not None and (not isinstance(max_comparisons, int) or max_comparisons < 1):
            logger.error(f"Некорректное максимальное количество сравнений: {max_comparisons}")
            return None
            
        try:
            # Удаляем старую сессию, если есть
            if user_id in self._sessions:
                del self._sessions[user_id]
                
            session = UserSession(
                characters_count=characters_count,
                max_comparisons=max_comparisons,
                new_characters_only=False
            )
            self._sessions[user_id] = session
            self._save_sessions()
            
            logger.info(f"Создана новая сессия для пользователя {user_id} (персонажей: {characters_count}, макс. сравнений: {max_comparisons})")
            return session
        except Exception as e:
            logger.error(f"Ошибка создания сессии: {e}")
            return None
    
    def create_new_characters_session(self, user_id: int) -> Optional[UserSession]:
        """Создает сессию для оценки новых персонажей."""
        try:
            if not self._new_characters:
                return None
            
            # Получаем индексы новых персонажей
            new_character_indices = []
            for char_name in self._new_characters:
                if self.character_service._name_to_index and char_name in self.character_service._name_to_index:
                    new_character_indices.append(self.character_service._name_to_index[char_name])
            
            if not new_character_indices:
                return None
            
            session = UserSession(
                characters_count=self.character_service.get_characters_count(),
                max_comparisons=None,
                new_characters_only=True,
                new_character_indices=new_character_indices
            )
            self._sessions[user_id] = session
            self._save_sessions()  # Сохраняем новую сессию
            return session
        except Exception as e:
            logger.error(f"Ошибка создания сессии новых персонажей: {e}")
            return None

    def create_session(self, user_id: int, characters_count: int = None, max_comparisons: int = None) -> Optional[UserSession]:
        """Создает новую сессию для пользователя с валидацией."""
        if not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Некорректный user_id: {user_id}")
            return None
            
        if characters_count is None:
            characters_count = self.character_service.get_characters_count() if self.character_service else 1
            
        if not isinstance(characters_count, int) or characters_count < 2:
            logger.error(f"Некорректное количество персонажей: {characters_count}")
            return None
            
        if max_comparisons is not None and (not isinstance(max_comparisons, int) or max_comparisons < 1):
            logger.error(f"Некорректное максимальное количество сравнений: {max_comparisons}")
            return None
            
        try:
            # Удаляем старую сессию, если есть
            if user_id in self._sessions:
                del self._sessions[user_id]
                
            session = UserSession(
                characters_count=characters_count,
                max_comparisons=max_comparisons,
                new_characters_only=False
            )
            self._sessions[user_id] = session
            self._save_sessions()
            
            logger.info(f"Создана новая сессия для пользователя {user_id} (персонажей: {characters_count}, макс. сравнений: {max_comparisons})")
            return session
        except Exception as e:
            logger.error(f"Ошибка создания сессии: {e}")
            return None
    
    def create_new_characters_session(self, user_id: int) -> Optional[UserSession]:
        """Создает сессию для оценки новых персонажей."""
        try:
            if not self._new_characters:
                return None
            
            # Получаем индексы новых персонажей
            new_character_indices = []
            for char_name in self._new_characters:
                if self.character_service._name_to_index and char_name in self.character_service._name_to_index:
                    new_character_indices.append(self.character_service._name_to_index[char_name])
            
            if not new_character_indices:
                return None
            
            session = UserSession(
                characters_count=self.character_service.get_characters_count(),
                max_comparisons=None,
                new_characters_only=True,
                new_character_indices=new_character_indices
            )
            self._sessions[user_id] = session
            self._save_sessions()  # Сохраняем новую сессию
            return session
        except Exception as e:
            logger.error(f"Ошибка создания сессии новых персонажей: {e}")
            return None


class RankingService:
    """Сервис для работы с рейтингами."""
    
    def __init__(self, character_service: CharacterService):
        self.character_service = character_service
    
    def generate_ranking(self, session: UserSession) -> List[RankingEntry]:
        """Генерирует рейтинг на основе количества побед с учетом транзитивности."""
        # Подсчитываем победы для каждого персонажа из транзитивных связей
        wins_count = {}
        for i in range(len(self.character_service.characters)):
            # Считаем количество персонажей, которых побеждает данный персонаж
            # через прямые и транзитивные связи
            defeated_count = 0
            for j in range(len(self.character_service.characters)):
                if i != j and (i, j) in session.wins:
                    defeated_count += 1
            wins_count[i] = defeated_count
        
        # Создаем список с индексами и количеством побед
        win_data = []
        for i in range(len(self.character_service.characters)):
            total_wins = wins_count.get(i, 0)
            win_data.append((total_wins, i))
        
        # Сортируем по убыванию количества побед
        win_data.sort(reverse=True, key=lambda x: x[0])
        
        ranking = []
        for place, (total_wins, character_index) in enumerate(win_data, 1):
            character = self.character_service.get_character_by_index(character_index)
            if character:
                direct_wins = sum(1 for (a, b), winner in session.results.items() if winner == character_index)
                
                # Создаем простой рейтинг на основе побед (без базового смещения)
                simple_rating = total_wins
                
                ranking.append(RankingEntry(
                    place=place,
                    character_name=character.name,
                    rating=simple_rating,
                    wins=direct_wins,
                    comparisons=len(session.results) // len(self.character_service.characters)  # Примерное количество
                ))
        
        return ranking
    
    def format_ranking_text(self, ranking: List[RankingEntry]) -> str:
        """Форматирует рейтинг: только место и имя (без очков и побед)."""
        lines = ["🏆 **Твой персональный рейтинг персонажей:**\n"]
        for entry in ranking:
            if entry.place <= 3:
                emoji = ["🥇", "🥈", "🥉"][entry.place - 1]
            elif entry.place <= 10:
                emoji = "⭐"
            else:
                emoji = "🔸"
            lines.append(f"{emoji} **{entry.place}.** {entry.character_name}")
        return "\n".join(lines) + "\n"
    

    
