"""A metric described entirely by a JSON spec, with no adapter code."""

import csv
import io
import json
import statistics
from pathlib import Path
from typing import Any

import openpyxl

from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.store.cache import Cache

AGGREGATIONS = ("first", "mean", "median", "sum", "max", "min")
FORMATS = ("csv", "json", "xlsx")


class DeclarativeSource:
    """Fetches one metric from a tabular endpoint described by a spec.

    This is the tier that can be written by a model rather than a programmer. The
    spec is data: it names a URL, a format, the column holding a county FIPS and
    the column holding the value, and nothing else is executable. That bounds the
    blast radius -- a wrong spec produces a metric with poor coverage, which the
    coverage gate surfaces, rather than arbitrary behaviour.

    Sources needing real logic -- constructed geometry, pagination, a class
    crosswalk, retry semantics -- are not expressible here and should stay as
    written adapters, where they can be tested.
    """

    def __init__(self, spec: dict[str, Any], cache: Cache) -> None:
        self._spec = self._validate(spec)
        self._cache = cache
        self._metric = Metric(
            key=spec["key"],
            label=spec["label"],
            unit=spec["unit"],
            direction=spec["direction"],
            category=spec["category"],
            description=spec["description"],
            source=spec["source"],
        )

    @staticmethod
    def _validate(spec: dict[str, Any]) -> dict[str, Any]:
        """Reject a malformed spec at construction rather than at fetch time."""
        required = (
            "key",
            "label",
            "unit",
            "direction",
            "category",
            "description",
            "source",
            "url",
            "format",
            "fips_column",
            "value_column",
        )
        missing = [f for f in required if f not in spec]
        if missing:
            raise ValueError(f"spec is missing required fields: {missing}")
        if spec["format"] not in FORMATS:
            raise ValueError(f"format must be one of {FORMATS}, got {spec['format']!r}")
        if spec["direction"] not in ("higher_better", "lower_better"):
            raise ValueError("direction must be higher_better or lower_better")
        aggregate = spec.get("aggregate", "first")
        if aggregate not in AGGREGATIONS:
            raise ValueError(f"aggregate must be one of {AGGREGATIONS}, got {aggregate!r}")
        return spec

    @classmethod
    def from_file(cls, path: Path, cache: Cache) -> "DeclarativeSource":
        """Build from a spec saved as JSON."""
        return cls(json.loads(path.read_text()), cache)

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """The single metric this spec declares."""
        return (self._metric,)

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Download, parse, group by FIPS and aggregate."""
        wanted = {p.fips for p in places}
        # Keyed on the URL, not the metric: several specs commonly read different
        # columns of one published table, and keying on the metric would download
        # that table once per column.
        payload = self._cache.fetch_url(self._spec["url"], key=self._spec["url"])
        parsers = {
            "csv": self._parse_csv,
            "json": self._parse_json,
            "xlsx": self._parse_xlsx,
        }
        rows = parsers[self._spec["format"]](payload)
        grouped: dict[str, list[float]] = {}
        for fips, value in rows:
            if fips in wanted:
                grouped.setdefault(fips, []).append(value)
        aggregate = self._spec.get("aggregate", "first")
        return {self._metric.key: {f: self._reduce(v, aggregate) for f, v in grouped.items()}}

    def _parse_csv(self, payload: bytes) -> list[tuple[str, float]]:
        """Rows from a CSV body."""
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        return self._extract(reader)

    def _parse_xlsx(self, payload: bytes) -> list[tuple[str, float]]:
        """Rows from one worksheet of an Excel workbook.

        Public agencies publish a great deal of county data only as a workbook, and
        refusing the format would push those sources back into written adapters for
        no reason other than the container.
        """
        path = self._cache.path_for(self._spec["url"], ".xlsx")
        if not path.exists():
            self._cache.write(self._spec["url"], payload, ".xlsx")
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = workbook[self._spec["sheet"]] if self._spec.get("sheet") else workbook.active
        rows = sheet.iter_rows(values_only=True)
        header = [str(c) if c is not None else "" for c in next(rows)]
        mapped = [dict(zip(header, r, strict=False)) for r in rows]
        workbook.close()
        return self._extract(mapped)

    def _parse_json(self, payload: bytes) -> list[tuple[str, float]]:
        """Rows from a JSON array, optionally nested under `records_path`."""
        body = json.loads(payload)
        for step in self._spec.get("records_path", "").split("."):
            if step:
                body = body[step]
        return self._extract(body)

    def _extract(self, rows) -> list[tuple[str, float]]:
        """Pull the FIPS and value columns out of any row mapping."""
        fips_column = self._spec["fips_column"]
        value_column = self._spec["value_column"]
        scale = float(self._spec.get("scale", 1.0))
        where = self._spec.get("where") or {}
        out: list[tuple[str, float]] = []
        for row in rows:
            if any(str(row.get(k, "")) != str(v) for k, v in where.items()):
                continue
            raw_fips = row.get(fips_column)
            raw_value = row.get(value_column)
            if raw_fips in (None, "") or raw_value in (None, ""):
                continue
            cleaned = str(raw_value).replace(",", "").replace("$", "").replace("%", "").strip()
            try:
                out.append((str(raw_fips).strip().zfill(5), float(cleaned) * scale))
            except ValueError:
                continue
        return out

    @staticmethod
    def _reduce(values: list[float], how: str) -> float:
        """Collapse repeated rows for one county into a single number."""
        if how == "first":
            return values[0]
        if how == "mean":
            return statistics.fmean(values)
        if how == "median":
            return statistics.median(values)
        if how == "sum":
            return sum(values)
        return max(values) if how == "max" else min(values)
