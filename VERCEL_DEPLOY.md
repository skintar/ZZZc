# 🚀 Бесплатное развёртывание TMA на Vercel

## Шаг 1: Подготовка

### 1.1 Создайте аккаунт
- Идите на [vercel.com](https://vercel.com)
- Зарегистрируйтесь через GitHub (рекомендуется)

### 1.2 Подготовьте код
Убедитесь, что ваш код в GitHub репозитории содержит:
```
├── api/
│   └── index.py          ✅ (готов)
├── web/                  ✅ (готов)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── Персонажи/            ✅ (готов)
├── vercel.json           ✅ (готов)
├── requirements.txt      ✅ (готов)
└── все остальные файлы
```

## Шаг 2: Развёртывание

### 2.1 В Vercel Dashboard:
1. Нажмите **"New Project"**
2. Выберите ваш GitHub репозиторий
3. Нажмите **"Import"**

### 2.2 Настройка переменных окружения:
В разделе **Environment Variables** добавьте:
- **Name**: `BOT_API_TOKEN`
- **Value**: `ваш_токен_от_BotFather`
- **Environments**: Production, Preview, Development

### 2.3 Настройка проекта:
- **Framework Preset**: Other
- **Root Directory**: ./
- **Build Command**: оставьте пустым
- **Output Directory**: оставьте пустым

## Шаг 3: После развёртывания

### 3.1 Получите ваш URL
После успешного деплоя вы получите URL вида:
`https://your-project-name.vercel.app`

### 3.2 Обновите локальный .env
```env
TMA_DOMAIN=your-project-name.vercel.app
```

### 3.3 Настройте бота в BotFather
1. Откройте @BotFather в Telegram
2. Выберите вашего бота → Bot Settings → Menu Button
3. Configure Menu Button:
   - **Text**: 🏆 Рейтинг персонажей
   - **URL**: https://your-project-name.vercel.app

### 3.4 Перезапустите локального бота
```bash
python main.py
```

## 🎯 Результат

Пользователи теперь видят кнопку меню в Telegram, которая открывает красивое TMA приложение!

## 🛠 Альтернативные бесплатные варианты

### Railway (бесплатно 500 часов/месяц)
```bash
# Установите Railway CLI
npm install -g @railway/cli

# Деплой
railway login
railway init
railway up
```

### Render (бесплатно с ограничениями)
1. Подключите GitHub репозиторий
2. Выберите Web Service
3. Python environment
4. Start Command: `python main.py`

### Fly.io (бесплатно с лимитами)
```bash
# Установите flyctl
# Создайте Dockerfile и fly.toml
fly auth login
fly launch
fly deploy
```

## ⚠️ Важные замечания

### Ограничения бесплатных планов:
- **Vercel**: 100GB bandwidth/месяц, 10GB storage
- **Railway**: 500 часов работы/месяц (спит при неактивности)
- **Render**: спит через 15 минут неактивности
- **Fly.io**: 160GB-hours/месяц

### Для продакшена рекомендуется:
1. Использовать базу данных вместо файлов
2. Настроить мониторинг
3. Backup стратегию
4. CDN для статических файлов

## 🔧 Отладка

### Если что-то не работает:
1. Проверьте логи в Vercel Dashboard → Functions
2. Убедитесь, что BOT_API_TOKEN установлен
3. Проверьте, что /api/health возвращает ответ
4. Убедитесь, что изображения персонажей загружены

### Полезные ссылки для проверки:
- `https://your-domain.vercel.app/` - главная страница
- `https://your-domain.vercel.app/api/characters` - API
- `https://your-domain.vercel.app/api/health` - проверка здоровья