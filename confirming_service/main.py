from fastapi import FastAPI, HTTPException
from sqlmodel import Field, SQLModel, create_engine, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://youruser:yourpassword@db/yourdb"

# Create an async engine
async_engine = create_async_engine(DATABASE_URL, echo=True, future=True)

# Create a session factory bound to the async engine
async_session_factory = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Booking(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    customer_id: int
    flight_id: int
    status: str

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

@app.get("/booking/{booking_id}")
async def get_booking_status(booking_id: int):
    async with async_session_factory() as session:
        statement = select(Booking).where(Booking.id == booking_id)
        result = await session.execute(statement)
        booking = result.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="still in progress")
        return {"status": booking.status}
