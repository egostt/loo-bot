import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiohttp import web
from database import init_db, add_user, add_account, get_user_accounts

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Добавь свой ID в .env

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Платформы
PLATFORMS = [
    "Яндекс.Карты", "Яндекс.Браузер", "Google Maps", "2ГИС",
    "Flamp", "ВКонтакте", "Dream Job", "Avito"
]

# Примеры скринов (ID файлов из Google Drive - заменим на Telegram file_id после первой загрузки)
PLATFORM_EXAMPLES = {
    "Яндекс.Карты": "examples/yandex_maps.jpg",
    "Яндекс.Браузер": "examples/yandex_browser.jpg",
    "Google Maps": "examples/google_maps.jpg",
    "2ГИС": "examples/2gis.jpg",
    "Flamp": "examples/flamp.jpg",
    "ВКонтакте": "examples/vk.jpg",
    "Dream Job": "examples/dreamjob.jpg",
    "Avito": "examples/avito.jpg"
}

# Состояния FSM
class Register(StatesGroup):
    first_name = State()
    last_name = State()
    gender = State()
    region = State()
    platform_choice = State()
    screenshot = State()
    account_gender = State()
    account_gender_confirm = State()
    account_name = State()
    account_name_confirm = State()
    more_platforms = State()

# Клавиатуры
gender_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="М", callback_data="gender_M"),
     InlineKeyboardButton(text="Ж", callback_data="gender_J")]
])

start_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✍️ Приступить к заданию", callback_data="start_registration")]
])

confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да", callback_data="confirm_yes")]
])

more_platforms_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Да", callback_data="more_yes"),
     InlineKeyboardButton(text="Нет", callback_data="more_no")]
])

