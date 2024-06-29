# Flight Booking System

## System Design

<img width="1040" alt="airline booking v2" src="https://github.com/thomas-chiang/flight_booking_system/assets/84237929/c1a396d4-4c39-4a6d-af9f-7809876dd2e2">


## Functional Requirements

1. **Book Flights**: Allow users to book flights.
2. **Search Flights**: Users can search for flights by specifying the origin, destination, and date.
3. **Pagination for Search Results**: Return available flights, prices, and remaining seats in a paginated manner.
4. **Overselling/Overbooking**: The system should account for the airline's practice of overbooking.

## Non-functional Requirements

1. **Low Latency**: The system should respond quickly to user requests.
2. **High Concurrency**: The system should handle a high volume of concurrent requests.

### Performance Estimates

- **Read Operations**: 10,000,000 requests per second (RPS)
- **Write Operations**: 10,000 writes per second (WPS)

### Storage Estimates

- **Unit Size**: 1 KB per record
- **Daily Storage**: 
  - 1 KB * 100 (companies) * 1,000 (flights) * 200 (seats) = 20 GB per day

## API Endpoints

1. **Search Flights**
   - **Endpoint**: `search_service/flights`
   - **Method**: `GET`
   - **Parameters**:
     - `from_place` (string): Origin
     - `to_place` (string): Destination
     - `flight_date` (string): Date of travel
     - `page` (integer): Page number for pagination
   - **Response**: List of available flights with prices and remaining seats

2. **Book Flights**
   - **Endpoint**: `booking_producer_service/booking_producing`
   - **Method**: `POST`
   - **Parameters**:
     - `flight_id` (string): Flight ID
     - `customer_id` (string): Customer ID
   - **Response**: Booking ID with confirmation details 

3. **(Optional: Process Bookings)**
   - **Endpoint**: `booking_consumer_service/booking_consuming`
   - **Method**: `POST`
   - **Parameters**:
     - `flight_id` (string): Flight ID
   - **Response**: Consumer situation for Flight ID

4. **Confirm Booking Result**
   - **Endpoint**: `/booking_result`
   - **Method**: `GET`
   - **Parameters**:
     - `booking_id` (string): Booking ID
   - **Response**: Booking status

## Database Schema

### Flight

- `id` (string): Primary key
- `from_place` (string): Origin (indexed)
- `to_place` (string): Destination (indexed)
- `flight_date` (date): Date of flight (indexed) (partition key for manual sharding)
- `price` (decimal): Price of the flight
- `booking_limit` (integer): Maximum number of bookings allowed
- `oversell_limit` (integer): Maximum number of overbookings allowed
- `current_booking` (integer): Current number of bookings

### Booking

- `id` (string): Primary key
- `customer_id` (string): Customer ID (indexed)
- `flight_id` (string): Flight ID
- `status` (string): Booking status (e.g., booked, oversold, failed)


## Run

```
docker-compose up --build
```

## Documentation
- openapi
- Search Flights: http://127.0.0.1:8001/docs
- Book Flights: http://127.0.0.1:8002/docs
- Process Bookings: http://127.0.0.1:8003/docs
- Confirm Booking Result: http://127.0.0.1:8004/docs
