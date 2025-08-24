import re
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    list_pending_payments, set_payment_status, get_user_by_tg,
    list_courses, add_course, get_stats, update_user_field, get_all_users,
    get_users_by_gender, get_user_by_id, delete_course
)
from config import ADMIN_IDS, DB_PATH
import logging
from datetime import datetime
import sqlite3
import pandas as pd
from io import BytesIO
from aiogram import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class AddCourseStates(StatesGroup):
    name = State()
    description = State()
    gender = State()
    boshlanish_sanasi = State()
    limit_count = State()
    narx = State()

def create_inline_keyboard(buttons: list, row_width: int = 2) -> InlineKeyboardMarkup:
    """Create an inline keyboard from a list of (text, callback_data) tuples."""
    keyboard = [
        [InlineKeyboardButton(text=text, callback_data=cb) for text, cb in buttons[i:i + row_width]]
        for i in range(0, len(buttons), row_width)
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def admin_only(func):
    """Restrict access to admin-only functions."""
    async def wrapper(message_or_callback, *args, **kwargs):
        user_id = getattr(message_or_callback.from_user, "id", None)
        if user_id not in ADMIN_IDS:
            text = "Siz admin emassiz."
            if isinstance(message_or_callback, Message):
                await message_or_callback.answer(text)
            elif isinstance(message_or_callback, CallbackQuery):
                await message_or_callback.message.answer(text)
                await message_or_callback.answer(show_alert=True)
            logger.warning(f"Non-admin user {user_id} attempted to access admin function")
            return
        return await func(message_or_callback, *args, **kwargs)
    return wrapper

async def generate_users_excel(users_data, columns) -> BytesIO:
    df = pd.DataFrame(users_data, columns=columns)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Users')
        worksheet = writer.sheets['Users']
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(idx, idx, max_len)
    buf.seek(0)
    return buf

def register_admin_handlers(dp):
    @dp.message(Command("admin"))
    @admin_only
    async def admin_panel(message: types.Message, *args, **kwargs):
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
    async def adm_users(callback: CallbackQuery, **kwargs):
        """Show user management options."""
        buttons = [
            ("👥 Hammasi", "view_all_users"),
            ("♂ Erkaklar", "view_males"),
            ("♀ Ayollar", "view_females"),
            ("🔍 Muayyan foydalanuvchi", "view_specific_user"),
            ("📥 Excel yuklab olish (hammasi)", "export_all_excel")
        ]
        kb = create_inline_keyboard(buttons)
        await callback.message.answer("Foydalanuvchilar bo'limi:", reply_markup=kb)
        await callback.answer()

    @dp.callback_query(F.data == "view_all_users")
    @admin_only
    async def view_all_users(callback: CallbackQuery, **kwargs):
        """View all users as an Excel file."""
        users = get_all_users()
        if not users:
            await callback.message.answer("Foydalanuvchilar yo'q.")
            await callback.answer()
            return
        columns = [
            'ID',
            'TG ID',
            'Til',
            'Ism',
            'Familiya',
            'Tug\'ilgan sana',
            'Jins',
            'Telefon',
            'Manzil',
            'Pasport oldi',
            'Pasport orqa',
            'Kurs ID',
            'Ro‘yxatdan o‘tgan vaqt',
            'To‘lov qilinganmi',
            'To‘lov vaqti',
            'Guruh xabari ID',
            'Kurs nomi'
        ]
        users_data = []
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for user in users:
            cur.execute("SELECT name FROM courses WHERE id = ?", (user['course_id'],))
            course_data = cur.fetchone()
            course_name = course_data[0] if course_data else "Noma'lum"
            users_data.append([
                user['id'],
                user['tg_id'],
                user['lang'],
                user['first_name'],
                user['last_name'],
                user['birth_date'],
                user['gender'],
                user['phone'],
                user['address'],
                user['passport_front'],
                user['passport_back'],
                user['course_id'],
                user['registered_at'],
                user['is_paid'],
                user['paid_at'],
                user['registration_message_id'],
                course_name
            ])
        conn.close()
        buf = await generate_users_excel(users_data, columns)
        await callback.message.answer_document(document=BufferedInputFile(buf.getvalue(), filename='all_users.xlsx'))
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} viewed all users as Excel.")

    @dp.callback_query(F.data == "view_males")
    @admin_only
    async def view_males(callback: CallbackQuery, **kwargs):
        """View male users as an Excel file."""
        users = get_users_by_gender('erkak')
        if not users:
            await callback.message.answer("Erkak foydalanuvchilar yo'q.")
            await callback.answer()
            return
        columns = [
            'ID',
            'TG ID',
            'Til',
            'Ism',
            'Familiya',
            'Tug\'ilgan sana',
            'Jins',
            'Telefon',
            'Manzil',
            'Kurs ID',
            'Kurs nomi'
        ]
        users_data = []
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for user in users:
            cur.execute("SELECT name FROM courses WHERE id = ?", (user['course_id'],))
            course_data = cur.fetchone()
            course_name = course_data[0] if course_data else "Noma'lum"
            users_data.append([
                user['id'],
                user['tg_id'],
                user['lang'],
                user['first_name'],
                user['last_name'],
                user['birth_date'],
                user['gender'],
                user['phone'],
                user['address'],
                user['course_id'],
                course_name
            ])
        conn.close()
        buf = await generate_users_excel(users_data, columns)
        await callback.message.answer_document(document=BufferedInputFile(buf.getvalue(), filename='males.xlsx'))
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} viewed male users as Excel.")

    @dp.callback_query(F.data == "view_females")
    @admin_only
    async def view_females(callback: CallbackQuery, **kwargs):
        """View female users as an Excel file."""
        users = get_users_by_gender('ayol')
        if not users:
            await callback.message.answer("Ayol foydalanuvchilar yo'q.")
            await callback.answer()
            return
        columns = [
            'ID',
            'TG ID',
            'Til',
            'Ism',
            'Familiya',
            'Tug\'ilgan sana',
            'Jins',
            'Telefon',
            'Manzil',
            'Kurs ID',
            'Kurs nomi'
        ]
        users_data = []
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for user in users:
            cur.execute("SELECT name FROM courses WHERE id = ?", (user['course_id'],))
            course_data = cur.fetchone()
            course_name = course_data[0] if course_data else "Noma'lum"
            users_data.append([
                user['id'],
                user['tg_id'],
                user['lang'],
                user['first_name'],
                user['last_name'],
                user['birth_date'],
                user['gender'],
                user['phone'],
                user['address'],
                user['course_id'],
                course_name
            ])
        conn.close()
        buf = await generate_users_excel(users_data, columns)
        await callback.message.answer_document(document=BufferedInputFile(buf.getvalue(), filename='females.xlsx'))
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} viewed female users as Excel.")

    @dp.callback_query(F.data == "view_specific_user")
    @admin_only
    async def view_specific_user_cb(callback: CallbackQuery, state: FSMContext, **kwargs):
        """Prompt for a specific user ID."""
        await callback.message.answer("Foydalanuvchi ID sini kiriting:")
        await state.set_state("await_user_id")
        await callback.answer()

    @dp.message(F.state == "await_user_id")
    @admin_only
    async def view_specific_user(message: Message, state: FSMContext, **kwargs):
        """View details of a specific user by ID."""
        try:
            user_id = int(message.text.strip())
            user = get_user_by_id(user_id)
            if not user:
                await message.answer("Foydalanuvchi topilmadi.")
                await state.clear()
                return
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT name FROM courses WHERE id = ?", (user['course_id'],))
            course_data = cur.fetchone()
            conn.close()
            course_name = course_data[0] if course_data else "Noma'lum"
            text = (
                f"ID: {user['id']}\n"
                f"TG ID: {user['tg_id']}\n"
                f"Til: {user['lang'] or 'Nomaʼlum'}\n"
                f"Ism: {user['first_name']}\n"
                f"Familiya: {user['last_name']}\n"
                f"Tug'ilgan sana: {user['birth_date']}\n"
                f"Jins: {user['gender']}\n"
                f"Telefon: {user['phone']}\n"
                f"Kurs: {course_name}"
            )
            await message.answer(text)
            await state.clear()
            logger.info(f"Admin {message.from_user.id} viewed user {user_id}.")
        except ValueError:
            await message.answer("Iltimos, to'g'ri ID kiriting (raqam).")
            logger.warning(f"Admin {message.from_user.id} entered invalid user ID: {message.text}")

    @dp.callback_query(F.data == "export_all_excel")
    @admin_only
    async def export_all_excel(callback: CallbackQuery, **kwargs):
        """Export all users as an Excel file."""
        users = get_all_users()
        if not users:
            await callback.message.answer("Foydalanuvchilar yo'q.")
            await callback.answer()
            return
        columns = [
            'ID',
            'TG ID',
            'Til',
            'Ism',
            'Familiya',
            'Tug\'ilgan sana',
            'Jins',
            'Telefon',
            'Manzil',
            'Kurs ID',
            'Kurs nomi'
        ]
        users_data = []
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for user in users:
            cur.execute("SELECT name FROM courses WHERE id = ?", (user['course_id'],))
            course_data = cur.fetchone()
            course_name = course_data[0] if course_data else "Noma'lum"
            users_data.append([
                user['id'],
                user['tg_id'],
                user['lang'],
                user['first_name'],
                user['last_name'],
                user['birth_date'],
                user['gender'],
                user['phone'],
                user['address'],
                user['course_id'],
                course_name
            ])
        conn.close()
        buf = await generate_users_excel(users_data, columns)
        await callback.message.answer_document(document=BufferedInputFile(buf.getvalue(), filename='all_users_export.xlsx'))
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} exported all users as Excel.")

    @dp.callback_query(F.data == "adm_pending")
    @admin_only
    async def adm_pending(callback: CallbackQuery, **kwargs):
        """List pending payments."""
        try:
            rows = list_pending_payments()
            if not rows:
                await callback.message.answer("Pending to'lovlar yo'q.")
                await callback.answer()
                return

            for r in rows[:10]:
                buttons = [
                    ("✅ Tasdiqlash", f"pay_approve:{r['id']}:{r['user_id']}"),
                    ("❌ Rad etish", f"pay_reject:{r['id']}:{r['user_id']}"),
                    ("🧾 Foydalanuvchini tahrirlash", f"edit_user:{r['user_id']}")
                ]
                kb = create_inline_keyboard(buttons)
                await callback.message.answer_photo(
                    photo=r['proof_file_id'],
                    caption=f"Payment ID: {r['id']}\nUser: {r['first_name']} {r['last_name']}\nSumma: {r['amount']:,}\nSana: {r['created_at']}",
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
    async def pay_approve(callback: CallbackQuery, **kwargs):
        """Approve a payment and notify the user."""
        try:
            _, pid, user_id = callback.data.split(":")
            pid = int(pid)
            user_id = int(user_id)
            set_payment_status(pid, "approved", reviewed_by=callback.from_user.id)

            await callback.message.answer(f"To'lov #{pid} tasdiqlandi.")

            user = get_user_by_tg(user_id)
            if user:
                lang = user['lang'] or "uz"
                try:
                    await callback.message.bot.send_message(
                        user['tg_id'], 
                        "✅ To'lovingiz tasdiqlandi. Endi kursga kirishingiz mumkin." if lang == "uz" else
                        "✅ Ваш платеж подтвержден. Теперь вы можете приступить к курсу."
                    )
                    logger.info(f"Sent approval notification to user {user['tg_id']} for payment {pid}.")
                except Exception as e:
                    logger.error(f"Error sending approval notification to user {user['tg_id']}: {str(e)}")

            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} approved payment {pid}.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error approving payment for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("pay_reject:"))
    @admin_only
    async def pay_reject(callback: CallbackQuery, **kwargs):
        """Reject a payment and notify the user."""
        try:
            _, pid, user_id = callback.data.split(":")
            pid = int(pid)
            user_id = int(user_id)
            set_payment_status(pid, "rejected", reviewed_by=callback.from_user.id)

            await callback.message.answer(f"To'lov #{pid} rad etildi.")

            user = get_user_by_tg(user_id)
            if user:
                lang = user['lang'] or "uz"
                try:
                    await callback.message.bot.send_message(
                        user['tg_id'], 
                        "❌ To'lovingiz rad etildi. Iltimos, qayta urinib ko‘ring." if lang == "uz" else
                        "❌ Ваш платеж отклонен. Пожалуйста, попробуйте снова."
                    )
                    logger.info(f"Sent rejection notification to user {user['tg_id']} for payment {pid}.")
                except Exception as e:
                    logger.error(f"Error sending rejection notification to user {user['tg_id']}: {str(e)}")

            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} rejected payment {pid}.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error rejecting payment for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "adm_courses")
    @admin_only
    async def adm_courses(callback: CallbackQuery, **kwargs):
        """Kurslar ro'yxatini ko‘rsatish."""
        try:
            rows = list_courses()
            buttons = []
            if rows:
                text = "📚 *Kurslar ro‘yxati:*\n\n" + "\n".join([
                    f"**{r['id']}.** {r['name']}\n"
                    f"📝 {r['description']}\n"
                    f"📅 Boshlanish sanasi: {r['boshlanish_sanasi']}\n"
                    f"👥 Jins: {r['gender']} | 📦 Joy: {r['joylar_soni']}/{r['limit_count']} ta\n"
                    for r in rows
                ])
                buttons.extend([(f"❌ {r['name']}", f"course_del:{r['id']}") for r in rows])
            else:
                text = (
                    "⚠️ *Hozircha kurslar mavjud emas!*\n\n"
                    "📌 Yangi kurs qo‘shish uchun quyidagi tugmadan foydalaning."
                )
            buttons.append(("➕ Kurs qo‘shish", "course_add"))
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} viewed courses.")
        except Exception as e:
            await callback.message.answer("❌ Kurslar ro‘yxatini yuklashda xatolik yuz berdi. Keyinroq urinib ko‘ring.")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error in adm_courses for admin {callback.from_user.id}: {e}", exc_info=True)

    @dp.callback_query(F.data.startswith("course_del:"))
    @admin_only
    async def delete_course_cb(callback: CallbackQuery, **kwargs):
        """Kursni ID bo‘yicha o‘chirish."""
        try:
            course_id = int(callback.data.split(":")[1])
            delete_course(course_id)
            await callback.message.answer(f"✅ Kurs o'chirildi. ID: {course_id}")
            logger.info(f"Admin {callback.from_user.id} deleted course ID: {course_id}")
            await callback.answer()
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error deleting course for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "course_add")
    @admin_only
    async def course_add_start(callback: CallbackQuery, state: FSMContext, **kwargs):
        """Start adding a new course."""
        await callback.message.answer("📚 Yangi kurs nomini kiriting:")
        await state.set_state(AddCourseStates.name)
        await callback.answer()

    @dp.message(AddCourseStates.name)
    @admin_only
    async def add_course_name(message: Message, state: FSMContext, **kwargs):
        """Get course name."""
        await state.update_data(name=message.text.strip())
        await message.answer("📝 Kurs tavsifini kiriting:")
        await state.set_state(AddCourseStates.description)

    @dp.message(AddCourseStates.description)
    @admin_only
    async def add_course_description(message: Message, state: FSMContext, **kwargs):
        """Get course description."""
        await state.update_data(description=message.text.strip())
        kb = create_inline_keyboard([
            ("👨 Erkak", "gender:erkak"),
            ("👩 Ayol", "gender:ayol"),
            ("👥 Hammasi", "gender:hammasi")
        ])
        await message.answer("👥 Qaysi jins uchun mo‘ljallangan?", reply_markup=kb)

    @dp.callback_query(F.data.startswith("gender:"))
    @admin_only
    async def add_course_gender(callback: CallbackQuery, state: FSMContext, **kwargs):
        """Get course gender."""
        gender = callback.data.split(":")[1]
        await state.update_data(gender=gender)
        await callback.message.answer("📦 Necha joy bo‘lishini kiriting (limit):")
        await state.set_state(AddCourseStates.limit_count)
        await callback.answer()

    @dp.message(AddCourseStates.limit_count)
    @admin_only
    async def add_course_limit_count(message: Message, state: FSMContext, **kwargs):
        """Get course limit count."""
        try:
            limit_count = int(message.text.strip())
            if limit_count <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Limit butun musbat son bo‘lishi kerak. Qayta kiriting:")
            return
        await state.update_data(limit_count=limit_count)
        await message.answer("📅 Kurs boshlanish sanasini kiriting (YYYY-MM-DD formatida):")
        await state.set_state(AddCourseStates.boshlanish_sanasi)

    @dp.message(AddCourseStates.boshlanish_sanasi)
    @admin_only
    async def add_course_boshlanish_sanasi(message: Message, state: FSMContext, **kwargs):
        """Get course start date."""
        boshlanish_sanasi = message.text.strip()
        try:
            datetime.strptime(boshlanish_sanasi, "%Y-%m-%d")
        except ValueError:
            await message.answer("❌ Sana formati noto‘g‘ri. To‘g‘ri format: YYYY-MM-DD")
            return
        await state.update_data(boshlanish_sanasi=boshlanish_sanasi)
        await message.answer("💰 Kurs narxini kiriting (faqat son, masalan: 250000):")
        await state.set_state(AddCourseStates.narx)

    @dp.message(AddCourseStates.narx)
    @admin_only
    async def add_course_finish(message: Message, state: FSMContext, **kwargs):
        """Finish adding a new course."""
        try:
            narx = float(message.text.strip())
            if narx < 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Narx musbat son bo‘lishi kerak. Qayta kiriting:")
            return
        await state.update_data(narx=narx)
        data = await state.get_data()
        add_course(
            name=data["name"],
            description=data["description"],
            gender=data["gender"],
            boshlanish_sanasi=data["boshlanish_sanasi"],
            limit_count=data["limit_count"],
            narx=data["narx"]
        )
        await message.answer(
            f"✅ Kurs qo‘shildi!\n\n"
            f"📚 {data['name']}\n"
            f"📝 {data['description']}\n"
            f"👥 {data['gender']}\n"
            f"📦 {data['limit_count']} ta joy\n"
            f"📅 Boshlanish sanasi: {data['boshlanish_sanasi']}\n"
            f"💰 Narx: {data['narx']:,} so‘m"
        )
        await state.clear()
        logger.info(f"Admin {message.from_user.id} added course: {data['name']}")

    @dp.callback_query(F.data == "adm_stats")
    @admin_only
    async def adm_stats(callback: CallbackQuery, **kwargs):
        """Show bot statistics."""
        try:
            s = get_stats()
            text = f"📊 Statistika:\n🎯 Jami foydalanuvchilar: {s['total']}\n💳 To'lov qilganlar: {s['paid']}\n"
            if s['per_course']:
                text += "📚 Kurslarga bo'linishi:\n"
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                for p in s['per_course']:
                    cur.execute("SELECT name FROM courses WHERE id = ?", (p['course_id'],))
                    cn = cur.fetchone()
                    name = cn[0] if cn else "Noma'lum"
                    text += f"- {name}: {p['users_count']}\n"
                conn.close()
            await callback.message.answer(text)
            await callback.answer()
            logger.info(f"Admin {callback.from_user.id} viewed statistics.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer("Xato", show_alert=True)
            logger.error(f"Error in adm_stats for admin {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("edit_user:"))
    @admin_only
    async def edit_user(callback: CallbackQuery, **kwargs):
        """Edit a user's details."""
        try:
            user_id = int(callback.data.split(":")[1])
            user = get_user_by_id(user_id)
            if not user:
                await callback.message.answer("Foydalanuvchi topilmadi.")
                await callback.answer()
                return
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT name FROM courses WHERE id = ?", (user['course_id'],))
            course_data = cur.fetchone()
            conn.close()
            course_name = course_data[0] if course_data else "Noma'lum"
            text = (
                f"Foydalanuvchi ma'lumotlari:\n"
                f"ID: {user_id}\n"
                f"TG ID: {user['tg_id']}\n"
                f"Til: {user['lang'] or 'Nomaʼlum'}\n"
                f"Ism: {user['first_name']}\n"
                f"Familiya: {user['last_name']}\n"
                f"Tug'ilgan sana: {user['birth_date']}\n"
                f"Jins: {user['gender']}\n"
                f"Telefon: {user['phone']}\n"
                f"Kurs: {course_name}\n\n"
                f"Tahrirlash uchun: /edituser {user_id} field value\n"
                f"Masalan: /edituser {user_id} first_name YangiIsm\n"
                f"Maydonlar: first_name, last_name, birth_date, gender, phone, course_id"
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
    async def edituser_cmd(message: Message, **kwargs):
        """Edit a user's field via command."""
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            await message.reply("Foydalanish: /edituser user_id field value\nMasalan: /edituser 1 first_name YangiIsm")
            return
        user_id, field, value = parts[1:4]
        valid_fields = ["first_name", "last_name", "birth_date", "gender", "phone", "course_id"]
        if field not in valid_fields:
            await message.reply(f"To'g'ri maydonni tanlang: {', '.join(valid_fields)}")
            return
        try:
            if field == "birth_date":
                datetime.strptime(value, "%Y-%m-%d")
            elif field == "gender" and value not in ["erkak", "ayol"]:
                await message.reply("Jins 'erkak' yoki 'ayol' bo'lishi kerak.")
                return
            elif field == "phone":
                if not re.match(r"^\+998\d{9}$", value):
                    await message.reply("Telefon raqami +998 bilan boshlanib, 9 ta raqamdan iborat bo'lishi kerak.")
                    return
            elif field == "course_id":
                value = int(value)
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT id FROM courses WHERE id = ?", (value,))
                if not cur.fetchone():
                    await message.reply("Bunday kurs mavjud emas.")
                    conn.close()
                    return
                conn.close()
            update_user_field(int(user_id), field, value)
            await message.reply(f"Foydalanuvchi {user_id} uchun {field} yangilandi: {value}")
            logger.info(f"Admin {message.from_user.id} updated {field} for user {user_id} to {value}.")
        except Exception as e:
            await message.reply(f"Xato yuz berdi: {str(e)}")
            logger.error(f"Error in edituser_cmd for admin {message.from_user.id}: {str(e)}")