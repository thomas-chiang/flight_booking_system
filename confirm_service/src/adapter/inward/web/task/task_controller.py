from fastapi import APIRouter, Depends, HTTPException
from .....db import db
from .task_schema import (
    TaskWebInterface,
    TaskCreateWebInterface,
    TaskUpdateWebInterface,
    TaskResult,
    TaskListResult,
)
from ....outward.persistence.task_repository import TaskRepository
from .....application.domain.model.task import Task
from .....application.domain.model.status import Status
from .....application.domain.service.task_service import (
    TaskService,
    TaskServiceTaskNotFoundError,
)
from .....application.port.inward.task_use_case import TaskUseCase
from .....application.port.outward.task_port import TaskPort
from ..auth.jwt import get_credentials

task_port: TaskPort = TaskRepository(db=db)
task_service: TaskUseCase = TaskService(task_port=task_port)


router = APIRouter(dependencies=[Depends(get_credentials)])


@router.get("/v1/tasks", response_model=TaskListResult, summary="List all tasks")
async def list_tasks():
    return TaskListResult(
        result=[
            TaskWebInterface(id=task.id, name=task.name, status=task.status.value)
            for task in task_service.list_tasks()
        ]
    )


@router.post(
    "/v1/task",
    response_model=TaskResult,
    status_code=201,
    summary="Create a new task",
)
async def create_task(task_create_for_web: TaskCreateWebInterface):
    task: Task = task_service.create_task(name=task_create_for_web.name)
    return TaskResult(
        result=TaskWebInterface(id=task.id, name=task.name, status=task.status.value)
    )


@router.put("/v1/task/{task_id}", response_model=TaskResult, summary="Update a task")
async def update_task(task_id: int, task_update_for_web: TaskUpdateWebInterface):
    try:
        task: Task = task_service.update_task(
            name=task_update_for_web.name,
            status=Status(task_update_for_web.status),
            id=task_id,
        )
    except TaskServiceTaskNotFoundError:
        raise TaskNotFoundError(task_id=task_id)

    return TaskResult(
        result=TaskWebInterface(id=task.id, name=task.name, status=task.status.value)
    )


@router.delete("/v1/task/{task_id}", status_code=200, summary="Delete a task")
async def delete_task(task_id: int):
    try:
        task_service.delete_task(task_id)
    except TaskServiceTaskNotFoundError:
        raise TaskNotFoundError(task_id=task_id)

    return


class TaskNotFoundError(HTTPException):
    def __init__(self, task_id):
        super().__init__(status_code=404, detail=f"Task id: {task_id} not found")
