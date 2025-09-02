"""Unit tests for health endpoint."""

import logging

import requests
from sqlalchemy.exc import SQLAlchemyError
from flask import Flask

from apps.legal_discovery import hippo_routes
from apps.legal_discovery.hippo_routes import health_bp


def test_health_endpoint_returns_status_keys(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    class DummySession:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def run(self, query):
            return None

    class DummyDriver:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def session(self, database=None):
            return DummySession()

    class DummyGraphDB:
        @staticmethod
        def driver(*args, **kwargs):
            return DummyDriver()

    monkeypatch.setattr(hippo_routes, "GraphDatabase", DummyGraphDB)
    monkeypatch.setattr(
        hippo_routes.requests, "get", lambda *a, **kw: type("R", (), {"status_code": 200})()
    )
    monkeypatch.setattr(hippo_routes.db.session, "execute", lambda *a, **kw: None)
    monkeypatch.setattr(hippo_routes.db.session, "commit", lambda *a, **kw: None)
    monkeypatch.setattr(hippo_routes.db.session, "close", lambda *a, **kw: None)
    class DummyRedis:
        def ping(self):
            return None
    monkeypatch.setattr(hippo_routes, "redis_client", DummyRedis())

    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert {"neo4j", "chroma", "blocked_requests", "cache"}.issubset(data)


def test_health_reports_neo4j_failure(monkeypatch, caplog):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    class FailingGraphDB:
        @staticmethod
        def driver(*args, **kwargs):  # pragma: no cover - monkeypatched
            raise RuntimeError("boom")

    monkeypatch.setattr(hippo_routes, "GraphDatabase", FailingGraphDB)

    with caplog.at_level(logging.ERROR):
        resp = client.get("/api/health")

    assert resp.status_code == 503
    payload = resp.get_json()
    data = payload["data"]
    meta = payload.get("meta", {})
    assert data["neo4j"] == "fail"
    assert "neo4j_error" in meta and "boom" in meta["neo4j_error"]
    assert "Neo4j health check failed" in caplog.text


def test_health_reports_chroma_failure(monkeypatch, caplog):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    def failing_get(*args, **kwargs):  # pragma: no cover - monkeypatched
        raise RuntimeError("boom")

    monkeypatch.setattr(hippo_routes.requests, "get", failing_get)

    with caplog.at_level(logging.ERROR):
        resp = client.get("/api/health")

    assert resp.status_code == 503
    payload = resp.get_json()
    data = payload["data"]
    meta = payload.get("meta", {})
    assert data["chroma"] == "fail"
    assert "chroma_error" in meta and "boom" in meta["chroma_error"]
    assert "Chroma health check failed" in caplog.text


def test_health_fallbacks_to_legacy_chroma(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    class DummySession:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def run(self, query):
            return None

    class DummyDriver:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def session(self, database=None):
            return DummySession()

    class DummyGraphDB:
        @staticmethod
        def driver(*args, **kwargs):
            return DummyDriver()

    monkeypatch.setattr(hippo_routes, "GraphDatabase", DummyGraphDB)

    class R:
        def __init__(self, code):
            self.status_code = code
            self.text = ""

    def fake_get(url, timeout=0):
        if url.endswith("/api/v1/heartbeat"):
            return R(404)
        return R(200)

    monkeypatch.setattr(hippo_routes.requests, "get", fake_get)
    monkeypatch.setattr(hippo_routes.db.session, "execute", lambda *a, **kw: None)
    monkeypatch.setattr(hippo_routes.db.session, "commit", lambda *a, **kw: None)
    monkeypatch.setattr(hippo_routes.db.session, "close", lambda *a, **kw: None)

    class DummyRedis:
        def ping(self):
            return None

    monkeypatch.setattr(hippo_routes, "redis_client", DummyRedis())

    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["chroma"] == "ok"


def test_health_fallbacks_to_bare_chroma(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    class DummySession:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def run(self, query):
            return None

    class DummyDriver:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def session(self, database=None):
            return DummySession()

    class DummyGraphDB:
        @staticmethod
        def driver(*args, **kwargs):
            return DummyDriver()

    monkeypatch.setattr(hippo_routes, "GraphDatabase", DummyGraphDB)

    class R:
        def __init__(self, code):
            self.status_code = code
            self.text = ""

    def fake_get(url, timeout=0):
        if url.endswith("/api/v1/heartbeat"):
            return R(404)
        if url.endswith("/api/heartbeat"):
            return R(404)
        return R(204)

    monkeypatch.setattr(hippo_routes.requests, "get", fake_get)
    monkeypatch.setattr(hippo_routes.db.session, "execute", lambda *a, **kw: None)
    monkeypatch.setattr(hippo_routes.db.session, "commit", lambda *a, **kw: None)
    monkeypatch.setattr(hippo_routes.db.session, "close", lambda *a, **kw: None)

    class DummyRedis:
        def ping(self):
            return None

    monkeypatch.setattr(hippo_routes, "redis_client", DummyRedis())

    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["chroma"] == "ok"


def test_health_reports_chroma_connection_error(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    def failing_get(*args, **kwargs):  # pragma: no cover - monkeypatched
        raise requests.exceptions.ConnectionError("no route")

    monkeypatch.setattr(hippo_routes.requests, "get", failing_get)

    resp = client.get("/api/health")
    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["data"]["chroma"] == "fail"
    assert "connection error" in payload.get("meta", {}).get("chroma_error", "").lower()


def test_health_reports_chroma_timeout(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    def failing_get(*args, **kwargs):  # pragma: no cover - monkeypatched
        raise requests.exceptions.Timeout("slow")

    monkeypatch.setattr(hippo_routes.requests, "get", failing_get)

    resp = client.get("/api/health")
    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["data"]["chroma"] == "fail"
    assert "timeout" in payload.get("meta", {}).get("chroma_error", "").lower()


def test_health_reports_postgres_failure(monkeypatch, caplog):
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    def failing_execute(*args, **kwargs):  # pragma: no cover - monkeypatched
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(hippo_routes.db.session, "execute", failing_execute)
    monkeypatch.setattr(hippo_routes.db.session, "commit", lambda *a, **kw: None)
    monkeypatch.setattr(hippo_routes.db.session, "close", lambda *a, **kw: None)

    with caplog.at_level(logging.ERROR):
        resp = client.get("/api/health")

    assert resp.status_code == 503
    payload = resp.get_json()
    data = payload["data"]
    meta = payload.get("meta", {})
    assert data["postgres"] == "fail"
    assert "postgres_error" in meta and "boom" in meta["postgres_error"]
    assert "Postgres health check failed" in caplog.text
