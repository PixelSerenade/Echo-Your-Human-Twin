from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from backend.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith(("postgres://", "postgresql://")):
    db_url = "postgresql+asyncpg://" + db_url.split("://", 1)[1]
if not db_url.startswith("postgresql+asyncpg://"):
    raise RuntimeError(
        "DATABASE_URL must use PostgreSQL with the asyncpg driver "
        "(postgresql+asyncpg://...). Configure backend/.env before starting the app."
    )

engine = create_async_engine(
    db_url,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
