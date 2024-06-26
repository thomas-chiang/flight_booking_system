import unittest
from typing import Dict
from src.application.domain.model.task import Task
from src.application.domain.model.status import Status
from src.adapter.outward.persistence.task_repository import (
    TaskRepository,
    TaskRepositoryTaskNotFoundError,
)


class TestTaskRepository(unittest.TestCase):
    def setUp(self):
        # Mock database dictionary
        self.db: Dict[int, Dict[str, any]] = {
            1: {"name": "Task 1", "status": Status.incomplete.value},
            2: {"name": "Task 2", "status": Status.complete.value},
        }
        self.repository = TaskRepository(self.db)

    def test_list_tasks(self):
        tasks = self.repository.list_tasks()
        self.assertEqual(len(tasks), len(self.db))
        for task in tasks:
            self.assertIsInstance(task, Task)

    def test_create_task(self):
        new_task_name = "New Task"
        new_task = self.repository.create_task(new_task_name)
        self.assertEqual(new_task.name, new_task_name)
        self.assertEqual(new_task.status, Status.incomplete)

    def test_update_task(self):
        task_id = 1
        new_task_name = "Updated Task"
        new_task_status = Status.complete

        updated_task = self.repository.update_task(
            new_task_name, new_task_status, task_id
        )
        self.assertEqual(updated_task.name, new_task_name)
        self.assertEqual(updated_task.status, new_task_status)

    def test_update_task_not_found(self):
        task_id = 999  # Non-existent task id
        with self.assertRaises(TaskRepositoryTaskNotFoundError):
            self.repository.update_task("Updated Task", Status.complete, task_id)

    def test_delete_task(self):
        task_id = 2
        self.repository.delete_task(task_id)
        self.assertNotIn(task_id, self.db)

    def test_delete_task_not_found(self):
        task_id = 999  # Non-existent task id
        with self.assertRaises(TaskRepositoryTaskNotFoundError):
            self.repository.delete_task(task_id)
