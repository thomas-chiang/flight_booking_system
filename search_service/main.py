from fastapi import FastAPI, Depends
from sqlmodel import SQLModel, Field, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from typing import Optional, List
from pydantic import BaseModel
from redis.asyncio import Redis
from faker import Faker
import os
import json
from datetime import date

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=True, future=True)
redis_client = Redis.from_url(REDIS_URL)

app = FastAPI()
fake = Faker()


class Flight(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    from_place: str = Field(index=True)
    to_place: str = Field(index=True)
    flight_date: date = Field(index=True)
    price: float
    booking_limit: int
    oversell_limit: int
    current_booking: int


class FlightFilter(BaseModel):
    from_place: Optional[str] = None
    to_place: Optional[str] = None
    flight_date: Optional[date] = None
    page: int = 1


class FlightResponse(BaseModel):
    id: str
    from_place: str
    to_place: str
    flight_date: date
    price: float
    booking_left: int


@app.on_event("startup")
async def on_startup():
    if ENVIRONMENT != "development":
        return

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Flight))
        if not result.scalars().all():
            await add_fake_data(session)


@app.get("/flights", response_model=List[FlightResponse])
async def get_flights(filter: FlightFilter = Depends()):
    cache_key = f"flights:{filter.from_place}:{filter.to_place}:{filter.flight_date}:{filter.page}"
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)

    async with AsyncSession(engine) as session:
        query = select(Flight)
        if filter.from_place:
            query = query.where(Flight.from_place == filter.from_place)
        if filter.to_place:
            query = query.where(Flight.to_place == filter.to_place)
        if filter.flight_date:
            query = query.where(Flight.flight_date == filter.flight_date)

        query = query.offset((filter.page - 1) * 5).limit(5)
        results = (await session.execute(query)).scalars().all()

    results_as_dicts = []
    for result in results:
        booking_left = result.oversell_limit - result.current_booking
        result_dict = {
            "id": result.id,
            "from_place": result.from_place,
            "to_place": result.to_place,
            "flight_date": result.flight_date.isoformat(),
            "price": result.price,
            "booking_left": booking_left,
        }
        results_as_dicts.append(result_dict)

    await redis_client.set(
        cache_key, json.dumps(results_as_dicts), ex=5
    )  # Cache for 5 seconds
    return results_as_dicts


async def add_fake_data(session: AsyncSession):
    for i in range(25):
        current_booking = fake.random_number(digits=2)
        booking_limit = fake.random_number(digits=2) + current_booking + 1
        oversell_limit = fake.random_number(digits=2) + booking_limit + 1

        flight = Flight(
            id="sample_flight_id_" + str(i),
            from_place=fake.city(),
            to_place=fake.city(),
            flight_date=fake.date_this_year(),
            price=fake.random_number(digits=3),
            booking_limit=booking_limit,
            oversell_limit=oversell_limit,
            current_booking=current_booking,
        )
        session.add(flight)
    await session.commit()
