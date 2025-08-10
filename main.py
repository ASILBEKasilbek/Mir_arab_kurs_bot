import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database import init_db
from handlers.registration import register_handlers as reg_register
from handlers.payment import register_payment_handlers
from handlers.admin import register_admin_handlers
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

    reg_register(dp)
    await set_default_commands(bot)
    await register_payment_handlers(dp)   # note: pay handler was async def to accept dp; if not, adjust
    register_admin_handlers(dp)

    print("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
