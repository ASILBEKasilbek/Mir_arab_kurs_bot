import re
from aiogram import F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ContentType
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from database import save_user
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Translation dictionary for multilingual support
TRANSLATIONS = {
    "uz": {
        "choose_language": "Tilni tanlang:",
        "register_prompt": "📋 Registratsiya qilasizmi?",
        "yes": "✅ Ha",
        "no": "❌ Yo‘q",
        "enter_first_name": "Ismingizni kiriting:",
        "enter_last_name": "Familiyangizni kiriting:",
        "enter_age": "Yoshingizni kiriting:",
        "invalid_age": "Iltimos, to‘g‘ri yoshni kiriting (1-150 oraliqda raqam):",
        "choose_gender": "Jinsingizni tanlang:",
        "enter_phone": "Telefon raqamingizni yuboring yoki yozing (masalan: +998901234567):",
        "invalid_phone": "Iltimos, to‘g‘ri telefon raqamini kiriting (masalan: +998901234567):",
        "choose_course": "Qaysi Qur'on kursida o‘qiyapsiz?",
        "confirm_data": "📋 Ma’lumotlaringiz:\nIsm: {first_name}\nFamiliya: {last_name}\nYosh: {age}\nJinsi: {gender}\nTelefon: {phone}\nKurs: {course}\n\nMa’lumotlar to‘g‘rimi?",
        "registration_canceled": "❌ Registratsiya bekor qilindi. Qaytadan boshlang: /start",
        "registration_completed": "✅ Registratsiya yakunlandi! Rahmat."
    },
    "ru": {
        "choose_language": "Выберите язык:",
        "register_prompt": "📋 Хотите пройти регистрацию?",
        "yes": "✅ Да",
        "no": "❌ Нет",
        "enter_first_name": "Введите ваше имя:",
        "enter_last_name": "Введите вашу фамилию:",
        "enter_age": "Введите ваш возраст:",
        "invalid_age": "Пожалуйста, введите корректный возраст (число от 1 до 150):",
        "choose_gender": "Выберите ваш пол:",
        "enter_phone": "Отправьте или введите ваш номер телефона (например: +998901234567):",
        "invalid_phone": "Пожалуйста, введите корректный номер телефона (например: +998901234567):",
        "choose_course": "Какой курс Корана вы изучаете?",
        "confirm_data": "📋 Ваши данные:\nИмя: {first_name}\nФамилия: {last_name}\nВозраст: {age}\nПол: {gender}\nТелефон: {phone}\nКурс: {course}\n\nДанные верны?",
        "registration_canceled": "❌ Регистрация отменена. Начните заново: /start",
        "registration_completed": "✅ Регистрация завершена! Спасибо."
    }
}

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

