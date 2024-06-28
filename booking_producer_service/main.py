from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aioredis
import aio_pika
import asyncio
import os
import sys
import uuid
import json
import aiormq
import threading
import requests


app = FastAPI()

REDIS_URL = os.getenv("REDIS_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
BOOKING_CONSUMER_URL = os.getenv("BOOKING_CONSUMER_URL", "http://localhost:8001/")

redis = aioredis.from_url(REDIS_URL, decode_responses=True)

class BookingRequest(BaseModel):
    flight_id: str
    customer_id: str


@app.post("/booking_producing")
async def create_booking(request: BookingRequest):
    flight_id = request.flight_id
    customer_id = request.customer_id
    booking_id = str(uuid.uuid4())

    await asyncio.gather(
        send_to_queue(flight_id, customer_id, booking_id),
        initialize_consumer(flight_id),
    )


    return {"status": "booking request processed", "booking_id": booking_id}


async def send_to_queue(flight_id, customer_id, booking_id):
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
        message = {"booking_id": booking_id, "customer_id": customer_id}
        message_body = json.dumps(message).encode()

        await channel.default_exchange.publish(
            aio_pika.Message(body=message_body),
            routing_key=flight_id,
        )
        print(f"Message sent to {flight_id}: {message}")
        sys.stdout.flush()


async def initialize_consumer(flight_id):
    timeout = 60
    start_time = asyncio.get_event_loop().time()

    while not await redis.exists(flight_id):
        
        current_time = asyncio.get_event_loop().time() - start_time
        if current_time > timeout:
            print(f"Timeout reached: {timeout} seconds")
            sys.stdout.flush()
            raise HTTPException(
                status_code=500,
                detail="Fail to consume booking message",
            )
        
        await asyncio.to_thread(use_thread_send_request_without_waiting_response, flight_id)

        print(int(timeout - current_time), "seconds left to retry every second")
        sys.stdout.flush()
        
        await asyncio.sleep(1)

def use_thread_send_request_without_waiting_response(flight_id):
    def send_request(flight_id):
        headers = {'Content-Type': 'application/json'}
        data = {
            'flight_id': flight_id,
        }
        try:
            response = requests.post(BOOKING_CONSUMER_URL, headers=headers, json=data)
            print(f"Status Code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

    thread = threading.Thread(target=send_request, args=[flight_id])
    thread.start()