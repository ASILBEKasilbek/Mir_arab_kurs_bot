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
        async def wrapper(message_or_callback, *args, **kwargs):
            user_id = getattr(message_or_callback.from_user, "id", None)
            if user_id not in ADMIN_IDS:
                try:
                    await message_or_callback.answer("Siz admin emassiz." if isinstance(message_or_callback, Message)
                                                    else "Siz admin emassiz.", show_alert=isinstance(message_or_callback, CallbackQuery))
                    logging.warning(f"Non-admin user {user_id} attempted to access admin function")
                except Exception as e:
                    logging.error(f"Error in admin_only decorator: {str(e)}")
                return
            return await func(message_or_callback, *args, **kwargs)
        return wrapper

    @dp.message(Command("admin"))
    @admin_only
    async def admin_panel(message: Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 To'lovlar (pending)", callback_data="adm_pending")],
            [InlineKeyboardButton(text="📋 Kurslar", callback_data="adm_courses")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
            [InlineKeyboardButton(text="🧾 Ro'yxat (all users)", callback_data="adm_users")]
        ])
        await message.answer("Admin panel:", reply_markup=kb)
        logging.info(f"Admin {message.from_user.id} accessed admin panel")

    @dp.callback_query(F.data == "adm_pending")
    @admin_only
    async def adm_pending(callback: CallbackQuery):
        try:
            rows = list_pending_payments()
            if not rows:
                await callback.message.answer("Pending payment yo'q.")
                await callback.answer()
                logging.info(f"Admin {callback.from_user.id} checked pending payments: none found")
                return
            for r in rows:
                pid, user_id, first, last, amount, file_id, created = r
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
            logging.info(f"Admin {callback.from_user.id} viewed pending payments")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logging.error(f"Error in adm_pending for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("pay_approve:"))
    @admin_only
    async def pay_approve(callback: CallbackQuery):
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
                    await dp.bot.send_message(t[0], "Sizning to'lovingiz tasdiqlandi. Endi kursga kirishingiz mumkin.")
                    logging.info(f"Sent approval notification to user {t[0]} for payment #{pid}")
                except Exception as e:
                    await callback.message.answer(f"Foydalanuvchiga xabar yuborishda xato: {str(e)}")
                    logging.error(f"Error sending notification to user {t[0]}: {str(e)}")
            await callback.answer()
            logging.info(f"Admin {callback.from_user.id} approved payment #{pid}")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logging.error(f"Error in pay_approve for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("pay_reject:"))
    @admin_only
    async def pay_reject(callback: CallbackQuery):
        try:
            _, pid, user_id = callback.data.split(":")
            set_payment_status(int(pid), "rejected", reviewed_by=callback.from_user.id)
            await callback.message.answer(f"To'lov #{pid} rad etildi. Foydalanuvchiga bildirish jo'nating.")
            with sqlite3.connect("users.db") as conn:
                cur = conn.cursor()
                cur.execute("SELECT tg_id FROM users WHERE id = ?", (int(user_id),))
                t = cur.fetchone()
            if t and t[0]:
                try:
                    await dp.bot.send_message(t[0], "Sizning to'lovingiz rad etildi. Iltimos, qayta urinib ko'ring.")
                    logging.info(f"Sent rejection notification to user {t[0]} for payment #{pid}")
                except Exception as e:
                    await callback.message.answer(f"Foydalanuvchiga xabar yuborishda xato: {str(e)}")
                    logging.error(f"Error sending rejection notification to user {t[0]}: {str(e)}")
            await callback.answer()
            logging.info(f"Admin {callback.from_user.id} rejected payment #{pid}")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logging.error(f"Error in pay_reject for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "adm_courses")
    @admin_only
    async def adm_courses(callback: CallbackQuery):
        try:
            rows = list_courses()
            text = "Kurslar:\n" + "\n".join([f"{r[0]}. {r[1]}" for r in rows]) if rows else "Hozircha kurslar yo'q."
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Kurs qo'shish", callback_data="course_add")],
            ])
            await callback.message.answer(text, reply_markup=kb)
            await callback.answer()
            logging.info(f"Admin {callback.from_user.id} viewed courses")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logging.error(f"Error in adm_courses for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "course_add")
    @admin_only
    async def course_add_cb(callback: CallbackQuery):
        await callback.message.answer("Kurs qo'shish uchun admin: /addcourse Kurs_nomi")
        await callback.answer()
        logging.info(f"Admin {callback.from_user.id} requested to add a course")

    @dp.message(Command("addcourse"))
    @admin_only
    async def addcourse_cmd(message: Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Foydalanish: /addcourse Kurs_nomi")
            logging.warning(f"Admin {message.from_user.id} provided invalid /addcourse command")
            return
        name = parts[1].strip()
        try:
            add_course(name)
            await message.reply(f"Kurs qo'shildi: {name}")
            logging.info(f"Admin {message.from_user.id} added course: {name}")
        except Exception as e:
            await message.reply(f"Xato yuz berdi: {str(e)}")
            logging.error(f"Error adding course for admin {message.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "adm_stats")
    @admin_only
    async def adm_stats(callback: CallbackQuery):
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
            logging.info(f"Admin {callback.from_user.id} viewed statistics")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logging.error(f"Error in adm_stats for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("edit_user:"))
    @admin_only
    async def edit_user(callback: CallbackQuery):
        try:
            user_id = callback.data.split(":")[1]
            with sqlite3.connect("users.db") as conn:
                cur = conn.cursor()
                cur.execute("SELECT first_name, last_name, age, gender, phone, course_id FROM users WHERE id = ?", (int(user_id),))
                user = cur.fetchone()
                if not user:
                    await callback.message.answer("Foydalanuvchi topilmadi.")
                    await callback.answer()
                    logging.warning(f"Admin {callback.from_user.id} tried to edit non-existent user {user_id}")
                    return
                first_name, last_name, age, gender, phone, course_id = user
                cur.execute("SELECT name FROM courses WHERE id = ?", (course_id,))
                course_name = cur.fetchone()[0] if cur.fetchone() else "Noma'lum"
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
            logging.info(f"Admin {callback.from_user.id} viewed user {user_id} details")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logging.error(f"Error in edit_user for admin {callback.from_user.id}: {str(e)}")