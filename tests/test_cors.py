"""A cooking card on another site's page reads /api from the browser: only listed origins may."""
from __future__ import annotations

from fastapi.testclient import TestClient

from kitchenette import api, config

PAGE = "https://chat.example.com"


def _get(origin: str):
    client = TestClient(api.create_app(scheduler=False, with_mcp=False))
    return client.get("/api/health", headers={"Origin": origin})


def test_no_other_site_may_read_by_default():
    r = _get(PAGE)
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_a_listed_origin_may_read_and_an_unlisted_one_may_not():
    config.override(server_cors_origins=[PAGE + "/"])     # a trailing slash is forgiven
    assert _get(PAGE).headers["access-control-allow-origin"] == PAGE
    assert "access-control-allow-origin" not in _get("https://elsewhere.example.com").headers


def test_preflight_lets_the_bearer_header_through():
    config.override(server_cors_origins=[PAGE])
    client = TestClient(api.create_app(scheduler=False, with_mcp=False))
    r = client.options("/api/kitchen", headers={
        "Origin": PAGE, "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization"})
    assert r.status_code == 200
    assert "authorization" in r.headers["access-control-allow-headers"].lower()
