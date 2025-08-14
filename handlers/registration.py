import json
import logging
import re
import bleach
from aiogram import F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ContentType
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from database import save_user, get_user_by_tg, update_user_field, list_courses

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load translations
with open("translations.json", "r", encoding="utf-8") as f:
    TRANSLATIONS = json.load(f)

class Registration(StatesGroup):
    lang = State()
    confirm = State()
    first_name = State()
    last_name = State()
    age = State()
    gender = State()
    phone = State()
    quran_course = State()
    final_confirm = State()

class EditProfile(StatesGroup):
    field = State()
    new_value = State()

def create_inline_keyboard(buttons: list, row_width: int = 2) -> InlineKeyboardMarkup:
    """Create an inline keyboard from a list of (text, callback_data) tuples."""
    keyboard = [
        [InlineKeyboardButton(text=text, callback_data=cb) for text, cb in buttons[i:i + row_width]]
        for i in range(0, len(buttons), row_width)
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent malicious data."""
    return bleach.clean(text, tags=[], strip=True).strip()

def register_handlers(dp):
    @dp.message(Command("start"))
    async def start_registration(message: Message, state: FSMContext):
        """Handle the /start command to initiate registration or show profile."""
        user = get_user_by_tg(message.from_user.id)
        if user:
            course_id = user[6]  # Assuming course_id is in index 6
            course_display = next((c[1] for c in list_courses() if c[0] == course_id), course_id)
            buttons = [
                ("📋 Ma’lumotlarim", "view_profile"),
                ("✏️ Tahrirlash", "edit_profile"),
                ("💳 To‘lov qilish", "pay_now"),
                ("❌ Bekor qilish", "cancel")
            ]
            kb = create_inline_keyboard(buttons)
            await message.answer(
                f"✅ Siz ro‘yxatdan o‘tgansiz!\n\n"
                f"Ism: {user[2]}\nFamiliya: {user[3]}\nKurs: {course_display}",
                reply_markup=kb, parse_mode="Markdown"
            )
            logger.info(f"User {message.from_user.id} accessed profile.")
            return

        buttons = [
            ("🇺🇿 O‘zbek", "lang_uz"),
            ("🇷🇺 Русский", "lang_ru"),
            ("❌ Bekor qilish", "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await message.answer("Tilni tanlang:", reply_markup=kb)
        await state.set_state(Registration.lang)
        logger.info(f"User {message.from_user.id} started registration.")

    @dp.callback_query(Registration.lang, F.data.startswith("lang_"))
    async def set_language(callback: CallbackQuery, state: FSMContext):
        """Set the user's language preference."""
        lang = callback.data.replace("lang_", "")
        await state.update_data(lang=lang)
        yes_text, no_text = TRANSLATIONS[lang]["yes"], TRANSLATIONS[lang]["no"]
        buttons = [
            (yes_text, "reg_yes"),
            (no_text, "reg_no"),
            ("❌ Bekor qilish", "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await callback.message.answer(TRANSLATIONS[lang]["register_prompt"], reply_markup=kb)
        await state.set_state(Registration.confirm)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} selected language: {lang}")

    @dp.callback_query(Registration.confirm)
    async def confirm_registration(callback: CallbackQuery, state: FSMContext):
        """Confirm whether the user wants to proceed with registration."""
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if callback.data == "reg_no":
            await callback.message.answer(TRANSLATIONS[lang]["registration_canceled"])
            await state.clear()
            await callback.answer()
            logger.info(f"User {callback.from_user.id} canceled registration.")
            return

        buttons = [("❌ Bekor qilish", "cancel")]
        kb = create_inline_keyboard(buttons)
        await callback.message.answer(TRANSLATIONS[lang]["enter_first_name"], reply_markup=kb)
        await state.set_state(Registration.first_name)
        await callback.answer()

    @dp.message(Registration.first_name)
    async def get_first_name(message: Message, state: FSMContext):
        """Get and validate the user's first name."""
        first_name = sanitize_input(message.text)
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if not first_name or len(first_name) < 2 or not first_name.isalpha():
            await message.answer("Iltimos, to‘g‘ri ism kiriting (faqat harflar, kamida 2 ta).")
            return

        await state.update_data(first_name=first_name)
        buttons = [("❌ Bekor qilish", "cancel")]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS[lang]["enter_last_name"], reply_markup=kb)
        await state.set_state(Registration.last_name)
        logger.info(f"User {message.from_user.id} entered first name: {first_name}")

    @dp.message(Registration.last_name)
    async def get_last_name(message: Message, state: FSMContext):
        """Get and validate the user's last name."""
        last_name = sanitize_input(message.text)
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if not last_name or len(last_name) < 2 or not last_name.isalpha():
            await message.answer("Iltimos, to‘g‘ri familiya kiriting (faqat harflar, kamida 2 ta).")
            return

        await state.update_data(last_name=last_name)
        buttons = [("❌ Bekor qilish", "cancel")]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS[lang]["enter_age"], reply_markup=kb)
        await state.set_state(Registration.age)
        logger.info(f"User {message.from_user.id} entered last name: {last_name}")

    @dp.message(Registration.age)
    async def get_age(message: Message, state: FSMContext):
        """Get and validate the user's age."""
        age_text = message.text.strip()
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if not age_text.isdigit() or not (1 <= int(age_text) <= 150):
            await message.answer(TRANSLATIONS[lang]["invalid_age"])
            return

        await state.update_data(age=int(age_text))
        buttons = [
            ("Erkak ♂" if lang == "uz" else "Мужской ♂", "gender_erkak"),
            ("Ayol ♀" if lang == "uz" else "Женский ♀", "gender_ayol"),
            ("❌ Bekor qilish", "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS[lang]["choose_gender"], reply_markup=kb)
        await state.set_state(Registration.gender)
        logger.info(f"User {message.from_user.id} entered age: {age_text}")

    @dp.callback_query(Registration.gender, F.data.startswith("gender_"))
    async def choose_gender(callback: CallbackQuery, state: FSMContext):
        """Set the user's gender."""
        gender = callback.data.replace("gender_", "")
        await state.update_data(gender=gender)
        data = await state.get_data()
        lang = data.get("lang", "uz")

        phone_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(
                text="📞 Telefon raqamni yuborish" if lang == "uz" else "📞 Отправить номер телефона",
                request_contact=True
            )]],
            resize_keyboard=True
        )
        buttons = [("❌ Bekor qilish", "cancel")]
        inline_kb = create_inline_keyboard(buttons)
        await callback.message.answer(
            TRANSLATIONS[lang]["enter_phone"],
            reply_markup=phone_kb
        )
        await callback.message.answer("Yoki raqamni yozing:", reply_markup=inline_kb)
        await state.set_state(Registration.phone)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} selected gender: {gender}")

    @dp.message(Registration.phone, F.content_type.in_([ContentType.CONTACT, ContentType.TEXT]))
    async def get_phone(message: Message, state: FSMContext):
        """Get and validate the user's phone number."""
        # 1️⃣ Telegram kontakt yoki yozilgan textdan raqam olish
        if message.content_type == ContentType.CONTACT and message.contact:
            phone_number = message.contact.phone_number
        else:
            phone_number = message.text.strip()

        # 2️⃣ Raqamni +998 formatiga keltirish
        if phone_number.startswith("998") and len(phone_number) == 12:
            phone_number = f"+{phone_number}"
        elif phone_number.startswith("0") and len(phone_number) == 10:
            phone_number = f"+998{phone_number[1:]}"
        
        # 3️⃣ Tilni olish
        data = await state.get_data()
        lang = data.get("lang", "uz")

        # 4️⃣ Tekshirish — faqat O‘zbek raqamlari
        phone_pattern = r"^\+998\d{9}$"
        if not re.match(phone_pattern, phone_number):
            await message.answer(TRANSLATIONS[lang]["invalid_phone"])
            return

        # 5️⃣ State’ga saqlash
        await state.update_data(phone=phone_number)

        # 6️⃣ Kurslar ro‘yxatini chiqarish
        courses = list_courses()
        buttons = [(course[1], f"course_{course[0]}") for course in courses]
        buttons.append(("❌ Bekor qilish", "cancel"))

        kb = create_inline_keyboard(buttons, row_width=1)
        await message.answer(TRANSLATIONS[lang]["choose_course"], reply_markup=kb)

        await state.set_state(Registration.quran_course)
        logger.info(f"User {message.from_user.id} entered phone: {phone_number}")

    @dp.callback_query(Registration.quran_course, F.data.startswith("course_"))
    async def choose_course(callback: CallbackQuery, state: FSMContext):
        """Set the user's selected course."""
        course_id = callback.data.replace("course_", "")
        await state.update_data(quran_course=course_id)
        data = await state.get_data()
        lang = data.get("lang", "uz")

        course_name = next((c[1] for c in list_courses() if c[0] == int(course_id)), course_id)
        confirm_text = TRANSLATIONS[lang]["confirm_data"].format(
            first_name=data["first_name"],
            last_name=data["last_name"],
            age=data["age"],
            gender="Erkak" if data["gender"] == "erkak" else "Ayol" if lang == "uz" else
                   "Мужской" if data["gender"] == "erkak" else "Женский",
            phone=data["phone"],
            course=course_name
        )
        buttons = [
            (TRANSLATIONS[lang]["yes"], "confirm_yes"),
            (TRANSLATIONS[lang]["no"], "confirm_no"),
            ("❌ Bekor qilish", "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await callback.message.answer(confirm_text, reply_markup=kb, parse_mode="Markdown")
        await state.set_state(Registration.final_confirm)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} selected course: {course_id}")

    @dp.callback_query(Registration.final_confirm, F.data.startswith("confirm_"))
    async def final_confirmation(callback: CallbackQuery, state: FSMContext):
        """Finalize registration and save user data."""
        choice = callback.data.replace("confirm_", "")
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if choice == "no":
            await callback.message.answer(TRANSLATIONS[lang]["registration_canceled"])
            await state.clear()
            await callback.answer()
            logger.info(f"User {callback.from_user.id} canceled registration.")
            return

        try:
            data["tg_id"] = callback.from_user.id
            save_user(data)
            buttons = [("💳 To‘lov qilish", "pay_now"), ("❌ Bekor qilish", "cancel")]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(
                TRANSLATIONS[lang]["registration_completed"],
                reply_markup=kb
            )
            await state.clear()
            await callback.answer()
            logger.info(f"User {callback.from_user.id} completed registration.")
        except Exception as e:
            await callback.message.answer(
                f"Xato yuz berdi: {str(e)}" if lang == "uz" else f"Произошла ошибка: {str(e)}"
            )
            await callback.answer(show_alert=True)
            logger.error(f"Error saving user {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "view_profile")
    async def view_profile(callback: CallbackQuery):
        """Display the user's profile."""
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer("❌ Foydalanuvchi topilmadi.")
            await callback.answer()
            return

        course_id = user[6]
        course_name = next((c[1] for c in list_courses() if c[0] == course_id), course_id)
        text = (
            f"📋 *Ma’lumotlaringiz:*\n"
            f"**Ism:** {user[2]}\n"
            f"**Familiya:** {user[3]}\n"
            f"**Yosh:** {user[4]}\n"
            f"**Jins:** {'Erkak' if user[5] == 'erkak' else 'Ayol'}\n"
            f"**Telefon:** {user[6]}\n"
            f"**Kurs:** {course_name}"
        )
        buttons = [
            ("✏️ Tahrirlash", "edit_profile"),
            ("💳 To‘lov qilish", "pay_now"),
            ("❌ Bekor qilish", "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        logger.info(f"User {callback.from_user.id} viewed profile.")

    @dp.callback_query(F.data == "edit_profile")
    async def start_edit(callback: CallbackQuery, state: FSMContext):
        """Start the profile editing process."""
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer("❌ Foydalanuvchi topilmadi.")
            await callback.answer()
            return

        await state.update_data(user_id=user[0], lang="uz")  # Default to uz, or store lang in DB
        buttons = [
            ("Ism", "edit_first_name"),
            ("Familiya", "edit_last_name"),
            ("Yosh", "edit_age"),
            ("Jins", "edit_gender"),
            ("Telefon", "edit_phone"),
            ("Kurs", "edit_course"),
            ("❌ Bekor qilish", "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await callback.message.answer("Qaysi maydonni tahrirlamoqchisiz?", reply_markup=kb)
        await state.set_state(EditProfile.field)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} started editing profile.")

    @dp.callback_query(EditProfile.field, F.data.startswith("edit_"))
    async def choose_field(callback: CallbackQuery, state: FSMContext):
        """Select the field to edit."""
        field = callback.data.replace("edit_", "")
        await state.update_data(field=field)
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if field == "gender":
            buttons = [
                ("Erkak ♂" if lang == "uz" else "Мужской ♂", "gender_erkak"),
                ("Ayol ♀" if lang == "uz" else "Женский ♀", "gender_ayol"),
                ("❌ Bekor qilish", "cancel")
            ]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(TRANSLATIONS[lang]["choose_gender"], reply_markup=kb)
            await state.set_state(EditProfile.new_value)
        elif field == "course":
            courses = list_courses()
            buttons = [(name, f"course_{id}") for id, name in courses] + [("❌ Bekor qilish", "cancel")]
            kb = create_inline_keyboard(buttons, row_width=1)
            await callback.message.answer(TRANSLATIONS[lang]["choose_course"], reply_markup=kb)
            await state.set_state(EditProfile.new_value)
        else:
            buttons = [("❌ Bekor qilish", "cancel")]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(
                TRANSLATIONS[lang].get(f"enter_{field}", "Yangi qiymatni kiriting:"),
                reply_markup=kb
            )
            await state.set_state(EditProfile.new_value)
        await callback.answer()

    @dp.message(EditProfile.new_value)
    async def update_field(message: Message, state: FSMContext):
        """Update the selected field with the new value."""
        data = await state.get_data()
        lang = data.get("lang", "uz")
        field = data["field"]
        user_id = data["user_id"]
        new_value = message.text.strip()

        # Validation
        if field == "first_name" or field == "last_name":
            new_value = sanitize_input(new_value)
            if not new_value or len(new_value) < 2 or not new_value.isalpha():
                await message.answer(f"Iltimos, to‘g‘ri {field} kiriting (faqat harflar, kamida 2 ta).")
                return
        elif field == "age":
            if not new_value.isdigit() or not (1 <= int(new_value) <= 150):
                await message.answer(TRANSLATIONS[lang]["invalid_age"])
                return
            new_value = int(new_value)
        elif field == "phone":
            phone_pattern = r"^\+998\d{9}$"
            if not re.match(phone_pattern, new_value):
                await message.answer(TRANSLATIONS[lang]["invalid_phone"])
                return
        elif field in ("gender", "course"):
            await message.answer("Iltimos, tugmalardan birini tanlang.")
            return

        try:
            update_user_field(user_id, field, new_value)
            buttons = [("💳 To‘lov qilish", "pay_now"), ("❌ Bekor qilish", "cancel")]
            kb = create_inline_keyboard(buttons)
            await message.answer("✅ Maydon yangilandi.", reply_markup=kb)
            await state.clear()
            logger.info(f"User {message.from_user.id} updated {field} to {new_value}.")
        except Exception as e:
            await message.answer(f"Xato yuz berdi: {str(e)}")
            logger.error(f"Error updating {field} for user {message.from_user.id}: {str(e)}")

    @dp.callback_query(EditProfile.new_value, F.data.startswith(("gender_", "course_")))
    async def update_choice_field(callback: CallbackQuery, state: FSMContext):
        """Update gender or course field based on callback."""
        data = await state.get_data()
        lang = data.get("lang", "uz")
        field = data["field"]
        user_id = data["user_id"]
        new_value = callback.data.replace(f"{field}_", "")

        try:
            update_user_field(user_id, field, new_value)
            buttons = [("💳 To‘lov qilish", "pay_now"), ("❌ Bekor qilish", "cancel")]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer("✅ Maydon yangilandi.", reply_markup=kb)
            await state.clear()
            await callback.answer()
            logger.info(f"User {callback.from_user.id} updated {field} to {new_value}.")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}")
            await callback.answer(show_alert=True)
            logger.error(f"Error updating {field} for user {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "cancel")
    async def cancel_action(callback: CallbackQuery, state: FSMContext):
        """Cancel any ongoing action."""
        data = await state.get_data()
        lang = data.get("lang", "uz")
        await callback.message.answer(TRANSLATIONS[lang]["registration_canceled"])
        await state.clear()
        await callback.answer()
        logger.info(f"User {callback.from_user.id} canceled action.")