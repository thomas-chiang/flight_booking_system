from fastapi import FastAPI
from .adapter.inward.web.task.task_controller import router as task_router
from .adapter.inward.web.token.token_controller import router as token_router
import requests

app = FastAPI()

app.include_router(token_router, tags=["auth"])
app.include_router(task_router, tags=["task"])

@app.get("/book_service")
def call_service2():
    response = requests.get("http://book_service:8000/")
    return {"book_service_response": response.json()}