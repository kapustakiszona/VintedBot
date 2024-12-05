from data_base.database import engine, Base, async_session


def connection(func):
    async def wrapper(*args, **kwargs):
        async with async_session() as session:
            return await func(session, *args, **kwargs)

    return wrapper

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)