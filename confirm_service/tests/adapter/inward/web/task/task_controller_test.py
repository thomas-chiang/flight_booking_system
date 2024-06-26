import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.application.domain.model.status import Status

client = TestClient(app)


@pytest.fixture(scope="module")
def token():
    response = client.post("/v1/token", auth=("admin", "password"))
    return response.json()["access_token"]


def test_create_task(token):
    response = client.post(
        "/v1/task",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Buy dinner"},
    )
    assert response.status_code == 201
    result = response.json()["result"]
    assert result["name"] == "Buy dinner"
    assert result["status"] == Status.incomplete.value
    assert result["id"] == 1


def test_list_tasks(token):
    response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == {"id": 1, "name": "Buy dinner", "status": 0}


def test_update_task(token):
    response = client.put(
        "/v1/task/1000",
        json={"name": "Buy breakfast", "status": Status.complete.value},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Task id: 1000 not found"}

    response = client.put(
        "/v1/task/1",
        json={"name": "Buy breakfast", "status": Status.complete.value},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["name"] == "Buy breakfast"
    assert result["status"] == Status.complete.value
    assert result["id"] == 1


def test_delete_task(token):
    response = client.delete(
        "/v1/task/1000", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Task id: 1000 not found"}

    response = client.delete("/v1/task/1", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert not response.json()
