# main.py
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv
from database import init_db
from handlers.registration import register_handlers as reg_register
from handlers.payment import register_payment_handlers
from handlers.admin import register_admin_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def set_default_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="⚪️ Botni ishga tushirish"),
        BotCommand(command="admin", description="🔧 Admin paneli (adminlar uchun)")
    ]
    await bot.set_my_commands(commands)
    logger.info("Default commands set successfully.")

async def main() -> None:
    try:
        init_db()
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())

        reg_register(dp)
        await register_payment_handlers(dp)  # Assuming synchronous; use await if async
        register_admin_handlers(dp)
        await set_default_commands(bot)

        logger.info("Bot is starting...")
        await dp.start_polling(bot, polling_timeout=10)
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())