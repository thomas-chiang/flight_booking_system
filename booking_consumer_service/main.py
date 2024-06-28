from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
import aioredis
import aio_pika
import json
import logging
from typing import Optional
import os
import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=True, future=True)

app = FastAPI()

redis = aioredis.from_url(REDIS_URL, decode_responses=True)

class Flight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    from_: str = Field(index=True)
    to: str = Field(index=True)
    flight_date: datetime.date = Field(index=True)
    price: float
    booking_limit: int
    oversell_limit: int
    current_booking: int

class Booking(SQLModel, table=True):
    id: str = Field(primary_key=True)
    customer_id: int
    flight_id: int
    status: str

class BookingRequest(BaseModel):
    flight_id: int

@app.post("/booking")
async def book(request: BookingRequest, background_tasks: BackgroundTasks):
    flight_id = request.flight_id
    
    processing_key = f"flight_{flight_id}"
    if await redis.exists(processing_key):
        raise HTTPException(status_code=409, detail="Booking is already being processed for this flight.")
    
    await redis.set(processing_key, 1)
    
    flight = await get_flight_info(flight_id)
    background_tasks.add_task(process_booking, flight)
    
    return {"message": "Booking request received. Processing..."}

async def get_flight_info(flight_id: int) -> Optional[Flight]:
    async with AsyncSession(engine) as session:
        flight = (await session.execute(select(Flight).where(Flight.id == flight_id))).one_or_none()
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found.") 
        return flight

async def process_booking(flight: Flight):
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()

    queue_name = str(flight.id)
    current_booking = flight.current_booking
    booking_limit = flight.booking_limit
    oversell_limit = flight.oversell_limit

    await channel.declare_queue(queue_name, durable=True)

    async with channel.iterator(queue_name) as queue:
        async for message in queue:
            async with message.process():
                body = message.body.decode()
                message_data = json.loads(body)
                customer_id = message_data.get('customer_id')
                booking_id = message_data.get('booking_id')
                
                async with AsyncSession(engine) as session:
                    async with session.begin():
                        if current_booking < booking_limit:
                            status = "booked"
                            current_booking += 1
                        elif current_booking < oversell_limit:
                            status = "oversold"
                            current_booking += 1
                        else:
                            status = "oversold"
                        
                        booking = Booking(customer_id=customer_id, flight_id=flight.id, status=status, id=booking_id)
                        session.add(booking)

                    await session.commit()

    await update_flight_info(flight.id, current_booking)
    await redis.delete(f"flight_{flight.id}")
    await connection.close()

async def update_flight_info(flight_id: int, current_booking: int):
    async with AsyncSession(engine) as session:
        async with session.begin():
            flight = (await session.execute(select(Flight).where(Flight.id == flight_id))).one_or_none()
            if flight:
                flight.current_booking = current_booking
                session.add(flight)
            await session.commit()

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
