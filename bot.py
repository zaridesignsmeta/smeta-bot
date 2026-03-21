"""
Smeta Bot + Web Server - eyni anda işləyir
"""

import asyncio
import logging
import threading
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

from config import BOT_TOKEN
from database import init_db
from handlers import router
from web import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def run_web():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await init_db()
    logger.info("✅ Verilənlər bazası hazırdır")

    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    logger.info("🌐 Veb server işə düşdü")

    logger.info("🚀 Bot işə düşdü...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
