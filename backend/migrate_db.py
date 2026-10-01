"""Apply PostgreSQL-only compatibility changes for an existing HumanTwin DB."""

import asyncio

from sqlalchemy import text

from backend.database import Base, engine
from backend import models  # noqa: F401 - registers ORM tables on Base.metadata


async def migrate() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
            "twin_name_customized BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        await connection.execute(text(
            "ALTER TABLE timetable ADD COLUMN IF NOT EXISTS specific_date TIMESTAMP NULL"
        ))
        await connection.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS progress INTEGER NOT NULL DEFAULT 0"))
        await connection.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS next_step TEXT NULL"))
        await connection.execute(text("ALTER TABLE goals ADD COLUMN IF NOT EXISTS milestones JSONB NOT NULL DEFAULT '[]'::jsonb"))
        await connection.execute(text("""
            UPDATE users
            SET twin_name = 'Echo'
            WHERE trim(COALESCE(twin_name, '')) = ''
               OR (NOT COALESCE(twin_name_customized, FALSE)
                   AND lower(trim(twin_name)) = lower(trim(name)))
        """))
    await engine.dispose()
    print("PostgreSQL schema is up to date.")


if __name__ == "__main__":
    asyncio.run(migrate())
