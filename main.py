import asyncio
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardRemove
)
from aiohttp import web
from dotenv import load_dotenv
from database import init_db, add_user, add_account, get_user_accounts, get_pending_users, approve_user_db, reject_user_db

# Загружаем .env только если файл существует (локальная разработка)
if os.path.exists('.env'):
    load_dotenv()

# ============================================
# КОНФИГУРАЦИЯ
# ============================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [6164972723]

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Проверь переменные окружения.")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ============================================
# ПЛАТФОРМЫ И ПРИМЕРЫ
# ============================================

PLATFORMS = [
    "Яндекс.Карты", "Яндекс.Браузер", "Google Maps", "2ГИС",
    "Flamp", "ВКонтакте", "Dream Job", "Avito"
]

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

REGION_PHOTO = "examples/regions.jpg"  # ⬅️ ПУТЬ К ФОТО С РЕГИОНАМИ

# ============================================
# СОСТОЯНИЯ
# ============================================

class Register(StatesGroup):
    first_name = State()
    last_name = State()
    gender = State()
    region = State()
    platform_choice = State()
    screenshot = State()
    account_name = State()
    confirm_name = State()
    account_gender = State()
    account_gender_confirm = State()
    more_platforms = State()

# ============================================
# КЛАВИАТУРЫ
# ============================================

gender_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👨 Мужской", callback_data="gender_M"),
     InlineKeyboardButton(text="👩 Женский", callback_data="gender_Ж")]
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

# ============================================
# WEB SERVER (для Render)
# ============================================

async def health_check(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()
    print(f"🌐 Web server started on port {os.getenv('PORT', 8080)}")

# ============================================
# КОМАНДЫ
# ============================================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Это бот для регистрации твоих аккаунтов на различных платформах.\n\n"
        "Нажми кнопку ниже, чтобы начать:",
        reply_markup=start_kb
    )

# ============================================
# РЕГИСТРАЦИЯ
# ============================================

# Начало регистрации
@dp.callback_query(lambda c: c.data == "start_registration")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("✏️ Введи своё имя:")
    await state.set_state(Register.first_name)

# Имя
@dp.message(Register.first_name)
async def reg_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("✏️ Введи свою фамилию:")
    await state.set_state(Register.last_name)

# Фамилия
@dp.message(Register.last_name)
async def reg_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("🧠 Укажи свой пол:", reply_markup=gender_kb)
    await state.set_state(Register.gender)

# Выбор пола ПОЛЬЗОВАТЕЛЯ
@dp.callback_query(Register.gender, lambda c: c.data.startswith("gender_"))
async def reg_gender(callback: CallbackQuery, state: FSMContext):
    user_gender = callback.data.replace("gender_", "")
    await state.update_data(gender=user_gender)
    await callback.message.edit_reply_markup()
    
    # Отправляем фото с регионами
    try:
        photo = FSInputFile(REGION_PHOTO)
        await callback.message.answer_photo(
            photo=photo,
            caption="📍 Выбери свой регион из списка на фото выше ☝️\n\nВведи название региона:"
        )
    except:
        await callback.message.answer("📍 Введи свой регион:")
    
    await state.set_state(Register.region)

# Регион
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
            caption=f"📸 Пример скриншота для <b>{platform}</b>",
            parse_mode="HTML"
        )
    except:
        pass
    
    await callback.message.answer(
        f"📸 Отправь скриншот своего профиля на платформе <b>{platform}</b>\n\n"
        f"⚠️ Убедись, что на скрине видно:\n"
        f"• Название платформы\n"
        f"• Твоё имя профиля\n"
        f"• Рейтинг/отзывы (если есть)",
        parse_mode="HTML"
    )
    
    await state.set_state(Register.screenshot)

