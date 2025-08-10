from aiogram import F
from aiogram.types import Message, ContentType, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from database import get_user_by_tg, create_payment, update_user_field
from config import ADMIN_IDS

# Foydalanuvchi to'lovni yuboradi: summa va skrin (file). Oddiy variant:
async def register_payment_handlers(dp):
    @dp.message(F.text.startswith("/pay"))
    async def pay_command(message: Message):
        # format: /pay 50000 yoki /pay
        parts = message.text.split()
        if len(parts) >= 2:
            amount = parts[1]
            await message.reply("Iltimos, toʻlov chekining suratini yuboring (photo) va agar mavjud bo'lsa usulni yozing.")
            # set state optionally
        else:
            await message.reply("Toʻlov miqdorini yozing, misol: /pay 50000")

    # Photo as proof
    @dp.message(F.content_type == ContentType.PHOTO)
    async def photo_payment(message: Message):
        tg_id = message.from_user.id
        user = get_user_by_tg(tg_id)
        if not user:
            await message.reply("Siz ro'yxatdan o'tmagansiz. Avval /start bilan ro'yxatdan o'ting.")
            return

        # limit fayl hajmini tekshirish mumkin (telegram returns file_id)
        file_id = message.photo[-1].file_id
        # optional: parse caption for amount
        caption = message.caption or ""
        amount = None
        for token in caption.split():
            if token.replace(".", "").isdigit():
                amount = float(token)
                break
        # default amount (admin may set)
        amount = amount or 0.0

        payment_id = create_payment(user_id=user[0], amount=amount, method="bank_transfer", proof_file_id=file_id)
        await message.reply("To'lov proof qabul qilindi. Admin tasdiqlaguncha kuting. Sizga xabar beramiz.", reply_markup=ReplyKeyboardRemove())

        # notify admins
        for admin in ADMIN_IDS:
            try:
                await dp.bot.send_photo(admin, photo=file_id,
                    caption=f"Yangi to'lov (ID: {payment_id})\nFoydalanuvchi: {user[2]} {user[3]}\nSumma: {amount}\nUser_id: {user[0]}")
            except Exception as e:
                print("Adminga yuborishda xato:", e)
