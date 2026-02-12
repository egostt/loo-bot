import asyncio
import os
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from database import *
from aiohttp import web  # ← ДОБАВЬ ЭТУ СТРОКУ

if os.path.exists('.env'):
    load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# ============ STATES ============
class Registration(StatesGroup):
    # Регистрация исполнителя
    rules = State()
    name = State()
    surname = State()
    gender = State()
    region = State()
    
    # Добавление профиля
    platform_choice = State()
    platform_rules = State()
    screenshot = State()
    account_name = State()
    confirm_name = State()
    account_gender_rules = State()
    account_gender = State()
    gender_verification = State()
    add_more = State()

# ============ КЛАВИАТУРЫ ============
def rules_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю правила", callback_data="accept_rules")],
        [InlineKeyboardButton(text="❌ Отказаться", callback_data="decline_rules")]
    ])

def gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парень", callback_data="gender_male")],
        [InlineKeyboardButton(text="👩 Девушка", callback_data="gender_female")]
    ])

def platforms_kb(used_platforms=None):
    if used_platforms is None:
        used_platforms = []
    
    all_platforms = [
        "Яндекс.Карты", "Яндекс.Браузер", "Google Maps", "2ГИС",
        "Flamp", "ВКонтакте", "Dream Job", "Avito"
    ]
    
    buttons = []
    for platform in all_platforms:
        if platform not in used_platforms:
            buttons.append([InlineKeyboardButton(text=platform, callback_data=f"platform_{platform}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def yes_no_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="no")]
    ])

def gender_change_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Изменить пол аккаунта", callback_data="change_account_gender")],
        [InlineKeyboardButton(text="🔄 Изменить пол пользователя", callback_data="change_user_gender")]
    ])

# ============ СЛОВАРЬ ПРИМЕРОВ СКРИНОВ ============
PLATFORM_SCREENSHOTS = {
    "Яндекс.Карты": "yandex_maps.jpg",
    "Яндекс.Браузер": "yandex_browser.jpg",
    "Google Maps": "google_maps.jpg",
    "2ГИС": "2gis.jpg",
    "Flamp": "flamp.jpg",
    "ВКонтакте": "vk.jpg",
    "Dream Job": "dreamjob.jpg",
    "Avito": "avito.jpg"
}

# ============ КОМАНДА /start ============
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_data = await get_user_by_id(message.from_user.id)
    
    if user_data and user_data['approved']:
        await message.answer("✅ Ты уже зарегистрирован и одобрен!")
        return
    
    await state.clear()
    await state.update_data(user_id=message.from_user.id, username=message.from_user.username)
    
    rules_text = """📋 ПРАВИЛА ИСПОЛЬЗОВАНИЯ БОТА

1️⃣ Запрещено размещать фейковые аккаунты
2️⃣ Вся информация должна быть достоверной
3️⃣ Нарушение правил ведёт к блокировке

❓ Принимаешь правила?"""
    
    await message.answer(rules_text, reply_markup=rules_kb())
    await state.set_state(Registration.rules)

