import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, Text, DateTime, Integer, ForeignKey
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
    status: Mapped[str] = mapped_column(Text, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    platform: Mapped[str] = mapped_column(Text)
    account_name: Mapped[str] = mapped_column(Text)
    account_gender: Mapped[str] = mapped_column(Text)
    screenshot_file_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
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
            region=region
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
            f"SELECT platform FROM accounts WHERE user_id = {user_id}"
        )
        return [row[0] for row in result.fetchall()]