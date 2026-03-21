"""
Smeta Bot - Farid's Renovation & Design Company
Telegram Bot with PostgreSQL + Excel + PDF generation
"""
from dotenv import load_dotenv
load_dotenv()
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await init_db()
    logger.info("✅ Verilənlər bazası hazırdır")
    logger.info("🚀 Bot işə düşdü...")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
