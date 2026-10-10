import pytest
from fastapi.testclient import TestClient

from claimlens.main import create_app


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html><div id=root></div></html>")
    (d / "assets" / "x.js").write_text("console.log(1)")
    return d


@pytest.fixture
def client(settings, dist):
    return TestClient(create_app(settings.model_copy(update={"frontend_dir": dist})))


def test_spa_route_returns_index(client):
    r = client.get("/cases/abc")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "id=root" in r.text


def test_root_returns_index(client):
    assert "id=root" in client.get("/").text


def test_asset_served(client):
    r = client.get("/assets/x.js")
    assert r.status_code == 200 and r.text == "console.log(1)"


def test_unknown_api_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and "detail" in r.json()


def test_path_traversal_returns_index_not_file(client):
    r = client.get("/..%2F..%2Fetc%2Fpasswd")
    assert "root:" not in r.text


def test_health_still_works(client):
    assert client.get("/health").json() == {"ok": True}


def test_no_frontend_dir_no_catch_all(settings, tmp_path):
    c = TestClient(create_app(settings.model_copy(update={"frontend_dir": tmp_path / "missing"})))
    assert c.get("/cases/abc").status_code == 404


def test_missing_asset_is_404_not_index(client):
    # a stale page asking for an old hashed bundle must not get HTML back
    assert client.get("/assets/old-123.js").status_code == 404
    assert client.get("/favicon-old.png").status_code == 404


def test_index_is_not_cached(client):
    assert client.get("/cases/abc").headers.get("cache-control") == "no-cache"