# ============ ПРИНЯТИЕ ПРАВИЛ ============
@router.callback_query(F.data == "accept_rules", Registration.rules)
async def accept_rules(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✅ Правила приняты!")
    await callback.message.answer("👤 Введи своё имя:")
    await state.set_state(Registration.name)

@router.callback_query(F.data == "decline_rules", Registration.rules)
async def decline_rules(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Регистрация отменена. Для повторной попытки напиши /start")
    await state.clear()

# ============ ИМЯ ============
@router.message(Registration.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("👤 Введи свою фамилию:")
    await state.set_state(Registration.surname)

# ============ ФАМИЛИЯ ============
@router.message(Registration.surname)
async def process_surname(message: Message, state: FSMContext):
    await state.update_data(surname=message.text)
    await message.answer("👤 Укажи свой пол:", reply_markup=gender_kb())
    await state.set_state(Registration.gender)

# ============ ПОЛ ИСПОЛНИТЕЛЯ ============
@router.callback_query(F.data.startswith("gender_"), Registration.gender)
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = "Мужской" if callback.data == "gender_male" else "Женский"
    await state.update_data(user_gender=gender)
    
    await callback.message.delete()
    
    # ВРЕМЕННО БЕЗ ИЗОБРАЖЕНИЯ
    await callback.message.answer(
        "🌍 Выбери свой регион:\n\n"
        "Введи код региона (например, 01) или название города:"
    )
    await state.set_state(Registration.region)

# ============ РЕГИОН ============
@router.message(Registration.region)
async def process_region(message: Message, state: FSMContext):
    await state.update_data(region=message.text)
    
    data = await state.get_data()
    
    # Сохраняем исполнителя в БД
    await add_user(
        user_id=data['user_id'],
        username=data.get('username', ''),
        name=data['name'],
        surname=data['surname'],
        gender=data['user_gender'],
        region=data['region']
    )
    
    await state.update_data(used_platforms=[])
    
    await message.answer("🌐 Давай добавим аккаунт!\n\nВыбери платформу:", reply_markup=platforms_kb())
    await state.set_state(Registration.platform_choice)

# ============ ВЫБОР ПЛАТФОРМЫ ============
@router.callback_query(F.data.startswith("platform_"), Registration.platform_choice)
async def process_platform_choice(callback: CallbackQuery, state: FSMContext):
    platform = callback.data.replace("platform_", "")
    await state.update_data(current_platform=platform)
    
    await callback.message.edit_text(
        "⚠️ Правило: можно добавить только 1 профиль на каждую платформу.\n\n❓ Продолжить?",
        reply_markup=yes_no_kb()
    )
    await state.set_state(Registration.platform_rules)

@router.callback_query(F.data == "yes", Registration.platform_rules)
async def accept_platform_rules(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    platform = data['current_platform']
    
    await callback.message.delete()
    
    # БЕЗ ПРИМЕРА СКРИНШОТА
    await callback.message.answer(
        f"📸 Отправь скриншот своего профиля на платформе {platform}\n\n"
        f"⚠️ Убедись, что на скрине видно:\n"
        f"• Название платформы\n"
        f"• Твоё имя профиля\n"
        f"• Рейтинг/отзывы (если есть)"
    )
    await state.set_state(Registration.screenshot)

@router.callback_query(F.data == "no", Registration.platform_rules)
async def decline_platform_rules(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    used_platforms = data.get('used_platforms', [])
    
    await callback.message.edit_text("🌐 Выбери другую платформу:", reply_markup=platforms_kb(used_platforms))
    await state.set_state(Registration.platform_choice)

# ============ СКРИНШОТ ============
@router.message(Registration.screenshot, F.photo)
async def process_screenshot(message: Message, state: FSMContext):
    photo = message.photo[-1].file_id
    await state.update_data(screenshot=photo)
    
    data = await state.get_data()
    platform = data['current_platform']
    
    await message.answer(f"✏️ Введи название профиля, как оно указано на скриншоте для {platform}:")
    await state.set_state(Registration.account_name)

@router.message(Registration.screenshot)
async def screenshot_invalid(message: Message):
    await message.answer("❌ Пожалуйста, отправь изображение (скриншот)!")

# ============ НАЗВАНИЕ ПРОФИЛЯ ============
@router.message(Registration.account_name)
async def process_account_name(message: Message, state: FSMContext):
    await state.update_data(account_name=message.text)
    
    data = await state.get_data()
    
    # Отправляем скриншот обратно для подтверждения
    await message.answer_photo(
        photo=data['screenshot'],
        caption=f"✏️ Введённое имя профиля: {message.text}\n\n❓ Имя совпадает с тем, что на скриншоте?",
        reply_markup=yes_no_kb()
    )
    await state.set_state(Registration.confirm_name)

# ============ ПОДТВЕРЖДЕНИЕ ИМЕНИ ============
@router.callback_query(F.data == "yes", Registration.confirm_name)
async def confirm_name_yes(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "⚠️ Правило: пол аккаунта должен совпадать с полом, указанным при регистрации.\n\n"
        "❓ Продолжить?",
        reply_markup=yes_no_kb()
    )
    await state.set_state(Registration.account_gender_rules)

@router.callback_query(F.data == "no", Registration.confirm_name)
async def confirm_name_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("✏️ Введи правильное название профиля:")
    await state.set_state(Registration.account_name)

# ============ ПРАВИЛА ПОЛА АККАУНТА ============
@router.callback_query(F.data == "yes", Registration.account_gender_rules)
async def accept_gender_rules(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    platform = data['current_platform']
    
    await callback.message.edit_text(f"🧠 Укажи пол этого аккаунта на {platform}:", reply_markup=gender_kb())
    await state.set_state(Registration.account_gender)

@router.callback_query(F.data == "no", Registration.account_gender_rules)
async def decline_gender_rules(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    used_platforms = data.get('used_platforms', [])
    
    await callback.message.edit_text("🌐 Выбери другую платформу:", reply_markup=platforms_kb(used_platforms))
    await state.set_state(Registration.platform_choice)

# ============ ПОЛ АККАУНТА ============
@router.callback_query(F.data.startswith("gender_"), Registration.account_gender)
async def process_account_gender(callback: CallbackQuery, state: FSMContext):
    account_gender = "Мужской" if callback.data == "gender_male" else "Женский"
    await state.update_data(account_gender=account_gender)
    
    data = await state.get_data()
    user_gender = data['user_gender']
    
    await callback.message.edit_text(
        f"👤 Пол пользователя: {user_gender}\n"
        f"🧠 Пол аккаунта: {account_gender}\n\n"
        f"❓ Нажми «Да», если всё верно:",
        reply_markup=yes_no_kb()
    )
    await state.set_state(Registration.gender_verification)

# ============ ПРОВЕРКА СОВПАДЕНИЯ ПОЛОВ ============
@router.callback_query(F.data == "yes", Registration.gender_verification)
async def gender_match_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    # Сохраняем профиль в БД
    await add_account(
        user_id=data['user_id'],
        platform=data['current_platform'],
        account_name=data['account_name'],
        screenshot=data['screenshot'],
        gender=data['account_gender']
    )
    
    # Добавляем платформу в использованные
    used_platforms = data.get('used_platforms', [])
    used_platforms.append(data['current_platform'])
    await state.update_data(used_platforms=used_platforms)
    
    await callback.message.edit_text(
        "✅ Аккаунт добавлен!\n\n❓ Есть ещё платформы, на которых у тебя есть профиль?",
        reply_markup=yes_no_kb()
    )
    await state.set_state(Registration.add_more)

@router.callback_query(F.data == "no", Registration.gender_verification)
async def gender_match_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔄 Что нужно изменить?",
        reply_markup=gender_change_kb()
    )

@router.callback_query(F.data == "change_account_gender")
async def change_account_gender(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    platform = data['current_platform']
    
    await callback.message.edit_text(f"🧠 Укажи правильный пол аккаунта на {platform}:", reply_markup=gender_kb())
    await state.set_state(Registration.account_gender)

@router.callback_query(F.data == "change_user_gender")
async def change_user_gender(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("👤 Укажи свой правильный пол:", reply_markup=gender_kb())
    await state.set_state(Registration.gender)

# ============ ДОБАВИТЬ ЕЩЁ ПЛАТФОРМУ? ============
@router.callback_query(F.data == "yes", Registration.add_more)
async def add_more_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    used_platforms = data.get('used_platforms', [])
    
    if len(used_platforms) >= 8:
        await callback.message.edit_text("✅ Все платформы добавлены!")
        await finish_registration(callback.message, state)
        return
    
    await callback.message.edit_text("🌐 Выбери платформу:", reply_markup=platforms_kb(used_platforms))
    await state.set_state(Registration.platform_choice)

@router.callback_query(F.data == "no", Registration.add_more)
async def add_more_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await finish_registration(callback.message, state)

async def finish_registration(message: Message, state: FSMContext):
    await message.answer(
        "✅ Регистрация завершена!\n\n"
        "Твои данные отправлены на модерацию.\n"
        "Ожидай подтверждения от администратора."
    )
    
    # Уведомление админу
    data = await state.get_data()
    user_data = await get_user_by_id(data['user_id'])
    
    if user_data:
        admin_text = f"🆕 Новая заявка на модерацию:\n\n"
        admin_text += f"👤 Имя: {user_data['name']} {user_data['surname']}\n"
        admin_text += f"🆔 ID: {user_data['user_id']}\n"
        admin_text += f"👤 Пол: {user_data['gender']}\n"
        admin_text += f"🌍 Регион: {user_data['region']}\n\n"
        admin_text += f"📱 Платформы:\n"
        
        for acc in user_data['accounts']:
            admin_text += f"• {acc['platform']}: {acc['account_name']}\n"
        
        approve_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_data['user_id']}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_data['user_id']}")]
        ])
        
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=approve_kb)
    
    await state.clear()

# ============ АДМИН: ОДОБРЕНИЕ/ОТКЛОНЕНИЕ ============
@router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await approve_user_db(user_id)
    
    await callback.message.edit_text(f"✅ Пользователь {user_id} одобрен!")
    await bot.send_message(user_id, "🎉 Твоя заявка одобрена! Теперь ты можешь пользоваться ботом.")

@router.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await reject_user_db(user_id)
    
    await callback.message.edit_text(f"❌ Пользователь {user_id} отклонён!")
    await bot.send_message(user_id, "❌ Твоя заявка отклонена. Для повторной попытки напиши /start")

# ============ ВЕБ-СЕРВЕР ДЛЯ RENDER ============
from aiohttp import web

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Веб-сервер запущен на порту {port}")

# ============ ЗАПУСК БОТА ============
async def main():
    print("🚀 Запуск бота...")
    print(f"📡 BOT_TOKEN: {BOT_TOKEN[:10] if BOT_TOKEN else '❌ НЕ УСТАНОВЛЕН'}...")
    print(f"🗄️ DATABASE_URL: {'✅ Установлен' if DATABASE_URL else '❌ Не установлен'}")
    
    # СНАЧАЛА запускаем веб-сервер (чтобы Render увидел порт)
    await start_web_server()
    print("✅ Веб-сервер запущен")
    
    # Инициализация БД
    await init_db()
    print("✅ База данных инициализирована")
    
    # Настройка бота
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    print("🧹 Webhook удалён, старые обновления сброшены")
    
    # Запуск polling
    print("🔄 Запуск polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Бот остановлен")
