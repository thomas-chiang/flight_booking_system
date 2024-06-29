from fastapi import FastAPI, Depends
from sqlmodel import SQLModel, Field, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy import desc
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
    price: float = Field(index=True)
    booking_limit: int
    oversell_limit: int
    current_booking: int


class FlightFilter(BaseModel):
    from_place: Optional[str] = None
    to_place: Optional[str] = None
    flight_date: Optional[date] = None
    cursor: Optional[float] = None
    cursor_type: Optional[str] = None  # "next" or "previous"
    page: int = 1
    limit: int = 5


class FlightResponse(BaseModel):
    id: str
    from_place: str
    to_place: str
    flight_date: date
    price: float
    booking_left: int


class PaginatedFlightResponse(BaseModel):
    flights: List[FlightResponse]
    previous_page_cursor: Optional[float]
    next_page_cursor: Optional[float]


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


@app.get("/flights", response_model=PaginatedFlightResponse)
async def get_flights(filter: FlightFilter = Depends()):
    cache_key = f"flights:{filter.from_place}:{filter.to_place}:{filter.flight_date}:{filter.cursor}:{filter.cursor_type}:{filter.page}:{filter.limit}"
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

        if filter.cursor:
            if filter.cursor_type == "next":
                query = query.where(Flight.price > filter.cursor).order_by(Flight.price)
            elif filter.cursor_type == "previous":
                query = query.where(Flight.price < filter.cursor).order_by(
                    desc(Flight.price)
                )
        else:
            query = query.offset((filter.page - 1) * filter.limit).order_by(
                Flight.price
            )

        query = query.limit(filter.limit)
        results = (await session.execute(query)).scalars().all()

        if filter.cursor_type == "previous":
            results.reverse()

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

    previous_page_cursor = (
        results[0].price
        if results and (filter.page > 1 or filter.cursor_type == "next")
        else None
    )
    next_page_cursor = results[-1].price if len(results) == filter.limit else None

    response = {
        "flights": results_as_dicts,
        "previous_page_cursor": previous_page_cursor,
        "next_page_cursor": next_page_cursor,
    }

    await redis_client.set(cache_key, json.dumps(response), ex=5)  # Cache for 5 seconds

    return response


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
