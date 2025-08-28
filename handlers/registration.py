# registration.py
import json
import logging
import re
import bleach
from datetime import datetime
from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ContentType
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from database import save_user, get_user_by_tg, update_user_field, list_courses
from config import BOT_TOKEN  # config.py dan BOT_TOKEN import qilindi
from aiogram import types
# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize bot
bot = Bot(token=BOT_TOKEN)

# Load translations
with open("translations.json", "r", encoding="utf-8") as f:
    TRANSLATIONS = json.load(f)

# Group IDs
REG_GROUP_ID = -1002905557734  # Foydalanuvchi ma'lumotlari uchun guruh
PAY_GROUP_ID = -1002397524134  # To'lovlar uchun guruh (payment.py da ishlatiladi)

class Registration(StatesGroup):
    lang = State()
    confirm = State()
    first_name = State()
    last_name = State()
    birth_date = State()
    gender = State()
    phone = State()
    address = State()
    passport_front = State()
    passport_back = State()
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

async def send_or_edit_reg_to_group(user: dict, course_name: str, edit_message_id: int = None):
    """Send or edit user registration data to the group with photos."""

    lang = user.get("lang", "uz")

    text = (
        f"📋 *Foydalanuvchi ma'lumotlari:*\n"
        f"**Ism:** {user.get('first_name','')}\n"
        f"**Familiya:** {user.get('last_name','')}\n"
        f"**Tug'ilgan sana:** {user.get('birth_date','')}\n"
        f"**Jins:** {TRANSLATIONS[lang]['gender_male'] if user.get('gender') == 'erkak' else TRANSLATIONS[lang]['gender_female']}\n"
        f"**Telefon:** {user.get('phone','')}\n"
        f"**Manzil:** {user.get('address','')}\n"
        f"**Kurs:** {course_name}\n"
        f"**TG ID:** {user.get('tg_id','')}\n"
        f"**Registratsiya vaqti:** {user.get('registered_at','')}\n"
        f"**To'lov holati:** {TRANSLATIONS[lang]['paid'] if user.get('is_paid') else TRANSLATIONS[lang]['not_paid']}"
    )

    try:
        passport_front = user.get("passport_front")
        passport_back = user.get("passport_back")

        # Agar rasm bo'lsa
        if passport_front or passport_back:
            media = []
            if passport_front:
                media.append(types.InputMediaPhoto(media=passport_front, caption=text, parse_mode="Markdown"))
            if passport_back:
                # caption faqat birinchi rasmga qo'yiladi
                media.append(types.InputMediaPhoto(media=passport_back))

            # Edit qilinmaydi, faqat yangi yuboriladi
            msgs = await bot.send_media_group(chat_id=REG_GROUP_ID, media=media)
            logger.info(f"Sent media group for user {user.get('tg_id')}")
            return msgs[0].message_id  # birinchi xabar ID qaytariladi

        else:
            # faqat matn yuboriladi
            if edit_message_id:
                await bot.edit_message_text(
                    text=text,
                    chat_id=REG_GROUP_ID,
                    message_id=edit_message_id,
                    parse_mode="Markdown"
                )
                logger.info(f"Updated group message {edit_message_id} for user {user.get('tg_id')}")
            else:
                message = await bot.send_message(
                    chat_id=REG_GROUP_ID,
                    text=text,
                    parse_mode="Markdown"
                )
                logger.info(f"Sent new group message for user {user.get('tg_id')}")
                return message.message_id

    except Exception as e:
        logger.error(f"Error sending/editing message to group for user {user.get('tg_id')}: {str(e)}")
        raise

