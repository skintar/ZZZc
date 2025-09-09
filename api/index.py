from aiohttp import web
from aiohttp.web import Request, Response
import os
import sys
import json
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Простая заглушка для API endpoints
async def health_check(request: Request) -> Response:
    """Health check endpoint."""
    return web.json_response({
        'status': 'healthy',
        'message': 'TMA API is running',
        'timestamp': '2025-09-09'
    })

async def get_characters(request: Request) -> Response:
    """Get characters list."""
    # Заглушка для персонажей
    characters = [
        {'index': i, 'name': f'Character {i+1}', 'image_path': f'/images/char{i+1}.png'}
        for i in range(10)
    ]
    return web.json_response(characters)

# Создаем приложение
app = web.Application()

# Добавляем маршруты
app.router.add_get('/api/health', health_check)
app.router.add_get('/api/characters', get_characters)

# CORS middleware
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        })
    
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

app.middlewares.append(cors_middleware)

# Основная функция-обработчик для Vercel
from aiohttp.web import Application

def create_app() -> Application:
    return app

# Для Vercel
handler = app
app_callable = app