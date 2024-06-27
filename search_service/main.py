from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional, List
from pydantic import BaseModel
from redis import Redis
from faker import Faker
import os
import json

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

engine = create_engine(DATABASE_URL, echo=True, future=True)
redis_client = Redis.from_url(REDIS_URL)

app = FastAPI()
fake = Faker()

class Flight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    from_: str = Field(index=True)
    to: str = Field(index=True)
    flight_date: str = Field(index=True)
    price: float
    booking_limit: int
    oversell_limit: int
    current_booking: int
    is_open: bool
    is_consumer_initialized: bool

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def add_fake_data(session: Session):
    for _ in range(25):
        flight = Flight(
            from_=fake.city(),
            to=fake.city(),
            flight_date=fake.date_this_year(),
            price=fake.random_number(digits=5),
            booking_limit=fake.random_number(digits=3),
            oversell_limit=fake.random_number(digits=3),
            current_booking=fake.random_number(digits=3),
            is_open=fake.boolean(),
            is_consumer_initialized=fake.boolean()
        )
        session.add(flight)
    session.commit()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    with Session(engine) as session:
        if not session.exec(select(Flight)).all():
            add_fake_data(session)

class FlightFilter(BaseModel):
    from_: Optional[str] = None
    to: Optional[str] = None
    flight_date: Optional[str] = None
    page: int = 1

@app.get("/flights", response_model=List[Flight])
def get_flights(filter: FlightFilter = Depends()):
    cache_key = f"flights:{filter.from_}:{filter.to}:{filter.flight_date}:{filter.page}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)
    
    with Session(engine) as session:
        query = select(Flight)
        if filter.from_:
            query = query.where(Flight.from_ == filter.from_)
        if filter.to:
            query = query.where(Flight.to == filter.to)
        if filter.flight_date:
            query = query.where(Flight.flight_date == filter.flight_date)

        query = query.offset((filter.page - 1) * 5).limit(5)
        results = session.exec(query).all()
    
    redis_client.set(cache_key, json.dumps([result.dict() for result in results]), ex=300) # Cache for 5 minutes
    return results
