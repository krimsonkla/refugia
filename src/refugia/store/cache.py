"""On-disk cache for fetched source data."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import httpx

from refugia import USER_AGENT


class Cache:
    """Stores raw downloads so re-scoring never re-fetches.

    Every source in this project is a slow public endpoint, and the whole point of
    separating fetch from score is that changing weights costs nothing. Entries are
    kept until explicitly refreshed rather than expiring on a timer: these datasets
    are annual or slower, so a TTL would only ever cause surprise re-downloads
    mid-analysis.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str, suffix: str = "") -> Path:
        """The file backing one cache key."""
        digest = hashlib.sha256(key.encode()).hexdigest()[:16]
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)[:60]
        return self._root / f"{safe}-{digest}{suffix}"

    def has(self, key: str, suffix: str = "") -> bool:
        """Whether this key is already stored."""
        return self.path_for(key, suffix).exists()

    def read(self, key: str, suffix: str = "") -> bytes:
        """Read a stored entry."""
        return self.path_for(key, suffix).read_bytes()

    def write(self, key: str, payload: bytes, suffix: str = "") -> Path | None:
        """Store an entry and return where it landed, or None if there was nothing.

        An empty payload is never stored. On disk it is indistinguishable from a
        real answer, so caching one turns a transient failure into a permanent
        wrong result that survives every later run -- and the runs that would have
        corrected it never make the request.
        """
        if not payload:
            return None
        target = self.path_for(key, suffix)
        target.write_bytes(payload)
        return target

    def oldest_entry(self) -> str:
        """The date of the oldest stored response, or "" when nothing is stored.

        `fetch` is cache-first, so when it last ran says nothing about how old the
        data it used is: a run that hits every entry stamps today onto figures a
        year old. This is the number that tells the difference.
        """
        times = [entry.stat().st_mtime for entry in self._root.iterdir() if entry.is_file()]
        if not times:
            return ""
        return datetime.fromtimestamp(min(times), tz=UTC).date().isoformat()

    def fetch_url(
        self,
        url: str,
        *,
        key: str | None = None,
        suffix: str = "",
        refresh: bool = False,
        timeout: float = 120.0,
    ) -> bytes:
        """Return the body at `url`, downloading only when not already cached."""
        cache_key = key or url
        if not refresh and self.has(cache_key, suffix):
            return self.read(cache_key, suffix)
        response = httpx.get(
            url, timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()
        self.write(cache_key, response.content, suffix)
        return response.content
