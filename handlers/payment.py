from aiogram import F
from aiogram.types import Message, CallbackQuery, ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from database import get_user_by_tg, create_payment
from config import ADMIN_IDS

async def register_payment_handlers(dp):
    @dp.callback_query(F.data == "pay_now")
    async def start_payment(callback: CallbackQuery, state: FSMContext):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Bank orqali", callback_data="method_bank")],
            [InlineKeyboardButton(text="📱 Payme", callback_data="method_payme")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_pay")]
        ])
        await callback.message.answer("To‘lov usulini tanlang:", reply_markup=kb)
        await callback.answer()

    @dp.callback_query(F.data.startswith("method_"))
    async def ask_payment_amount(callback: CallbackQuery, state: FSMContext):
        method = callback.data.replace("method_", "")
        await state.update_data(method=method)
        await callback.message.answer("💰 To‘lov miqdorini yozing (so‘mda):")
        await state.set_state("await_amount")
        await callback.answer()

    @dp.message(F.state == "await_amount")
    async def get_amount(message: Message, state: FSMContext):
        if not message.text.isdigit():
            await message.answer("Iltimos, faqat raqam kiriting.")
            return
        amount = int(message.text)
        await state.update_data(amount=amount)
        await message.answer("📷 Endi to‘lov chekining suratini yuboring.")
        await state.set_state("await_proof")

    @dp.message(F.state == "await_proof", F.content_type == ContentType.PHOTO)
    async def get_payment_proof(message: Message, state: FSMContext):
        data = await state.get_data()
        tg_id = message.from_user.id
        user = get_user_by_tg(tg_id)
        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. Avval /start bilan ro'yxatdan o'ting.")
            return

        file_id = message.photo[-1].file_id
        payment_id = create_payment(
            user_id=user[0],
            amount=data["amount"],
            method=data["method"],
            proof_file_id=file_id
        )
        await message.answer("✅ To‘lov qabul qilindi. Admin tasdiqlaguncha kuting.")
        await state.clear()

        # Adminlarga xabar
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
                        f"💵 Yangi to‘lov!\n"
                        f"ID: {payment_id}\n"
                        f"Foydalanuvchi: {user[2]} {user[3]}\n"
                        f"Summa: {data['amount']:,} so‘m\n"
                        f"Usul: {data['method']}\n"
                        f"Tg_id: {tg_id}"
                    ),
                    reply_markup=kb
                )
            except Exception as e:
                print("Adminga yuborishda xato:", e)
