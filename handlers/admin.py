from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    list_pending_payments, set_payment_status, get_user_by_tg,
    list_courses, add_course, get_stats, update_user_field
)
from config import ADMIN_IDS
import sqlite3
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def register_admin_handlers(dp):

    def admin_only(func):
        """Faqat adminlar uchun ruxsat beruvchi dekorator"""
        async def wrapper(message_or_callback, *args, **kwargs):
            user_id = getattr(message_or_callback.from_user, "id", None)
            if user_id not in ADMIN_IDS:
                try:
                    text = "Siz admin emassiz."
                    if isinstance(message_or_callback, Message):
                        await message_or_callback.answer(text)
                    elif isinstance(message_or_callback, CallbackQuery):
                        await message_or_callback.answer(text, show_alert=True)
                    logging.warning(f"Non-admin user {user_id} attempted to access admin function")
                except Exception as e:
                    logging.error(f"Error in admin_only decorator: {str(e)}")
                return
            return await func(message_or_callback, *args, **kwargs)
        return wrapper

    # ======== ADMIN PANEL ========
    @dp.message(Command("admin"))
    @admin_only
    async def admin_panel(message: Message, **kwargs):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lovlar (pending)", callback_data="adm_pending")],
            [InlineKeyboardButton(text="📋 Kurslar", callback_data="adm_courses")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")]
        ])
        await message.answer("Admin panel:", reply_markup=kb)
        logging.info(f"Admin {message.from_user.id} accessed admin panel")

    # ======== PENDING PAYMENTS ========
    @dp.callback_query(F.data == "adm_pending")
    @admin_only
    async def adm_pending(callback: CallbackQuery, **kwargs):
        try:
            rows = list_pending_payments()
            if not rows:
                await callback.message.answer("Pending payment yo'q.")
                await callback.answer()
                return

            for pid, user_id, first, last, amount, file_id, created in rows:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay_approve:{pid}:{user_id}"),
                        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"pay_reject:{pid}:{user_id}")
                    ],
                    [InlineKeyboardButton(text="🧾 Foydalanuvchini tahrirlash", callback_data=f"edit_user:{user_id}")]
                ])
                await callback.message.answer_photo(
                    photo=file_id,
                    caption=f"Payment ID: {pid}\nUser: {first} {last}\nSumma: {amount}\nSana: {created}",
                    reply_markup=kb
                )
            await callback.answer()
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logging.error(f"Error in adm_pending: {str(e)}")

    # ======== APPROVE PAYMENT ========
    @dp.callback_query(F.data.startswith("pay_approve:"))
    @admin_only
    async def pay_approve(callback: CallbackQuery, **kwargs):
        try:
            _, pid, user_id = callback.data.split(":")
            set_payment_status(int(pid), "approved", reviewed_by=callback.from_user.id)
            update_user_field(int(user_id), "is_paid", 1)
            update_user_field(int(user_id), "paid_at", datetime.utcnow().isoformat())

            await callback.message.answer(f"To'lov #{pid} tasdiqlandi.")

            with sqlite3.connect("users.db") as conn:
                cur = conn.cursor()
                cur.execute("SELECT tg_id FROM users WHERE id = ?", (int(user_id),))
                t = cur.fetchone()

            if t and t[0]:
                try:
                    await dp.bot.send_message(t[0], "✅ To'lovingiz tasdiqlandi. Endi kursga kirishingiz mumkin.")
                except Exception as e:
                    logging.error(f"Error sending notification to user {t[0]}: {str(e)}")

            await callback.answer()
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)

    # ======== REJECT PAYMENT ========
    @dp.callback_query(F.data.startswith("pay_reject:"))
    @admin_only
    async def pay_reject(callback: CallbackQuery, **kwargs):
        try:
            _, pid, user_id = callback.data.split(":")
            set_payment_status(int(pid), "rejected", reviewed_by=callback.from_user.id)
            await callback.message.answer(f"To'lov #{pid} rad etildi.")

            with sqlite3.connect("users.db") as conn:
                cur = conn.cursor()
                cur.execute("SELECT tg_id FROM users WHERE id = ?", (int(user_id),))
                t = cur.fetchone()

            if t and t[0]:
                try:
                    await dp.bot.send_message(t[0], "❌ To'lovingiz rad etildi. Iltimos, qayta urinib ko‘ring.")
                except Exception as e:
                    logging.error(f"Error sending rejection notification to user {t[0]}: {str(e)}")

            await callback.answer()
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)

    # ======== COURSES ========
    @dp.callback_query(F.data == "adm_courses")
    @admin_only
    async def adm_courses(callback: CallbackQuery, **kwargs):
        try:
            rows = list_courses()
            text = "Kurslar:\n" + "\n".join([f"{r[0]}. {r[1]}" for r in rows]) if rows else "Hozircha kurslar yo'q."
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Kurs qo'shish", callback_data="course_add")],
            ])
            await callback.message.answer(text, reply_markup=kb)
            await callback.answer()
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)

    @dp.callback_query(F.data == "course_add")
    @admin_only
    async def course_add_cb(callback: CallbackQuery, **kwargs):
        await callback.message.answer("Kurs qo'shish uchun: /addcourse Kurs_nomi")
        await callback.answer()

    @dp.message(Command("addcourse"))
    @admin_only
    async def addcourse_cmd(message: Message, **kwargs):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Foydalanish: /addcourse Kurs_nomi")
            return
        name = parts[1].strip()
        try:
            add_course(name)
            await message.reply(f"Kurs qo'shildi: {name}")
        except Exception as e:
            await message.reply(f"Xato yuz berdi: {str(e)}")

    # ======== STATISTICS ========
    @dp.callback_query(F.data == "adm_stats")
    @admin_only
    async def adm_stats(callback: CallbackQuery, **kwargs):
        try:
            s = get_stats()
            text = f"📊 Statistika:\n🎯 Jami foydalanuvchilar: {s['total']}\n💳 To'lov qilganlar: {s['paid']}\n"
            if s['per_course']:
                text += "📚 Kurslarga bo'linishi:\n"
                with sqlite3.connect("users.db") as conn:
                    cur = conn.cursor()
                    for cid, cnt in s['per_course']:
                        cur.execute("SELECT name FROM courses WHERE id = ?", (cid,))
                        cn = cur.fetchone()
                        name = cn[0] if cn else "Noma'lum"
                        text += f"- {name}: {cnt}\n"
            await callback.message.answer(text)
            await callback.answer()
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)

    # ======== EDIT USER ========
    @dp.callback_query(F.data.startswith("edit_user:"))
    @admin_only
    async def edit_user(callback: CallbackQuery, **kwargs):
        try:
            user_id = callback.data.split(":")[1]
            with sqlite3.connect("users.db") as conn:
                cur = conn.cursor()
                cur.execute("SELECT first_name, last_name, age, gender, phone, course_id FROM users WHERE id = ?", (int(user_id),))
                user = cur.fetchone()

                if not user:
                    await callback.message.answer("Foydalanuvchi topilmadi.")
                    await callback.answer()
                    return

                first_name, last_name, age, gender, phone, course_id = user
                cur.execute("SELECT name FROM courses WHERE id = ?", (course_id,))
                course_data = cur.fetchone()
                course_name = course_data[0] if course_data else "Noma'lum"

            text = (f"Foydalanuvchi ma'lumotlari:\n"
                    f"Ism: {first_name}\n"
                    f"Familiya: {last_name}\n"
                    f"Yosh: {age}\n"
                    f"Jins: {gender}\n"
                    f"Telefon: {phone}\n"
                    f"Kurs: {course_name}\n\n"
                    f"Tahrirlash uchun: /edituser {user_id} field value\n"
                    f"Masalan: /edituser {user_id} first_name YangiIsm")

            await callback.message.answer(text)
            await callback.answer()
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
