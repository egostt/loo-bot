import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import Message
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiohttp import web

# Клавиатуры
gender_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="М", callback_data="gender_M"),
            InlineKeyboardButton(text="Ж", callback_data="gender_J")
        ]
    ]
)

start_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Приступить к заданию", callback_data="start_registration")]
    ]
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Состояния FSM
class Register(StatesGroup):
    full_name = State()
    gender = State()
    region = State()
    account_count = State()
    current_account = State()
    account_platform = State()
    account_name = State()
    account_gender = State()
    done = State()

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "👋 Добро пожаловать в <b>LOO BOT 2.0</b>!\n\n"
        "✨ Чтобы начать выполнение задания, нажмите кнопку ниже:",
        reply_markup=start_kb,
        parse_mode="HTML"
    )

# Обработчик кнопки
@dp.callback_query(lambda c: c.data == "start_registration")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("👤 Введи своё ФИО (Фамилия Имя):")
    await state.set_state(Register.full_name)

# Ввод ФИО
@dp.message(Register.full_name)
async def reg_fullname(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("🧠 Укажи свой пол:", reply_markup=gender_kb)

# Выбор пола
@dp.callback_query(lambda c: c.data.startswith("gender_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await callback.message.edit_reply_markup()
    await callback.message.answer("🌍 Из какого ты региона? (например: Москва / 78 регион):")
    await state.set_state(Register.region)

# Ввод региона
@dp.message(Register.region)
async def reg_region(message: Message, state: FSMContext):
    await state.update_data(region=message.text)
    await message.answer("4️⃣ Сколько аккаунтов хочешь добавить?")
    await state.set_state(Register.account_count)

# Количество аккаунтов
@dp.message(Register.account_count)
async def reg_account_count(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введи число (например: 2)")
        return

    await state.update_data(account_count=count, accounts=[], current_index=1)
    await message.answer("➕ Добавим аккаунт 1.\nУкажи платформу (например: Яндекс / Google):")
    await state.set_state(Register.account_platform)

# Платформа аккаунта
@dp.message(Register.account_platform)
async def reg_account_platform(message: Message, state: FSMContext):
    await state.update_data(account_platform=message.text)
    await message.answer("Имя аккаунта на этой платформе:")
    await state.set_state(Register.account_name)

# Имя аккаунта
@dp.message(Register.account_name)
async def reg_account_name(message: Message, state: FSMContext):
    await state.update_data(account_name=message.text)
    await message.answer("Пол аккаунта (М / Ж):")
    await state.set_state(Register.account_gender)

# Пол аккаунта
@dp.message(Register.account_gender)
async def reg_account_gender(message: Message, state: FSMContext):
    data = await state.get_data()

    profile = {
        "platform": data["account_platform"],
        "name": data["account_name"],
        "gender": message.text
    }

    accounts = data.get("accounts", [])
    accounts.append(profile)

    current_index = data["current_index"]
    account_count = data["account_count"]
    await state.update_data(accounts=accounts)

    if current_index >= account_count:
        await finish_registration(message, state)
    else:
        await state.update_data(current_index=current_index + 1)
        await message.answer(f"➕ Добавим аккаунт {current_index + 1}.\nУкажи платформу:")
        await state.set_state(Register.account_platform)

# Завершение регистрации
async def finish_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    full_name = data["full_name"]
    gender = data["gender"]
    region = data["region"]
    accounts = data["accounts"]

    text = (
        f"<b>✅ Регистрация завершена!</b>\n\n"
        f"👤 ФИО: <b>{full_name}</b>\n"
        f"Пол: {gender}\n"
        f"Регион: {region}\n\n"
        f"🌐 Аккаунты:\n"
    )

    for i, acc in enumerate(accounts, 1):
        text += f"{i}. {acc['platform']} — {acc['name']} ({acc['gender']})\n"

    await message.answer(text)
    await state.clear()

# Веб-сервер для Render
async def health_check(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Web server started on port {port}")

# Запуск бота
async def main():
    me = await bot.get_me()
    print(f"🤖 Бот: @{me.username} | ID: {me.id}")
    print("✅ Бот запущен...")
    await dp.start_polling(bot, skip_updates=False)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    loop.run_until_complete(main())