# 🚀 Быстрое развёртывание на Vercel

## Шаг 1: Загрузить код
Если у вас нет Git, загрузите файлы через GitHub:

1. **Откройте ваш репозиторий** на github.com
2. **Нажмите "Upload files"**
3. **Перетащите файлы**:
   - `api/index.py`
   - `vercel.json`
   - `public/index.html`
   - `requirements.txt`
4. **Commit changes**

## Шаг 2: Развернуть на Vercel
1. **Войдите в vercel.com**
2. **Найдите ваш проект**
3. **Нажмите "Redeploy"**
4. **Дождитесь завершения** (2-3 минуты)

## Шаг 3: Проверить
После деплоя проверьте:
- `https://ваш-домен.vercel.app/` - главная страница ✅
- `https://ваш-домен.vercel.app/api/health` - API статус ✅
- `https://ваш-домен.vercel.app/web/index.html` - TMA ✅

## Шаг 4: Настроить бота
1. **Скопируйте URL** вашего Vercel проекта
2. **Обновите .env**:
   ```
   TMA_DOMAIN=ваш-домен.vercel.app
   ```
3. **@BotFather** → Menu Button → `https://ваш-домен.vercel.app/web/index.html`
4. **Перезапустите бота**: `python main.py`

## 🎉 Готово!
Ваше TMA приложение работает в продакшне!