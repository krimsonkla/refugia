"""Rank US places to live against a personal allergen, wellbeing and cost profile."""

__version__ = "0.1.0"

# Every request this project makes says who is making it. The endpoints are small
# public services and none of them asked to be here; an operator seeing unfamiliar
# traffic should be able to find out what it is and where to complain, which is
# the difference between a fork's share of six thousand requests being a project
# and being an anomaly.
USER_AGENT = f"refugia/{__version__} (+https://github.com/krimsonkla/refugia)"
