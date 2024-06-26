from fastapi import FastAPI
from .adapter.inward.web.task.task_controller import router as task_router
from .adapter.inward.web.token.token_controller import router as token_router

app = FastAPI()

app.include_router(token_router, tags=["auth"])
app.include_router(task_router, tags=["task"])
