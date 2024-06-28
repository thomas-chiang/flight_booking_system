from fastapi import FastAPI, HTTPException
from sqlmodel import Field, SQLModel, create_engine, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
import os
import aioredis

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

# Create an async engine
async_engine = create_async_engine(DATABASE_URL, echo=True, future=True)

# Create a session factory bound to the async engine
async_session_factory = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

redis = aioredis.from_url(REDIS_URL, decode_responses=True)


class Booking(SQLModel, table=True):
    id: str = Field(primary_key=True)
    customer_id: str
    flight_id: str
    status: str


app = FastAPI()


@app.on_event("startup")
async def on_startup():
    global redis
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_factory() as session:
        # Create a new Booking instance
        sample_id = "sample_id"
        statement = select(Booking).where(Booking.id == sample_id)
        result = await session.execute(statement)
        booking = result.scalar_one_or_none()
        if not booking:
            new_booking = Booking(
                id=sample_id,
                customer_id=sample_id,
                flight_id=sample_id,
                status="failed",
            )

            session.add(new_booking)
            await session.commit()
            print("Fake booking created with id 'sample_id'")


@app.get("/booking_result/{booking_id}")
async def get_booking_status(booking_id: str):
    booking_key = booking_id

    if await redis.exists(booking_key):
        raise HTTPException(status_code=404, detail="still in progress")

    async with async_session_factory() as session:
        statement = select(Booking).where(Booking.id == booking_id)
        result = await session.execute(statement)
        booking = result.scalar_one_or_none()
        if not booking:
            await redis.setex(booking_key, 3, "in progress")
            raise HTTPException(status_code=404, detail="still in progress")
        return {"status": booking.status}
