"""The generic CSV adapter is how a metric enters the model without new code."""

import pytest

from refugia.metrics.sources.csv_file import CsvFileSource


def _write(tmp_path, text, name="m.csv"):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_reads_a_fips_keyed_column(tmp_path, places, parks):
    """The happy path: two columns, matched on FIPS."""
    path = _write(tmp_path, "fips,value\n00001,10\n00002,20\n")
    result = CsvFileSource(path, metric=parks).fetch(places)
    assert result == {"parks": {"00001": 10.0, "00002": 20.0}}


def test_pads_short_fips(tmp_path, places, parks):
    """A spreadsheet that dropped the leading zeros still joins."""
    path = _write(tmp_path, "fips,value\n1,10\n2,20\n")
    result = CsvFileSource(path, metric=parks).fetch(places)
    assert set(result["parks"]) == {"00001", "00002"}


def test_strips_currency_and_separators(tmp_path, places, parks):
    """Values copied out of a report are still numbers."""
    path = _write(tmp_path, 'fips,value\n00001,"$1,250"\n')
    result = CsvFileSource(path, metric=parks).fetch(places)
    assert result["parks"]["00001"] == 1250.0


def test_ignores_places_outside_the_universe(tmp_path, places, parks):
    """A national file must not smuggle in counties nobody is considering."""
    path = _write(tmp_path, "fips,value\n00001,10\n99999,99\n")
    result = CsvFileSource(path, metric=parks).fetch(places)
    assert "99999" not in result["parks"]


def test_unparseable_rows_are_skipped_not_fatal(tmp_path, places, parks):
    """One bad cell must not lose the rest of the file."""
    path = _write(tmp_path, "fips,value\n00001,n/a\n00002,20\n")
    result = CsvFileSource(path, metric=parks).fetch(places)
    assert result["parks"] == {"00002": 20.0}


def test_a_missing_column_names_what_was_found(tmp_path, places, parks):
    """The error has to tell the user what their file actually contains."""
    path = _write(tmp_path, "county,value\n00001,10\n")
    with pytest.raises(ValueError, match="county"):
        CsvFileSource(path, metric=parks).fetch(places)
