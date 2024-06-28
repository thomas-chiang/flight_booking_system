import pika
import json

# Sample data
message_data = {
    'booking_id': '12345',
    'customer_id': '67890'
}

# Convert to JSON string
message_body = json.dumps(message_data)

# Establish a connection to RabbitMQ server
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Declare a queue
channel.queue_declare(queue='my_queue')

# Publish a message
channel.basic_publish(exchange='',
                      routing_key='my_queue',
                      body=message_body)

print(f"Message sent to RabbitMQ: {message_body}")

# Close the connection
connection.close()