# Получение скриншота
@dp.message(Register.screenshot, F.photo)
async def reg_screenshot(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(screenshot_file_id=file_id)
    
    data = await state.get_data()
    platform = data["current_platform"]
    
    await message.answer(
        f"✏️ Введи название профиля, как оно указано на скриншоте для <b>{platform}</b>:",
        parse_mode="HTML"
    )
    await state.set_state(Register.account_name)

# Ввод имени профиля
@dp.message(Register.account_name)
async def reg_account_name(message: Message, state: FSMContext):
    account_name = message.text
    await state.update_data(account_name=account_name)
    
    data = await state.get_data()
    
    # Показываем скрин и просим подтвердить
    await message.answer_photo(
        photo=data["screenshot_file_id"],
        caption=(
            f"📸 Твой скриншот\n\n"
            f"✏️ Введённое имя профиля: <b>{account_name}</b>\n\n"
            f"❓ Имя совпадает с тем, что на скриншоте?"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, всё верно", callback_data="name_correct")],
            [InlineKeyboardButton(text="✏️ Нет, исправить", callback_data="name_incorrect")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(Register.confirm_name)

# Подтверждение имени
@dp.callback_query(Register.confirm_name, lambda c: c.data == "name_correct")
async def confirm_name_correct(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    
    # Теперь спрашиваем пол аккаунта
    await callback.message.answer(
        "🧠 Укажи пол этого аккаунта:",
        reply_markup=gender_kb
    )
    await state.set_state(Register.account_gender)

# Исправление имени
@dp.callback_query(Register.confirm_name, lambda c: c.data == "name_incorrect")
async def confirm_name_incorrect(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        "✏️ Введи правильное название профиля:"
    )
    await state.set_state(Register.account_name)

# Выбор пола аккаунта
@dp.callback_query(Register.account_gender, lambda c: c.data.startswith("gender_"))
async def reg_account_gender(callback: CallbackQuery, state: FSMContext):
    account_gender = callback.data.replace("gender_", "")
    await state.update_data(account_gender=account_gender)
    await callback.message.edit_reply_markup()
    
    data = await state.get_data()
    user_gender = data["gender"]
    
    # Показываем правило и подтверждение
    await callback.message.answer(
        f"⚠️ <b>Правило:</b> пол аккаунта должен совпадать с полом, указанным при регистрации.\n\n"
        f"Твой пол: <b>{'Мужской' if user_gender == 'M' else 'Женский'}</b>\n"
        f"Пол аккаунта: <b>{'Мужской' if account_gender == 'M' else 'Женский'}</b>\n\n"
        f"Нажми «Да», если всё верно:",
        reply_markup=confirm_kb,
        parse_mode="HTML"
    )
    await state.set_state(Register.account_gender_confirm)

# Подтверждение пола
@dp.callback_query(Register.account_gender_confirm, lambda c: c.data == "confirm_yes")
async def confirm_gender(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    
    # Сохраняем аккаунт
    data = await state.get_data()
    accounts = data.get("accounts", [])
    accounts.append({
        "platform": data["current_platform"],
        "name": data["account_name"],
        "gender": data["account_gender"],
        "screenshot": data["screenshot_file_id"]
    })
    await state.update_data(accounts=accounts)
    
    await callback.message.answer(
        "✅ Аккаунт добавлен!\n\n"
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
            "⚠️ <b>Правило:</b> можно добавить только 1 профиль на каждую платформу.\n\n"
            "🌐 Выбери следующую платформу:",
            reply_markup=get_platforms_kb(exclude=used_platforms),
            parse_mode="HTML"
        )
        await state.set_state(Register.platform_choice)
    else:
        await finish_registration(callback.message, state)

# Завершение регистрации
async def finish_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Сохраняем пользователя
    await add_user(
        user_id=user_id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        gender=data["gender"],
        region=data["region"]
    )
    
    # Сохраняем аккаунты
    for acc in data["accounts"]:
        await add_account(
            user_id=user_id,
            platform=acc["platform"],
            account_name=acc["name"],
            account_gender=acc["gender"],
            screenshot_file_id=acc["screenshot"]
        )
    
    await message.answer(
        "✅ <b>Регистрация завершена!</b>\n\n"
        "Твои данные отправлены на модерацию.\n"
        "Ожидай подтверждения от администратора.",
        parse_mode="HTML"
    )
    await state.clear()

# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У тебя нет доступа к админ-панели")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи на модерации", callback_data="admin_pending")],
        [InlineKeyboardButton(text="✅ Одобренные пользователи", callback_data="admin_approved")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])
    
    await message.answer(
        "🔧 <b>Админ-панель</b>\n\nВыбери действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "admin_pending")
async def show_pending_users(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    pending = await get_pending_users()
    
    if not pending:
        await callback.message.answer("✅ Нет пользователей на модерации")
        return
    
    for user in pending:
        accounts_text = "\n".join([f"• {acc['platform']}: {acc['profile_name']}" for acc in user['accounts']])
        
        text = (
            f"👤 <b>{user['first_name']} {user['last_name']}</b>\n"
            f"🆔 Telegram ID: {user['telegram_id']}\n"
            f"👥 Пол: {user['gender']}\n"
            f"📍 Регион: {user['region']}\n\n"
            f"<b>Аккаунты:</b>\n{accounts_text}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user['id']}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user['id']}")
            ]
        ])
        
        # Отправляем скрины
        for acc in user['accounts']:
            await callback.message.answer_photo(
                photo=acc['screenshot'],
                caption=f"<b>{acc['platform']}</b>: {acc['profile_name']}",
                parse_mode="HTML"
            )
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    user_id = int(callback.data.replace("approve_", ""))
    await approve_user_db(user_id)
    
    await callback.message.edit_text("✅ Пользователь одобрен!")
    
    # Уведомляем пользователя
    await bot.send_message(
        user_id,
        "✅ <b>Твоя регистрация одобрена!</b>\n\nТеперь ты можешь получать задания.",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    user_id = int(callback.data.replace("reject_", ""))
    await reject_user_db(user_id)
    
    await callback.message.edit_text("❌ Пользователь отклонён")
    
    # Уведомляем пользователя
    await bot.send_message(
        user_id,
        "❌ Твоя регистрация отклонена.\n\nСвяжись с администратором для уточнения причин."
    )

# ============================================
# ЗАПУСК БОТА
# ============================================

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