def register_handlers(dp):
    @dp.message(Command("start"))
    async def choose_language(message: Message, state: FSMContext):
        lang_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇿 O‘zbek", callback_data="lang_uz")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")]
        ])
        await message.answer(TRANSLATIONS["uz"]["choose_language"], reply_markup=lang_kb)
        await state.set_state(Registration.lang)
        logging.info(f"User {message.from_user.id} started registration")

    @dp.callback_query(Registration.lang, F.data.startswith("lang_"))
    async def set_language(callback: CallbackQuery, state: FSMContext):
        lang = callback.data.replace("lang_", "")
        await state.update_data(lang=lang)

        text = TRANSLATIONS[lang]["register_prompt"]
        yes_text, no_text = TRANSLATIONS[lang]["yes"], TRANSLATIONS[lang]["no"]

        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=yes_text, callback_data="reg_yes"),
             InlineKeyboardButton(text=no_text, callback_data="reg_no")]
        ])
        await callback.message.answer(text, reply_markup=confirm_kb)
        await state.set_state(Registration.confirm)
        await callback.answer()
        logging.info(f"User {callback.from_user.id} selected language: {lang}")

    @dp.callback_query(Registration.confirm)
    async def confirm_registration(callback: CallbackQuery, state: FSMContext):
        if callback.data == "reg_no":
            data = await state.get_data()
            lang = data.get("lang", "uz")
            await callback.message.answer(TRANSLATIONS[lang]["registration_canceled"])
            await state.clear()
            await callback.answer()
            logging.info(f"User {callback.from_user.id} canceled registration")
            return

        data = await state.get_data()
        lang = data.get("lang", "uz")
        await callback.message.answer(TRANSLATIONS[lang]["enter_first_name"])
        await state.set_state(Registration.first_name)
        await callback.answer()

    @dp.message(Registration.first_name)
    async def get_first_name(message: Message, state: FSMContext):
        first_name = message.text.strip()
        if not first_name:
            data = await state.get_data()
            lang = data.get("lang", "uz")
            await message.answer(TRANSLATIONS[lang]["enter_first_name"])
            return
        await state.update_data(first_name=first_name)
        data = await state.get_data()
        lang = data.get("lang", "uz")
        await message.answer(TRANSLATIONS[lang]["enter_last_name"])
        await state.set_state(Registration.last_name)
        logging.info(f"User {message.from_user.id} entered first name: {first_name}")

    @dp.message(Registration.last_name)
    async def get_last_name(message: Message, state: FSMContext):
        last_name = message.text.strip()
        if not last_name:
            data = await state.get_data()
            lang = data.get("lang", "uz")
            await message.answer(TRANSLATIONS[lang]["enter_last_name"])
            return
        await state.update_data(last_name=last_name)
        data = await state.get_data()
        lang = data.get("lang", "uz")
        await message.answer(TRANSLATIONS[lang]["enter_age"])
        await state.set_state(Registration.age)
        logging.info(f"User {message.from_user.id} entered last name: {last_name}")

    @dp.message(Registration.age)
    async def get_age(message: Message, state: FSMContext):
        age_text = message.text.strip()
        data = await state.get_data()
        lang = data.get("lang", "uz")
        if not age_text.isdigit() or int(age_text) < 1 or int(age_text) > 150:
            await message.answer(TRANSLATIONS[lang]["invalid_age"])
            return
        await state.update_data(age=int(age_text))
        gender_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Erkak ♂" if lang == "uz" else "Мужской ♂", callback_data="gender_erkak"),
             InlineKeyboardButton(text="Ayol ♀" if lang == "uz" else "Женский ♀", callback_data="gender_ayol")]
        ])
        await message.answer(TRANSLATIONS[lang]["choose_gender"], reply_markup=gender_kb)
        await state.set_state(Registration.gender)
        logging.info(f"User {message.from_user.id} entered age: {age_text}")

    @dp.callback_query(Registration.gender, F.data.startswith("gender_"))
    async def choose_gender(callback: CallbackQuery, state: FSMContext):
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
        await callback.message.answer(TRANSLATIONS[lang]["enter_phone"], reply_markup=phone_kb)
        await state.set_state(Registration.phone)
        await callback.answer()
        logging.info(f"User {callback.from_user.id} selected gender: {gender}")

    @dp.message(Registration.phone, F.content_type.in_({ContentType.CONTACT, ContentType.TEXT}))
    async def get_phone(message: Message, state: FSMContext):
        phone_number = message.contact.phone_number if message.contact else message.text.strip()
        data = await state.get_data()
        lang = data.get("lang", "uz")
        phone_pattern = r"^\+?[1-9]\d{1,14}$"
        if not re.match(phone_pattern, phone_number):
            await message.answer(TRANSLATIONS[lang]["invalid_phone"])
            return
        await state.update_data(phone=phone_number)
        course_names = {
            "uz": ["Boshlang‘ich", "O‘rta", "Yuqori"],
            "ru": ["Начальный", "Средний", "Высший"]
        }
        quran_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=course_names[lang][0], callback_data="course_boshlangich")],
            [InlineKeyboardButton(text=course_names[lang][1], callback_data="course_orta")],
            [InlineKeyboardButton(text=course_names[lang][2], callback_data="course_yuqori")]
        ])
        await message.answer(TRANSLATIONS[lang]["choose_course"], reply_markup=quran_kb)
        await state.set_state(Registration.quran_course)
        logging.info(f"User {message.from_user.id} entered phone: {phone_number}")

    @dp.callback_query(Registration.quran_course, F.data.startswith("course_"))
    async def choose_course(callback: CallbackQuery, state: FSMContext):
        course = callback.data.replace("course_", "")
        await state.update_data(quran_course=course)
        data = await state.get_data()
        lang = data.get("lang", "uz")
        course_display = {
            "boshlangich": "Boshlang‘ich" if lang == "uz" else "Начальный",
            "orta": "O‘rta" if lang == "uz" else "Средний",
            "yuqori": "Yuqori" if lang == "uz" else "Высший"
        }[course]
        confirm_text = TRANSLATIONS[lang]["confirm_data"].format(
            first_name=data["first_name"],
            last_name=data["last_name"],
            age=data["age"],
            gender="Erkak" if data["gender"] == "erkak" else "Ayol" if lang == "uz" else
                   "Мужской" if data["gender"] == "erkak" else "Женский",
            phone=data["phone"],
            course=course_display
        )
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=TRANSLATIONS[lang]["yes"], callback_data="confirm_yes"),
             InlineKeyboardButton(text=TRANSLATIONS[lang]["no"], callback_data="confirm_no")]
        ])
        await callback.message.answer(confirm_text, reply_markup=confirm_kb)
        await state.set_state(Registration.final_confirm)
        await callback.answer()
        logging.info(f"User {callback.from_user.id} selected course: {course}")

    @dp.callback_query(Registration.final_confirm, F.data.startswith("confirm_"))
    async def final_confirmation(callback: CallbackQuery, state: FSMContext):
        choice = callback.data.replace("confirm_", "")
        data = await state.get_data()
        lang = data.get("lang", "uz")
        if choice == "no":
            await callback.message.answer(TRANSLATIONS[lang]["registration_canceled"])
            await state.clear()
            await callback.answer("Bekor qilindi" if lang == "uz" else "Отменено")
            logging.info(f"User {callback.from_user.id} canceled final confirmation")
            return
        try:
            data["tg_id"] = callback.from_user.id
            save_user(data)
            await callback.message.answer(TRANSLATIONS[lang]["registration_completed"])
            await state.clear()
            await callback.answer("Saqlandi ✅" if lang == "uz" else "Сохранено ✅")
            logging.info(f"User {callback.from_user.id} completed registration")
        except Exception as e:
            await callback.message.answer(f"Xato yuz berdi: {str(e)}" if lang == "uz" else f"Произошла ошибка: {str(e)}")
            await callback.answer("Xato" if lang == "uz" else "Ошибка", show_alert=True)
            logging.error(f"Error during final confirmation for user {callback.from_user.id}: {str(e)}")