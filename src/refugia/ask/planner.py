"""Turns a plain-English question into a scoring profile a local model never computes."""

import json

import httpx

from refugia import USER_AGENT

from refugia.metrics.metric import Metric
from refugia.scoring.profile import Profile
from refugia.scoring.scored_place import ScoredPlace
from refugia.scoring.vocabulary import criterion_fields

PLAN_SYSTEM = """\
You translate a question about where to live into a JSON scoring profile.

You do NOT rank places, compute scores, or state any figure. A deterministic engine
does that from the profile you emit. Your only job is to choose metrics, weights and
filters.

Reply with JSON only, in this shape:
{"name": "...", "normalization": "percentile",
 "weights": {"<metric_key>": <number>, ...},
 "criteria": [{"field": "<metric_key or place field>",
               "comparison": "min|max|in|not_in", "value": <number or [strings]>}]}

Rules:
- Use only the metric keys listed below, plus these place fields for criteria:
  population, state, cbsa_type.
- Weights are positive numbers denoting relative importance; the engine rescales them.
- Every metric already encodes whether high or low is good. Never negate a weight to
  mean "less of this"; just weight it.
- Use criteria for hard requirements ("under $400k", "not in Texas"), weights for
  preferences ("cheap matters a lot").
"""

NARRATE_SYSTEM = """\
You explain a ranking that has already been computed.

Every number you may state is in the DATA block. Never invent, interpolate, round
into a new claim, or infer a figure that is not there. If the answer is not in the
data, say so plainly. Be concise and concrete: name places, cite their figures, and
say what drove the result. No preamble.
"""


class QueryPlanner:
    """Runs a local Ollama model as a query planner and narrator.

    The model never sees a number it is expected to reason arithmetically about, and
    never produces a ranking. It emits a profile, the engine ranks deterministically,
    and the model then describes rows it has been handed. A local 8-30B model will
    confabulate a plausible PM2.5 reading if asked to read one out of context; it
    cannot if it is never the thing holding the numbers.
    """

    def __init__(
        self,
        *,
        model: str = "qwen3:30b-a3b",
        host: str = "http://localhost:11434",
        timeout: float = 180.0,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = timeout

    def plan(self, question: str, metrics: tuple[Metric, ...]) -> Profile:
        """Ask the model for a scoring profile matching the question."""
        catalogue = "\n".join(
            f"- {m.key}: {m.label} ({m.unit}); {m.direction}; {m.description}" for m in metrics
        )
        raw = self._chat(
            PLAN_SYSTEM + "\nAvailable metrics:\n" + catalogue,
            question,
            expect_json=True,
        )
        payload = json.loads(raw)
        known = {m.key for m in metrics}
        payload["weights"] = {k: v for k, v in payload.get("weights", {}).items() if k in known}
        allowed_fields = criterion_fields(metrics)
        payload["criteria"] = [
            c for c in payload.get("criteria", []) if c.get("field") in allowed_fields
        ]
        if not payload["weights"]:
            raise ValueError("the model returned no usable metric weights")
        return Profile.from_dict(payload)

    def narrate(
        self,
        question: str,
        profile: Profile,
        ranked: list[ScoredPlace],
        metrics: tuple[Metric, ...],
    ) -> str:
        """Describe an already-computed ranking without recomputing anything."""
        units = {m.key: m.unit for m in metrics}
        rows = [
            {
                "rank": position,
                "place": scored.place.label,
                "state": scored.place.state,
                "score": round(scored.total, 1),
                "values": {
                    k: f"{v:,.1f} {units.get(k, '')}".strip() for k, v in sorted(scored.raw.items())
                },
            }
            for position, scored in enumerate(ranked, start=1)
        ]
        data = json.dumps({"weights": profile.normalized_weights, "results": rows}, indent=1)
        return self._chat(NARRATE_SYSTEM, f"QUESTION: {question}\n\nDATA:\n{data}")

    def _chat(self, system: str, user: str, *, expect_json: bool = False) -> str:
        """One non-streaming Ollama chat turn."""
        body = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0},
        }
        if expect_json:
            body["format"] = "json"
        try:
            response = httpx.post(
                f"{self._host}/api/chat",
                json=body,
                headers={"User-Agent": USER_AGENT},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(
                f"could not reach Ollama at {self._host} ({error}). "
                f"Start it with `ollama serve` and pull the model with "
                f"`ollama pull {self._model}`."
            ) from error
        return response.json()["message"]["content"]
