"""Точка входа в приложение."""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv(Path(__file__).parent / ".env", override=True) 

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

from config import BotConfig
from bot import create_and_run_bot
from web_server import TMAWebServer


def validate_environment() -> None:
    """Валидирует окружение и файловую систему."""
    # Проверяем наличие .env файла
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        example_file = Path(__file__).parent / ".env.example"
        if example_file.exists():
            logging.error(f"Файл .env не найден. Скопируйте {example_file} в .env и настройте")
        else:
            logging.error("Файл .env не найден. Создайте файл с переменными окружения")
        sys.exit(1)
    
    # Проверяем обязательные переменные
    required_vars = ["BOT_API_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logging.error(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        sys.exit(1)
    
    logging.info("✅ Валидация окружения прошла успешно")


def validate_filesystem(config: BotConfig) -> None:
    """Валидирует файловую систему и создает необходимые директории."""
    # Проверяем и создаем директорию персонажей
    characters_path = Path(config.characters_dir)
    if not characters_path.exists():
        logging.warning(f"Директория {config.characters_dir} не существует, создаем...")
        characters_path.mkdir(parents=True, exist_ok=True)
    
    # Проверяем наличие файлов персонажей
    from config import CHARACTER_NAMES
    character_files = list(characters_path.glob("*.jpg")) + list(characters_path.glob("*.png"))
    if len(character_files) < len(CHARACTER_NAMES):
        logging.warning(f"Найдено {len(character_files)} файлов персонажей из {len(CHARACTER_NAMES)} ожидаемых")
        logging.info("Убедитесь, что все изображения персонажей находятся в директории Персонажи/")
    
    # Создаем рабочие директории
    data_dirs = ["data", "logs", "backups"]
    for dir_name in data_dirs:
        dir_path = Path(dir_name)
        dir_path.mkdir(exist_ok=True)
    
    logging.info("✅ Валидация файловой системы завершена")


def load_config() -> BotConfig:
    """Загружает и валидирует конфигурацию бота."""
    try:
        # Сначала валидируем окружение
        validate_environment()
        
        # Загружаем конфигурацию
        config = BotConfig.from_env()
        
        # Валидируем файловую систему
        validate_filesystem(config)
        
        logging.info("✅ Конфигурация загружена и проверена успешно")
        return config
        
    except ValueError as e:
        logging.error(f"Ошибка загрузки конфигурации: {e}")
        logging.error("Убедитесь, что файл .env существует и содержит BOT_API_TOKEN")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Неожиданная ошибка при загрузке конфигурации: {e}")
        sys.exit(1)


async def main() -> None:
    """Главная функция приложения."""
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    try:
        logging.info("🚀 Запуск бота...")
        config = load_config()
        
        # Устанавливаем уровень логирования из конфигурации
        logging.getLogger().setLevel(getattr(logging, config.log_level.upper()))
        
        # Создаем бота
        from bot import CharacterBot
        bot = CharacterBot(config)
        
        # Создаем веб-сервер для TMA
        web_server = TMAWebServer(bot)
        
        # Запускаем веб-сервер
        logging.info(f"🌐 Запуск веб-сервера на порту {config.web_port}...")
        web_runner = await web_server.start_server(port=config.web_port)
        
        try:
            # Запускаем бота
            logging.info("🤖 Запуск Telegram бота...")
            await bot.start()
        except KeyboardInterrupt:
            logging.info("🛑 Бот остановлен пользователем")
        except Exception as e:
            logging.error(f"Ошибка во время работы бота: {e}")
            raise
        finally:
            logging.info("🧹 Остановка веб-сервера...")
            await web_runner.cleanup()
            logging.info("✅ Завершение работы")
            
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
