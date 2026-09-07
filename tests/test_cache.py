"""A cached failure is indistinguishable from data and survives every later run."""

import httpx
import pytest

from refugia import USER_AGENT
from refugia.store.cache import Cache


class _Response:
    """Just enough of an httpx response for the cache to work with."""

    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _Server:
    """Answers every request with one body, and records what it was asked."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response(self.body)


@pytest.fixture
def server(monkeypatch):
    """Replace httpx.get with something that never touches the network."""

    def _serve(body: bytes = b"payload") -> _Server:
        stub = _Server(body)
        monkeypatch.setattr(httpx, "get", stub.get)
        return stub

    return _serve


def test_a_body_is_cached(tmp_path, server):
    """The ordinary case: fetched once, served from disk after that."""
    stub = server()
    cache = Cache(tmp_path)
    assert cache.fetch_url("https://example.invalid/a") == b"payload"
    assert cache.fetch_url("https://example.invalid/a") == b"payload"
    assert len(stub.calls) == 1


def test_an_empty_body_is_never_stored(tmp_path, server):
    """An empty file on disk reads back exactly like a real answer."""
    server(b"")
    cache = Cache(tmp_path)
    assert cache.fetch_url("https://example.invalid/b") == b""
    assert not cache.has("https://example.invalid/b")


def test_an_empty_body_is_retried_next_run(tmp_path, server):
    """The point of not storing it: the next run gets another chance."""
    stub = server(b"")
    cache = Cache(tmp_path)
    cache.fetch_url("https://example.invalid/c")
    cache.fetch_url("https://example.invalid/c")
    assert len(stub.calls) == 2


def test_write_refuses_an_empty_payload(tmp_path):
    """The guard belongs on the store, not on each of its callers."""
    cache = Cache(tmp_path)
    assert cache.write("k", b"") is None
    assert not cache.has("k")


def test_requests_identify_themselves(tmp_path, server):
    """A hundred forks of a public repo hitting one endpoint should be nameable."""
    stub = server()
    Cache(tmp_path).fetch_url("https://example.invalid/d")
    assert stub.calls[0][1]["headers"]["User-Agent"] == USER_AGENT
    assert "refugia" in USER_AGENT and "github.com" in USER_AGENT


def test_the_cache_directory_is_not_created_until_something_is_written(tmp_path):
    """`refugia metrics` reads the registry and should leave no data/ behind."""
    root = tmp_path / "data" / "cache"
    Cache(root)
    assert not root.exists()


def test_the_oldest_entry_of_an_uncreated_cache_is_empty(tmp_path):
    """Asking a cache that has never been written to must not raise."""
    assert Cache(tmp_path / "never").oldest_entry() == ""
