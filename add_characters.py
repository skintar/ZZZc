#!/usr/bin/env python3
"""
Скрипт для добавления новых персонажей в бота.
Использование: python add_characters.py "Персонаж1" "Персонаж2" "Персонаж3"
"""

import sys
import os
from services import SessionService
from config import CHARACTER_NAMES

def main():
    if len(sys.argv) < 2:
        print("❌ Использование: python add_characters.py 'Персонаж1' 'Персонаж2' 'Персонаж3'")
        print("📝 Пример: python add_characters.py 'НовыйГерой' 'НоваяГероиня'")
        return
    
    # Получаем имена персонажей из аргументов
    new_characters = sys.argv[1:]
    
    print(f"🎯 Добавляем персонажей: {', '.join(new_characters)}")
    
    # Проверяем, что персонажи существуют в конфигурации
    existing_characters = set(CHARACTER_NAMES)
    valid_characters = []
    invalid_characters = []
    
    for name in new_characters:
        if name in existing_characters:
            valid_characters.append(name)
        else:
            invalid_characters.append(name)
    
    if invalid_characters:
        print(f"❌ Не найдены в конфигурации: {', '.join(invalid_characters)}")
        print(f"📋 Доступные персонажи: {', '.join(CHARACTER_NAMES)}")
        return
    
    if not valid_characters:
        print("❌ Не указаны валидные имена персонажей")
        return
    
    try:
        # Создаем сервис и добавляем персонажей
        session_service = SessionService()
        session_service.add_new_characters(valid_characters)
        
        print(f"✅ Успешно добавлены: {', '.join(valid_characters)}")
        print("📢 Уведомления будут отправлены при следующем запуске бота")
        
        # Показываем текущее содержимое new_characters.json
        new_chars = session_service._new_characters
        if new_chars:
            print("\n📋 Текущие новые персонажи:")
            for timestamp, chars in new_chars.items():
                print(f"  {timestamp}: {', '.join(chars)}")
        else:
            print("\n📋 Список новых персонажей пуст")
            
    except Exception as e:
        print(f"❌ Ошибка при добавлении персонажей: {e}")

if __name__ == "__main__":
    main() 