from fastapi.testclient import TestClient
from freezegun import freeze_time
from src.main import app

client = TestClient(app)


def test_token_expires_after_one_minute():
    token: str

    with freeze_time("2023-01-01 00:00:00"):
        response = client.post("/v1/token", auth=("admin", "password"))
        assert response.status_code == 200
        token = response.json()["access_token"]

    with freeze_time("2023-01-01 00:00:30"):
        response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    with freeze_time("2023-01-01 00:01:30"):
        response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert response.json() == {
            "detail": "Token time expired: expired_token: The token is expired"
        }
