"""Конфигурация бота."""

import os
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class BotConfig:
    """Конфигурация бота."""
    
    api_token: str
    characters_dir: str = "Персонажи"
    log_level: str = "INFO"
    max_comparisons: int = 50
    flood_delay: float = 0.5
    backup_interval: int = 3600  # секунды
    max_backups: int = 5
    tma_domain: str = "localhost:8000"  # Домен для TMA
    
    # Параметры оптимизации
    auto_save_interval: int = 5  # Каждые 5 сравнений
    max_cache_size: int = 1000  # Максимальный размер кэша
    memory_cleanup_interval: int = 1800  # 30 минут
    session_timeout_hours: int = 24  # Таймаут сессий
    
    def __post_init__(self):
        """Валидация конфигурации после инициализации."""
        if not self.api_token or len(self.api_token) < 10:
            raise ValueError("Некорректный API токен")
        
        if self.max_comparisons < 1:
            raise ValueError("max_comparisons должно быть больше 0")
        
        if self.flood_delay < 0.1:
            raise ValueError("flood_delay должно быть больше 0.1 секунды")
    
    @classmethod
    def from_env(cls) -> "BotConfig":
        """Создает конфигурацию из переменных окружения."""
        api_token = os.getenv("BOT_API_TOKEN")
        if not api_token:
            raise ValueError("BOT_API_TOKEN environment variable is required")
        
        try:
            return cls(
                api_token=api_token,
                characters_dir=os.getenv("CHARACTERS_DIR", "Персонажи"),
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                max_comparisons=int(os.getenv("MAX_COMPARISONS", "50")),
                flood_delay=float(os.getenv("FLOOD_DELAY", "0.5")),
                backup_interval=int(os.getenv("BACKUP_INTERVAL", "3600")),
                max_backups=int(os.getenv("MAX_BACKUPS", "5")),
                tma_domain=os.getenv("TMA_DOMAIN", "localhost:8000"),
                auto_save_interval=int(os.getenv("AUTO_SAVE_INTERVAL", "5")),
                max_cache_size=int(os.getenv("MAX_CACHE_SIZE", "1000")),
                memory_cleanup_interval=int(os.getenv("MEMORY_CLEANUP_INTERVAL", "1800")),
                session_timeout_hours=int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))
            )
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid environment variable value: {e}")


# Список персонажей
CHARACTER_NAMES = [
    "Солдат 0", "Солдат 11", "Энби", "Николь", "Билли", "Нэкомата", "Коляда", "Бен",
    "Антон", "Грейс", "Ликаон", "Эллен", "Корин", "Рина", "Бёрнис", "Цезарь", "Люси",
    "Пайпер", "Лайтер", "Пульхра", "Мияби", "Харумаса", "Янаги", "Сокаку", "Чжу Юань",
    "Цинъи", "Джейн", "Астра", "Эвелин", "Вивиан", "Хуго", "Гашетка", "Пань Иньху",
    "Исюань", "Фуфу", "Юдзуха", "Сет", "Белль", "Вайз", "Сид", "Элис", "Орфей", "Манато",
    "Йидхари", "Люсия"
]

# Режимы оценки
EVALUATION_MODES = {
    'quick': {
        'name': '⚡ Быстрый (до 5 мин)',
        'description': 'Быстрая оценка с основными сравнениями',
        'max_comparisons': 15,
        'estimated_time': '3-5 минут',
        'accuracy': '85-90%',
        'top3_accuracy': '95%',
        'emoji': '⚡'
    },
    'medium': {
        'name': '🎯 Средний (5-10 мин)',
        'description': 'Сбалансированная оценка с хорошей точностью',
        'max_comparisons': 30,
        'estimated_time': '6-9 минут',
        'accuracy': '90-95%',
        'top3_accuracy': '98%',
        'emoji': '🎯'
    },
    'precise': {
        'name': '🏆 Точный (10-20 мин)',
        'description': 'Максимальная точность для идеального рейтинга',
        'max_comparisons': 50,
        'estimated_time': '12-18 минут',
        'accuracy': '95-98%',
        'top3_accuracy': '99%',
        'emoji': '🏆'
    }
}

