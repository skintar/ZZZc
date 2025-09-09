# 📋 Подробное руководство по развертыванию на Vercel

## ⚙️ Понимание предупреждений Vercel

### Предупреждение о `builds`
```
WARN! Due to `builds` existing in your configuration file, the Build and Development Settings defined in your Project Settings will not apply.
```

**Это нормально!** Когда в vercel.json есть секция `builds`, Vercel использует только настройки из файла конфигурации, игнорируя настройки из веб-интерфейса. Это обеспечивает консистентность развертывания.

## 🏗️ Архитектура развертывания

### Структура проекта для Vercel
```
├── api/
│   └── index.py          # Serverless функция Python
├── public/               # Статические файлы
│   └── index.html       # Главная страница
├── web/                 # TMA приложение (статика)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── vercel.json          # Конфигурация Vercel
├── requirements.txt     # Зависимости Python (упрощенные)
└── ...
```

### Маршрутизация
- `/` → `public/index.html` (главная)
- `/api/*` → `api/index.py` (serverless функции)
- `/web/*` → статические файлы TMA
- Статические файлы (css, js, images) → `public/`

## 🔧 Пошаговое развертывание

### Шаг 1: Подготовка кода
1. **Убедитесь, что файлы обновлены**:
   - ✅ `api/index.py` - использует BaseHTTPRequestHandler
   - ✅ `vercel.json` - правильная конфигурация builds
   - ✅ `requirements.txt` - минимальные зависимости
   - ✅ `public/index.html` - тестовая страница

### Шаг 2: Загрузка в GitHub

#### Вариант A: С установленным Git
```bash
# В папке проекта
git add .
git commit -m "Fix Vercel 404 - serverless Python functions"
git push origin main
```

#### Вариант B: Через веб-интерфейс GitHub
1. Откройте репозиторий на github.com
2. Нажмите "Upload files"
3. Перетащите файлы:
   - `api/index.py`
   - `vercel.json`
   - `public/index.html`
   - `requirements.txt`
4. Commit message: "Fix Vercel 404 - serverless Python functions"
5. Нажмите "Commit changes"

### Шаг 3: Развертывание на Vercel

1. **Войдите в vercel.com**
2. **Найдите ваш проект** в dashboard
3. **Дождитесь автоматического деплоя** (если настроен) ИЛИ
4. **Нажмите "Redeploy"** для принудительного деплоя

### Шаг 4: Мониторинг развертывания

1. **Перейдите в "Functions" таб** - проверьте статус Python функции
2. **Откройте "Deployments"** - посмотрите логи сборки
3. **Проверьте "Settings → Environment Variables"** - убедитесь в наличии нужных переменных

## 🧪 Тестирование развертывания

После успешного деплоя протестируйте:

### Основные endpoints
```bash
# Главная страница
curl https://ваш-домен.vercel.app/

# Health check API
curl https://ваш-домен.vercel.app/api/health

# Characters API
curl https://ваш-домен.vercel.app/api/characters

# TMA приложение
curl https://ваш-домен.vercel.app/web/index.html
```

### Ожидаемые ответы
- **/** → HTML страница с статусом деплоя
- **/api/health** → JSON с `{"status": "healthy"}`
- **/api/characters** → JSON массив персонажей
- **/web/index.html** → Полное TMA приложение

## 🔗 Интеграция с Telegram Bot

### Обновление конфигурации
1. **Скопируйте URL** вашего Vercel проекта (например: `your-app.vercel.app`)
2. **Обновите .env файл**:
   ```env
   TMA_DOMAIN=your-app.vercel.app
   ```

### Настройка @BotFather
1. Найдите вашего бота в @BotFather
2. `/setmenubutton`
3. Выберите вашего бота
4. URL: `https://your-app.vercel.app/web/index.html`
5. Text: `🎮 Рейтинг персонажей`

### Перезапуск локального бота
```bash
# Остановите текущий процесс (Ctrl+C)
# Перезапустите с новой конфигурацией
python main.py
```

## 🚨 Устранение неполадок

### Ошибка 404 NOT_FOUND
- ✅ Проверьте `api/index.py` - должен использовать BaseHTTPRequestHandler
- ✅ Убедитесь в правильности `vercel.json` routes
- ✅ Проверьте логи деплоя в Vercel dashboard

### Ошибки Python функций
- ✅ Проверьте Function logs в Vercel
- ✅ Убедитесь, что `requirements.txt` содержит только нужные зависимости
- ✅ Проверьте синтаксис `api/index.py`

### CORS ошибки
- ✅ API уже настроено с headers `Access-Control-Allow-Origin: *`
- ✅ Проверьте Network tab в браузере

### Telegram WebApp не загружается
- ✅ URL должен быть HTTPS (Vercel предоставляет автоматически)
- ✅ Проверьте правильность URL в @BotFather
- ✅ Убедитесь, что TMA_DOMAIN в .env соответствует Vercel домену

## 📊 Мониторинг продакшн системы

### Встроенные метрики Vercel
- **Function duration** - время выполнения serverless функций
- **Function invocations** - количество вызовов
- **Bandwidth usage** - использование трафика
- **Error rate** - процент ошибок

### Health check endpoint
Используйте `/api/health` для мониторинга:
```json
{
  "status": "healthy",
  "message": "TMA API is running on Vercel",
  "timestamp": "2025-09-09",
  "version": "1.0.0"
}
```

### Алерты и уведомления
1. **Vercel Monitoring** - встроенные алерты в Pro плане
2. **UptimeRobot** - бесплатный внешний мониторинг
3. **Custom monitoring** - интеграция с вашим ботом

## 🔄 Обновления и CI/CD

### Автоматическое развертывание
Vercel автоматически деплоит при push в main/master ветку GitHub.

### Процесс обновлений
1. Внесите изменения в код
2. Commit + Push в GitHub
3. Vercel автоматически создает новый деплой
4. Проверьте новую версию
5. При необходимости - rollback в Vercel dashboard

## 🎯 Следующие шаги

1. ✅ **Завершите текущий деплой**
2. 🔄 **Протестируйте все endpoints**
3. 🤖 **Настройте Telegram bot**
4. 📈 **Настройте мониторинг**
5. 🚀 **Запустите в продакшн!**

---

*Документация обновлена: 2025-09-09*  
*Версия Vercel API: 2*  
*Python Runtime: @vercel/python*