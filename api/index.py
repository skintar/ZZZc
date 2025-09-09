"""
Vercel serverless function для API
"""
import os
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from web_server import TMAWebServer
from bot import CharacterBot
from config import BotConfig

# Создаем конфигурацию для Vercel
config = BotConfig(
    api_token=os.getenv("BOT_API_TOKEN", "dummy_token"),
    characters_dir="Персонажи",
    tma_domain=os.getenv("VERCEL_URL", "localhost:3000"),
    web_port=3000
)

# Создаем бота и веб-сервер
try:
    bot = CharacterBot(config)
    web_server = TMAWebServer(bot)
    app = web_server.app
except Exception as e:
    print(f"Error initializing app: {e}")
    from aiohttp import web
    app = web.Application()
    
    @app.router.get('/health')
    async def health(request):
        return web.json_response({"status": "error", "message": str(e)})

# Основная функция для Vercel
async def handler(request):
    """Основной обработчик для Vercel serverless functions."""
    try:
        # Получаем response от aiohttp app
        resp = await app._handle(request)
        return resp
    except Exception as e:
        from aiohttp import web
        return web.json_response({"error": str(e)}, status=500)

# Экспортируем для Vercel
app_handler = handler