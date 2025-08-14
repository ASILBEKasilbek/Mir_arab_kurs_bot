# admin.py
import re
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.fsm.context import FSMContext
from database import (
    list_pending_payments, set_payment_status, get_user_by_tg,
    list_courses, add_course, get_stats, update_user_field, get_all_users,
    get_users_by_gender, get_user_by_id
)
from config import ADMIN_IDS
import logging
from datetime import datetime
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_inline_keyboard(buttons: list, row_width: int = 2) -> InlineKeyboardMarkup:
    """Create an inline keyboard from a list of (text, callback_data) tuples."""
    keyboard = [
        [InlineKeyboardButton(text=text, callback_data=cb) for text, cb in buttons[i:i + row_width]]
        for i in range(0, len(buttons), row_width)
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def admin_only(func):
    """Restrict access to admin-only functions, filtering out unexpected kwargs."""
    async def wrapper(message_or_callback, *args, **kwargs):
        # Only pass kwargs that the function expects
        valid_kwargs = {k: v for k, v in kwargs.items() if k in func.__code__.co_varnames}
        user_id = getattr(message_or_callback.from_user, "id", None)
        if user_id not in ADMIN_IDS:
            text = "Siz admin emassiz."
            if isinstance(message_or_callback, Message):
                await message_or_callback.answer(text)
            elif isinstance(message_or_callback, CallbackQuery):
                await message_or_callback.answer(text, show_alert=True)
            logger.warning(f"Non-admin user {user_id} attempted to access admin function")
            return
        return await func(message_or_callback, *args, **valid_kwargs)
    return wrapper

async def generate_users_pdf(users_data, columns) -> BytesIO:
    """Generate a PDF with user data in a table format."""
    df = pd.DataFrame(users_data, columns=columns)
    fig, ax = plt.subplots(figsize=(12, len(df) * 0.5 + 1))
    ax.axis('off')
    table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.2)
    buf = BytesIO()
    fig.savefig(buf, format='pdf', bbox_inches='tight')
    plt.close(fig)  # Close the figure to free memory
    buf.seek(0)
    return buf

