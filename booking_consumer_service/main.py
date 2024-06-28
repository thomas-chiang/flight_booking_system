import asyncio
import aio_pika
import aioredis
import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from typing import Optional
from datetime import date
from faker import Faker
from contextlib import asynccontextmanager
import sys
import aiormq

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=True, future=True)

app = FastAPI()

fake = Faker()

redis = aioredis.from_url(REDIS_URL, decode_responses=True)


class Flight(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    from_place: str = Field(index=True)
    to_place: str = Field(index=True)
    flight_date: date = Field(index=True)
    price: float
    booking_limit: int
    oversell_limit: int
    current_booking: int


class Booking(SQLModel, table=True):
    id: str = Field(primary_key=True)
    customer_id: str
    flight_id: str
    status: str


class BookingRequest(BaseModel):
    flight_id: str


@app.post("/booking_consuming")
async def book(request: BookingRequest):
    flight_id = request.flight_id

    processing_key = f"processing:{flight_id}"
    if await redis.exists(processing_key):
        raise HTTPException(
            status_code=409,
            detail="Booking is already being processed for this flight.",
        )

    flight = await get_flight_info(flight_id)
    await process_booking(flight)

    return


async def get_flight_info(flight_id: int) -> Optional[Flight]:
    async with AsyncSession(engine) as session:
        flight = (
            await session.execute(select(Flight).where(Flight.id == flight_id))
        ).scalar_one_or_none()
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found.")
        return flight


async def update_flight_info(flight_id: int, current_booking: int):
    async with AsyncSession(engine) as session:
        async with session.begin():
            flight = (
                await session.execute(select(Flight).where(Flight.id == flight_id))
            ).scalar_one_or_none()
            if flight:
                flight.current_booking = current_booking
                session.add(flight)
            await session.commit()


@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Flight))
        if not result.scalars().all():
            await add_fake_data(session)

    await push_initial_fake_message_to_rabbitmq()


@asynccontextmanager
async def redis_lock(key: str):
    lock_acquired = await redis.set(key, 1, nx=True)
    try:
        if lock_acquired:
            yield
        else:
            raise HTTPException(status_code=409, detail="Resource is locked.")
    finally:
        if lock_acquired:
            await redis.delete(key)


async def process_booking(flight: Flight):
    queue_name = str(flight.id)
    lock_key = queue_name

    async with redis_lock(lock_key):
        current_booking = flight.current_booking
        booking_limit = flight.booking_limit
        oversell_limit = flight.oversell_limit
        connection = await aio_pika.connect_robust(RABBITMQ_URL)

        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(queue_name, durable=True)

            empty_queue_counter = 0
            max_retries = 15

            while True:
                message = None
                try:
                    message = await queue.get(
                        timeout=1
                    )  # Set a timeout for the get method
                except aio_pika.exceptions.QueueEmpty as e:
                    empty_queue_counter += 1
                    if empty_queue_counter >= max_retries:
                        print(f"No message received after {max_retries} attempts. Stopping...")
                        sys.stdout.flush()
                        await update_flight_info(flight.id, current_booking)
                        break
                    print("QueueEmpty, waiting for message")
                    sys.stdout.flush()
                    await asyncio.sleep(1)
                    continue

                if message is not None:
                    message_data = json.loads(message.body.decode())
                    customer_id = message_data.get("customer_id")
                    booking_id = message_data.get("booking_id")

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

                            booking = Booking(
                                customer_id=customer_id,
                                flight_id=flight.id,
                                status=status,
                                id=booking_id,
                            )
                            session.add(booking)
                            print("Booked Successfully for ", booking)

                        await session.commit()
                    await message.ack()
                    empty_queue_counter = (
                        0  # Reset the counter after successfully processing a message
                    )


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


async def push_initial_fake_message_to_rabbitmq():
    max_retries = 10  # Maximum number of retries
    retry_delay = 5
    for attempt in range(max_retries):
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
        except aiormq.exceptions.AMQPConnectionError as e:
            print(
                f"Connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds..."
            )
            sys.stdout.flush()
            await asyncio.sleep(retry_delay)

    async with connection:
        channel = await connection.channel()
        queue_name = "sample_flight_id_0"
        message = {
            "booking_id": "sample_booking_id",
            "customer_id": "sample_customer_id",
        }
        message_body = json.dumps(message).encode()

        queue = await channel.declare_queue(queue_name, durable=True)

        try:
            existing_message = await queue.get(timeout=1)
            # If we get a message, it means the queue is not empty
            print(f"Queue {queue_name} is not empty. Message already exists.")
            sys.stdout.flush()
            await existing_message.reject(requeue=True)
            return
        except aio_pika.exceptions.QueueEmpty:
            # If we get a QueueEmpty exception, it means the queue is empty
            print(f"Queue {queue_name} is empty. Publishing new message.")
            sys.stdout.flush()

        # If the message does not exist, publish it
        await channel.default_exchange.publish(
            aio_pika.Message(body=message_body),
            routing_key=queue_name,
        )
        print(f"Message sent to {queue_name}: {message}")
