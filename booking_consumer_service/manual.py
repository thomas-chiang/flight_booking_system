import pika
import json
import uuid

# Sample data
message_data = {
    'booking_id': str(uuid.uuid4()),
    'customer_id': '67890'
}

# Convert to JSON string
message_body = json.dumps(message_data)

# Establish a connection to RabbitMQ server
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
routing_key = "1"
# Declare a queue
channel.queue_declare(queue=routing_key)

# Publish a message
channel.basic_publish(exchange='',
                      routing_key=routing_key,
                      body=message_body)

print(f"Message sent to RabbitMQ: {message_body}")

# Close the connection
connection.close()