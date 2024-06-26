from .status import Status


class Task:
    def __init__(self, id: int, name: str, status: Status):
        self.id = id
        self.name = name
        self.status = status
