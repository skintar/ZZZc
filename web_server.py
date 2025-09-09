"""
Веб-сервер для TMA (Telegram Mini App)
"""
import asyncio
import json
import os
from datetime import datetime
from aiohttp import web, ClientSession
from aiohttp.web import Request, Response
import logging
from pathlib import Path

from bot import CharacterBot
from services import CharacterService, SessionService, RankingService
from config import BotConfig

logger = logging.getLogger(__name__)

class TMAWebServer:
    def __init__(self, bot: CharacterBot):
        self.bot = bot
        self.character_service = bot.character_service
        self.session_service = bot.session_service
        self.ranking_service = bot.ranking_service
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Настройка маршрутов API"""
        # API endpoints
        self.app.router.add_get('/api/health', self.health_check)
        self.app.router.add_get('/api/characters', self.get_characters)
        self.app.router.add_post('/api/session', self.get_session)
        self.app.router.add_post('/api/start-rating', self.start_rating)
        self.app.router.add_post('/api/make-choice', self.make_choice)
        self.app.router.add_post('/api/go-back', self.go_back)
        self.app.router.add_post('/api/ranking', self.get_ranking)
        self.app.router.add_post('/api/full-ranking', self.get_full_ranking)
        self.app.router.add_get('/api/global-ranking', self.get_global_ranking)
        self.app.router.add_get('/api/character-image/{character_id}', self.get_character_image)
        
        # Статические файлы (должны быть последними)
        self.app.router.add_static('/', 'web/', name='static', show_index=True)
        
        # CORS для разработки
        self.app.middlewares.append(self.cors_middleware)
    
    @web.middleware
    async def cors_middleware(self, request, handler):
        """CORS middleware для разработки"""
        if request.method == 'OPTIONS':
            return web.Response(headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            })
        
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    async def health_check(self, request: Request) -> Response:
        """Проверка здоровья API."""
        try:
            characters_count = self.character_service.get_characters_count()
            return web.json_response({
                'status': 'healthy',
                'characters_loaded': characters_count,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0.0'
            })
        except Exception as e:
            logger.error(f"Ошибка health check: {e}")
            return web.json_response({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, status=500)
    
    async def get_characters(self, request: Request) -> Response:
        """Получить список всех персонажей"""
        try:
            characters = []
            for i in range(self.character_service.get_characters_count()):
                char = self.character_service.get_character_by_index(i)
                if char:
                    characters.append({
                        'index': i,
                        'name': char.name,
                        'image_path': char.image_path
                    })
            
            return web.json_response(characters)
        except Exception as e:
            logger.error(f"Ошибка получения персонажей: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def get_session(self, request: Request) -> Response:
        """Получить текущую сессию пользователя"""
        try:
            data = await request.json()
            user_id = data.get('user_id')
            
            if not user_id:
                return web.json_response({'error': 'User ID required'}, status=400)
            
            session = self.session_service.get_session(user_id)
            if not session:
                return web.json_response({'session': None})
            
            return web.json_response({
                'session': {
                    'characters_count': session.characters_count,
                    'comparisons_made': session.comparisons_made,
                    'is_completed': session.is_completed,
                    'current_pair': session.get_current_pair(),
                    'choice_history': session.choice_history,
                    'new_characters_only': session.new_characters_only,
                    'new_character_indices': session.new_character_indices
                }
            })
        except Exception as e:
            logger.error(f"Ошибка получения сессии: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def start_rating(self, request: Request) -> Response:
        """Начать новую сессию оценки"""
        try:
            data = await request.json()
            user_id = data.get('user_id')
            new_characters_only = data.get('new_characters_only', False)
            
            if not user_id:
                return web.json_response({'error': 'User ID required'}, status=400)
            
            if new_characters_only:
                session = self.session_service.create_new_characters_session(user_id)
            else:
                session = self.session_service.create_session(user_id)
            
            if not session:
                return web.json_response({'error': 'Failed to create session'}, status=500)
            
            return web.json_response({
                'characters_count': session.characters_count,
                'comparisons_made': session.comparisons_made,
                'is_completed': session.is_completed,
                'current_pair': session.get_current_pair(),
                'choice_history': session.choice_history,
                'new_characters_only': session.new_characters_only,
                'new_character_indices': session.new_character_indices,
                'estimated_total': getattr(session, 'estimated_total', 0)
            })
        except Exception as e:
            logger.error(f"Ошибка начала оценки: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def make_choice(self, request: Request) -> Response:
        """Сделать выбор между персонажами"""
        try:
            data = await request.json()
            user_id = data.get('user_id')
            pair = data.get('pair')
            choice = data.get('choice')
            
            if not all([user_id, pair, choice is not None]):
                return web.json_response({'error': 'Missing required parameters'}, status=400)
            
            session = self.session_service.get_session(user_id)
            if not session:
                return web.json_response({'error': 'Session not found'}, status=404)
            
            # Записываем выбор
            self.session_service.record_choice(user_id, tuple(pair), choice)
            
            # Получаем следующую пару
            next_pair = session.get_current_pair()
            
            return web.json_response({
                'characters_count': session.characters_count,
                'comparisons_made': session.comparisons_made,
                'is_completed': session.is_completed,
                'current_pair': next_pair,
                'choice_history': session.choice_history,
                'new_characters_only': session.new_characters_only,
                'new_character_indices': session.new_character_indices,
                'estimated_total': getattr(session, 'estimated_total', 0)
            })
        except Exception as e:
            logger.error(f"Ошибка сохранения выбора: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def go_back(self, request: Request) -> Response:
        """Отменить последний выбор"""
        try:
            data = await request.json()
            user_id = data.get('user_id')
            
            if not user_id:
                return web.json_response({'error': 'User ID required'}, status=400)
            
            session = self.session_service.get_session(user_id)
            if not session:
                return web.json_response({'error': 'Session not found'}, status=404)
            
            # Отменяем последний выбор
            if not self.session_service.undo_last_choice(user_id):
                return web.json_response({'error': 'Nothing to undo'}, status=400)
            
            # Получаем предыдущую пару
            last_pair = session.peek_last_pair()
            
            return web.json_response({
                'characters_count': session.characters_count,
                'comparisons_made': session.comparisons_made,
                'is_completed': session.is_completed,
                'current_pair': last_pair,
                'choice_history': session.choice_history,
                'new_characters_only': session.new_characters_only,
                'new_character_indices': session.new_character_indices,
                'estimated_total': getattr(session, 'estimated_total', 0)
            })
        except Exception as e:
            logger.error(f"Ошибка отмены выбора: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def get_ranking(self, request: Request) -> Response:
        """Получить рейтинг пользователя"""
        try:
            data = await request.json()
            user_id = data.get('user_id')
            
            if not user_id:
                return web.json_response({'error': 'User ID required'}, status=400)
            
            session = self.session_service.get_session(user_id)
            if not session:
                return web.json_response({'error': 'Session not found'}, status=404)
            
            # Генерируем рейтинг
            ranking = self.ranking_service.generate_ranking(session)
            
            # Сохраняем рейтинг
            all_names = [entry.character_name for entry in ranking]
            self.session_service.update_user_ranking_with_backup(user_id, all_names)
            
            # Форматируем для API
            ranking_data = []
            for entry in ranking:
                ranking_data.append({
                    'character_name': entry.character_name,
                    'points': entry.points,
                    'wins': entry.wins,
                    'losses': entry.losses,
                    'win_percentage': entry.win_percentage
                })
            
            return web.json_response({'ranking': ranking_data})
        except Exception as e:
            logger.error(f"Ошибка получения рейтинга: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def get_full_ranking(self, request: Request) -> Response:
        """Получить полный рейтинг пользователя"""
        return await self.get_ranking(request)  # Пока что то же самое
    
    async def get_global_ranking(self, request: Request) -> Response:
        """Получить глобальный рейтинг"""
        try:
            global_stats = self.session_service._load_global_stats()
            if not global_stats:
                return web.json_response({'ranking': []})
            
            # Сортируем по количеству побед
            sorted_chars = sorted(
                global_stats.items(),
                key=lambda x: x[1].get('wins', 0),
                reverse=True
            )
            
            ranking_data = []
            for i, (char_name, stats) in enumerate(sorted_chars):
                ranking_data.append({
                    'position': i + 1,
                    'character_name': char_name,
                    'wins': stats.get('wins', 0),
                    'losses': stats.get('losses', 0),
                    'total_comparisons': stats.get('wins', 0) + stats.get('losses', 0)
                })
            
            return web.json_response({'ranking': ranking_data})
        except Exception as e:
            logger.error(f"Ошибка получения глобального рейтинга: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def get_character_image(self, request: Request) -> Response:
        """Получить изображение персонажа"""
        try:
            character_id = int(request.match_info['character_id'])
            char = self.character_service.get_character_by_index(character_id)
            
            if not char or not os.path.exists(char.image_path):
                return web.Response(status=404)
            
            return web.FileResponse(char.image_path)
        except (ValueError, FileNotFoundError):
            return web.Response(status=404)
        except Exception as e:
            logger.error(f"Ошибка получения изображения: {e}")
            return web.Response(status=500)
    
    async def start_server(self, host='localhost', port=8080):
        """Запуск веб-сервера"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        logger.info(f"TMA веб-сервер запущен на http://{host}:{port}")
        return runner

async def main():
    """Запуск TMA сервера"""
    # Создаем бота
    from config import BotConfig
    config = BotConfig.from_env()
    bot = CharacterBot(config)
    
    # Создаем веб-сервер
    web_server = TMAWebServer(bot)
    runner = await web_server.start_server()
    
    try:
        # Запускаем бота
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Остановка сервера...")
    finally:
        await runner.cleanup()
        await bot.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
