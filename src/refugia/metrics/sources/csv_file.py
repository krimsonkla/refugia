"""Any FIPS-keyed CSV, adopted as a metric without writing a new source."""

import csv
import io
from pathlib import Path

from refugia.metrics.metric import Metric
from refugia.places.place import Place


class CsvFileSource:
    """Reads one metric out of a local CSV keyed by county FIPS.

    This is the escape hatch that keeps the registry honest. Every other source
    encodes a specific API; this one lets a metric found anywhere -- a state agency
    table, a scraped ranking, a spreadsheet assembled by hand -- enter the model at
    the same standing as the built-in ones, with no code change and no fork.
    """

    def __init__(
        self,
        path: Path,
        *,
        metric: Metric,
        fips_column: str = "fips",
        value_column: str = "value",
    ) -> None:
        self._path = path
        self._metric = metric
        self._fips_column = fips_column
        self._value_column = value_column

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """The single metric this file supplies."""
        return (self._metric,)

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Read the file and keep rows whose FIPS is in the universe."""
        wanted = {p.fips for p in places}
        text = self._path.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None or self._fips_column not in reader.fieldnames:
            raise ValueError(
                f"{self._path} has no column {self._fips_column!r}; " f"found {reader.fieldnames}"
            )
        values: dict[str, float] = {}
        for row in reader:
            fips = str(row[self._fips_column]).strip().zfill(5)
            raw = row.get(self._value_column)
            if fips not in wanted or raw in (None, ""):
                continue
            try:
                values[fips] = float(str(raw).replace(",", "").replace("$", "").strip())
            except ValueError:
                continue
        return {self._metric.key: values}
