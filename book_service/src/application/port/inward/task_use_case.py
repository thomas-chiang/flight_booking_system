from abc import ABC, abstractmethod
from typing import List
from ...domain.model.task import Task
from ...domain.model.status import Status


class TaskUseCase(ABC):
    @abstractmethod
    def list_tasks(self) -> List[Task]:
        pass

    @abstractmethod
    def create_task(self, name: str) -> Task:
        pass

    @abstractmethod
    def update_task(self, name: str, status: Status, id: int) -> Task:
        pass

    @abstractmethod
    def delete_task(self, id: int) -> None:
        pass