# Кастомные эмодзи для персонажей ZZZ
# Ссылка на набор: https://t.me/addemoji/ZZZcharacter_by_TgEmodziBot
# Формат: "<emoji document_id=\"ID\">🔥</emoji>" для premium эмодзи
CHARACTER_EMOJIS = {
    "Солдат 0": "<emoji document_id=\"5339198936580125423\">🤖</emoji>",
    "Солдат 11": "<emoji document_id=\"5336918308945953009\">🔫</emoji>",
    "Энби": "<emoji document_id=\"5339331560875263653\">⚡</emoji>",
    "Николь": "<emoji document_id=\"5339097519517367678\">💼</emoji>",
    "Билли": "<emoji document_id=\"5339349037097188476\">🎪</emoji>",
    "Нэкомата": "<emoji document_id=\"5336996752228647421\">🐱</emoji>",
    "Коляда": "<emoji document_id=\"5337234646172205568\">🎄</emoji>",
    "Бен": "<emoji document_id=\"5336814589780722247\">🐻</emoji>",
    "Антон": "<emoji document_id=\"5339478624850451663\">🔧</emoji>",
    "Грейс": "<emoji document_id=\"5339117181877648419\">💃</emoji>",
    "Ликаон": "<emoji document_id=\"5339099486612388452\">🐺</emoji>",
    "Эллен": "<emoji document_id=\"5339368673687666639\">🦈</emoji>",
    "Корин": "<emoji document_id=\"5339385827787047503\">🧸</emoji>",
    "Рина": "<emoji document_id=\"5339318048908148102\">⚙️</emoji>",
    "Бёрнис": "<emoji document_id=\"5339519551593807071\">🔥</emoji>",
    "Цезарь": "<emoji document_id=\"5336814632730394250\">👑</emoji>",
    "Люси": "<emoji document_id=\"5339394018289677335\">💎</emoji>",
    "Пайпер": "<emoji document_id=\"5339028817220501644\">🎵</emoji>",
    "Лайтер": "<emoji document_id=\"5339274936026432758\">🚗</emoji>",
    "Пульхра": "<emoji document_id=\"5336793458541625158\">✨</emoji>",
    "Мияби": "<emoji document_id=\"5339188087492738313\">🌸</emoji>",
    "Харумаса": "<emoji document_id=\"5336894265719028652\">🎯</emoji>",
    "Янаги": "<emoji document_id=\"5337025279401430326\">⚖️</emoji>",
    "Сокаку": "<emoji document_id=\"5339131771881552395\">❄️</emoji>",
    "Чжу Юань": "<emoji document_id=\"5337262297171657599\">🏛️</emoji>",
    "Цинъи": "<emoji document_id=\"5339502096846716588\">⚔️</emoji>",
    "Джейн": "<emoji document_id=\"5339255196356736476\">🕷️</emoji>",
    "Астра": "<emoji document_id=\"5339423065153502434\">🌟</emoji>",
    "Эвелин": "<emoji document_id=\"5339263756226561867\">🎭</emoji>",
    "Вивиан": "<emoji document_id=\"5339234627758360807\">🎨</emoji>",
    "Хуго": "<emoji document_id=\"5339352820963376726\">🏗️</emoji>",
    "Гашетка": "<emoji document_id=\"5339464842300389907\">🔗</emoji>",
    "Пань Иньху": "<emoji document_id=\"5339225049981291536\">🐅</emoji>",
    "Исюань": "<emoji document_id=\"5336953171195494688\">🌙</emoji>",
    "Фуфу": "<emoji document_id=\"5339201835683052876\">🌺</emoji>",
    "Юдзуха": "<emoji document_id=\"5337148068221451392\">🍃</emoji>",
    "Сет": "<emoji document_id=\"5339110679297162318\">🏺</emoji>",
    "Белль": "<emoji document_id=\"5339354732223822310\">📚</emoji>",
    "Вайз": "<emoji document_id=\"5337121117301669587\">🔬</emoji>",
    "Сид": "<emoji document_id=\"5339431925671035033\">💤</emoji>",
    "Элис": "<emoji document_id=\"5339238265595658614\">🎀</emoji>",
    "Орфей": "<emoji document_id=\"5339187576391629786\">🎼</emoji>",
    "Манато": "<emoji document_id=\"5339407714940387534\">🎨</emoji>",
    "Йидхари": "<emoji document_id=\"5337114524526869266\">🌌</emoji>",
    "Люсия": "<emoji document_id=\"5337012153981370633\">✨</emoji>"
}

