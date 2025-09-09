# Vercel serverless function for TMA API
from http.server import BaseHTTPRequestHandler
import json
import urllib.parse as urlparse

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Парсим URL
        path = urlparse.urlparse(self.path).path
        
        # Устанавливаем заголовки
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        # Роутинг
        if path.endswith('/health'):
            response = {
                'status': 'healthy',
                'message': 'TMA API is running on Vercel',
                'timestamp': '2025-09-09',
                'version': '1.0.0'
            }
        elif path.endswith('/characters'):
            response = [
                {'index': i, 'name': f'Character {i+1}', 'image_path': f'/images/char{i+1}.png'}
                for i in range(10)
            ]
        else:
            response = {
                'message': 'TMA API - Telegram Mini App',
                'endpoints': [
                    '/api/health - проверка статуса',
                    '/api/characters - список персонажей'
                ],
                'status': 'running',
                'path': path
            }
        
        # Отправляем ответ
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
    
    def do_POST(self):
        self.do_GET()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()