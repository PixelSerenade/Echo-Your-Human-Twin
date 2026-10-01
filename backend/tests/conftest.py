"""Use one PostgreSQL connection per test loop with asyncpg."""

from sqlalchemy.pool import NullPool

from backend.database import engine


# pytest-asyncio may create a distinct event loop for each test. A normal
# asyncpg pool retains loop-bound connections, so avoid cross-loop reuse.
engine.sync_engine.pool = NullPool(engine.sync_engine.pool._creator)
