from fastapi.testclient import TestClient
import importlib

from app.main import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auto_init_db_branch(monkeypatch) -> None:
    called = {"count": 0}
    monkeypatch.setenv("AUTO_INIT_DB", "true")

    import app.db.init_db as init_db_module
    monkeypatch.setattr(init_db_module, "init_db", lambda: called.__setitem__("count", called["count"] + 1))

    import app.main as main_module
    importlib.reload(main_module)

    assert called["count"] == 1
