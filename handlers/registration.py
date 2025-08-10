from aiogram import F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ContentType
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from database import save_user


class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    age = State()
    gender = State()
    phone = State()
    quran_course = State()


def register_handlers(dp):
    @dp.message(Command("start"))
    async def start_registration(message: Message, state: FSMContext):
        await message.answer("Assalomu alaykum! 😊\nRegistratsiya boshlaymiz.\nIsmingizni kiriting:")
        await state.set_state(Registration.first_name)

    @dp.message(Registration.first_name)
    async def get_first_name(message: Message, state: FSMContext):
        await state.update_data(first_name=message.text)
        await message.answer("Familiyangizni kiriting:")
        await state.set_state(Registration.last_name)

    @dp.message(Registration.last_name)
    async def get_last_name(message: Message, state: FSMContext):
        await state.update_data(last_name=message.text)
        await message.answer("Yoshingizni kiriting:")
        await state.set_state(Registration.age)

    @dp.message(Registration.age)
    async def get_age(message: Message, state: FSMContext):
        await state.update_data(age=message.text)

        gender_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Erkak ♂", callback_data="gender_erkak"),
             InlineKeyboardButton(text="Ayol ♀", callback_data="gender_ayol")]
        ])
        await message.answer("Jinsingizni tanlang:", reply_markup=gender_kb)
        await state.set_state(Registration.gender)

    @dp.callback_query(Registration.gender, F.data.startswith("gender_"))
    async def choose_gender(callback: CallbackQuery, state: FSMContext):
        gender = callback.data.replace("gender_", "")
        await state.update_data(gender=gender)

        phone_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]],
            resize_keyboard=True
        )
        await callback.message.answer(
            "Telefon raqamingizni yuboring yoki yozing (masalan: +998901234567):",
            reply_markup=phone_kb
        )
        await state.set_state(Registration.phone)
        await callback.answer()

    @dp.message(Registration.phone, F.content_type.in_({ContentType.CONTACT, ContentType.TEXT}))
    async def get_phone(message: Message, state: FSMContext):
        phone_number = message.contact.phone_number if message.contact else message.text
        await state.update_data(phone=phone_number)

        quran_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Boshlang‘ich", callback_data="course_boshlangich")],
            [InlineKeyboardButton(text="O‘rta", callback_data="course_orta")],
            [InlineKeyboardButton(text="Yuqori", callback_data="course_yuqori")]
        ])
        await message.answer("Qaysi Qur'on kursida o‘qiyapsiz?", reply_markup=quran_kb)
        await state.set_state(Registration.quran_course)

    @dp.callback_query(Registration.quran_course, F.data.startswith("course_"))
    async def choose_course(callback: CallbackQuery, state: FSMContext):
        course = callback.data.replace("course_", "")
        await state.update_data(quran_course=course)

        data = await state.get_data()
        save_user(data)

        await callback.message.answer(
            f"✅ Registratsiya yakunlandi!\n"
            f"Ism: {data['first_name']}\n"
            f"Familiya: {data['last_name']}\n"
            f"Yosh: {data['age']}\n"
            f"Jinsi: {data['gender']}\n"
            f"Telefon: {data['phone']}\n"
            f"Kurs: {data['quran_course']}",
            reply_markup=None
        )

        await state.clear()
        await callback.answer("Saqlandi ✅")