# Мотивирующие фразы для пользователей
MOTIVATIONAL_PHRASES = [
    "✨ Ты отлично справляешься!",
    "🎯 Каждый выбор приближает к идеальному рейтингу!",
    "🌟 Твои предпочтения уникальны и интересны!",
    "💫 Продолжай в том же духе!",
    "🎪 Ты создаешь что-то особенное!",
    "🔥 Твоя интуиция работает отлично!",
    "🌸 Каждое сравнение делает рейтинг лучше!",
    "⭐ Ты почти у цели!",
    "🎭 Твои вкусы формируют уникальный топ!",
    "🌈 Каждый выбор важен и ценен!"
]

# Константы сообщений (обновленные для лучшей визуализации)
MESSAGES = {
    "start": (
        "🎆 **Добро пожаловать в рейтинг персонажей!** 🎆\n\n"
        "🎯 Создай свой уникальный топ через парные сравнения!\n"
        "✨ Выбери, что тебя интересует:"
    ),
    "comparison": "🤔 Кто больше нравится? \n📊 {current}/{total}",
    "ranking_header": "🏆 **Твой персональный топ:**\n\n",
    "ranking_item": "{place}. {name} — {score}\n",
    "restart": "🔄 Готов к новому рейтингу? Нажми /start!",
    "choice_accepted": "✨ Отлично! Выбор записан!",
    "session_expired": "⏰ Сессия истекла. Начнём заново!",
    "file_not_found": "❌ Ой! Файлы не найдены: {path_a}, {path_b}",
    "characters_dir_missing": "📁 Создай папку '{dir}' с фото персонажей!",
    "bot_started": "🚀 Бот успешно запущен и готов к работе!",
    "menu_build_ranking": "🏆 Создать рейтинг",
    "menu_global_top": "🌍 Глобальный топ",
    "menu_my_rating": "📊 Мой рейтинг",
    "mode_selection": (
        "⚡ **Выбери режим оценки:**\n\n"
        "🎯 Каждый режим даёт точный результат для топ-мест:\n\n"
        "• **Быстрый** — основные сравнения\n"
        "• **Средний** — сбалансированная точность\n"
        "• **Точный** — максимальная детализация"
    ),
    "ranking_start": (
        "🎬 **Начинаем создание рейтинга!**\n\n"
        "📝 Я буду показывать пары персонажей\n"
        "✨ Просто выбирай того, кто больше нравится!"
    ),
    "flood_warning": "⏱️ Не так быстро! Подожди немного.",
    "no_rating": "🤔 У тебя пока нет рейтинга. Создай первый!",
    "no_global_top": "🌱 Глобальный топ формируется. Будь первым!",
    "help": (
        "🤖 **Добро пожаловать в бота рейтинга персонажей!**\n\n"
        "**📋 Основные команды:**\n"
        "• `/start` — главное меню с выбором действий\n"
        "• `/help` — эта подробная справка\n\n"
        "**🎯 Функции бота:**\n\n"
        "🏗️ **Создать рейтинг**\n"
        "Сравнивай персонажей попарно и получи свой уникальный рейтинг! "
        "Я покажу тебе двух персонажей и спрошу, кто больше нравится. "
        "После завершения ты получишь полный рейтинг всех персонажей с красивым оформлением.\n\n"
        "🌍 **Глобальный топ**\n"
        "Посмотри топ-5 самых популярных персонажей по результатам всех пользователей! "
        "Учитываются только последние рейтинги каждого пользователя, так что данные всегда актуальные.\n\n"
        "👤 **Мой полный рейтинг**\n"
        "Быстро покажи свой последний созданный рейтинг (все персонажи). "
        "Удобно, если хочешь вспомнить свой топ или поделиться с друзьями!\n\n"
        "**🎪 Особенности:**\n"
        "• Умная система сравнений для точного результата\n"
        "• Красивые изображения персонажей\n"
        "• Защита от спама и автоматических действий\n"
        "• Автоматические резервные копии данных\n"
        "• Уведомления о новых персонажах\n\n"
        "**🚀 Начни прямо сейчас!**\n"
        "Отправь `/start` и выбери, что хочешь сделать!"
    ),
    "error_generic": "❌ Произошла ошибка. Попробуй еще раз!",
    "error_config": "⚙️ Ошибка конфигурации. Обратись к администратору.",
    "error_network": "🌐 Проблемы с сетью. Попробуй позже.",
    "maintenance": "🔧 Бот на техническом обслуживании. Попробуй позже!"
}
