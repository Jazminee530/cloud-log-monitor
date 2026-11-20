from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

# Without a context manager, TestClient does not run the DB-init lifespan.
# These tests deliberately mock the queue; Docker integration tests are separate.
client = TestClient(app)


def test_rejects_blank_source():
    response = client.post("/logs", json={"source": "", "level": "INFO", "message": "ok"})
    assert response.status_code == 422


def test_queues_valid_log():
    fake_queue = MagicMock()
    fake_queue.enqueue.return_value.id = "fake-job-123"
    with patch("app.main.get_queue", return_value=fake_queue):
        response = client.post(
            "/logs", json={"event_id": "test-event-1", "source": "demo", "level": "WARNING", "message": "Failed login"}
        )
    assert response.status_code == 202
    assert response.json()["event_id"] == "test-event-1"
    assert response.json()["status"] == "queued"
    fake_queue.enqueue.assert_called_once()
