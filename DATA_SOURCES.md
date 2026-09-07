# Data sources

refugia ships no data. Every figure it shows is fetched at run time, by you, from
the publisher — the repository contains endpoints and code, and `data/` is
ignored. So the terms below govern what you do with what you fetch, and in
particular what you do with a page you publish from it, rather than governing
this repository.

**Two carry real obligations.** County Health Rankings licenses its content for
personal and non-profit use only and requires a specific citation; Zillow requires
clear attribution. Both citations are in the footer of every published page. The
rest are US federal works, public domain, where attribution is courtesy.

**Two positions are inferred rather than confirmed**, and are marked as such
below. Do not restate them as fact without checking.

---

## County Health Rankings & Roadmaps

University of Wisconsin Population Health Institute ·
`https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data2025_v2.csv`

Five metrics: `air_pollution`, `life_expectancy`, `poor_mental_health_days`,
`poor_or_fair_health`, `social_associations`.

**Terms — verified.** Not public domain. All content is CHR&R's, all rights
reserved, under a non-exclusive licence "to access and use those portions of the
CHR&R Website without a password or logon **for personal or non-profit purposes**
including educational, research, or public health". Content "may not be copied or
otherwise used for **commercial use** (including without limitation, use to train
AI models intended to be offered as commercial products) without CHR&R's express
prior written consent."

**Required citation**, carried in the page footer:

> University of Wisconsin Population Health Institute. County Health Rankings &
> Roadmaps. www.countyhealthrankings.org

CHR&R compiles from federal sources; what is licensed is their analytic file, not
the underlying facts. A use that cannot live inside the non-commercial licence can
often reach the same measures from the original publishers instead.

## Zillow

Zillow Group · `https://files.zillowstatic.com/research/public_csvs/zhvi/`

One metric: `home_value`, the Zillow Home Value Index.

**Terms — verified.** "All data accessed and downloaded from this page is free for
public use by consumers, media, analysts, academics and policymakers, consistent
with our published Terms of Use," and "proper and clear attribution of all data to
Zillow is required." The stricter licence that forbids derivative works governs the
Public Records Data **API**, which this does not use.

**Attribution**, carried in the page footer: the index named in full, linked to
`zillow.com/research/data`.

## LANDFIRE

USGS and USDA Forest Service ·
`https://lfps.usgs.gov/arcgis/rest/services/Landfire_LF2024/` and
`https://www.landfire.gov/sites/default/files/CSV/2024/LF2024_EVT.csv`

Three metrics: `juniper_cover`, `sagebrush_cover`, `populus_cover`, sampled as
land-cover fractions in a radius around each county's population-weighted centre.

**Terms — inferred, not confirmed.** LANDFIRE is a federal interagency programme
and its products are routinely treated as public domain, but this project has not
checked that against a published statement. Treat it as unverified.

LF2025 is a partial release: it returns NoData across the eastern US. LF2024 is
national and is what the code uses.

## CDC PLACES

Centers for Disease Control and Prevention, with the Robert Wood Johnson
Foundation and the CDC Foundation ·
`https://data.cdc.gov/resource/swc5-untb.json` (county) and
`https://data.cdc.gov/resource/vgc8-iyc4.json` (place)

County metrics `depression`, `mental_distress`, `short_sleep`, `asthma`,
`physical_distress`; and the place release for the city panel, which adds
self-rated health and social isolation.

**Terms.** A work of the US federal government, public domain. No key or
registration is required.

These are **model-based small-area estimates** built from BRFSS survey responses,
not direct county measurements — which is most of why the published page carries
the caveat it does.

## NASA POWER

NASA Langley Research Center ·
`https://power.larc.nasa.gov/api/temporal/climatology/regional`

Four metrics: `sunshine`, `hottest_day`, `coldest_day`, `humidity`.

**Terms — verified.** "There are no restrictions on the use, access, and/or
download of data from the NASA POWER Project." NASA requests citation.

## EPA Air Quality System

US Environmental Protection Agency ·
`https://aqs.epa.gov/aqsweb/airdata/annual_aqi_by_county_{year}.zip`

Two metrics: `unhealthy_air_days`, `worst_air_day`, from the annual county AQI
summaries — the episodic half that an annual mean averages away.

**Terms.** A work of the US federal government, public domain.

## Wildfire Risk to Communities

USDA Forest Service, with Headwaters Economics and Pyrologix ·
`https://wildfirerisk.org/wp-content/uploads/2026/04/wrc_download_20260415.xlsx`

One metric: `wildfire_risk`, a national percentile.

**Terms — inferred, not confirmed.** The site publishes no licence, terms of use
or citation requirement. It was created by the USDA Forest Service under the 2018
Consolidated Appropriations Act, but non-federal partners co-produced it, so
public domain does not follow automatically from federal funding. The data is
published for public download and nothing suggests a restriction; the position is
simply not established.

## US Census Bureau

`https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt`
(county population-weighted centroids) ·
`https://www2.census.gov/programs-surveys/metro-micro/geographies/` (CBSA
delineation) ·
`https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/` (city
population estimates) ·
`https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/`
(place gazetteer)

Not metrics: the candidate universe itself, the population-weighted centres the
vegetation sample is taken around, and the city markers on the map.

**Terms.** A work of the US federal government, public domain.

## us-atlas

Michael Bostock · `https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json`

County and state outlines, projected to SVG paths at build time and embedded in
the published page.

**Terms — verified.** ISC licence, which is permissive but conditions
redistribution on retaining the copyright notice. Because the page embeds
geometry derived from the topology, that notice travels with every published
page and is in the footer. us-atlas is itself a redistribution of the Census
cartographic boundary files, which are public domain.

---

## If you publish a page

A page written by `refugia publish` embeds values for every county it ranks, so
sharing one is redistribution in a way that running the tool is not. The footer
carries the required citations automatically. What it cannot decide for you is
whether your use is commercial: if it is, the County Health Rankings licence needs
their prior written consent, or those five metrics need to come from the federal
sources underneath them.

Attribution currently travels as prose in this file and as a footer string built
from each metric's `source` field. A metric cannot carry its own citation or terms
URL, which is why this file has to be kept in step by hand.
