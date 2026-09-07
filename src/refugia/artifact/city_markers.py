"""The largest places inside each county, positioned on the county map."""

import csv
import io
import zipfile

from refugia.artifact.geometry import project
from refugia.places.place import Place
from refugia.store.cache import Cache

POPULATION_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/"
    "totals/sub-est2024.csv"
)
GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/"
    "2024_Gaz_place_national.zip"
)

# Population estimates carry a row per place *part* within a county, which is the
# only Census product that ties a place to a county at all.
PLACE_IN_COUNTY = "157"

# The legal type the Census appends is always lower case, which is what makes it
# separable from the name: "Carson City" is a place called Carson City, while
# "Bend city" is Bend. Matching is therefore case sensitive, and longest first so
# that "urban county" is not mistaken for "county".
SUFFIXES = tuple(
    sorted(
        (
            " (pt.)",
            " (balance)",
            " city",
            " town",
            " village",
            " borough",
            " CDP",
            " municipality",
            " township",
            " county",
            " urban county",
            " consolidated government",
            " metro government",
            " metropolitan government",
            " unified government",
            " corporation",
            " plantation",
            " gore",
            " grant",
            " location",
            " reservation",
        ),
        key=len,
        reverse=True,
    )
)


class CityMarkers:
    """Finds the biggest places in each county and projects them onto the map.

    A city that straddles a county line is counted once, in the county holding the
    largest share of it. Keeping every fragment would put a marker for Sioux Falls
    in a neighbouring county at coordinates outside it, because the position on
    file is the whole place's centre rather than the fragment's.
    """

    def __init__(self, cache: Cache, *, per_county: int = 3) -> None:
        self._cache = cache
        self._per_county = per_county

    def for_places(
        self,
        places: tuple[Place, ...],
        transform: tuple[float, float, float],
    ) -> dict[str, list[dict]]:
        """Return {county fips: [{name, population, x, y}, ...]} biggest first."""
        grouped: dict[str, list[dict]] = {}
        for marker in self._markers(places, transform):
            # The county keys the grouping; the place GEOID stays on the marker
            # because it is the join key for everything published per place.
            grouped.setdefault(marker.pop("fips"), []).append(marker)
        return {
            fips: sorted(items, key=lambda c: -c["population"])[: self._per_county]
            for fips, items in grouped.items()
        }

    def _markers(
        self,
        places: tuple[Place, ...],
        transform: tuple[float, float, float],
    ) -> list[dict]:
        """Every place, once, projected onto the map."""
        coordinates = self._coordinates()
        scale, offset_x, offset_y = transform
        out = []
        for geoid, (population, fips, name) in self._largest_part(places).items():
            point = coordinates.get(geoid)
            if point is None:
                continue
            x, y = project(point[1], point[0])
            out.append(
                {
                    "fips": fips,
                    "geoid": geoid,
                    "name": _clean(name),
                    "population": population,
                    "lat": point[0],
                    "lon": point[1],
                    "x": round(x * scale + offset_x, 1),
                    "y": round(y * scale + offset_y, 1),
                }
            )
        return out

    def _largest_part(self, places: tuple[Place, ...]) -> dict[str, tuple[int, str, str]]:
        """Each place mapped to the county holding the largest share of it."""
        wanted = {p.fips for p in places}
        best: dict[str, tuple[int, str, str]] = {}
        for row in self._population_rows():
            if row["SUMLEV"] != PLACE_IN_COUNTY:
                continue
            fips = row["STATE"] + row["COUNTY"]
            if fips not in wanted:
                continue
            try:
                population = int(row["POPESTIMATE2024"])
            except (KeyError, ValueError):
                continue
            geoid = row["STATE"] + row["PLACE"]
            if geoid not in best or population > best[geoid][0]:
                best[geoid] = (population, fips, row["NAME"])
        return best

    def _population_rows(self) -> list[dict]:
        """Place-level population estimates."""
        payload = self._cache.fetch_url(POPULATION_URL, key=POPULATION_URL, suffix=".csv")
        return list(csv.DictReader(io.StringIO(payload.decode("latin-1"))))

    def _coordinates(self) -> dict[str, tuple[float, float]]:
        """Place GEOID to (lat, lon), from the gazetteer."""
        payload = self._cache.fetch_url(GAZETTEER_URL, key=GAZETTEER_URL, suffix=".zip")
        out: dict[str, tuple[float, float]] = {}
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            with archive.open(archive.namelist()[0]) as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="latin-1"), delimiter="\t")
                # The gazetteer pads its final header to a fixed width.
                header = [h.strip() for h in next(reader)]
                index = {name: position for position, name in enumerate(header)}
                for row in reader:
                    if len(row) <= index["INTPTLONG"]:
                        continue
                    try:
                        out[row[index["GEOID"]].strip()] = (
                            float(row[index["INTPTLAT"]]),
                            float(row[index["INTPTLONG"]]),
                        )
                    except ValueError:
                        continue
        return out


def _clean(name: str) -> str:
    """Drop the legal type the Census appends to a place name.

    Repeatedly, because the suffixes stack: a place split across counties is
    published as "Portland city (pt.)", and removing one of the two leaves the
    other on the label.
    """
    cleaned = name.strip()
    changed = True
    while changed:
        changed = False
        for suffix in SUFFIXES:
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
                changed = True
                break
    return cleaned or name
