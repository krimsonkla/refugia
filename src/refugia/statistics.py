"""Small numeric helpers shared by scoring and by composite metrics."""

from collections.abc import Mapping


def percentile_rank(values: Mapping[str, float]) -> dict[str, float]:
    """Rank values to 0-100, averaging ranks within ties.

    Lives below both the normaliser and the sources because a composite metric has
    to rank its components the same way the scoring engine would; two independent
    implementations of this would disagree at the ties and nobody would notice.
    """
    ordered = sorted(values.items(), key=lambda kv: kv[1])
    count = len(ordered)
    if count == 0:
        return {}
    if count == 1:
        return {ordered[0][0]: 50.0}
    out: dict[str, float] = {}
    index = 0
    while index < count:
        stop = index
        while stop + 1 < count and ordered[stop + 1][1] == ordered[index][1]:
            stop += 1
        score = 100.0 * ((index + stop) / 2.0) / (count - 1)
        for position in range(index, stop + 1):
            out[ordered[position][0]] = score
        index = stop + 1
    return out
