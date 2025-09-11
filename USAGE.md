# 🤖 Telegram Bot для рейтинга персонажей ZZZ

## 🚀 Быстрый запуск

### Продакшен (только бот):
```bash
python simple_bot.py
```

### Разработка (бот + веб-интерфейс):
```bash
python main.py
```

## ⚙️ Настройка

1. Скопируйте `.env.example` в `.env`
2. Укажите `BOT_API_TOKEN` в `.env`
3. Настройте `TMA_DOMAIN` для Telegram Mini App

## 📁 Структура проекта

- `simple_bot.py` - запуск только бота (продакшен)
- `main.py` - полный запуск с веб-сервером
- `stable-tma.html` - стабильная версия Telegram Mini App
- `bot.py` - основная логика бота
- `handlers.py` - обработчики команд
- `services.py` - бизнес-логика
- `config.py` - конфигурация

## 🎯 TMA

Стабильная версия: `https://skintar.github.io/ZZZc/stable-tma.html`

Все готово к работе! 🎉