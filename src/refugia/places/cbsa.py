"""A county's metropolitan or micropolitan area membership."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Cbsa:
    """The Census statistical area a county belongs to.

    The three values are jointly present or jointly absent -- a county is either in
    a CBSA, with all of a code, a title and a kind, or in none of them. Carrying
    them as three nullable fields on `Place` invited the state where one is set and
    the others are not, which no reader could interpret.
    """

    code: str
    name: str
    kind: str
