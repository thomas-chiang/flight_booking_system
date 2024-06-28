from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis.asyncio as redis
import aio_pika
import asyncio
import aiohttp
import os
import sys
import uuid

app = FastAPI()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
BOOKING_CONSUMER_URL = os.getenv("BOOKING_CONSUMER_URL", "http://localhost:8001/")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

class BookingRequest(BaseModel):
    flight_id: str
    customer_id: str

@app.post("/booking")
async def create_booking(request: BookingRequest):
    flight_id = request.flight_id
    customer_id = request.customer_id
    booking_id = str(uuid.uuid4())

    await asyncio.gather(
        send_to_queue(flight_id, customer_id, booking_id),
        initialize_consumer(flight_id)
    )

    return {"status": "booking request processed", "booking_id": booking_id}

async def send_to_queue(flight_id, customer_id, booking_id):
    connection = await aio_pika.connect_robust(f"amqp://guest:guest@{RABBITMQ_HOST}/")
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(flight_id, aio_pika.ExchangeType.TOPIC)
        message_body = customer_id + "_" + booking_id
        message = aio_pika.Message(body=message_body.encode())
        await exchange.publish(message, routing_key=flight_id)

async def initialize_consumer(flight_id):
    timeout = 10
    start_time = asyncio.get_event_loop().time()
    
    while not await r.exists(flight_id):
        if asyncio.get_event_loop().time() - start_time > timeout:
            print(f"Timeout reached: {timeout} seconds")
            sys.stdout.flush()
            break

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(BOOKING_CONSUMER_URL, json={"flight_id": flight_id}):
                    pass
            except Exception as e:
                print(e)
                sys.stdout.flush()
        
        await asyncio.sleep(1)