def register_handlers(dp):
    @dp.message(Command("start"))
    async def start_registration(message: Message, state: FSMContext):
        user = get_user_by_tg(message.from_user.id)
        if user:
            course_id = user['course_id']
            is_paid = user['is_paid']
            lang = user['lang'] if user['lang'] else "uz"
            course_display = next((c['name'] for c in list_courses() if c['id'] == course_id), "Kurs tanlanmagan")
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
                    first_name=user['first_name'],
                    last_name=user['last_name'],
                    course=course_display,
                    payment_status=TRANSLATIONS[lang]["paid"] if is_paid else TRANSLATIONS[lang]["not_paid"]
                ),
                reply_markup=kb, parse_mode="Markdown"
            )
            logger.info(f"User {message.from_user.id} accessed profile.")
            return

        buttons = [
            ("🇺🇿 O‘zbek", "lang_uz"),
            ("🇷🇺 Кирилча", "lang_ru"),
            (TRANSLATIONS["uz"]["cancel"], "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS["uz"]["choose_language"], reply_markup=kb)
        await state.set_state(Registration.lang)
        logger.info(f"User {message.from_user.id} started registration.")

    @dp.callback_query(Registration.lang, F.data.startswith("lang_"))
    async def set_language(callback: CallbackQuery, state: FSMContext):
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
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if callback.data == "reg_no":
            await callback.message.answer(TRANSLATIONS[lang]["registration_canceled"])
            await state.clear()
            await callback.answer()
            logger.info(f"User {callback.from_user.id} canceled registration.")
            return
        elif callback.data == "reg_yes":
            buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(TRANSLATIONS[lang]["enter_first_name"], reply_markup=kb)
            await state.set_state(Registration.first_name)
            await callback.answer()

    @dp.message(Registration.first_name)
    async def get_first_name(message: Message, state: FSMContext):
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
        last_name = sanitize_input(message.text)
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if not last_name or len(last_name) < 2 or not last_name.isalpha():
            await message.answer(TRANSLATIONS[lang]["invalid_last_name"])
            return

        await state.update_data(last_name=last_name)
        buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS[lang]["enter_birth_date"], reply_markup=kb)
        await state.set_state(Registration.birth_date)
        logger.info(f"User {message.from_user.id} entered last name: {last_name}")

    @dp.message(Registration.birth_date)
    async def get_birth_date(message: Message, state: FSMContext):
        birth_date_text = message.text.strip()
        data = await state.get_data()
        lang = data.get("lang", "uz")

        try:
            birth_date = datetime.strptime(birth_date_text, "%Y-%m-%d")
            today = datetime.now()

            if birth_date > today:
                raise ValueError("Future date")

            # 18 yoshdan kichiklarni tekshirish
            age = (today - birth_date).days // 365
            if age < 18:
                await message.answer("❌ Siz 18 yoshdan kichiksiz. Ro'yxatdan o'tish mumkin emas.")
                return

            await state.update_data(birth_date=birth_date_text)

        except ValueError:
            await message.answer(TRANSLATIONS[lang]["invalid_birth_date"])
            return

        buttons = [
            (TRANSLATIONS[lang]["gender_male"], "gender_erkak"),
            (TRANSLATIONS[lang]["gender_female"], "gender_ayol"),
            (TRANSLATIONS[lang]["cancel"], "cancel")
        ]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS[lang]["choose_gender"], reply_markup=kb)
        await state.set_state(Registration.gender)

        logger.info(f"User {message.from_user.id} entered birth date: {birth_date_text}")

    @dp.callback_query(Registration.gender, F.data.startswith("gender_"))
    async def choose_gender(callback: CallbackQuery, state: FSMContext):
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
        buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS[lang]["enter_address"], reply_markup=kb)
        await state.set_state(Registration.address)
        logger.info(f"User {message.from_user.id} entered phone: {phone_number}")

    @dp.message(Registration.address)
    async def get_address(message: Message, state: FSMContext):
        address = sanitize_input(message.text)
        data = await state.get_data()
        lang = data.get("lang", "uz")

        if not address or len(address) < 5:
            await message.answer(TRANSLATIONS[lang]["invalid_address"])
            return

        await state.update_data(address=address)
        buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS[lang]["upload_passport_front"], reply_markup=kb)
        await state.set_state(Registration.passport_front)
        logger.info(f"User {message.from_user.id} entered address: {address}")

    @dp.message(Registration.passport_front, F.photo)
    async def get_passport_front(message: Message, state: FSMContext):
        photo = message.photo[-1]
        file_id = photo.file_id
        await state.update_data(passport_front=file_id)
        data = await state.get_data()
        lang = data.get("lang", "uz")
        buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
        kb = create_inline_keyboard(buttons)
        await message.answer(TRANSLATIONS[lang]["upload_passport_back"], reply_markup=kb)
        await state.set_state(Registration.passport_back)
        logger.info(f"User {message.from_user.id} uploaded passport front: {file_id}")

    @dp.message(Registration.passport_back, F.photo)
    async def get_passport_back(message: Message, state: FSMContext):
        photo = message.photo[-1]
        file_id = photo.file_id
        await state.update_data(passport_back=file_id)
        data = await state.get_data()
        lang = data.get("lang", "uz")

        confirm_text = TRANSLATIONS[lang]["confirm_data"].format(
            first_name=data["first_name"],
            last_name=data["last_name"],
            birth_date=data["birth_date"],
            gender=TRANSLATIONS[lang]["gender_male"] if data["gender"] == "erkak" else TRANSLATIONS[lang]["gender_female"],
            phone=data["phone"],
            address=data["address"],
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
        logger.info(f"User {message.from_user.id} uploaded passport back: {file_id}")

    @dp.callback_query(Registration.data_confirm, F.data.startswith("data_"))
    async def confirm_data(callback: CallbackQuery, state: FSMContext):
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
            user_data = {
                "tg_id": callback.from_user.id,
                "lang": data.get("lang"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "birth_date": data.get("birth_date"),
                "gender": data.get("gender"),
                "phone": data.get("phone"),
                "address": data.get("address"),
                "passport_front": data.get("passport_front"),
                "passport_back": data.get("passport_back"),
                "course_id": None,
                "registered_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "is_paid": 0,
                "paid_at": None,
                "registration_message_id": None
            }
            save_user(user_data)
            user = get_user_by_tg(callback.from_user.id)
            course_name = "Kurs tanlanmagan"
            message_id = await send_or_edit_reg_to_group(user, course_name)
            update_user_field(callback.from_user.id, "registration_message_id", message_id)
            logger.info(f"User {callback.from_user.id} saved to database and sent to group.")
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
            if (course['gender'] == "hammasi" or course['gender'] == user_gender)
            and course['joylar_soni'] < course['limit_count']
        ]
        if not courses:
            await callback.message.answer(TRANSLATIONS[lang]["no_courses_available"] + "\nKeyinroq /start bilan qayting va kurs tanlang.")
            await state.clear()
            await callback.answer()
            logger.info(f"No courses available for user {callback.from_user.id} with gender {user_gender}.")
            return

        course_text = TRANSLATIONS[lang]["choose_course"] + "\n\n"
        buttons = []
        for course in courses:
            available = course['limit_count'] - course['joylar_soni']
            course_text += (
                f"📚 *{course['name']}*\n"
                f"{TRANSLATIONS[lang]['course_description']}: {course['description']}\n"
                f"{TRANSLATIONS[lang]['course_gender']}: {TRANSLATIONS[lang]['gender_all'] if course['gender'] == 'hammasi' else TRANSLATIONS[lang]['gender_male'] if course['gender'] == 'erkak' else TRANSLATIONS[lang]['gender_female']}\n"
                f"{TRANSLATIONS[lang]['start_date']}: {course['boshlanish_sanasi']}\n"
                f"{TRANSLATIONS[lang]['seats_available']}: {available}/{course['limit_count']}\n"
                f"{TRANSLATIONS[lang]['price']}: {course['narx']} UZS\n\n"
            )
            buttons.append((course['name'], f"course_{course['id']}"))

        buttons.append((TRANSLATIONS[lang]["cancel"], "cancel"))
        kb = create_inline_keyboard(buttons, row_width=1)
        await callback.message.answer(course_text, reply_markup=kb, parse_mode="Markdown")
        await state.set_state(Registration.quran_course)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} proceeded to course selection.")

    @dp.callback_query(F.data == "choose_course")
    async def choose_course_prompt(callback: CallbackQuery, state: FSMContext):
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        lang = user['lang'] if user['lang'] else "uz"
        user_gender = user['gender']
        courses = [
            course for course in list_courses()
            if (course['gender'] == "hammasi" or course['gender'] == user_gender)
            and course['joylar_soni'] < course['limit_count']
        ]
        if not courses:
            await callback.message.answer(TRANSLATIONS[lang]["no_courses_available"])
            await callback.answer()
            logger.info(f"No courses available for user {callback.from_user.id} with gender {user_gender}.")
            return

        course_text = TRANSLATIONS[lang]["choose_course"] + "\n\n"
        buttons = []
        for course in courses:
            available = course['limit_count'] - course['joylar_soni']
            course_text += (
                f"📚 *{course['name']}*\n"
                f"{TRANSLATIONS[lang]['course_description']}: {course['description']}\n"
                f"{TRANSLATIONS[lang]['course_gender']}: {TRANSLATIONS[lang]['gender_all'] if course['gender'] == 'hammasi' else TRANSLATIONS[lang]['gender_male'] if course['gender'] == 'erkak' else TRANSLATIONS[lang]['gender_female']}\n"
                f"{TRANSLATIONS[lang]['start_date']}: {course['boshlanish_sanasi']}\n"
                f"{TRANSLATIONS[lang]['seats_available']}: {course['limit_count']-available}/{course['limit_count']}\n"
                f"{TRANSLATIONS[lang]['price']}: {course['narx']} UZS\n\n"
            )
            buttons.append((course['name'], f"course_{course['id']}"))

        buttons.append((TRANSLATIONS[lang]["cancel"], "cancel"))
        kb = create_inline_keyboard(buttons, row_width=1)
        await callback.message.answer(course_text, reply_markup=kb, parse_mode="Markdown")
        await state.set_state(Registration.quran_course)
        await callback.answer()
        logger.info(f"User {callback.from_user.id} prompted to choose course.")

    @dp.callback_query(Registration.quran_course, F.data.startswith("course_"))
    async def choose_course(callback: CallbackQuery, state: FSMContext):
        course_id = int(callback.data.replace("course_", ""))
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        lang = user['lang'] if user['lang'] else "uz"
        try:
            update_user_field(callback.from_user.id, "course_id", course_id)
            course_name = next((c['name'] for c in list_courses() if c['id'] == course_id), str(course_id))
            user = get_user_by_tg(callback.from_user.id)
            reg_message_id = user['registration_message_id']
            await send_or_edit_reg_to_group(user, course_name, reg_message_id)
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
            logger.info(f"User {callback.from_user.id} selected course: {course_id} and updated group post.")
        except Exception as e:
            await callback.message.answer(
                TRANSLATIONS[lang]["error"].format(error=str(e))
            )
            await callback.answer(show_alert=True)
            logger.error(f"Error updating course for user {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "view_profile")
    async def view_profile(callback: CallbackQuery):
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        course_id = user['course_id']
        is_paid = user['is_paid']
        lang = user['lang'] if user['lang'] else "uz"
        course_name = next((c['name'] for c in list_courses() if c['id'] == course_id), TRANSLATIONS[lang]["no_course"])
        text = (
            f"📋 *{TRANSLATIONS[lang]['profile_info']}:*\n"
            f"**{TRANSLATIONS[lang]['first_name']}:** {user['first_name']}\n"
            f"**{TRANSLATIONS[lang]['last_name']}:** {user['last_name']}\n"
            f"**{TRANSLATIONS[lang]['birth_date']}:** {user['birth_date']}\n"
            f"**{TRANSLATIONS[lang]['gender']}:** {TRANSLATIONS[lang]['gender_male'] if user['gender'] == 'erkak' else TRANSLATIONS[lang]['gender_female']}\n"
            f"**{TRANSLATIONS[lang]['phone']}:** {user['phone']}\n"
            f"**{TRANSLATIONS[lang]['address']}:** {user['address']}\n"
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
        user = get_user_by_tg(callback.from_user.id)
        if not user:
            await callback.message.answer(TRANSLATIONS["uz"]["user_not_found"])
            await callback.answer()
            return

        lang = user['lang'] if user['lang'] else "uz"
        await state.update_data(user_id=user['id'], lang=lang)
        buttons = [
            (TRANSLATIONS[lang]["first_name"], "edit_first_name"),
            (TRANSLATIONS[lang]["last_name"], "edit_last_name"),
            (TRANSLATIONS[lang]["birth_date"], "edit_birth_date"),
            (TRANSLATIONS[lang]["gender"], "edit_gender"),
            (TRANSLATIONS[lang]["phone"], "edit_phone"),
            (TRANSLATIONS[lang]["address"], "edit_address"),
            (TRANSLATIONS[lang]["passport_front"], "edit_passport_front"),
            (TRANSLATIONS[lang]["passport_back"], "edit_passport_back"),
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
            user_gender = user['gender'] if user else "hammasi"
            courses = [
                course for course in list_courses()
                if (course['gender'] == "hammasi" or course['gender'] == user_gender)
                and course['joylar_soni'] < course['limit_count']
            ]
            buttons = [(course['name'], f"course_{course['id']}") for course in courses] + [(TRANSLATIONS[lang]["cancel"], "cancel")]
            kb = create_inline_keyboard(buttons, row_width=1)
            await callback.message.answer(TRANSLATIONS[lang]["choose_course"], reply_markup=kb)
            await state.set_state(EditProfile.new_value)
        elif field in ("passport_front", "passport_back"):
            buttons = [(TRANSLATIONS[lang]["cancel"], "cancel")]
            kb = create_inline_keyboard(buttons)
            await callback.message.answer(
                TRANSLATIONS[lang].get(f"upload_{field}", TRANSLATIONS[lang]["upload_new_photo"]),
                reply_markup=kb
            )
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
        data = await state.get_data()
        lang = data.get("lang", "uz")
        field = data["field"]
        user_id = data["user_id"]
        if message.photo and field in ("passport_front", "passport_back"):
            new_value = message.photo[-1].file_id
        else:
            new_value = message.text.strip()

        if field == "first_name" or field == "last_name":
            new_value = sanitize_input(new_value)
            if not new_value or len(new_value) < 2 or not new_value.isalpha():
                await message.answer(TRANSLATIONS[lang][f"invalid_{field}"])
                return
        elif field == "birth_date":
            try:
                birth_date = datetime.strptime(new_value, "%Y-%m-%d")
                if birth_date > datetime.now():
                    raise ValueError("Future date")
            except ValueError:
                await message.answer(TRANSLATIONS[lang]["invalid_birth_date"])
                return
        elif field == "phone":
            phone_pattern = r"^\+998\d{9}$"
            if not re.match(phone_pattern, new_value):
                await message.answer(TRANSLATIONS[lang]["invalid_phone"])
                return
        elif field == "address":
            new_value = sanitize_input(new_value)
            if not new_value or len(new_value) < 5:
                await message.answer(TRANSLATIONS[lang]["invalid_address"])
                return
        elif field in ("gender", "course"):
            await message.answer(TRANSLATIONS[lang]["use_buttons"])
            return

        try:
            update_user_field(user_id, field, new_value)
            user = get_user_by_tg(user_id)
            course_id = user['course_id']
            is_paid = user['is_paid']
            course_name = next((c['name'] for c in list_courses() if c['id'] == course_id), TRANSLATIONS[lang]["no_course"])
            reg_message_id = user['registration_message_id']
            await send_or_edit_reg_to_group(user, course_name, reg_message_id)
            buttons = [
                (TRANSLATIONS[lang]["choose_course"], "choose_course") if not course_id or not is_paid else None,
                (f"{TRANSLATIONS[lang]['pay_now']} ({course_name})", f"pay_now:{course_id}") if course_id and not is_paid else None,
                (TRANSLATIONS[lang]["cancel"], "cancel")
            ]
            buttons = [b for b in buttons if b]
            kb = create_inline_keyboard(buttons)
            await message.answer(TRANSLATIONS[lang]["field_updated"], reply_markup=kb)
            await state.clear()
            logger.info(f"User {message.from_user.id} updated {field} to {new_value} and updated group post.")
        except Exception as e:
            await message.answer(TRANSLATIONS[lang]["error"].format(error=str(e)))
            logger.error(f"Error updating {field} for user {message.from_user.id}: {str(e)}")

    @dp.callback_query(EditProfile.new_value, F.data.startswith(("gender_", "course_")))
    async def update_choice_field(callback: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        lang = data.get("lang", "uz")
        field = data["field"]
        user_id = data["user_id"]
        new_value = callback.data.replace(f"{field}_", "") if field == "gender" else int(callback.data.replace("course_", ""))

        try:
            update_user_field(user_id, field if field != "course" else "course_id", new_value)
            user = get_user_by_tg(user_id)
            course_id = user['course_id']
            is_paid = user['is_paid']
            course_name = next((c['name'] for c in list_courses() if c['id'] == course_id), TRANSLATIONS[lang]["no_course"])
            reg_message_id = user['registration_message_id']
            await send_or_edit_reg_to_group(user, course_name, reg_message_id)
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
            logger.info(f"User {callback.from_user.id} updated {field} to {new_value} and updated group post.")
        except Exception as e:
            await callback.message.answer(TRANSLATIONS[lang]["error"].format(error=str(e)))
            await callback.answer(show_alert=True)
            logger.error(f"Error updating {field} for user {callback.from_user.id}: {str(e)}")

    @dp.callback_query(F.data == "cancel")
    async def cancel_action(callback: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        lang = data.get("lang", "uz")
        await callback.message.answer(TRANSLATIONS[lang]["registration_canceled"])
        await state.clear()
        await callback.answer()
        logger.info(f"User {callback.from_user.id} canceled action.")