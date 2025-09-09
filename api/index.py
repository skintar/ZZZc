from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Парсим URL
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Устанавливаем CORS заголовки
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        # Роутинг
        if path == '/api/health':
            response = {
                'status': 'healthy',
                'message': 'TMA API is running on Vercel',
                'timestamp': '2025-09-09',
                'version': '1.0.0'
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif path == '/api/characters':
            # Заглушка для персонажей
            characters = [
                {'index': i, 'name': f'Character {i+1}', 'image_path': f'/images/char{i+1}.png'}
                for i in range(10)
            ]
            self.wfile.write(json.dumps(characters).encode())
            
        else:
            # Список доступных endpoints
            response = {
                'message': 'TMA API',
                'endpoints': [
                    '/api/health',
                    '/api/characters'
                ],
                'status': 'running'
            }
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        # Обработка POST запросов (если понадобится)
        self.do_GET()