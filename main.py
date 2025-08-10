import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database import init_db
from handlers.registration import register_handlers
from aiogram import types

async def set_default_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="⚪️ Botni ishga tushirish"),
    ]
    await bot.set_my_commands(commands)

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    register_handlers(dp)
    await set_default_commands(bot)

    print("Bot ishga tushmoqda...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
