"""Assembles the candidate place universe from Census reference files."""

import csv
import io
from pathlib import Path

import openpyxl

from refugia.places.cbsa import Cbsa
from refugia.places.place import Place
from refugia.store.cache import Cache

CENTROIDS_URL = (
    "https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt"
)
DELINEATION_URL = (
    "https://www2.census.gov/programs-surveys/metro-micro/geographies/"
    "reference-files/2023/delineation-files/list1_2023.xlsx"
)

UNIVERSES = ("metro_micro", "metro", "all")


class PlaceRegistry:
    """Builds and holds the counties a run scores.

    Two Census files are enough. The centres-of-population file supplies the
    population-weighted centroid, which is the coordinate vegetation sampling must
    use: the area centroid of a large western county sits in rangeland nobody lives
    in, and would describe a landscape the candidate would never breathe. The
    delineation file supplies CBSA membership, which is both the default filter and
    the join key for anything published per metro.
    """

    def __init__(self, places: tuple[Place, ...]) -> None:
        self._places = places
        self._by_fips = {p.fips: p for p in places}

    @classmethod
    def load(
        cls,
        cache: Cache,
        *,
        universe: str = "metro_micro",
        refresh: bool = False,
    ) -> "PlaceRegistry":
        """Fetch the Census reference files and build the place set."""
        if universe not in UNIVERSES:
            raise ValueError(f"universe must be one of {UNIVERSES}, got {universe!r}")
        centroids = cache.fetch_url(CENTROIDS_URL, key="census-cenpop2020-county", refresh=refresh)
        delineation = cache.fetch_url(
            DELINEATION_URL, key="census-cbsa-list1-2023", suffix=".xlsx", refresh=refresh
        )
        cbsa = cls._parse_delineation(
            cache.path_for("census-cbsa-list1-2023", ".xlsx"), delineation
        )
        return cls(cls._build(centroids, cbsa, universe))

    @staticmethod
    def _parse_delineation(path: Path, payload: bytes) -> dict[str, tuple[str, str, str]]:
        """Map county FIPS -> (cbsa_code, cbsa_title, 'metro'|'micro')."""
        if not path.exists():
            path.write_bytes(payload)
        workbook = openpyxl.load_workbook(path, read_only=True)
        sheet = workbook.active
        header_row = None
        columns: dict[str, int] = {}
        out: dict[str, tuple[str, str, str]] = {}
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip() if c is not None else "" for c in row]
            if header_row is None:
                if "CBSA Code" in cells and "FIPS State Code" in cells:
                    header_row = cells
                    columns = {name: i for i, name in enumerate(cells)}
                continue
            code = cells[columns["CBSA Code"]]
            state = cells[columns["FIPS State Code"]]
            county = cells[columns["FIPS County Code"]]
            if not code or not state or not county:
                continue
            kind = (
                "metro"
                if "Metropolitan" in cells[columns["Metropolitan/Micropolitan Statistical Area"]]
                else "micro"
            )
            out[f"{state.zfill(2)}{county.zfill(3)}"] = (code, cells[columns["CBSA Title"]], kind)
        workbook.close()
        return out

    @staticmethod
    def _build(
        centroids: bytes,
        cbsa: dict[str, tuple[str, str, str]],
        universe: str,
    ) -> tuple[Place, ...]:
        """Join centroids to CBSA membership and apply the universe filter."""
        places: list[Place] = []
        reader = csv.DictReader(io.StringIO(centroids.decode("utf-8-sig")))
        for row in reader:
            fips = f"{row['STATEFP'].zfill(2)}{row['COUNTYFP'].zfill(3)}"
            membership = cbsa.get(fips)
            if universe == "metro_micro" and membership is None:
                continue
            if universe == "metro" and (membership is None or membership[2] != "metro"):
                continue
            places.append(
                Place(
                    fips=fips,
                    name=row["COUNAME"],
                    state=row["STNAME"],
                    lat=float(row["LATITUDE"]),
                    lon=float(row["LONGITUDE"]),
                    population=int(row["POPULATION"]),
                    cbsa=Cbsa(*membership) if membership else None,
                )
            )
        return tuple(sorted(places, key=lambda p: p.fips))

    @property
    def places(self) -> tuple[Place, ...]:
        """Every candidate, ordered by FIPS."""
        return self._places

    def get(self, fips: str) -> Place | None:
        """One candidate by FIPS, or None."""
        return self._by_fips.get(fips)

    def __len__(self) -> int:
        return len(self._places)
