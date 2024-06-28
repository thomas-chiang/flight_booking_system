from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import SQLModel, Field, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from typing import Optional, List
from pydantic import BaseModel
from redis.asyncio import Redis
from faker import Faker
import os
import json
import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=True, future=True)
redis_client = Redis.from_url(REDIS_URL)

app = FastAPI()
fake = Faker()

class Flight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    from_: str = Field(index=True)
    to: str = Field(index=True)
    flight_date: datetime.date = Field(index=True)
    price: float
    booking_limit: int
    oversell_limit: int
    current_booking: int

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def add_fake_data(session: AsyncSession):
    for _ in range(25):
        current_booking = fake.random_number(digits=2)
        booking_limit = fake.random_number(digits=2) + current_booking + 1
        oversell_limit = fake.random_number(digits=2) + booking_limit + 1

        flight = Flight(
            from_=fake.city(),
            to=fake.city(),
            flight_date=fake.date_this_year(),
            price=fake.random_number(digits=3),
            booking_limit=booking_limit,
            oversell_limit=oversell_limit,
            current_booking=current_booking,
        )
        session.add(flight)
    await session.commit()

@app.on_event("startup")
async def on_startup():
    await create_db_and_tables()
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Flight))
        if not result.scalars().all():
            await add_fake_data(session)

class FlightFilter(BaseModel):
    from_: Optional[str] = None
    to: Optional[str] = None
    flight_date: Optional[datetime.date] = None
    page: int = 1

@app.get("/flights", response_model=List[Flight])
async def get_flights(filter: FlightFilter = Depends()):
    cache_key = f"flights:{filter.from_}:{filter.to}:{filter.flight_date}:{filter.page}"
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)
    
    async with AsyncSession(engine) as session:
        query = select(Flight)
        if filter.from_:
            query = query.where(Flight.from_ == filter.from_)
        if filter.to:
            query = query.where(Flight.to == filter.to)
        if filter.flight_date:
            query = query.where(Flight.flight_date == filter.flight_date)

        query = query.offset((filter.page - 1) * 5).limit(5)
        results = (await session.execute(query)).scalars().all()
    
    # Convert date objects to strings before caching
    results_as_dicts = []
    for result in results:
        result_dict = result.dict()
        result_dict['flight_date'] = result_dict['flight_date'].isoformat()  # Convert date to string
        results_as_dicts.append(result_dict)
    
    await redis_client.set(cache_key, json.dumps(results_as_dicts), ex=5)  # Cache for 5 seconds
    return results