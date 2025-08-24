# payment.py
from aiogram import Bot, F
from aiogram.types import Message, CallbackQuery, ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_user_by_tg, create_payment, get_course_by_id, set_payment_status
from config import BOT_TOKEN, ADMIN_IDS
import sqlite3
bot = Bot(token=BOT_TOKEN)

class PaymentStates(StatesGroup):
    await_proof = State()

async def register_payment_handlers(dp):

    @dp.callback_query(F.data.startswith("pay_now:"))
    async def ask_payment_proof(callback: CallbackQuery, state: FSMContext):
        tg_id = callback.from_user.id
        user = get_user_by_tg(tg_id)
        if not user:
            await callback.message.answer("❌ Siz ro'yxatdan o'tmagansiz. Avval /start bilan ro'yxatdan o'ting.")
            await callback.answer()
            return

        if user['is_paid'] == 1:
            await callback.message.answer("✅ Siz allaqachon to'lov qilgansiz.")
            await callback.answer()
            return

        course_id = int(callback.data.split(":")[1])
        course = get_course_by_id(course_id)
        if not course:
            await callback.message.answer("❌ Kurs topilmadi.")
            await callback.answer()
            return

        await callback.message.answer(
            f"📚 Siz {course['name']} kursi uchun to‘lov qilmoqdasiz.\n\n"
            "Iltimos, to‘lov chekini yuboring.\n\n"
            "💳 To‘lov rekvizitlari:\n"
            "Mir Arab ўрта махсус ислом билим юрти\n"
            "\"Алоқабанк\" Бухоро филиали\n"
            "x/r: 20208000900534709001 AT\n"
            "MFO: 00401\n"
            "ИНН: 202301014\n"
            "ОКПО: 17498091\n\n"
            "📷 To‘lov chekining suratini yuboring."
        )

        await state.update_data(course_id=course_id)
        await state.set_state(PaymentStates.await_proof)
        await callback.answer()

    @dp.message(PaymentStates.await_proof, F.content_type == ContentType.PHOTO)
    async def get_payment_proof(message: Message, state: FSMContext):
        tg_id = message.from_user.id
        user = get_user_by_tg(tg_id)
        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. Avval /start bilan ro'yxatdan o'ting.")
            return

        file_id = message.photo[-1].file_id
        data = await state.get_data()
        course_id = data.get("course_id")
        course = get_course_by_id(course_id)

        # Bazaga saqlash
        payment_id = create_payment(
            user_id=user['id'],
            amount=course['narx'],
            method="transfer",
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
                await bot.send_photo(
                    admin,
                    photo=file_id,
                    caption=(
                        f"📥 Yangi chek!\n"
                        f"ID: {payment_id}\n"
                        f"Foydalanuvchi: {user['first_name']} {user['last_name']}\n"
                        f"Tg_id: {tg_id}"
                    ),
                    reply_markup=kb
                )
            except Exception as e:
                print("Adminga yuborishda xato:", e)

    @dp.callback_query(F.data.startswith("approve_"))
    async def approve_payment(callback: CallbackQuery):
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("Siz admin emassiz.")
            return

        payment_id = int(callback.data.replace("approve_", ""))
        set_payment_status(payment_id, "approved", callback.from_user.id)

        # Foydalanuvchiga xabar
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT u.tg_id FROM payments p JOIN users u ON p.user_id = u.id WHERE p.id = ?", (payment_id,))
        tg_id = cur.fetchone()[0]
        conn.close()

        await bot.send_message(tg_id, "✅ To'lov tasdiqlandi! Kursga qo'shildingiz.")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Tasdiqlandi.")

    @dp.callback_query(F.data.startswith("reject_"))
    async def reject_payment(callback: CallbackQuery):
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("Siz admin emassiz.")
            return

        payment_id = int(callback.data.replace("reject_", ""))
        set_payment_status(payment_id, "rejected", callback.from_user.id)

        # Foydalanuvchiga xabar
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT u.tg_id FROM payments p JOIN users u ON p.user_id = u.id WHERE p.id = ?", (payment_id,))
        tg_id = cur.fetchone()[0]
        conn.close()

        await bot.send_message(tg_id, "❌ To'lov rad etildi. Iltimos, qayta urinib ko'ring.")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Rad etildi.")