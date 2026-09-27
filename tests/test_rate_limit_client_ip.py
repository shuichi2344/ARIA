from types import SimpleNamespace

import pytest
from starlette.requests import Request

from aria.api import security


@pytest.fixture(autouse=True)
def _clear_trusted_proxy_cache():
    yield
    security._trusted_proxy_networks.cache_clear()


def _request(peer: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request({
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": (peer, 12345),
        "server": ("testserver", 80),
    })


def _configure_trusted_proxies(monkeypatch, cidrs: str) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(trusted_proxy_ips=cidrs),
    )
    security._trusted_proxy_networks.cache_clear()


def test_untrusted_peer_cannot_spoof_forwarded_client_ip(monkeypatch):
    _configure_trusted_proxies(monkeypatch, "10.0.0.0/8")

    assert security._get_client_ip(_request("198.51.100.25", "203.0.113.80")) == "198.51.100.25"


def test_no_proxy_configuration_ignores_forwarded_header(monkeypatch):
    _configure_trusted_proxies(monkeypatch, "")

    assert security._get_client_ip(_request("198.51.100.25", "203.0.113.80")) == "198.51.100.25"


def test_trusted_proxy_forwarded_client_is_used(monkeypatch):
    _configure_trusted_proxies(monkeypatch, "10.0.0.0/8")

    assert security._get_client_ip(_request("10.1.2.3", "198.51.100.25")) == "198.51.100.25"


def test_forwarded_chain_ignores_client_supplied_prefix(monkeypatch):
    _configure_trusted_proxies(monkeypatch, "10.0.0.0/8")

    assert security._get_client_ip(_request("10.1.2.3", "203.0.113.80, 198.51.100.25")) == "198.51.100.25"


def test_malformed_forwarded_header_falls_back_to_peer(monkeypatch):
    _configure_trusted_proxies(monkeypatch, "10.0.0.0/8")

    assert security._get_client_ip(_request("10.1.2.3", "not-an-ip")) == "10.1.2.3"
