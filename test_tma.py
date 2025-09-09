#!/usr/bin/env python3
"""Test TMA web server."""

import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

# Загружаем .env
load_dotenv(Path(__file__).parent / ".env")

from web_server import TMAWebServer
from bot import CharacterBot
from config import BotConfig

async def main():
    config = BotConfig.from_env()
    bot = CharacterBot(config)
    server = TMAWebServer(bot)
    
    print("Starting TMA web server...")
    runner = await server.start_server()
    print("✅ TMA Server started at http://localhost:8080")
    print("🌐 Visit http://localhost:8080/index.html to see your TMA interface")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())