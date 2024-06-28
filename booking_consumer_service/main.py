from fastapi import FastAPI, HTTPException
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
import asyncio
from aio_pika import connect, IncomingMessage

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
async def book(request: BookingRequest):
    flight_id = request.flight_id

    processing_key = flight_id
    if await redis.exists(processing_key):
        raise HTTPException(status_code=409, detail="Booking is already being processed for this flight.")

    flight = await get_flight_info(flight_id)

    await process_booking(flight)

    return {"message": "Booking request received. Processing..."}

async def get_flight_info(flight_id: int) -> Optional[Flight]:
    async with AsyncSession(engine) as session:
        flight = (await session.execute(select(Flight).where(Flight.id == flight_id))).one_or_none()
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found.")
        return flight

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

async def process_booking(flight: Flight):
    queue_name = str(flight.id)
    current_booking = flight.current_booking
    booking_limit = flight.booking_limit
    oversell_limit = flight.oversell_limit

    connection = await connect(RABBITMQ_URL)
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(queue_name, durable=True, exclusive=True)

        await redis.set(queue_name, 1)

        while True:
            message = await queue.get(timeout=300)
            if message is None:
                print("No message received for 5 minutes. Stopping...")
                await redis.delete(queue_name)
                await update_flight_info(flight.id, current_booking)
                break

            message_data = json.loads(message.body.decode())
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
                        status = "failed"

                    booking = Booking(customer_id=customer_id, flight_id=flight.id, status=status, id=booking_id)
                    session.add(booking)

                await session.commit()
        
        

