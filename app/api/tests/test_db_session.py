import importlib


def test_build_database_url_prefers_explicit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:5432/db")
    monkeypatch.setenv("DB_HOST", "ignored")
    import app.db.session as session_module

    assert session_module._build_database_url() == "postgresql+psycopg://u:p@h:5432/db"


def test_build_database_url_sqlite_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    import app.db.session as session_module

    assert session_module._build_database_url() == "sqlite:///./app.db"


def test_build_database_url_postgres_with_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "db.example")
    monkeypatch.setenv("DB_NAME", "codequality")
    monkeypatch.setenv("DB_USER", "postgres_admin")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_PORT", "5432")
    import app.db.session as session_module

    assert (
        session_module._build_database_url()
        == "postgresql+psycopg://postgres_admin:secret@db.example:5432/codequality"
    )


def test_build_database_url_postgres_without_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "db.example")
    monkeypatch.setenv("DB_NAME", "codequality")
    monkeypatch.setenv("DB_USER", "postgres_admin")
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.setenv("DB_PORT", "5432")
    import app.db.session as session_module

    assert session_module._build_database_url() == "postgresql+psycopg://postgres_admin@db.example:5432/codequality"


def test_database_url_constant_uses_builder(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "db.example")
    monkeypatch.setenv("DB_NAME", "codequality")
    monkeypatch.setenv("DB_USER", "postgres_admin")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_PORT", "5432")

    import app.db.session as session_module

    reloaded = importlib.reload(session_module)
    assert reloaded.DATABASE_URL == "postgresql+psycopg://postgres_admin:secret@db.example:5432/codequality"


def test_get_session_closes_session(monkeypatch):
    import app.db.session as session_module

    class FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    fake = FakeSession()
    monkeypatch.setattr(session_module, "SessionLocal", lambda: fake)

    generator = session_module.get_session()
    yielded = next(generator)
    assert yielded is fake

    try:
        next(generator)
    except StopIteration:
        pass

    assert fake.closed is True
