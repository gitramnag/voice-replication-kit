"""Build blind labels and summarize complete human listening scores."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from voice_replication_kit.errors import UserValidationError as ValueError

from voice_replication_kit.requests import validate_request


REQUIRED_METRICS = (
    "identity",
    "naturalness",
    "pacing",
    "pronunciation",
    "artifact_free",
    "emotion_fit",
)
FORBIDDEN_IDENTITY_FIELDS = {
    "evaluator",
    "evaluator_name",
    "reviewer",
    "reviewer_name",
    "listener_name",
}
VISIBLE_CANDIDATE_FIELDS = (
    "prompt_id",
    "source_segment_id",
    "unit_index",
    "style",
    "language",
    "text_shape",
)


def _request_digest(request_id: str) -> str:
    return hashlib.sha256(request_id.encode("utf-8")).hexdigest()


def _blind_label(index: int) -> str:
    return f"V{index:03d}"


def build_blind_map(requests: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Map unique request IDs to stable labels without exposing matrix order."""
    request_ids = [str(row.get("request_id", "")).strip() for row in requests]
    if not request_ids or any(not request_id for request_id in request_ids):
        raise ValueError("every request needs a non-empty request_id")
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("request ids must be unique")
    ordered = sorted(
        request_ids,
        key=lambda request_id: (
            _request_digest(request_id),
            request_id,
        ),
    )
    return {
        request_id: f"CLIP-{index:03d}"
        for index, request_id in enumerate(ordered, 1)
    }


def build_blind_pack(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Split private matrix rows into evaluator metadata and an unblinding map."""
    for row in rows:
        validate_request(row)
    request_ids = [str(row.get("request_id", "")).strip() for row in rows]
    if not request_ids or any(not request_id for request_id in request_ids):
        raise ValueError("every matrix row needs a non-empty request_id")
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("request ids must be unique")
    for row in rows:
        missing = [field for field in VISIBLE_CANDIDATE_FIELDS if field not in row]
        if missing:
            raise ValueError(f"matrix row is missing evaluator fields: {missing}")

    by_request_id = {str(row["request_id"]): row for row in rows}
    ordered_ids = sorted(request_ids)
    visible: list[dict[str, Any]] = []
    secret: dict[str, str] = {}
    for index, request_id in enumerate(ordered_ids, 1):
        label = _blind_label(index)
        if label in secret:
            raise ValueError("blind labels must be unique")
        row = by_request_id[request_id]
        visible.append(
            {
                "blind_label": label,
                **{field: row[field] for field in VISIBLE_CANDIDATE_FIELDS},
                "candidate_audio_basename": f"{label}.wav",
            }
        )
        secret[label] = request_id
    return visible, secret


def _score(value: Any, metric: str, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} {metric} must be a number from 1 to 5")
    score = float(value)
    if not 1 <= score <= 5:
        raise ValueError(f"{label} {metric} must be a number from 1 to 5")
    return score


def summarize_scores(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize complete ratings by style without guessing through gaps or ties."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_labels: set[str] = set()
    for row in rows:
        lowered_keys = {str(key).lower() for key in row}
        if lowered_keys & FORBIDDEN_IDENTITY_FIELDS:
            raise ValueError("score rows must not contain personal evaluator identity fields")
        label = str(row.get("blind_label", "")).strip()
        style = str(row.get("style", "")).strip()
        if not label or not style:
            raise ValueError("every score row needs a blind_label and style")
        if label in seen_labels:
            raise ValueError("blind labels must be unique")
        seen_labels.add(label)
        scores = [_score(row.get(metric), metric, label) for metric in REQUIRED_METRICS]
        complete = all(score is not None for score in scores)
        grouped[style].append(
            {
                "blind_label": label,
                "complete": complete,
                "mean": (
                    round(sum(score for score in scores if score is not None) / len(scores), 3)
                    if complete
                    else None
                ),
            }
        )

    styles: dict[str, dict[str, Any]] = {}
    for style in sorted(grouped):
        candidates = grouped[style]
        rated = [candidate for candidate in candidates if candidate["complete"]]
        complete = len(rated) == len(candidates)
        best_score: float | None = None
        winner: str | None = None
        tied_labels: list[str] = []
        if complete and rated:
            best_score = max(float(candidate["mean"]) for candidate in rated)
            tied_labels = sorted(
                str(candidate["blind_label"])
                for candidate in rated
                if candidate["mean"] == best_score
            )
            if len(tied_labels) == 1:
                winner = tied_labels[0]
                tied_labels = []
        styles[style] = {
            "candidate_count": len(candidates),
            "rated_candidate_count": len(rated),
            "complete": complete,
            "best_score": best_score if complete else None,
            "winner": winner if complete else None,
            "tied_labels": tied_labels if complete else [],
        }

    return {
        "complete": bool(styles) and all(item["complete"] for item in styles.values()),
        "required_metrics": list(REQUIRED_METRICS),
        "styles": styles,
    }
