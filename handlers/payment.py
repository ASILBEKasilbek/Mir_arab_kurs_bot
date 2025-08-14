from aiogram import F
from aiogram.types import Message, CallbackQuery, ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_user_by_tg, create_payment
from config import ADMIN_IDS

class PaymentStates(StatesGroup):
    await_proof = State()

async def register_payment_handlers(dp):

    # 1. Tugma bosilganda chek so'rash
    @dp.callback_query(F.data == "pay_now")
    async def ask_payment_proof(callback: CallbackQuery, state: FSMContext):
        await callback.message.answer("📷 To‘lov chekining suratini yuboring.")
        await state.set_state(PaymentStates.await_proof)  # State to'g'ri belgilanadi
        await callback.answer()

    # 2. Rasm kelganda avtomatik adminga yuborish
    @dp.message(PaymentStates.await_proof, F.content_type == ContentType.PHOTO)
    async def get_payment_proof(message: Message, state: FSMContext):
        print(90)
        tg_id = message.from_user.id
        user = get_user_by_tg(tg_id)
        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. Avval /start bilan ro'yxatdan o'ting.")
            return

        file_id = message.photo[-1].file_id

        # Bazaga saqlash
        payment_id = create_payment(
            user_id=user[0],
            amount=0,  # Miqdor so'ralmaydi
            method="",
            proof_file_id=file_id
        )

        await message.answer("✅ Chekingiz qabul qilindi. Admin tasdiqlaguncha kuting.")
        await state.clear()

        # Adminga yuborish
        for admin in ADMIN_IDS:
            try:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{payment_id}")],
                    [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{payment_id}")]
                ])
                await dp.bot.send_photo(
                    admin,
                    photo=file_id,
                    caption=(
                        f"📥 Yangi chek!\n"
                        f"ID: {payment_id}\n"
                        f"Foydalanuvchi: {user[2]} {user[3]}\n"
                        f"Tg_id: {tg_id}"
                    ),
                    reply_markup=kb
                )
            except Exception as e:
                print("Adminga yuborishda xato:", e)
