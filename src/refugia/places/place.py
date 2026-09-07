"""One candidate place to live: a US county, with its metro context."""

from dataclasses import dataclass

from refugia.places.cbsa import Cbsa


@dataclass(frozen=True, slots=True)
class Place:
    """A county-level candidate.

    The county is the unit because every free national dataset this project uses
    resolves to a county FIPS: CDC PLACES, the smoke reanalysis and the wildfire
    risk tables are all published that way. Metro attributes (cost of living) are
    published per CBSA and joined down onto the counties they contain.

    `lat`/`lon` are the county's centroid of population, not of area. Sampling
    vegetation around the area centroid of a large western county would describe
    empty rangeland nobody lives in.
    """

    fips: str
    name: str
    state: str
    lat: float
    lon: float
    population: int
    cbsa: Cbsa | None = None

    @property
    def label(self) -> str:
        """Human-facing name.

        The county leads, because the county is the unit being ranked. Labelling a
        row by its metro makes the four counties of one metro read as four
        identical rows, when they differ in exactly the vegetation the ranking
        turns on.
        """
        return f"{self.name} County, {self.state}"

    @property
    def cbsa_type(self) -> str | None:
        """`metro` or `micro`, exposed flat because filters name it that way.

        Profiles and the query planner's vocabulary both use this name, so it stays
        addressable as a field even though it is stored inside the CBSA object.
        """
        return self.cbsa.kind if self.cbsa else None

    @property
    def metro(self) -> str:
        """The CBSA this county belongs to, if any."""
        return self.cbsa.name if self.cbsa else ""
