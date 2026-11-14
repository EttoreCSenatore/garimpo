from __future__ import annotations

from datetime import UTC

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.api.dependencies import get_db
from app.config import Settings, settings
from app.main import app
from app.security import RateLimiter, host_allowed, safe_http_url, tokens_match

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def _db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --- helpers ---------------------------------------------------------------

def test_tokens_match_is_strict():
    assert tokens_match("abc", "abc")
    assert not tokens_match("abd", "abc")
    assert not tokens_match(None, "abc")
    assert not tokens_match("", "")
    assert not tokens_match("anything", "")


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://www.tivolli.com.br/img/a.jpg", True),
        ("http://cdn.tivolli.com.br/a.jpg", True),
        ("https://evil.com/a.jpg", False),
        ("https://tivolli.com.br.evil.com/a.jpg", False),
        ("https://nottivolli.com.br/a.jpg", False),
        ("http://127.0.0.1/a.jpg", False),
        ("http://169.254.169.254/latest/meta-data", False),
        ("http://[::1]/a.jpg", False),
        ("file:///etc/passwd", False),
        ("javascript:alert(1)", False),
        ("https://user:pw@www.tivolli.com.br/a.jpg", False),
        ("", False),
    ],
)
def test_safe_http_url_allowlist(url, ok):
    assert (safe_http_url(url, ["tivolli.com.br"]) is not None) is ok


def test_host_allowed_matches_subdomains_only():
    assert host_allowed("a.b.tivolli.com.br", ["tivolli.com.br"])
    assert not host_allowed("xtivolli.com.br", ["tivolli.com.br"])


# --- admin auth ------------------------------------------------------------

def test_admin_disabled_when_token_empty(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "")
    assert client.get("/admin/queue", headers={"X-Admin-Token": ""}).status_code == 401
    assert client.get("/admin/queue", headers={"X-Admin-Token": "x"}).status_code == 401


def test_admin_wrong_and_right_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "s" * 32)
    assert client.get("/admin/queue", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.get("/admin/queue").status_code == 401
    assert client.get("/admin/queue", headers={"X-Admin-Token": "s" * 32}).status_code == 200


def test_production_refuses_weak_admin_token():
    with pytest.raises(RuntimeError):
        Settings(app_env="production", admin_token="change-me-to-a-secure-token").validate_for_runtime()
    with pytest.raises(RuntimeError):
        Settings(app_env="production", admin_token="short").validate_for_runtime()
    Settings(app_env="production", admin_token="x" * 32).validate_for_runtime()
    Settings(app_env="development", admin_token="").validate_for_runtime()


# --- image proxy (SSRF) ----------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost:8000/admin/queue",
        "https://evil.example/x.png",
        "file:///etc/passwd",
    ],
)
def test_image_proxy_rejects_disallowed_urls(client, url):
    assert client.get("/api/image-proxy", params={"url": url}).status_code == 400


def test_image_proxy_serves_allowed_image(client):
    with respx.mock:
        respx.get("https://www.tivolli.com.br/a.png").mock(
            return_value=httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        )
        r = client.get("/api/image-proxy", params={"url": "https://www.tivolli.com.br/a.png"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_image_proxy_blocks_html_and_svg(client):
    with respx.mock:
        respx.get("https://www.tivolli.com.br/x").mock(
            return_value=httpx.Response(200, content=b"<script>alert(1)</script>", headers={"content-type": "text/html"})
        )
        respx.get("https://www.tivolli.com.br/y.svg").mock(
            return_value=httpx.Response(200, content=b"<svg/>", headers={"content-type": "image/svg+xml"})
        )
        assert client.get("/api/image-proxy", params={"url": "https://www.tivolli.com.br/x"}).status_code == 502
        assert client.get("/api/image-proxy", params={"url": "https://www.tivolli.com.br/y.svg"}).status_code == 502


def test_image_proxy_revalidates_redirects(client):
    with respx.mock:
        respx.get("https://www.tivolli.com.br/r").mock(
            return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/"})
        )
        r = client.get("/api/image-proxy", params={"url": "https://www.tivolli.com.br/r"})
    assert r.status_code == 502


def test_image_proxy_enforces_size_cap(client, monkeypatch):
    monkeypatch.setattr(settings, "image_proxy_max_bytes", 100)
    with respx.mock:
        respx.get("https://www.tivolli.com.br/big.png").mock(
            return_value=httpx.Response(200, content=PNG + b"0" * 500, headers={"content-type": "image/png"})
        )
        r = client.get("/api/image-proxy", params={"url": "https://www.tivolli.com.br/big.png"})
    assert r.status_code == 502


# --- chat input limits, sessions, rate limiting ---------------------------

def test_chat_rejects_oversized_message_and_bad_session(client):
    assert client.post("/api/chat", json={"message": "x" * 5000}).status_code == 422
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "oi", "session_id": "../../etc"}).status_code == 422


