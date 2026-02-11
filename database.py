import os
import asyncpg
from dotenv import load_dotenv

if os.path.exists('.env'):
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Исправляем формат URL для asyncpg
if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

async def init_db():
    """Инициализация базы данных"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Таблица пользователей
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            name TEXT,
            surname TEXT,
            gender TEXT,
            region TEXT,
            approved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Таблица профилей
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            platform TEXT,
            account_name TEXT,
            screenshot TEXT,
            gender TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    await conn.close()
    print("✅ База данных инициализирована")

async def add_user(user_id: int, username: str, name: str, surname: str, gender: str, region: str):
    """Добавление пользователя"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    await conn.execute("""
        INSERT INTO users (user_id, username, name, surname, gender, region, approved)
        VALUES ($1, $2, $3, $4, $5, $6, FALSE)
        ON CONFLICT (user_id) DO UPDATE
        SET username = $2, name = $3, surname = $4, gender = $5, region = $6
    """, user_id, username, name, surname, gender, region)
    
    await conn.close()

async def add_account(user_id: int, platform: str, account_name: str, screenshot: str, gender: str):
    """Добавление профиля"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    await conn.execute("""
        INSERT INTO accounts (user_id, platform, account_name, screenshot, gender)
        VALUES ($1, $2, $3, $4, $5)
    """, user_id, platform, account_name, screenshot, gender)
    
    await conn.close()

async def get_user_by_id(user_id: int):
    """Получение пользователя с его профилями"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    
    if not user:
        await conn.close()
        return None
    
    accounts = await conn.fetch("SELECT * FROM accounts WHERE user_id = $1", user_id)
    
    await conn.close()
    
    return {
        'user_id': user['user_id'],
        'username': user['username'],
        'name': user['name'],
        'surname': user['surname'],
        'gender': user['gender'],
        'region': user['region'],
        'approved': user['approved'],
        'accounts': [dict(acc) for acc in accounts]
    }

async def get_user_accounts(user_id: int):
    """Алиас для get_user_by_id (для обратной совместимости)"""
    return await get_user_by_id(user_id)

async def get_pending_users():
    """Получение пользователей на модерации"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    users = await conn.fetch("SELECT * FROM users WHERE approved = FALSE")
    
    result = []
    for user in users:
        accounts = await conn.fetch("SELECT * FROM accounts WHERE user_id = $1", user['user_id'])
        result.append({
            'user_id': user['user_id'],
            'username': user['username'],
            'name': user['name'],
            'surname': user['surname'],
            'gender': user['gender'],
            'region': user['region'],
            'accounts': [dict(acc) for acc in accounts]
        })
    
    await conn.close()
    return result

async def approve_user_db(user_id: int):
    """Одобрение пользователя"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET approved = TRUE WHERE user_id = $1", user_id)
    await conn.close()

async def reject_user_db(user_id: int):
    """Отклонение пользователя (удаление)"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)
    await conn.close()

async def remove_platform_from_available(user_id: int, platform: str):
    """Удаление платформы из доступных (не используется, но оставлена для совместимости)"""
    pass
