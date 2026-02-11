iimport asyncio
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
from database import (
    init_db, add_user, add_account, get_user_accounts, 
    get_pending_users, approve_user_db, reject_user_db,
    get_user_by_id, remove_platform_from_available
)

# Загружаем .env только если файл существует
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
# ПЛАТФОРМЫ
# ============================================

PLATFORMS = [
    "Яндекс.Карты",
    "Яндекс.Браузер",
    "Google Maps",
    "2ГИС",
    "Flamp",
    "ВКонтакте",
    "Dream Job",
    "Avito"
]

# Пути к примерам скринов (должны быть в папке images/)
PLATFORM_EXAMPLES = {
    "Яндекс.Карты": "images/yandex_maps_example.jpg",
    "Яндекс.Браузер": "images/yandex_browser_example.jpg",
    "Google Maps": "images/google_maps_example.jpg",
    "2ГИС": "images/2gis_example.jpg",
    "Flamp": "images/flamp_example.jpg",
    "ВКонтакте": "images/vk_example.jpg",
    "Dream Job": "images/dreamjob_example.jpg",
    "Avito": "images/avito_example.jpg"
}

# ============================================
# СОСТОЯНИЯ FSM
# ============================================

class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_surname = State()
    waiting_for_gender = State()
    waiting_for_region = State()
    waiting_for_confirmation = State()
    
    # Добавление платформы
    waiting_for_platform_choice = State()
    waiting_for_screenshot = State()
    waiting_for_account_name = State()
    waiting_for_account_name_confirmation = State()
    waiting_for_account_gender = State()
    waiting_for_more_platforms = State()

class SearchStates(StatesGroup):
    waiting_for_platform = State()

# ============================================
# КЛАВИАТУРЫ
# ============================================

def get_gender_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨 Парень"), KeyboardButton(text="👩 Девушка")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_confirmation_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, всё верно"), KeyboardButton(text="❌ Начать заново")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_platforms_keyboard(exclude_platforms=None):
    """Генерирует клавиатуру с платформами, исключая уже зарегистрированные"""
    if exclude_platforms is None:
        exclude_platforms = []
    
    available_platforms = [p for p in PLATFORMS if p not in exclude_platforms]
    
    buttons = []
    for i in range(0, len(available_platforms), 2):
        row = [KeyboardButton(text=available_platforms[i])]
        if i + 1 < len(available_platforms):
            row.append(KeyboardButton(text=available_platforms[i + 1]))
        buttons.append(row)
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_yes_no_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да"), KeyboardButton(text="Нет")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти профили")],
            [KeyboardButton(text="➕ Добавить профиль"), KeyboardButton(text="📋 Мои профили")],
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

