"""The fetched metric values for a run, and how they persist between commands."""

import json
from dataclasses import dataclass
from pathlib import Path

from refugia.metrics.metric import Metric
from refugia.places.cbsa import Cbsa
from refugia.places.place import Place


@dataclass(frozen=True, slots=True)
class Dataset:
    """Places, metric declarations and raw values, as one saved artifact.

    Fetching and scoring are separate commands because fetching is slow and network
    bound while scoring is instantaneous. Persisting the join between them means a
    user can re-weight a hundred times, or hand the file to the artifact and the
    local model, without touching a single upstream service again.
    """

    places: tuple[Place, ...]
    metrics: tuple[Metric, ...]
    values: dict[str, dict[str, float]]
    # When this file was assembled, and the date of the oldest cached response
    # behind it. Both, because they answer different questions: a build can be an
    # hour old and made entirely of figures cached last year.
    built_at: str = ""
    oldest_response: str = ""

    def save(self, path: Path) -> None:
        """Write the whole dataset as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1))

    @classmethod
    def load(cls, path: Path) -> "Dataset":
        """Read a dataset previously saved by `save`."""
        return cls.from_dict(json.loads(path.read_text()))

    def to_dict(self) -> dict:
        """Plain-mapping form, used for both the file and the artifact payload."""
        return {
            "places": [
                {
                    "fips": p.fips,
                    "name": p.name,
                    "state": p.state,
                    "lat": p.lat,
                    "lon": p.lon,
                    "population": p.population,
                    "cbsa_code": p.cbsa.code if p.cbsa else None,
                    "cbsa_name": p.cbsa.name if p.cbsa else None,
                    "cbsa_type": p.cbsa.kind if p.cbsa else None,
                }
                for p in self.places
            ],
            "metrics": [
                {
                    "key": m.key,
                    "label": m.label,
                    "unit": m.unit,
                    "direction": m.direction,
                    "category": m.category,
                    "description": m.description,
                    "source": m.source,
                    "citation": m.citation,
                    "terms_url": m.terms_url,
                }
                for m in self.metrics
            ],
            "values": self.values,
            "built_at": self.built_at,
            "oldest_response": self.oldest_response,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Dataset":
        """Rebuild from the mapping produced by `to_dict`."""
        return cls(
            places=tuple(cls._place(p) for p in payload["places"]),
            metrics=tuple(Metric(**m) for m in payload["metrics"]),
            values={k: dict(v) for k, v in payload["values"].items()},
            # Absent in any dataset saved before provenance existed, and a stale
            # file should still load rather than becoming unreadable.
            built_at=payload.get("built_at", ""),
            oldest_response=payload.get("oldest_response", ""),
        )

    @staticmethod
    def _place(row: dict) -> Place:
        """Rebuild one place, folding the flat CBSA columns back into a value object.

        The file keeps them flat because the page reads them that way, and a nested
        object there would buy nothing.
        """
        cbsa = (
            Cbsa(row["cbsa_code"], row["cbsa_name"], row["cbsa_type"])
            if row.get("cbsa_code")
            else None
        )
        return Place(
            fips=row["fips"],
            name=row["name"],
            state=row["state"],
            lat=row["lat"],
            lon=row["lon"],
            population=row["population"],
            cbsa=cbsa,
        )

    def coverage(self) -> dict[str, float]:
        """Share of places each metric actually has a value for, 0-1."""
        count = len(self.places) or 1
        return {m.key: len(self.values.get(m.key, {})) / count for m in self.metrics}
