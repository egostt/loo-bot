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

PLATFORMS = {
    "Instagram": "https://instagram.com/username",
    "TikTok": "https://tiktok.com/@username",
    "YouTube": "https://youtube.com/@username",
    "Telegram": "https://t.me/username",
    "Twitter": "https://twitter.com/username",
    "VK": "https://vk.com/username",
    "Twitch": "https://twitch.tv/username",
    "OnlyFans": "https://onlyfans.com/username",
    "Fansly": "https://fansly.com/username",
    "Другое": "Введи полную ссылку"
}

# ============================================
# СОСТОЯНИЯ FSM
# ============================================

class RegistrationStates(StatesGroup):
    waiting_for_gender = State()
    waiting_for_platform = State()
    waiting_for_link = State()
    waiting_for_more_platforms = State()

class SearchStates(StatesGroup):
    waiting_for_platform = State()

# ============================================
# КЛАВИАТУРЫ
# ============================================

def get_platforms_keyboard():
    buttons = []
    platforms_list = list(PLATFORMS.keys())
    
    for i in range(0, len(platforms_list), 2):
        row = [KeyboardButton(text=platforms_list[i])]
        if i + 1 < len(platforms_list):
            row.append(KeyboardButton(text=platforms_list[i + 1]))
        buttons.append(row)
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_more_platforms_keyboard():
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
            [KeyboardButton(text="➕ Добавить аккаунт"), KeyboardButton(text="📋 Мои аккаунты")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

def get_admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти профили")],
            [KeyboardButton(text="➕ Добавить аккаунт"), KeyboardButton(text="📋 Мои аккаунты")],
            [KeyboardButton(text="👥 Заявки на регистрацию"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def validate_link(platform: str, link: str) -> bool:
    if platform == "Другое":
        return link.startswith("http://") or link.startswith("https://")
    
    platform_domains = {
        "Instagram": ["instagram.com", "instagr.am"],
        "TikTok": ["tiktok.com"],
        "YouTube": ["youtube.com", "youtu.be"],
        "Telegram": ["t.me", "telegram.me"],
        "Twitter": ["twitter.com", "x.com"],
        "VK": ["vk.com"],
        "Twitch": ["twitch.tv"],
        "OnlyFans": ["onlyfans.com"],
        "Fansly": ["fansly.com"]
    }
    
    domains = platform_domains.get(platform, [])
    return any(domain in link.lower() for domain in domains)

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    user = await get_user_accounts(user_id)
    
    if user and user.get('approved'):
        # Пользователь уже одобрен
        await message.answer(
            "🎉 Ты уже зарегистрирован!\n\n"
            "Используй /menu для доступа к функциям бота.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    if user and not user.get('approved'):
        # Заявка на рассмотрении
        await message.answer(
            "⏳ Твоя заявка на рассмотрении у администратора.\n\n"
            "Ожидай одобрения!",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    # Новый пользователь - показываем правила СРАЗУ
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
    
    # СНАЧАЛА СПРАШИВАЕМ ПОЛ
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨 Парень"), KeyboardButton(text="👩 Девушка")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.answer(
        "Выбери свой пол:",
        reply_markup=keyboard
    )
    
    await state.set_state(RegistrationStates.waiting_for_gender)
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

@router.message(StateFilter(RegistrationStates.waiting_for_gender))
async def gender_handler(message: Message, state: FSMContext):
    if message.text not in ["👨 Парень", "👩 Девушка"]:
        await message.answer("Пожалуйста, выбери пол из предложенных вариантов.")
        return
    
    # Сохраняем пол
    await state.update_data(gender=message.text)
    
    # ТЕПЕРЬ ПОКАЗЫВАЕМ ПЛАТФОРМЫ
    await message.answer(
        "Выбери платформу, на которой у тебя есть профиль:",
        reply_markup=get_platforms_keyboard()
    )
    
    await state.set_state(RegistrationStates.waiting_for_platform)

@router.message(Command("menu"))
async def menu_handler(message: Message):
    user_id = message.from_user.id
    user = await get_user_accounts(user_id)
    
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
➕ Добавить аккаунт - Добавить новый профиль
📋 Мои аккаунты - Список твоих профилей

**Поддержка:**
По всем вопросам пиши @admin
"""
    await message.answer(help_text, parse_mode="Markdown")

# ============================================
# РЕГИСТРАЦИЯ - ВЫБОР ПЛАТФОРМЫ
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_platform))
async def platform_handler(message: Message, state: FSMContext):
    platform = message.text
    
    if platform not in PLATFORMS:
        await message.answer(
            "❌ Неизвестная платформа. Выбери из списка:",
            reply_markup=get_platforms_keyboard()
        )
        return
    
    await state.update_data(current_platform=platform)
    
    example = PLATFORMS[platform]
    await message.answer(
        f"📝 Отправь ссылку на свой профиль в {platform}\n\n"
        f"Пример: {example}",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await state.set_state(RegistrationStates.waiting_for_link)

# ============================================
# РЕГИСТРАЦИЯ - ВВОД ССЫЛКИ
# ============================================

@router.message(StateFilter(RegistrationStates.waiting_for_link))
async def link_handler(message: Message, state: FSMContext):
    link = message.text.strip()
    data = await state.get_data()
    platform = data.get('current_platform')
    
    if not validate_link(platform, link):
        await message.answer(
            f"❌ Неправильная ссылка для {platform}\n\n"
            f"Пример: {PLATFORMS[platform]}\n\n"
            "Попробуй ещё раз:"
        )
        return
    
    # Сохраняем аккаунт
    accounts = data.get('accounts', [])
    accounts.append({'platform': platform, 'link': link})
    await state.update_data(accounts=accounts)
    
    # Добавляем в базу данных
    user_id = message.from_user.id
    username = message.from_user.username or "Без username"
    gender = data.get('gender', 'Не указан')
    
    # Если это первый аккаунт - создаём пользователя
    if len(accounts) == 1:
        await add_user(user_id, username, gender)
    
    # Добавляем аккаунт
    await add_account(user_id, platform, link)
    
    await message.answer(
        "✅ Аккаунт добавлен!\n\n"
        "❓ Есть ещё платформы, на которых у тебя есть профиль?",
        reply_markup=get_more_platforms_keyboard()
    )
    
    await state.set_state(RegistrationStates.waiting_for_more_platforms)

# ============================================
# РЕГИСТРАЦИЯ - ЕЩЁ ПЛАТФОРМЫ?
# ============================================

@router.message(F.text == "Да", StateFilter(RegistrationStates.waiting_for_more_platforms))
async def more_platforms_yes_handler(message: Message, state: FSMContext):
    await message.answer(
        "Выбери платформу:",
        reply_markup=get_platforms_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_platform)

@router.message(F.text == "Нет", StateFilter(RegistrationStates.waiting_for_more_platforms))
async def no_more_platforms_handler(message: Message, state: FSMContext):
    user_data = await state.get_data()
    await state.clear()
    
    await message.answer(
        "✅ Регистрация завершена!\n\n"
        "⏳ Твоя заявка отправлена на модерацию.\n"
        "Ожидай одобрения администратора.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Уведомляем админов
    user_id = message.from_user.id
    username = message.from_user.username or "Без username"
    
    admin_text = f"""
🆕 **НОВАЯ ЗАЯВКА НА РЕГИСТРАЦИЮ**

👤 Пользователь: @{username}
🆔 ID: `{user_id}`
👤 Пол: {user_data.get('gender', 'Не указан')}

📱 Аккаунты:
"""
    
    accounts = user_data.get('accounts', [])
    for acc in accounts:
        admin_text += f"• {acc['platform']}: {acc['link']}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

# ============================================
# ДОБАВЛЕНИЕ АККАУНТА (ДЛЯ ЗАРЕГИСТРИРОВАННЫХ)
# ============================================

@router.message(F.text == "➕ Добавить аккаунт")
async def add_account_start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user_accounts(user_id)
    
    if not user or not user.get('approved'):
        await message.answer("❌ Ты не зарегистрирован или не одобрен.")
        return
    
    await message.answer(
        "Выбери платформу:",
        reply_markup=get_platforms_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_platform)

# ============================================
# МОИ АККАУНТЫ
# ============================================

@router.message(F.text == "📋 Мои аккаунты")
async def my_accounts_handler(message: Message):
    user_id = message.from_user.id
    user = await get_user_accounts(user_id)
    
    if not user or not user.get('approved'):
        await message.answer("❌ Ты не зарегистрирован или не одобрен.")
        return
    
    accounts = user.get('accounts', [])
    
    if not accounts:
        await message.answer("📭 У тебя пока нет добавленных аккаунтов.")
        return
    
    text = "📋 **Твои аккаунты:**\n\n"
    for acc in accounts:
        text += f"• **{acc['platform']}**: {acc['link']}\n"
    
    await message.answer(text, parse_mode="Markdown")

# ============================================
# ПОИСК ПРОФИЛЕЙ
# ============================================

@router.message(F.text == "🔍 Найти профили")
async def search_start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user_accounts(user_id)
    
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
    
    # Здесь должен быть код поиска в базе данных
    # Пока заглушка
    await message.answer(
        f"🔍 Поиск профилей в {platform}...\n\n"
        "📭 Пока нет профилей в этой платформе.",
        reply_markup=get_main_menu_keyboard() if not is_admin(message.from_user.id) else get_admin_menu_keyboard()
    )

# ============================================
# АДМИН - ЗАЯВКИ НА РЕГИСТРАЦИЮ
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
        username = user['username']
        gender = user['gender']
        accounts = user['accounts']
        
        text = f"""
🆕 **ЗАЯВКА НА РЕГИСТРАЦИЮ**

👤 Пользователь: @{username}
🆔 ID: `{user_id}`
👤 Пол: {gender}

📱 Аккаунты:
"""
        for acc in accounts:
            text += f"• {acc['platform']}: {acc['link']}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

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
    
    # Здесь должна быть статистика из базы данных
    await message.answer(
        "📊 **СТАТИСТИКА БОТА**\n\n"
        "👥 Всего пользователей: 0\n"
        "✅ Одобренных: 0\n"
        "⏳ На модерации: 0\n"
        "📱 Всего аккаунтов: 0",
        parse_mode="Markdown"
    )

# ============================================
# WEB SERVER (ДЛЯ RENDER)
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
# ЗАПУСК БОТА
# ============================================

async def main():
    # Инициализация базы данных
    await init_db()
    
    # Запуск веб-сервера
    await start_web_server()
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    print(f"🤖 Бот: @{bot_info.username} | ID: {bot_info.id}")
    print("✅ Бот запущен...")
    
    # Запуск polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Бот остановлен")
