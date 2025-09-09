# 🚀 Быстрый деплой на Vercel (5 минут)

## 1. Зарегистрируйся на Vercel
👉 [vercel.com](https://vercel.com) → Sign up with GitHub

## 2. Загрузи код
```bash
# Если у тебя нет GitHub репозитория:
git init
git add .
git commit -m "TMA bot ready for deploy"
# Создай репозиторий на GitHub и push туда код
```

## 3. Деплой в Vercel
1. New Project → Import твой репозиторий
2. Environment Variables → Add:
   - `BOT_API_TOKEN` = твой токен от @BotFather
3. Deploy!

## 4. Настрой бота
После деплоя:
1. Скопируй URL (типа `https://zzz-123.vercel.app`)
2. @BotFather → твой бот → Bot Settings → Menu Button:
   - Text: `🏆 Рейтинг персонажей`  
   - URL: `https://zzz-123.vercel.app`

## 5. Готово! 🎉
Пользователи увидят кнопку меню в Telegram, которая откроет твоё TMA приложение!

---

### Альтернативы (тоже бесплатно):
- **Railway**: railway.app (500 часов/месяц)
- **Render**: render.com (спит через 15 мин)
- **Fly.io**: fly.io (хороший бесплатный план)

### Проблемы?
Проверь:
- `https://твой-домен.vercel.app/api/health` должен возвращать OK
- BOT_API_TOKEN установлен в Environment Variables
- Изображения персонажей загружены в папку Персонажи/