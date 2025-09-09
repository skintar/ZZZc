#!/usr/bin/env python3
"""
Скрипт для очистки старых файлов и оптимизации бота.
"""

import os
import glob
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_old_backups(max_backups: int = 5):
    """Очищает старые бэкапы, оставляя только последние max_backups."""
    backup_files = glob.glob("global_stats.json.*")
    backup_files.sort(key=os.path.getmtime, reverse=True)
    
    if len(backup_files) > max_backups:
        files_to_remove = backup_files[max_backups:]
        for file_path in files_to_remove:
            try:
                os.remove(file_path)
                logger.info(f"Удален старый бэкап: {file_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении {file_path}: {e}")
    
    logger.info(f"Оставлено {min(len(backup_files), max_backups)} бэкапов")


def cleanup_old_logs(max_log_size_mb: int = 50):
    """Очищает старые логи, если они превышают размер."""
    log_file = "bot.log"
    
    if os.path.exists(log_file):
        size_mb = os.path.getsize(log_file) / (1024 * 1024)
        
        if size_mb > max_log_size_mb:
            # Создаем бэкап лога
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"bot.log.{timestamp}"
            
            try:
                # Читаем последние 1000 строк
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Сохраняем последние 1000 строк
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-1000:])
                
                # Сохраняем полный лог как бэкап
                with open(backup_name, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                logger.info(f"Лог очищен. Размер был {size_mb:.1f}MB, создан бэкап: {backup_name}")
            except Exception as e:
                logger.error(f"Ошибка при очистке лога: {e}")


def validate_data_files():
    """Проверяет и исправляет файлы данных."""
    files_to_check = ["global_stats.json", "new_characters.json"]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Файл {file_path} корректен")
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка в файле {file_path}: {e}")
                # Создаем бэкап поврежденного файла
                backup_name = f"{file_path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(file_path, backup_name)
                logger.info(f"Создан бэкап поврежденного файла: {backup_name}")
                
                # Создаем новый пустой файл
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                logger.info(f"Создан новый пустой файл {file_path}")


def optimize_images():
    """Проверяет размеры изображений персонажей."""
    characters_dir = "Персонажи"
    
    if not os.path.exists(characters_dir):
        logger.warning(f"Директория {characters_dir} не найдена")
        return
    
    image_files = glob.glob(os.path.join(characters_dir, "*.png"))
    
    for image_path in image_files:
        try:
            size_mb = os.path.getsize(image_path) / (1024 * 1024)
            if size_mb > 2:  # Если изображение больше 2MB
                logger.warning(f"Большое изображение: {image_path} ({size_mb:.1f}MB)")
        except Exception as e:
            logger.error(f"Ошибка при проверке {image_path}: {e}")


def main():
    """Основная функция очистки."""
    logger.info("Начинаем очистку и оптимизацию...")
    
    # Очистка старых бэкапов
    cleanup_old_backups()
    
    # Очистка старых логов
    cleanup_old_logs()
    
    # Проверка файлов данных
    validate_data_files()
    
    # Оптимизация изображений
    optimize_images()
    
    logger.info("Очистка завершена!")


if __name__ == "__main__":
    main() 