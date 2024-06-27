from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, create_engine, Session, select
import aioredis
import pika
import json
import asyncio
import logging
from typing import Optional

DATABASE_URL = "postgresql://user:password@postgres/mydb"
REDIS_URL = "redis://redis:6379"
RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"

engine = create_engine(DATABASE_URL)

app = FastAPI()

redis = aioredis.from_url(REDIS_URL, decode_responses=True)

class Flight(SQLModel, table=True):
    id: int = Field(primary_key=True)
    from_: str
    to: str
    date: str
    price: float
    booking_limit: int
    oversell_limit: int
    current_booking: int

class Customer(SQLModel, table=True):
    id: int = Field(primary_key=True)

class Booking(SQLModel, table=True):
    id: int = Field(primary_key=True)
    customer_id: int
    flight_id: int
    status: str

class BookingRequest(BaseModel):
    flight_id: int
    customer_id: int

@app.post("/book")
async def book(request: BookingRequest, background_tasks: BackgroundTasks):
    flight_id = request.flight_id
    customer_id = request.customer_id
    
    # Check if the flight_id is being processed
    processing_key = f"processing:{flight_id}"
    if await redis.exists(processing_key):
        raise HTTPException(status_code=409, detail="Booking is already being processed for this flight.")
    
    await redis.set(processing_key, 1)
    
    try:
        flight = await get_flight_info(flight_id)
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found.")
        
        background_tasks.add_task(process_booking, flight_id, customer_id)
        return {"message": "Booking request received. Processing..."}
    finally:
        await redis.delete(processing_key)

async def get_flight_info(flight_id: int) -> Optional[Flight]:
    with Session(engine) as session:
        flight = session.exec(select(Flight).where(Flight.id == flight_id)).one_or_none()
        return flight

async def process_booking(flight_id: int, customer_id: int):
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()

    queue_name = f"booking_{flight_id}"
    channel.queue_declare(queue=queue_name)

    def callback(ch, method, properties, body):
        asyncio.run(handle_message(flight_id, customer_id, body))
        ch.basic_ack(delivery_tag=method.delivery_tag)
        ch.stop_consuming()

    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    channel.start_consuming()
    connection.close()

async def handle_message(flight_id: int, customer_id: int, message: bytes):
    data = json.loads(message)
    flight = await get_flight_info(flight_id)
    
    if not flight:
        return
    
    current_booking = flight.current_booking
    
    with Session(engine) as session:
        if current_booking < flight.booking_limit:
            status = "booked"
            current_booking += 1
        elif current_booking < flight.oversell_limit:
            status = "oversold"
            current_booking += 1
        else:
            status = "oversold"
        
        booking = Booking(customer_id=customer_id, flight_id=flight_id, status=status)
        session.add(booking)
        session.commit()
    
    await redis.set(f"current_booking:{flight_id}", current_booking)
    
    await update_flight_info(flight_id, current_booking)

async def update_flight_info(flight_id: int, current_booking: int):
    with Session(engine) as session:
        flight = session.exec(select(Flight).where(Flight.id == flight_id)).one_or_none()
        if flight:
            flight.current_booking = current_booking
            session.add(flight)
            session.commit()

    # Remove flight_id from Redis
    await redis.delete(f"current_booking:{flight_id}")

@app.on_event("startup")
async def startup_event():
    SQLModel.metadata.create_all(engine)