def get_platforms_kb(exclude=[]):
    buttons = []
    for platform in PLATFORMS:
        if platform not in exclude:
            buttons.append([InlineKeyboardButton(text=platform, callback_data=f"platform_{platform}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать в <b>LOO BOT 2.0</b>!\n\n"
        "✨ Чтобы начать выполнение задания, нажмите кнопку ниже:",
        reply_markup=start_kb
    )

# Начало регистрации
@dp.callback_query(lambda c: c.data == "start_registration")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("👤 Введи своё <b>имя</b>:")
    await state.set_state(Register.first_name)

# Ввод имени
@dp.message(Register.first_name)
async def reg_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("👤 Введи свою <b>фамилию</b>:")
    await state.set_state(Register.last_name)

# Ввод фамилии
@dp.message(Register.last_name)
async def reg_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("🧠 Укажи свой пол:", reply_markup=gender_kb)
    await state.set_state(Register.gender)

# Выбор пола
@dp.callback_query(Register.gender, lambda c: c.data.startswith("gender_"))
async def reg_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await callback.message.edit_reply_markup()
    
    # Отправляем фото с регионами
    try:
        photo = FSInputFile("examples/regions.jpg")
        await callback.message.answer_photo(
            photo=photo,
            caption="🌍 Укажи свой регион (например: Москва, 78 регион):"
        )
    except:
        await callback.message.answer("🌍 Укажи свой регион (например: Москва, 78 регион):")
    
    await state.set_state(Register.region)

# Ввод региона
@dp.message(Register.region)
async def reg_region(message: Message, state: FSMContext):
    await state.update_data(region=message.text, accounts=[])
    await message.answer(
        "🌐 Давай добавим аккаунт!\n\nВыбери платформу:",
        reply_markup=get_platforms_kb()
    )
    await state.set_state(Register.platform_choice)

# Выбор платформы
@dp.callback_query(Register.platform_choice, lambda c: c.data.startswith("platform_"))
async def reg_platform(callback: CallbackQuery, state: FSMContext):
    platform = callback.data.replace("platform_", "")
    await state.update_data(current_platform=platform)
    await callback.message.edit_reply_markup()
    
    # Отправляем пример скрина
    example_path = PLATFORM_EXAMPLES.get(platform)
    try:
        photo = FSInputFile(example_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=f"📸 Отправь скриншот своего профиля на платформе <b>{platform}</b>\n\n"
                    f"Пример на фото выше ☝️"
        )
    except:
        await callback.message.answer(
            f"📸 Отправь скриншот своего профиля на платформе <b>{platform}</b>"
        )
    
    await state.set_state(Register.screenshot)

# Получение скриншота
@dp.message(Register.screenshot, F.photo)
async def reg_screenshot(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(screenshot_file_id=file_id)
    await message.answer("🧠 Укажи пол этого аккаунта:", reply_markup=gender_kb)
    await state.set_state(Register.account_gender)

# Выбор пола аккаунта
@dp.callback_query(Register.account_gender, lambda c: c.data.startswith("gender_"))
async def reg_account_gender(callback: CallbackQuery, state: FSMContext):
    account_gender = callback.data.replace("gender_", "")
    await state.update_data(account_gender=account_gender)
    await callback.message.edit_reply_markup()
    
    data = await state.get_data()
    user_gender = data["gender"]
    
    await callback.message.answer(
        f"⚠️ <b>Правило:</b> пол аккаунта должен совпадать с полом, указанным при регистрации.\n\n"
        f"Твой пол: <b>{user_gender}</b>\n"
        f"Пол аккаунта: <b>{account_gender}</b>\n\n"
        f"Нажми «Да», если ознакомился и согласен с правилами:",
        reply_markup=confirm_kb
    )
    await state.set_state(Register.account_gender_confirm)

# Подтверждение пола
@dp.callback_query(Register.account_gender_confirm, lambda c: c.data == "confirm_yes")
async def confirm_gender(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("✏️ Введи название аккаунта:")
    await state.set_state(Register.account_name)

# Ввод названия аккаунта
@dp.message(Register.account_name)
async def reg_account_name(message: Message, state: FSMContext):
    await state.update_data(account_name=message.text)
    await message.answer(
        "⚠️ <b>Правило:</b> можно внести только 1 профиль к каждой платформе.\n\n"
        "Нажми «Да», если ознакомился и согласен с правилами:",
        reply_markup=confirm_kb
    )
    await state.set_state(Register.account_name_confirm)

# Подтверждение названия
@dp.callback_query(Register.account_name_confirm, lambda c: c.data == "confirm_yes")
async def confirm_name(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    # Сохраняем аккаунт
    accounts = data.get("accounts", [])
    accounts.append({
        "platform": data["current_platform"],
        "name": data["account_name"],
        "gender": data["account_gender"],
        "screenshot": data["screenshot_file_id"]
    })
    await state.update_data(accounts=accounts)
    
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "❓ Есть ещё платформы, на которых у тебя есть профиль?",
        reply_markup=more_platforms_kb
    )
    await state.set_state(Register.more_platforms)

# Ещё платформы?
@dp.callback_query(Register.more_platforms, lambda c: c.data.startswith("more_"))
async def more_platforms(callback: CallbackQuery, state: FSMContext):
    answer = callback.data.replace("more_", "")
    
    if answer == "yes":
        data = await state.get_data()
        used_platforms = [acc["platform"] for acc in data["accounts"]]
        await callback.message.edit_reply_markup()
        await callback.message.answer(
            "🌐 Выбери следующую платформу:",
            reply_markup=get_platforms_kb(exclude=used_platforms)
        )
        await state.set_state(Register.platform_choice)
    else:
        await finish_registration(callback.message, state)

# Завершение регистрации
async def finish_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Сохраняем в БД
    await add_user(
        user_id=user_id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        gender=data["gender"],
        region=data["region"]
    )
    
    for acc in data["accounts"]:
        await add_account(
            user_id=user_id,
            platform=acc["platform"],
            account_name=acc["name"],
            account_gender=acc["gender"],
            screenshot_file_id=acc["screenshot"]
        )
    
    # Отправляем админу на модерацию
    if ADMIN_ID:
        admin_text = (
            f"🆕 <b>Новая заявка на модерацию</b>\n\n"
            f"👤 Пользователь: {data['first_name']} {data['last_name']}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"Пол: {data['gender']}\n"
            f"Регион: {data['region']}\n\n"
            f"🌐 Аккаунты ({len(data['accounts'])}):\n"
        )
        
        for i, acc in enumerate(data["accounts"], 1):
            admin_text += f"{i}. {acc['platform']} — {acc['name']} ({acc['gender']})\n"
        
        await bot.send_message(ADMIN_ID, admin_text)
        
        for acc in data["accounts"]:
            await bot.send_photo(
                ADMIN_ID,
                photo=acc["screenshot"],
                caption=f"Скриншот: {acc['platform']}"
            )
    
    await message.answer(
        "✅ <b>Регистрация завершена!</b>\n\n"
        "Твои данные отправлены на модерацию.\n"
        "Ожидай подтверждения от администратора."
    )
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
    await init_db()
    me = await bot.get_me()
    print(f"🤖 Бот: @{me.username} | ID: {me.id}")
    print("✅ Бот запущен...")
    await dp.start_polling(bot, skip_updates=False)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    loop.run_until_complete(main())