def register_admin_handlers(dp):
    @dp.message(Command("admin"))
    @admin_only
    async def admin_panel(message: Message):
        """Display the admin panel."""
        buttons = [
            ("💳 To'lovlar (pending)", "adm_pending"),
            ("📋 Kurslar", "adm_courses"),
            ("👥 Foydalanuvchilar", "adm_users"),
            ("📊 Statistika", "adm_stats")
        ]
        kb = create_inline_keyboard(buttons)
        await message.answer("Admin panel:", reply_markup=kb)
        logger.info(f"Admin {message.from_user.id} accessed admin panel.")

    @dp.callback_query(F.data == "adm_users")
    @admin_only
    async def adm_users(callback: CallbackQuery):
        """Show user management options."""
        buttons = [
            ("👥 Hammasi", "view_all_users"),
            ("♂ Erkaklar", "view_males"),
            ("♀ Ayollar", "view_females"),
            ("🔍 Muayyan foydalanuvchi", "view_specific_user"),
            ("📥 PDF yuklab olish (hammasi)", "export_all_pdf")
        ]
        kb = create_inline_keyboard(buttons)
        await callback.message.answer("Foydalanuvchilar bo'limi:", reply_markup=kb)
        await callback.answer()

    @dp.callback_query(F.data == "view_all_users")
    @admin_only
    async def view_all_users(callback: CallbackQuery):
        """View all users as a PDF."""
        users = get_all_users()
        if not users:
            await callback.message.answer("Foydalanuvchilar yo'q.")
            await callback.answer()
            return
        columns = ['ID', 'TG ID', 'Ism', 'Familiya', 'Yosh', 'Jins', 'Telefon', 'Kurs']
        # Convert course_id to course name for display
        with sqlite3.connect("users.db") as conn:
            cur = conn.cursor()
            users_data = []
            for user in users:
                cur.execute("SELECT name FROM courses WHERE id = ?", (user[7],))
                course_data = cur.fetchone()
                course_name = course_data[0] if course_data else "Noma'lum"
                users_data.append(list(user[:-1]) + [course_name])
        buf = await generate_users_pdf(users_data, columns)
        await callback.message.answer_document(document=InputFile(buf, filename='all_users.pdf'))
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} viewed all users as PDF.")

    @dp.callback_query(F.data == "view_males")
    @admin_only
    async def view_males(callback: CallbackQuery):
        """View male users as a PDF."""
        users = get_users_by_gender('erkak')
        if not users:
            await callback.message.answer("Erkak foydalanuvchilar yo'q.")
            await callback.answer()
            return
        columns = ['ID', 'TG ID', 'Ism', 'Familiya', 'Yosh', 'Jins', 'Telefon', 'Kurs']
        with sqlite3.connect("users.db") as conn:
            cur = conn.cursor()
            users_data = []
            for user in users:
                cur.execute("SELECT name FROM courses WHERE id = ?", (user[7],))
                course_data = cur.fetchone()
                course_name = course_data[0] if course_data else "Noma'lum"
                users_data.append(list(user[:-1]) + [course_name])
        buf = await generate_users_pdf(users_data, columns)
        await callback.message.answer_document(document=InputFile(buf, filename='males.pdf'))
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} viewed male users as PDF.")

    @dp.callback_query(F.data == "view_females")
    @admin_only
    async def view_females(callback: CallbackQuery):
        """View female users as a PDF."""
        users = get_users_by_gender('ayol')
        if not users:
            await callback.message.answer("Ayol foydalanuvchilar yo'q.")
            await callback.answer()
            return
        columns = ['ID', 'TG ID', 'Ism', 'Familiya', 'Yosh', 'Jins', 'Telefon', 'Kurs']
        with sqlite3.connect("users.db") as conn:
            cur = conn.cursor()
            users_data = []
            for user in users:
                cur.execute("SELECT name FROM courses WHERE id = ?", (user[7],))
                course_data = cur.fetchone()
                course_name = course_data[0] if course_data else "Noma'lum"
                users_data.append(list(user[:-1]) + [course_name])
        buf = await generate_users_pdf(users_data, columns)
        await callback.message.answer_document(document=InputFile(buf, filename='females.pdf'))
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} viewed female users as PDF.")

    @dp.callback_query(F.data == "view_specific_user")
    @admin_only
    async def view_specific_user_cb(callback: CallbackQuery, state: FSMContext):
        """Prompt for a specific user ID."""
        await callback.message.answer("Foydalanuvchi ID sini kiriting:")
        await state.set_state("await_user_id")
        await callback.answer()

    @dp.message(F.state == "await_user_id")
    @admin_only
    async def view_specific_user(message: Message, state: FSMContext):
        """View details of a specific user by ID."""
        try:
            user_id = int(message.text.strip())
            user = get_user_by_id(user_id)
            if not user:
                await message.answer("Foydalanuvchi topilmadi.")
                await state.clear()
                return
            with sqlite3.connect("users.db") as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM courses WHERE id = ?", (user[7],))
                course_data = cur.fetchone()
                course_name = course_data[0] if course_data else "Noma'lum"
            text = (
                f"ID: {user[0]}\n"
                f"TG ID: {user[1]}\n"
                f"Ism: {user[2]}\n"
                f"Familiya: {user[3]}\n"
                f"Yosh: {user[4]}\n"
                f"Jins: {user[5]}\n"
                f"Telefon: {user[6]}\n"
                f"Kurs: {course_name}"
            )
            await message.answer(text)
            await state.clear()
            logger.info(f"Admin {message.from_user.id} viewed user {user_id}.")
        except ValueError:
            await message.answer("Iltimos, to'g'ri ID kiriting (raqam).")
            logger.warning(f"Admin {message.from_user.id} entered invalid user ID: {message.text}")

    @dp.callback_query(F.data == "export_all_pdf")
    @admin_only
    async def export_all_pdf(callback: CallbackQuery):
        """Export all users as a PDF."""
        users = get_all_users()
        if not users:
            await callback.message.answer("Foydalanuvchilar yo'q.")
            await callback.answer()
            return
        columns = ['ID', 'TG ID', 'Ism', 'Familiya', 'Yosh', 'Jins', 'Telefon', 'Kurs']
        with sqlite3.connect("users.db") as conn:
            cur = conn.cursor()
            users_data = []
            for user in users:
                cur.execute("SELECT name FROM courses WHERE id = ?", (user[7],))
                course_data = cur.fetchone()
                course_name = course_data[0] if course_data else "Noma'lum"
                users_data.append(list(user[:-1]) + [course_name])
        buf = await generate_users_pdf(users_data, columns)
        await callback.message.answer_document(document=InputFile(buf, filename='all_users_export.pdf'))
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} exported all users as PDF.")

    @dp.callback_query(F.data == "adm_pending")
    @admin_only
    async def adm_pending(callback: CallbackQuery):
        """List pending payments."""
        try:
            rows = list_pending_payments()
            if not rows:
                await callback.message.answer("Pending to'lovlar yo'q.")
                await callback.answer()
                return

            for pid, user_id, first, last, amount, file_id, created in rows[:10]:
                buttons = [
                    ("✅ Tasdiqlash", f"pay_approve:{pid}:{user_id}"),
                    ("❌ Rad etish", f"pay_reject:{pid}:{user_id}"),
                    ("🧾 Foydalanuvchini tahrirlash", f"edit_user:{user_id}")
                ]
                kb = create_inline_keyboard(buttons)
                await callback.message.answer_photo(
                    photo=file_id,
                    caption=f"Payment ID: {pid}\nUser: {first} {last}\nSumma: {amount:,}\nSana: {created}",
                    reply_markup=kb
                )
            if len(rows) > 10:
                await callback.message.answer("Ko'proq to'lovlar bor. /morepending bilan davom eting.")
            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} viewed pending payments.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error in adm_pending for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("pay_approve:"))
    @admin_only
    async def pay_approve(callback: CallbackQuery):
        """Approve a payment and notify the user."""
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
                    await callback.message.bot.send_message(
                        t[0], 
                        "✅ To'lovingiz tasdiqlandi. Endi kursga kirishingiz mumkin."
                    )
                    logger.info(f"Sent approval notification to user {t[0]} for payment {pid}.")
                except Exception as e:
                    logger.error(f"Error sending approval notification to user {t[0]}: {str(e)}")

            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} approved payment {pid}.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error approving payment for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("pay_reject:"))
    @admin_only
    async def pay_reject(callback: CallbackQuery):
        """Reject a payment and notify the user."""
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
                    await callback.message.bot.send_message(
                        t[0], 
                        "❌ To'lovingiz rad etildi. Iltimos, qayta urinib ko‘ring."
                    )
                    logger.info(f"Sent rejection notification to user {t[0]} for payment {pid}.")
                except Exception as e:
                    logger.error(f"Error sending rejection notification to user {t[0]}: {str(e)}")

            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} rejected payment {pid}.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error rejecting payment for admin {callback.from_user.id}: {str(e)}")
    @dp.callback_query(F.data == "adm_courses")
    @admin_only
    async def adm_courses(callback: CallbackQuery):
        """List available courses."""
        try:
            rows = list_courses()
            if rows:
                text = "Kurslar:\n" + "\n".join([f"{r[0]}. {r[1]} - {r[2]}" for r in rows])
                # Har bir kursga "O'chirish" tugmasi qo'shamiz
                buttons = [(f"❌ {r[1]}", f"course_del:{r[0]}") for r in rows]
            else:
                text = "Hozircha kurslar yo'q."
                buttons = []
            
            # Qo'shish tugmasini oxirida chiqaramiz
            buttons.append(("➕ Kurs qo'shish", "course_add"))

            kb = create_inline_keyboard(buttons)
            await callback.message.answer(text, reply_markup=kb)
            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} viewed courses.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error in adm_courses for admin {callback.from_user.id}: {str(e)}")


    @dp.callback_query(F.data.startswith("course_del:"))
    @admin_only
    async def delete_course_cb(callback: CallbackQuery):
        """Delete a course by ID."""
        try:
            course_id = int(callback.data.split(":")[1])
            delete_course(course_id)  # Bazadan o'chirish funksiyasi
            await callback.message.answer(f"Kurs o'chirildi. ID: {course_id}")
            logger.info(f"Admin {callback.from_user.id} deleted course ID: {course_id}")
            await callback.answer()
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error deleting course for admin {callback.from_user.id}: {str(e)}")


    @dp.callback_query(F.data == "course_add")
    @admin_only
    async def course_add_cb(callback: CallbackQuery):
        """Prompt to add a new course."""
        await callback.message.answer("Kurs qo'shish uchun: /addcourse Kurs_nomi [Tavsif]\nMasalan: /addcourse YangiKurs Yangi kurs tavsifi")
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} requested to add a course.")


    @dp.message(Command("addcourse"))
    @admin_only
    async def addcourse_cmd(message: Message):
        """Add a new course."""
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            await message.reply("Foydalanish: /addcourse Kurs_nomi [Tavsif]\nMasalan: /addcourse YangiKurs Yangi kurs tavsifi")
            return
        name = parts[1].strip()
        description = parts[2].strip() if len(parts) > 2 else ""
        try:
            add_course(name, description)
            await message.reply(f"Kurs qo'shildi: {name} - {description}")
            logger.info(f"Admin {message.from_user.id} added course: {name}")
        except Exception as e:
            await message.reply(f"Xato yuz berdi: {str(e)}")
            logger.error(f"Error adding course for admin {message.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "adm_stats")
    @admin_only
    async def adm_stats(callback: CallbackQuery):
        """Show bot statistics."""
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
            logger.info(f"Admin {callback.from_user.id} viewed statistics.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error in adm_stats for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("edit_user:"))
    @admin_only
    async def edit_user(callback: CallbackQuery):
        """Edit a user's details."""
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

            text = (
                f"Foydalanuvchi ma'lumotlari:\n"
                f"Ism: {first_name}\n"
                f"Familiya: {last_name}\n"
                f"Yosh: {age}\n"
                f"Jins: {gender}\n"
                f"Telefon: {phone}\n"
                f"Kurs: {course_name}\n\n"
                f"Tahrirlash uchun: /edituser {user_id} field value\n"
                f"Masalan: /edituser {user_id} first_name YangiIsm\n"
                f"Maydonlar: first_name, last_name, age, gender, phone, course_id"
            )
            await callback.message.answer(text)
            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} viewed user {user_id} for editing.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error in edit_user for admin {callback.from_user.id}: {str(e)}")

    @dp.message(Command("edituser"))
    @admin_only
    async def edituser_cmd(message: Message):
        """Edit a user's field via command."""
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            await message.reply("Foydalanish: /edituser user_id field value\nMasalan: /edituser 1 first_name YangiIsm")
            return
        user_id, field, value = parts[1:4]
        valid_fields = ["first_name", "last_name", "age", "gender", "phone", "course_id"]
        if field not in valid_fields:
            await message.reply(f"To'g'ri maydonni tanlang: {', '.join(valid_fields)}")
            return
        try:
            if field == "age":
                value = int(value)
                if not (1 <= value <= 150):
                    await message.reply("Yosh 1 dan 150 gacha bo'lishi kerak.")
                    return
            elif field == "gender" and value not in ["erkak", "ayol"]:
                await message.reply("Jins 'erkak' yoki 'ayol' bo'lishi kerak.")
                return
            elif field == "phone":
                if not re.match(r"^\+998\d{9}$", value):
                    await message.reply("Telefon raqami +998 bilan boshlanib, 9 ta raqamdan iborat bo'lishi kerak.")
                    return
            elif field == "course_id":
                with sqlite3.connect("users.db") as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM courses WHERE id = ?", (int(value),))
                    if not cur.fetchone():
                        await message.reply("Bunday kurs mavjud emas.")
                        return
            update_user_field(int(user_id), field, value)
            await message.reply(f"Foydalanuvchi {user_id} uchun {field} yangilandi: {value}")
            logger.info(f"Admin {message.from_user.id} updated {field} for user {user_id} to {value}.")
        except Exception as e:
            await message.reply(f"Xato yuz berdi: {str(e)}")
            logger.error(f"Error in edituser_cmd for admin {message.from_user.id}: {str(e)}")