def get_admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти профили")],
            [KeyboardButton(text="➕ Добавить профиль"), KeyboardButton(text="📋 Мои профили")],
            [KeyboardButton(text="👥 Заявки на регистрацию"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    user = await get_user_by_id(user_id)
    
    if user and user.get('approved'):
        await message.answer(
            "🎉 Ты уже зарегистрирован!\n\n"
            "Используй /menu для доступа к функциям бота.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    if user and not user.get('approved'):
        await message.answer(
            "⏳ Твоя заявка на рассмотрении у администратора.\n\n"
            "Ожидай одобрения!",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    # Новый пользователь - показываем правила
    rules_text = """
📋 **ПРАВИЛА ИСПОЛЬЗОВАНИЯ БОТА**

1️⃣ Запрещено размещать фейковые аккаунты
2️⃣ Вся информация должна быть достоверной
3️⃣ Уважай других пользователей
4️⃣ Не спамь и не флуди
5️⃣ Администрация имеет право удалить аккаунт без объяснения причин

❗️ Нажимая "Принимаю", ты соглашаешься с правилами.
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю правила", callback_data="accept_rules")],
        [InlineKeyboardButton(text="❌ Отказаться", callback_data="decline_rules")]
    ])
    
    await message.answer(rules_text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "accept_rules")
async def accept_rules_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.message.answer(
        "👤 Введи своё имя:",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await state.set_state(RegistrationStates.waiting_for_name)
    await callback.answer()

@router.callback_query(F.data == "decline_rules")
async def decline_rules_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "❌ Ты отказался от правил.\n\n"
        "Для регистрации нужно принять правила. Напиши /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await callback.answer()

# ============================================
# РЕГИСТРАЦИЯ - ИМЯ
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_name))
async def name_handler(message: Message, state: FSMContext):
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Попробуй ещё раз:")
        return
    
    await state.update_data(name=name)
    await message.answer("👤 Введи свою фамилию:")
    await state.set_state(RegistrationStates.waiting_for_surname)

# ============================================
# РЕГИСТРАЦИЯ - ФАМИЛИЯ
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_surname))
async def surname_handler(message: Message, state: FSMContext):
    surname = message.text.strip()
    
    if len(surname) < 2:
        await message.answer("❌ Фамилия слишком короткая. Попробуй ещё раз:")
        return
    
    await state.update_data(surname=surname)
    await message.answer(
        "👤 Укажи свой пол:",
        reply_markup=get_gender_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_gender)

# ============================================
# РЕГИСТРАЦИЯ - ПОЛ
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_gender))
async def gender_handler(message: Message, state: FSMContext):
    if message.text not in ["👨 Парень", "👩 Девушка"]:
        await message.answer("❌ Пожалуйста, выбери пол из предложенных вариантов.")
        return
    
    await state.update_data(gender=message.text)
    
    # Отправляем изображение с регионами
    try:
        photo = FSInputFile("images/regions.jpg")
        await message.answer_photo(
            photo=photo,
            caption="🌍 Введи свой регион или город (как на картинке):",
            reply_markup=ReplyKeyboardRemove()
        )
    except:
        await message.answer(
            "🌍 Введи свой регион или город:",
            reply_markup=ReplyKeyboardRemove()
        )
    
    await state.set_state(RegistrationStates.waiting_for_region)

# ============================================
# РЕГИСТРАЦИЯ - РЕГИОН
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_region))
async def region_handler(message: Message, state: FSMContext):
    region = message.text.strip()
    
    if len(region) < 2:
        await message.answer("❌ Регион слишком короткий. Попробуй ещё раз:")
        return
    
    await state.update_data(region=region)
    
    # Показываем данные для подтверждения
    data = await state.get_data()
    
    confirmation_text = f"""
✅ Проверь свои данные:

👤 Имя: {data['name']}
👤 Фамилия: {data['surname']}
🚻 Пол: {data['gender']}
🌍 Регион: {region}

Всё верно?
"""
    
    await message.answer(
        confirmation_text,
        reply_markup=get_confirmation_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_confirmation)

# ============================================
# РЕГИСТРАЦИЯ - ПОДТВЕРЖДЕНИЕ
# ============================================

@router.message(F.text == "✅ Да, всё верно", StateFilter(RegistrationStates.waiting_for_confirmation))
async def confirmation_yes_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    
    # Сохраняем пользователя в БД
    user_id = message.from_user.id
    username = message.from_user.username or "Без username"
    
    await add_user(
        user_id=user_id,
        username=username,
        name=data['name'],
        surname=data['surname'],
        gender=data['gender'],
        region=data['region']
    )
    
    await message.answer(
        "📱 Теперь добавь свои профили на платформах\n\n"
        "Выбери платформу:",
        reply_markup=get_platforms_keyboard()
    )
    
    await state.set_state(RegistrationStates.waiting_for_platform_choice)

@router.message(F.text == "❌ Начать заново", StateFilter(RegistrationStates.waiting_for_confirmation))
async def confirmation_no_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔄 Регистрация отменена.\n\n"
        "Напиши /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )

# ============================================
# ДОБАВЛЕНИЕ ПРОФИЛЯ - ВЫБОР ПЛАТФОРМЫ
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_platform_choice))
async def platform_choice_handler(message: Message, state: FSMContext):
    platform = message.text
    
    data = await state.get_data()
    registered_platforms = data.get('registered_platforms', [])
    
    if platform not in PLATFORMS:
        await message.answer(
            "❌ Неизвестная платформа. Выбери из списка:",
            reply_markup=get_platforms_keyboard(registered_platforms)
        )
        return
    
    if platform in registered_platforms:
        await message.answer(
            "❌ Ты уже зарегистрировал профиль на этой платформе.\n\n"
            "Выбери другую:",
            reply_markup=get_platforms_keyboard(registered_platforms)
        )
        return
    
    await state.update_data(current_platform=platform)
    
    # Отправляем правила
    await message.answer(
        "📋 **ПРАВИЛА РЕГИСТРАЦИИ ПРОФИЛЯ**\n\n"
        "Здесь правила",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Отправляем пример скрина
    example_path = PLATFORM_EXAMPLES.get(platform)
    
    if example_path and os.path.exists(example_path):
        try:
            photo = FSInputFile(example_path)
            await message.answer_photo(
                photo=photo,
                caption=f"📸 Пример скрина профиля в {platform}\n\n"
                        "Теперь отправь свой скрин профиля:"
            )
        except:
            await message.answer(
                f"📸 Отправь скрин своего профиля в {platform}:"
            )
    else:
        await message.answer(
            f"📸 Отправь скрин своего профиля в {platform}:"
        )
    
    await state.set_state(RegistrationStates.waiting_for_screenshot)

# ============================================
# ДОБАВЛЕНИЕ ПРОФИЛЯ - СКРИНШОТ
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_screenshot), F.photo)
async def screenshot_handler(message: Message, state: FSMContext):
    # Сохраняем file_id фото
    photo_id = message.photo[-1].file_id
    await state.update_data(screenshot=photo_id)
    
    data = await state.get_data()
    platform = data['current_platform']
    
    await message.answer(
        f"📝 Введи название аккаунта в {platform}\n\n"
        "⚠️ Пиши точно как на скрине (включая знаки препинания, пробелы и регистр букв):",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await state.set_state(RegistrationStates.waiting_for_account_name)

@router.message(StateFilter(RegistrationStates.waiting_for_screenshot))
async def screenshot_not_photo_handler(message: Message, state: FSMContext):
    await message.answer("❌ Пожалуйста, отправь именно фото (скриншот).")

# ============================================
# ДОБАВЛЕНИЕ ПРОФИЛЯ - НАЗВАНИЕ АККАУНТА
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_account_name))
async def account_name_handler(message: Message, state: FSMContext):
    account_name = message.text
    
    await state.update_data(account_name=account_name)
    
    data = await state.get_data()
    platform = data['current_platform']
    
    await message.answer(
        f"✅ Название аккаунта: {account_name}\n\n"
        f"Всё правильно?",
        reply_markup=get_yes_no_keyboard()
    )
    
    await state.set_state(RegistrationStates.waiting_for_account_name_confirmation)

# ============================================
# ДОБАВЛЕНИЕ ПРОФИЛЯ - ПОДТВЕРЖДЕНИЕ НАЗВАНИЯ
# ============================================

@router.message(F.text == "Да", StateFilter(RegistrationStates.waiting_for_account_name_confirmation))
async def account_name_confirmed_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    user_gender = data.get('gender', '')
    
    await message.answer(
        "⚠️ **ВАЖНО!**\n\n"
        f"Пол профиля должен соответствовать твоему полу ({user_gender})\n\n"
        "Выбери пол профиля:",
        reply_markup=get_gender_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(RegistrationStates.waiting_for_account_gender)

@router.message(F.text == "Нет", StateFilter(RegistrationStates.waiting_for_account_name_confirmation))
async def account_name_rejected_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    platform = data['current_platform']
    
    await message.answer(
        f"📝 Введи название аккаунта в {platform} заново:\n\n"
        "⚠️ Пиши точно как на скрине:",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await state.set_state(RegistrationStates.waiting_for_account_name)

# ============================================
# ДОБАВЛЕНИЕ ПРОФИЛЯ - ПОЛ ПРОФИЛЯ
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_account_gender))
async def account_gender_handler(message: Message, state: FSMContext):
    if message.text not in ["👨 Парень", "👩 Девушка"]:
        await message.answer("❌ Пожалуйста, выбери пол из предложенных вариантов.")
        return
    
    account_gender = message.text
    data = await state.get_data()
    user_gender = data.get('gender', '')
    
    # Проверяем соответствие пола
    if account_gender != user_gender:
        await message.answer(
            f"❌ Пол профиля ({account_gender}) не совпадает с твоим полом ({user_gender})!\n\n"
            "Выбери правильный пол:",
            reply_markup=get_gender_keyboard()
        )
        return
    
    # Сохраняем профиль в БД
    user_id = message.from_user.id
    platform = data['current_platform']
    account_name = data['account_name']
    screenshot = data['screenshot']
    
    await add_account(
        user_id=user_id,
        platform=platform,
        account_name=account_name,
        screenshot=screenshot,
        gender=account_gender
    )
    
    # Добавляем платформу в список зарегистрированных
    registered_platforms = data.get('registered_platforms', [])
    registered_platforms.append(platform)
    await state.update_data(registered_platforms=registered_platforms)
    
    await message.answer(
        f"✅ Профиль в {platform} добавлен!\n\n"
        "❓ Хочешь зарегистрировать профиль на другой площадке?",
        reply_markup=get_yes_no_keyboard()
    )
    
    await state.set_state(RegistrationStates.waiting_for_more_platforms)

# ============================================
# ДОБАВЛЕНИЕ ПРОФИЛЯ - ЕЩЁ ПЛАТФОРМЫ?
# ============================================

@router.message(F.text == "Да", StateFilter(RegistrationStates.waiting_for_more_platforms))
async def more_platforms_yes_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    registered_platforms = data.get('registered_platforms', [])
    
    if len(registered_platforms) >= len(PLATFORMS):
        await message.answer(
            "✅ Ты зарегистрировал профили на всех доступных платформах!\n\n"
            "Завершаем регистрацию...",
            reply_markup=ReplyKeyboardRemove()
        )
        await finish_registration(message, state)
        return
    
    await message.answer(
        "Выбери платформу:",
        reply_markup=get_platforms_keyboard(registered_platforms)
    )
    await state.set_state(RegistrationStates.waiting_for_platform_choice)

@router.message(F.text == "Нет", StateFilter(RegistrationStates.waiting_for_more_platforms))
async def more_platforms_no_handler(message: Message, state: FSMContext):
    await finish_registration(message, state)

async def finish_registration(message: Message, state: FSMContext):
    """Завершение регистрации и отправка на модерацию"""
    user_data = await state.get_data()
    await state.clear()
    
    await message.answer(
        "✅ Регистрация завершена!\n\n"
        "Твои данные отправлены на модерацию.\n"
        "Ожидай подтверждения от администратора.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Уведомляем админов
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)
    
    if not user:
        return
    
    admin_text = f"""
🆕 **НОВАЯ ЗАЯВКА НА РЕГИСТРАЦИЮ**

👤 Имя: {user['name']} {user['surname']}
🆔 ID: `{user_id}`
👤 Username: @{user['username']}
🚻 Пол: {user['gender']}
🌍 Регион: {user['region']}

📱 Профили:
"""
    
    accounts = user.get('accounts', [])
    for acc in accounts:
        admin_text += f"• {acc['platform']}: {acc['account_name']}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=keyboard, parse_mode="Markdown")
            
            # Отправляем скрины профилей
            for acc in accounts:
                if acc.get('screenshot'):
                    try:
                        await bot.send_photo(
                            admin_id,
                            photo=acc['screenshot'],
                            caption=f"📱 {acc['platform']}: {acc['account_name']}"
                        )
                    except:
                        pass
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

# ============================================
# МЕНЮ
# ============================================

@router.message(Command("menu"))
async def menu_handler(message: Message):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)
    
    if not user or not user.get('approved'):
        await message.answer(
            "❌ Ты не зарегистрирован или твоя заявка ещё не одобрена.\n\n"
            "Используй /start для регистрации."
        )
        return
    
    if is_admin(user_id):
        await message.answer(
            "👨‍💼 Админ-панель\n\nВыбери действие:",
            reply_markup=get_admin_menu_keyboard()
        )
    else:
        await message.answer(
            "📱 Главное меню\n\nВыбери действие:",
            reply_markup=get_main_menu_keyboard()
        )

# ============================================
# МОЙ ПРОФИЛЬ
# ============================================

@router.message(F.text == "👤 Мой профиль")
async def my_profile_handler(message: Message):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)
    
    if not user or not user.get('approved'):
        await message.answer("❌ Ты не зарегистрирован или не одобрен.")
        return
    
    profile_text = f"""
👤 **МОЙ ПРОФИЛЬ**

👤 Имя: {user['name']} {user['surname']}
🆔 ID: `{user_id}`
🚻 Пол: {user['gender']}
🌍 Регион: {user['region']}

📱 Профилей добавлено: {len(user.get('accounts', []))}
"""
    
    await message.answer(profile_text, parse_mode="Markdown")

# ============================================
# МОИ ПРОФИЛИ
# ============================================

@router.message(F.text == "📋 Мои профили")
async def my_accounts_handler(message: Message):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)
    
    if not user or not user.get('approved'):
        await message.answer("❌ Ты не зарегистрирован или не одобрен.")
        return
    
    accounts = user.get('accounts', [])
    
    if not accounts:
        await message.answer("📭 У тебя пока нет добавленных профилей.")
        return
    
    text = "📋 **Твои профили:**\n\n"
    for acc in accounts:
        text += f"• **{acc['platform']}**: {acc['account_name']}\n"
    
    await message.answer(text, parse_mode="Markdown")

# ============================================
# ДОБАВИТЬ ПРОФИЛЬ (ДЛЯ ЗАРЕГИСТРИРОВАННЫХ)
# ============================================

@router.message(F.text == "➕ Добавить профиль")
async def add_profile_start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)
    
    if not user or not user.get('approved'):
        await message.answer("❌ Ты не зарегистрирован или не одобрен.")
        return
    
    # Получаем уже зарегистрированные платформы
    accounts = user.get('accounts', [])
    registered_platforms = [acc['platform'] for acc in accounts]
    
    await state.update_data(
        name=user['name'],
        surname=user['surname'],
        gender=user['gender'],
        region=user['region'],
        registered_platforms=registered_platforms
    )
    
    await message.answer(
        "Выбери платформу:",
        reply_markup=get_platforms_keyboard(registered_platforms)
    )
    await state.set_state(RegistrationStates.waiting_for_platform_choice)

# ============================================
# ПОИСК ПРОФИЛЕЙ
# ============================================

@router.message(F.text == "🔍 Найти профили")
async def search_start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user_by_id(user_id)
    
    if not user or not user.get('approved'):
        await message.answer("❌ Ты не зарегистрирован или не одобрен.")
        return
    
    await message.answer(
        "Выбери платформу для поиска:",
        reply_markup=get_platforms_keyboard()
    )
    await state.set_state(SearchStates.waiting_for_platform)

@router.message(StateFilter(SearchStates.waiting_for_platform))
async def search_platform_handler(message: Message, state: FSMContext):
    platform = message.text
    
    if platform not in PLATFORMS:
        await message.answer(
            "❌ Неизвестная платформа. Выбери из списка:",
            reply_markup=get_platforms_keyboard()
        )
        return
    
    await state.clear()
    
    # TODO: Здесь должен быть код поиска в базе данных
    await message.answer(
        f"🔍 Поиск профилей в {platform}...\n\n"
        "📭 Пока нет профилей в этой платформе.",
        reply_markup=get_main_menu_keyboard() if not is_admin(message.from_user.id) else get_admin_menu_keyboard()
    )

# ============================================
# ПОМОЩЬ
# ============================================

@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def help_handler(message: Message):
    help_text = """
ℹ️ **ПОМОЩЬ**

**Основные команды:**
/start - Начать регистрацию
/menu - Главное меню
/help - Эта справка

**Функции бота:**
🔍 Найти профили - Поиск по платформам
➕ Добавить профиль - Добавить новый профиль
📋 Мои профили - Список твоих профилей
👤 Мой профиль - Информация о тебе

**Поддержка:**
По всем вопросам пиши @admin
"""
    await message.answer(help_text, parse_mode="Markdown")

# ============================================
# АДМИН - ЗАЯВКИ
# ============================================

@router.message(F.text == "👥 Заявки на регистрацию")
async def pending_users_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    pending = await get_pending_users()
    
    if not pending:
        await message.answer("📭 Нет новых заявок.")
        return
    
    for user in pending:
        user_id = user['user_id']
        
        text = f"""
🆕 **ЗАЯВКА НА РЕГИСТРАЦИЮ**

👤 Имя: {user['name']} {user['surname']}
🆔 ID: `{user_id}`
👤 Username: @{user['username']}
🚻 Пол: {user['gender']}
🌍 Регион: {user['region']}

📱 Профили:
"""
        accounts = user.get('accounts', [])
        for acc in accounts:
            text += f"• {acc['platform']}: {acc['account_name']}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        
        # Отправляем скрины
        for acc in accounts:
            if acc.get('screenshot'):
                try:
                    await message.answer_photo(
                        photo=acc['screenshot'],
                        caption=f"📱 {acc['platform']}: {acc['account_name']}"
                    )
                except:
                    pass

@router.callback_query(F.data.startswith("approve_"))
async def approve_user_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав")
        return
    
    user_id = int(callback.data.split("_")[1])
    await approve_user_db(user_id)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ **ОДОБРЕНО**",
        parse_mode="Markdown"
    )
    
    try:
        await bot.send_message(
            user_id,
            "🎉 Поздравляем! Твоя заявка одобрена!\n\n"
            "Используй /menu для доступа к функциям бота."
        )
    except:
        pass
    
    await callback.answer("✅ Пользователь одобрен")

@router.callback_query(F.data.startswith("reject_"))
async def reject_user_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав")
        return
    
    user_id = int(callback.data.split("_")[1])
    await reject_user_db(user_id)
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ **ОТКЛОНЕНО**",
        parse_mode="Markdown"
    )
    
    try:
        await bot.send_message(
            user_id,
            "❌ К сожалению, твоя заявка отклонена.\n\n"
            "Для повторной регистрации напиши /start"
        )
    except:
        pass
    
    await callback.answer("❌ Пользователь отклонён")

# ============================================
# АДМИН - СТАТИСТИКА
# ============================================

@router.message(F.text == "📊 Статистика")
async def stats_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    # TODO: Реализовать статистику из БД
    await message.answer(
        "📊 **СТАТИСТИКА БОТА**\n\n"
        "👥 Всего пользователей: 0\n"
        "✅ Одобренных: 0\n"
        "⏳ На модерации: 0\n"
        "📱 Всего профилей: 0",
        parse_mode="Markdown"
    )

# ============================================
# WEB SERVER
# ============================================

async def health_check(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"🌐 Web server started on port {port}")

# ============================================
# ЗАПУСК
# ============================================

async def main():
    await init_db()
    await start_web_server()
    
    bot_info = await bot.get_me()
    print(f"🤖 Бот: @{bot_info.username} | ID: {bot_info.id}")
    print("✅ Бот запущен...")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Бот остановлен")
