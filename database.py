import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, Text, DateTime, Integer, ForeignKey, Boolean, select
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)
    gender: Mapped[str] = mapped_column(Text)
    region: Mapped[str] = mapped_column(Text)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)  # ⬅️ ДОБАВЬ ЭТО
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    platform: Mapped[str] = mapped_column(Text)
    account_name: Mapped[str] = mapped_column(Text)
    account_gender: Mapped[str] = mapped_column(Text)
    screenshot_file_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных инициализирована")

async def add_user(user_id: int, first_name: str, last_name: str, gender: str, region: str):
    async with async_session_maker() as session:
        user = User(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            region=region,
            is_approved=False  # ⬅️ ПО УМОЛЧАНИЮ НЕ ОДОБРЕН
        )
        session.add(user)
        await session.commit()

async def add_account(user_id: int, platform: str, account_name: str, account_gender: str, screenshot_file_id: str):
    async with async_session_maker() as session:
        account = Account(
            user_id=user_id,
            platform=platform,
            account_name=account_name,
            account_gender=account_gender,
            screenshot_file_id=screenshot_file_id
        )
        session.add(account)
        await session.commit()

async def get_user_accounts(user_id: int):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Account.platform).where(Account.user_id == user_id)  # ⬅️ ИСПРАВЬ ЭТО
        )
        return [row[0] for row in result.fetchall()]

# Получить пользователей на модерации
async def get_pending_users():
    async with async_session_maker() as session:  # ⬅️ ИСПРАВЬ ЭТО
        result = await session.execute(
            select(User).where(User.is_approved == False)
        )
        users = result.scalars().all()
        
        users_data = []
        for user in users:
            accounts_result = await session.execute(
                select(Account).where(Account.user_id == user.user_id)  # ⬅️ ИСПРАВЬ ЭТО
            )
            accounts = accounts_result.scalars().all()
            
            users_data.append({
                "id": user.user_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "gender": user.gender,
                "region": user.region,
                "telegram_id": user.user_id,
                "accounts": [
                    {
                        "platform": acc.platform,
                        "profile_name": acc.account_name,  # ⬅️ ИСПРАВЬ ЭТО
                        "screenshot": acc.screenshot_file_id  # ⬅️ ИСПРАВЬ ЭТО
                    }
                    for acc in accounts
                ]
            })
        
        return users_data

# Одобрить пользователя
async def approve_user_db(telegram_id: int):
    async with async_session_maker() as session:  # ⬅️ ИСПРАВЬ ЭТО
        result = await session.execute(
            select(User).where(User.user_id == telegram_id)  # ⬅️ ИСПРАВЬ ЭТО
        )
        user = result.scalar_one_or_none()
        if user:
            user.is_approved = True
            await session.commit()

# Отклонить пользователя
async def reject_user_db(telegram_id: int):
    async with async_session_maker() as session:  # ⬅️ ИСПРАВЬ ЭТО
        result = await session.execute(
            select(User).where(User.user_id == telegram_id)  # ⬅️ ИСПРАВЬ ЭТО
        )
        user = result.scalar_one_or_none()
        if user:
            await session.delete(user)
            await session.commit()