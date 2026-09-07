"""Metrics the place release publishes and the county release does not."""

# Measures the place release carries that the county release does not, so they
# have no definition among the county metrics and would otherwise be collected and
# never shown.
CITY_ONLY = (
    {
        "key": "social_isolation",
        "label": "Social isolation",
        "unit": "% of adults",
        "direction": "lower_better",
        "category": "community",
        "description": (
            "Adults reporting they rarely or never get the social and emotional "
            "support they need. Published per place only, and only where the state "
            "ran the survey module it comes from - eleven states did not, Oregon "
            "among them, so a town there has no figure and nothing to compare against."
        ),
        "source": "CDC PLACES 2025 release, place data",
    },
)