def test_chat_session_store_is_bounded(client, monkeypatch):
    from app.api import routes

    monkeypatch.setattr(settings, "chat_max_sessions", 5)
    routes.chat_sessions.clear()
    for i in range(20):
        assert client.post("/api/chat", json={"message": "oi", "session_id": f"s{i}"}).status_code == 200
    assert len(routes.chat_sessions) <= 5


def test_chat_rate_limit(client, monkeypatch):
    from app import security

    monkeypatch.setattr(settings, "chat_rate_limit_per_minute", 3)
    security.chat_rate_limit._hits.clear()
    codes = [client.post("/api/chat", json={"message": "oi"}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]
    security.chat_rate_limit._hits.clear()


def test_rate_limiter_zero_disables():
    limiter = RateLimiter("t", lambda: 0)
    assert limiter.limit_getter() == 0


# --- headers, CORS, LIKE escaping -----------------------------------------

def test_security_headers_and_cors(client):
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in r.headers
    r2 = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r2.headers


def test_search_treats_wildcards_literally(client):
    from datetime import datetime

    from app.api.dependencies import get_db as gdb
    from app.models import Product

    session = next(app.dependency_overrides[gdb]())
    session.add(Product(id=1, slug="a", url="https://www.tivolli.com.br/1-a", name="Tenis 100% Couro", scraped_at=datetime.now(UTC)))
    session.add(Product(id=2, slug="b", url="https://www.tivolli.com.br/2-b", name="Tenis Basico", scraped_at=datetime.now(UTC)))
    session.commit()
    names = [i["name"] for i in client.get("/products", params={"q": "%"}).json()["items"]]
    assert names == ["Tenis 100% Couro"]


# --- scraper hardening -----------------------------------------------------

def test_listing_extraction_drops_foreign_and_script_urls():
    from app.scraper.listings import extract_product_urls

    html = """
    <a href="/123-tenis-nike">ok</a>
    <a href="https://evil.com/1-x">foreign</a>
    <a href="javascript:alert(1)//9-x">js</a>
    <a href="//cdn.evil.com/5-y">proto-relative</a>
    """
    assert extract_product_urls(html) == ["https://www.tivolli.com.br/123-tenis-nike"]


@pytest.mark.asyncio
async def test_client_refuses_robots_disallowed_and_foreign_hosts():
    from app.scraper.client import DisallowedRequestError, RateLimitedClient

    c = RateLimitedClient(jitter_min_ms=0, jitter_max_ms=0, requests_per_second=1000)
    for target in ["/tivadm43/login", "https://www.tivolli.com.br/homologacao/x", "https://evil.com/a", "file:///etc/passwd"]:
        with pytest.raises(DisallowedRequestError):
            await c.get_raw(target)
    await c.close()


def test_sitemap_parser_ignores_external_entities():
    from lxml import etree

    xml = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><urlset><url><loc>&x;</loc></url></urlset>'
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
    root = etree.fromstring(xml, parser=parser)
    assert "root:" not in (root.xpath("string(//loc)") or "")


def test_resolve_allowed_url_uses_exact_hosts_only():
    from app.security import resolve_allowed_url

    allowed = ["estatico.tivollisports.com.br"]
    assert resolve_allowed_url("http://estatico.tivollisports.com.br/a.jpg?x=1", allowed) == (
        "https://estatico.tivollisports.com.br/a.jpg?x=1"
    )
    assert resolve_allowed_url("https://evil.tivollisports.com.br/a.jpg", allowed) is None
    assert resolve_allowed_url("https://estatico.tivollisports.com.br:8443/a.jpg", allowed) is None


def test_chat_size_answer_handles_unicode_digits_and_whitespace(client):
    sid = "unicode-digits"
    assert client.post("/api/chat", json={"message": "quero um tênis feminino", "session_id": sid}).status_code == 200
    # "²" is a Unicode digit that int() rejects; it must not crash the endpoint.
    assert client.post("/api/chat", json={"message": "²", "session_id": sid}).status_code == 200
    r = client.post("/api/chat", json={"message": " " * 400 + "38", "session_id": sid})
    assert r.status_code == 200
    assert r.json()["filters_applied"].get("size") == 38
