import json
import logging
import re
import bleach
from datetime import datetime
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
    data_confirm = State()
    quran_course = State()

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
            course_id = user[8]  # course_id is in index 8
            is_paid = user[10]  # is_paid is in index 10
            lang = user[2] if user[2] else "uz"  # lang is in index 2
            course_display = next((c[1] for c in list_courses() if c[0] == course_id), "Kurs tanlanmagan")
            buttons = [
                (TRANSLATIONS[lang]["view_profile"], "view_profile"),
                (TRANSLATIONS[lang]["edit_profile"], "edit_profile")
            ]
            if not course_id or not is_paid:
                buttons.append((TRANSLATIONS[lang]["choose_course"], "choose_course"))
            if course_id and not is_paid:
                buttons.append((f"{TRANSLATIONS[lang]['pay_now']} ({course_display})", f"pay_now:{course_id}"))
            buttons.append((TRANSLATIONS[lang]["cancel"], "cancel"))
            kb = create_inline_keyboard(buttons)
            await message.answer(
                TRANSLATIONS[lang]["profile_summary"].format(
                    first_name=user[3],
                    last_name=user[4],
                    course=course_display,
                    payment_status=TRANSLATIONS[lang]["paid"] if is_paid else TRANSLATIONS[lang]["not_paid"]
                ),
                reply_markup=kb, parse_mode="Markdown"
            )
            logger.info(f"User {message.from_user.id} accessed profile.")
            return

        buttons = [
            ("🇺🇿 O‘zbek", "lang_uz"),
            ("🇷🇺 Русский", "lang_ru"),
            (TRANSLATIONS["uz"]["cancel"], "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS["uz"]["choose_language"], reply_markup=kb)
        await state.set_state(Registration.lang)
        logger.info(f"User {message.from_user.id} started registration.")

    @dp.callback_query(Registration.lang, F.data.startswith("lang_"))
    async def set_language(callback: CallbackQuery, state: FSMContext):
        """Set the user's language preference."""
        lang = callback.data.replace("lang_", "")
        await state.update_data(lang=lang)
        buttons = [
            (TRANSLATIONS[lang]["yes"], "reg_yes"),
            (TRANSLATIONS[lang]["no"], "reg_no"),
            (TRANSLATIONS[lang]["cancel"], "cancel")
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

        buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
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
            await message.answer(TRANSLATIONS[lang]["invalid_first_name"])
            return

        await state.update_data(first_name=first_name)
        buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
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
            await message.answer(TRANSLATIONS[lang]["invalid_last_name"])
            return

        await state.update_data(last_name=last_name)
        buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
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

        if not age_text.isdigit() or not (18 <= int(age_text) <= 150):
            await message.answer(TRANSLATIONS[lang]["invalid_age"])
            return

        await state.update_data(age=int(age_text))
        buttons = [
            (TRANSLATIONS[lang]["gender_male"], "gender_erkak"),
            (TRANSLATIONS[lang]["gender_female"], "gender_ayol"),
            (TRANSLATIONS[lang]["cancel"], "cancel")
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
                text=TRANSLATIONS[lang]["share_phone"],
                request_contact=True
            )]],
            resize_keyboard=True
        )
        buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
        inline_kb = create_inline_keyboard(buttons)
        await callback.message.answer(
            TRANSLATIONS[lang]["enter_phone"],
            reply_markup=phone_kb
        )
        await callback.message.answer(TRANSLATIONS[lang]["or_type_phone"], reply_markup=inline_kb)
        await state.set_state(Registration.phone)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} selected gender: {gender}")

    @dp.message(Registration.phone, F.content_type.in_([ContentType.CONTACT, ContentType.TEXT]))
    async def get_phone(message: Message, state: FSMContext):
        """Get and validate the user's phone number, then ask for data confirmation."""
        if message.content_type == ContentType.CONTACT and message.contact:
            phone_number = message.contact.phone_number
        else:
            phone_number = message.text.strip()

        if phone_number.startswith("998") and len(phone_number) == 12:
            phone_number = f"+{phone_number}"
        elif phone_number.startswith("0") and len(phone_number) == 10:
            phone_number = f"+998{phone_number[1:]}"
        
        data = await state.get_data()
        lang = data.get("lang", "uz")

        phone_pattern = r"^\+998\d{9}$"
        if not re.match(phone_pattern, phone_number):
            await message.answer(TRANSLATIONS[lang]["invalid_phone"])
            return

        await state.update_data(phone=phone_number)

        confirm_text = TRANSLATIONS[lang]["confirm_data"].format(
            first_name=data["first_name"],
            last_name=data["last_name"],
            age=data["age"],
            gender=TRANSLATIONS[lang]["gender_male"] if data["gender"] == "erkak" else TRANSLATIONS[lang]["gender_female"],
            phone=phone_number,
            course=""
        )
        buttons = [
            (TRANSLATIONS[lang]["yes"], "data_yes"),
            (TRANSLATIONS[lang]["no"], "data_no"),
            (TRANSLATIONS[lang]["cancel"], "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await message.answer(
            f"{confirm_text}\n\n{TRANSLATIONS[lang]['confirm_prompt']}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await state.set_state(Registration.data_confirm)
        logger.info(f"User {message.from_user.id} entered phone: {phone_number}")

    @dp.callback_query(Registration.data_confirm, F.data.startswith("data_"))
    async def confirm_data(callback: CallbackQuery, state: FSMContext):
        """Handle data confirmation and save user to database."""
        choice = callback.data.replace("data_", "")
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if choice == "no":
            buttons = [
                ("🇺🇿 O‘zbek", "lang_uz"),
                ("🇷🇺 Русский", "lang_ru"),
                (TRANSLATIONS[lang]["cancel"], "cancel")
            ]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(TRANSLATIONS[lang]["restart_registration"], reply_markup=kb)
            await state.set_state(Registration.lang)
            await callback.answer()
            logger.info(f"User {callback.from_user.id} chose to restart registration.")
            return

        try:
            # Save user to database without course
            user_data = {
                "tg_id": callback.from_user.id,
                "lang": data.get("lang"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "age": data.get("age"),
                "gender": data.get("gender"),
                "phone": data.get("phone"),
                "course_id": None,
                "registered_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "is_paid": 0,
                "paid_at": None
            }
            save_user(user_data)
            logger.info(f"User {callback.from_user.id} saved to database without course.")
        except Exception as e:
            await callback.message.answer(
                TRANSLATIONS[lang]["error"].format(error=str(e))
            )
            await callback.answer(show_alert=True)
            logger.error(f"Error saving user {callback.from_user.id}: {str(e)}")
            return

        user_gender = data.get("gender", "hammasi")
        courses = [
            course for course in list_courses()
            if course[3] == "hammasi" or course[3] == user_gender
        ]
        if not courses:
            await callback.message.answer(TRANSLATIONS[lang]["no_courses_available"])
            await state.clear()
            await callback.answer()
            logger.info(f"No courses available for user {callback.from_user.id} with gender {user_gender}.")
            return

        course_text = TRANSLATIONS[lang]["choose_course"] + "\n\n"
        buttons = []
        for course in courses:
            course_id, name, description, gender, start_date, limit_count, seats_available, price = course
            course_text += (
                f"📚 *{name}*\n"
                f"{TRANSLATIONS[lang]['course_description']}: {description}\n"
                f"{TRANSLATIONS[lang]['course_gender']}: {TRANSLATIONS[lang]['gender_all'] if gender == 'hammasi' else TRANSLATIONS[lang]['gender_male'] if gender == 'erkak' else TRANSLATIONS[lang]['gender_female']}\n"
                f"{TRANSLATIONS[lang]['start_date']}: {start_date}\n"
                f"{TRANSLATIONS[lang]['seats_available']}: {seats_available}/{limit_count}\n"
                f"{TRANSLATIONS[lang]['price']}: {price} UZS\n\n"
            )
            buttons.append((name, f"course_{course_id}"))

        buttons.append((TRANSLATIONS[lang]["cancel"], "cancel"))
        kb = create_inline_keyboard(buttons, row_width=1)
        await callback.message.answer(course_text, reply_markup=kb, parse_mode="Markdown")
        await state.set_state(Registration.quran_course)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} proceeded to course selection.")

    @dp.callback_query(F.data == "choose_course")
    async def choose_course_prompt(callback: CallbackQuery, state: FSMContext):
        """Prompt user to select a course."""
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        lang = user[2] if user[2] else "uz"
        user_gender = user[6]  # gender is in index 6
        courses = [
            course for course in list_courses()
            if course[3] == "hammasi" or course[3] == user_gender
        ]
        if not courses:
            await callback.message.answer(TRANSLATIONS[lang]["no_courses_available"])
            await callback.answer()
            logger.info(f"No courses available for user {callback.from_user.id} with gender {user_gender}.")
            return

        course_text = TRANSLATIONS[lang]["choose_course"] + "\n\n"
        buttons = []
        for course in courses:
            course_id, name, description, gender, start_date, limit_count, seats_available, price = course
            course_text += (
                f"📚 *{name}*\n"
                f"{TRANSLATIONS[lang]['course_description']}: {description}\n"
                f"{TRANSLATIONS[lang]['course_gender']}: {TRANSLATIONS[lang]['gender_all'] if gender == 'hammasi' else TRANSLATIONS[lang]['gender_male'] if gender == 'erkak' else TRANSLATIONS[lang]['gender_female']}\n"
                f"{TRANSLATIONS[lang]['start_date']}: {start_date}\n"
                f"{TRANSLATIONS[lang]['seats_available']}: {seats_available}/{limit_count}\n"
                f"{TRANSLATIONS[lang]['price']}: {price} UZS\n\n"
            )
            buttons.append((name, f"course_{course_id}"))

        buttons.append((TRANSLATIONS[lang]["cancel"], "cancel"))
        kb = create_inline_keyboard(buttons, row_width=1)
        await callback.message.answer(course_text, reply_markup=kb, parse_mode="Markdown")
        await state.set_state(Registration.quran_course)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} prompted to choose course.")

    @dp.callback_query(Registration.quran_course, F.data.startswith("course_"))
    async def choose_course(callback: CallbackQuery, state: FSMContext):
        """Set the user's selected course."""
        course_id = callback.data.replace("course_", "")
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        lang = user[2] if user[2] else "uz"
        try:
            update_user_field(callback.from_user.id, "course_id", int(course_id))
            course_name = next((c[1] for c in list_courses() if c[0] == int(course_id)), course_id)
            buttons = [
                (f"{TRANSLATIONS[lang]['pay_now']} ({course_name})", f"pay_now:{course_id}"),
                (TRANSLATIONS[lang]["cancel"], "cancel")
            ]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(
                TRANSLATIONS[lang]["course_selected"].format(course=course_name),
                reply_markup=kb,
                parse_mode="Markdown"
            )
            await state.clear()
            await callback.answer()
            logger.info(f"User {callback.from_user.id} selected course: {course_id}")
        except Exception as e:
            await callback.message.answer(
                TRANSLATIONS[lang]["error"].format(error=str(e))
            )
            await callback.answer(show_alert=True)
            logger.error(f"Error updating course for user {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data.startswith("pay_now:"))
    async def handle_payment(callback: CallbackQuery, state: FSMContext):
        """Handle payment action for selected course."""
        course_id = callback.data.replace("pay_now:", "")
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        lang = user[2] if user[2] else "uz"
        course_name = next((c[1] for c in list_courses() if str(c[0]) == course_id), course_id)
        await callback.message.answer(
            TRANSLATIONS[lang]["payment_prompt"].format(course=course_name),
            parse_mode="Markdown"
        )
        await callback.answer()
        logger.info(f"User {callback.from_user.id} initiated payment for course: {course_id}")

    @dp.callback_query(F.data == "view_profile")
    async def view_profile(callback: CallbackQuery):
        """Display the user's profile."""
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        course_id = user[8]  # course_id is in index 8
        is_paid = user[10]  # is_paid is in index 10
        lang = user[2] if user[2] else "uz"
        course_name = next((c[1] for c in list_courses() if c[0] == course_id), TRANSLATIONS[lang]["no_course"])
        text = (
            f"📋 *{TRANSLATIONS[lang]['profile_info']}:*\n"
            f"**{TRANSLATIONS[lang]['first_name']}:** {user[3]}\n"
            f"**{TRANSLATIONS[lang]['last_name']}:** {user[4]}\n"
            f"**{TRANSLATIONS[lang]['age']}:** {user[5]}\n"
            f"**{TRANSLATIONS[lang]['gender']}:** {TRANSLATIONS[lang]['gender_male'] if user[6] == 'erkak' else TRANSLATIONS[lang]['gender_female']}\n"
            f"**{TRANSLATIONS[lang]['phone']}:** {user[7]}\n"
            f"**{TRANSLATIONS[lang]['course']}:** {course_name}\n"
            f"**{TRANSLATIONS[lang]['payment_status']}:** {TRANSLATIONS[lang]['paid'] if is_paid else TRANSLATIONS[lang]['not_paid']}"
        )
        buttons = [
            (TRANSLATIONS[lang]["edit_profile"], "edit_profile"),
        ]
        if not course_id or not is_paid:
            buttons.append((TRANSLATIONS[lang]["choose_course"], "choose_course"))
        if course_id and not is_paid:
            buttons.append((f"{TRANSLATIONS[lang]['pay_now']} ({course_name})", f"pay_now:{course_id}"))
        buttons.append((TRANSLATIONS[lang]["cancel"], "cancel"))
        kb = create_inline_keyboard(buttons)
        await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        logger.info(f"User {callback.from_user.id} viewed profile.")

    @dp.callback_query(F.data == "edit_profile")
    async def start_edit(callback: CallbackQuery, state: FSMContext):
        """Start the profile editing process."""
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        lang = user[2] if user[2] else "uz"
        await state.update_data(user_id=user[0], lang=lang)
        buttons = [
            (TRANSLATIONS[lang]["first_name"], "edit_first_name"),
            (TRANSLATIONS[lang]["last_name"], "edit_last_name"),
            (TRANSLATIONS[lang]["age"], "edit_age"),
            (TRANSLATIONS[lang]["gender"], "edit_gender"),
            (TRANSLATIONS[lang]["phone"], "edit_phone"),
            (TRANSLATIONS[lang]["course"], "edit_course"),
            (TRANSLATIONS[lang]["cancel"], "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await callback.message.answer(TRANSLATIONS[lang]["choose_field"], reply_markup=kb)
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
                (TRANSLATIONS[lang]["gender_male"], "gender_erkak"),
                (TRANSLATIONS[lang]["gender_female"], "gender_ayol"),
                (TRANSLATIONS[lang]["cancel"], "cancel")
            ]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(TRANSLATIONS[lang]["choose_gender"], reply_markup=kb)
            await state.set_state(EditProfile.new_value)
        elif field == "course":
            user = get_user_by_tg(callback.from_user.id)
            user_gender = user[6] if user else "hammasi"
            courses = [
                course for course in list_courses()
                if course[3] == "hammasi" or course[3] == user_gender
            ]
            buttons = [(name, f"course_{id}") for id, name, *_ in courses] + [(TRANSLATIONS[lang]["cancel"], "cancel")]
            kb = create_inline_keyboard(buttons, row_width=1)
            await callback.message.answer(TRANSLATIONS[lang]["choose_course"], reply_markup=kb)
            await state.set_state(EditProfile.new_value)
        else:
            buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(
                TRANSLATIONS[lang].get(f"enter_{field}", TRANSLATIONS[lang]["enter_new_value"]),
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

        if field == "first_name" or field == "last_name":
            new_value = sanitize_input(new_value)
            if not new_value or len(new_value) < 2 or not new_value.isalpha():
                await message.answer(TRANSLATIONS[lang][f"invalid_{field}"])
                return
        elif field == "age":
            if not new_value.isdigit() or not (18 <= int(new_value) <= 150):
                await message.answer(TRANSLATIONS[lang]["invalid_age"])
                return
            new_value = int(new_value)
        elif field == "phone":
            phone_pattern = r"^\+998\d{9}$"
            if not re.match(phone_pattern, new_value):
                await message.answer(TRANSLATIONS[lang]["invalid_phone"])
                return
        elif field in ("gender", "course"):
            await message.answer(TRANSLATIONS[lang]["use_buttons"])
            return

        try:
            update_user_field(user_id, field, new_value)
            user = get_user_by_tg(user_id)
            course_id = user[8]
            is_paid = user[10]
            course_name = next((c[1] for c in list_courses() if c[0] == course_id), TRANSLATIONS[lang]["no_course"])
            buttons = [
                (TRANSLATIONS[lang]["choose_course"], "choose_course") if not course_id or not is_paid else None,
                (f"{TRANSLATIONS[lang]['pay_now']} ({course_name})", f"pay_now:{course_id}") if course_id and not is_paid else None,
                (TRANSLATIONS[lang]["cancel"], "cancel")
            ]
            buttons = [b for b in buttons if b]
            kb = create_inline_keyboard(buttons)
            await message.answer(TRANSLATIONS[lang]["field_updated"], reply_markup=kb)
            await state.clear()
            logger.info(f"User {message.from_user.id} updated {field} to {new_value}.")
        except Exception as e:
            await message.answer(TRANSLATIONS[lang]["error"].format(error=str(e)))
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
            update_user_field(user_id, field if field != "course" else "course_id", new_value)
            user = get_user_by_tg(user_id)
            course_id = user[8]
            is_paid = user[10]
            course_name = next((c[1] for c in list_courses() if c[0] == course_id), TRANSLATIONS[lang]["no_course"])
            buttons = [
                (TRANSLATIONS[lang]["choose_course"], "choose_course") if not course_id or not is_paid else None,
                (f"{TRANSLATIONS[lang]['pay_now']} ({course_name})", f"pay_now:{course_id}") if course_id and not is_paid else None,
                (TRANSLATIONS[lang]["cancel"], "cancel")
            ]
            buttons = [b for b in buttons if b]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(TRANSLATIONS[lang]["field_updated"], reply_markup=kb)
            await state.clear()
            await callback.answer()
            logger.info(f"User {callback.from_user.id} updated {field} to {new_value}.")
        except Exception as e:
            await callback.message.answer(TRANSLATIONS[lang]["error"].format(error=str(e)))
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