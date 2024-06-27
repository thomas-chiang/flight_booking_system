from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis.asyncio as redis
import aio_pika
import asyncio
import aiohttp
import os

app = FastAPI()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
BOOKING_CONSUMER_URL = os.getenv("BOOKING_CONSUMER_URL", "http://localhost:8001/")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

class BookingRequest(BaseModel):
    flight_id: str
    customer_id: str

@app.post("/booking")
async def create_booking(request: BookingRequest):
    flight_id = request.flight_id
    customer_id = request.customer_id

    await asyncio.gather(
        send_to_queue(flight_id, customer_id),
        check_and_update_redis(flight_id)
    )

    return {"status": "booking request processed"}

async def send_to_queue(flight_id, customer_id):
    connection = await aio_pika.connect_robust(f"amqp://guest:guest@{RABBITMQ_HOST}/")
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(flight_id, aio_pika.ExchangeType.TOPIC)
        message = aio_pika.Message(body=customer_id.encode())
        await exchange.publish(message, routing_key=flight_id)

async def check_and_update_redis(flight_id):
    if not await r.exists(flight_id):
        async with aiohttp.ClientSession() as session:
            try: 
                async with session.post(BOOKING_CONSUMER_URL, json={"flight_id": flight_id}) as response:
                    if response.status == 200:
                        await r.set(flight_id, 1)
            except Exception as e:
                print(e)