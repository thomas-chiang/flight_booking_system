from pydantic import BaseModel
from .....application.domain.model.status import Status
from typing import List


class TaskWebInterface(BaseModel):
    id: int
    name: str
    status: Status


class TaskCreateWebInterface(BaseModel):
    name: str


class TaskUpdateWebInterface(BaseModel):
    name: str
    status: Status


class TaskResult(BaseModel):
    result: TaskWebInterface


class TaskListResult(BaseModel):
    result: List[TaskWebInterface]
