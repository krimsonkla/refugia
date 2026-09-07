"""Concrete data adapters, one per upstream publisher."""

from refugia.metrics.sources.cdc_places import CdcPlacesSource
from refugia.metrics.sources.csv_file import CsvFileSource
from refugia.metrics.sources.epa_air_quality import EpaAirQualitySource
from refugia.metrics.sources.landfire_vegetation import LandfireVegetationSource
from refugia.metrics.sources.nasa_power_climate import NasaPowerClimateSource
from refugia.metrics.sources.zillow_home_value import ZillowHomeValueSource

__all__ = [
    "CdcPlacesSource",
    "CsvFileSource",
    "EpaAirQualitySource",
    "LandfireVegetationSource",
    "NasaPowerClimateSource",
    "ZillowHomeValueSource",
]
