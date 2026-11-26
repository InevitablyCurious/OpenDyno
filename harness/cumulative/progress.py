"""ProgressVector mapping for cumulative benchmark cell telemetry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .types import MISSING_TELEMETRY_SEAMS, ProgressVector

_MISSING = object()


def _field(source: Any, name: str) -> Any:
    if source is None:
        return _MISSING
    if isinstance(source, Mapping):
        return source.get(name, _MISSING)
    return getattr(source, name, _MISSING)


def _optional_int(value: Any) -> int | None:
    if value is _MISSING or value is None or isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        signless = text[1:] if text[0] in "+-" else text
        if not signless.isdigit():
            return None
        return int(text)

    if isinstance(value, float):
        if not value.is_integer():
            return None
        return int(value)

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is _MISSING or value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_default(value: Any, *, default: int) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        return default
    return parsed


def _str_or_default(value: Any, *, default: str) -> str:
    if value is _MISSING or value is None:
        return default
    return str(value)


def _optional_str(value: Any) -> str | None:
    if value is _MISSING or value is None:
        return None
    return str(value)


def _str_list(value: Any) -> list[str]:
    if value is _MISSING or not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _contention_fields(result: Any) -> dict[str, Any]:
    contention = _field(result, "contention")
    if contention is _MISSING or contention is None:
        return {}

    return {
        "http_429_count": _optional_int(_field(contention, "http_429_count")),
        "http_402_count": _optional_int(_field(contention, "http_402_count")),
        "retry_count": _int_or_default(_field(contention, "retry_count"), default=0),
        "upstream_error_count": _optional_int(
            _field(contention, "upstream_error_count")
        ),
        "max_request_ms": _optional_int(_field(contention, "max_request_ms")),
        "median_request_ms": _optional_int(_field(contention, "median_request_ms")),
    }


def _problems_after_from_result(result: Any) -> int | None:
    problems_final = _field(result, "problems_final")
    if problems_final is _MISSING or problems_final is None:
        return None
    if isinstance(problems_final, list):
        return len(problems_final)
    return _optional_int(problems_final)


def _worker_image_fields(result: Any) -> dict[str, Any]:
    fingerprint = _field(result, "worker_image_fingerprint")
    if fingerprint is _MISSING or fingerprint is None:
        return {"worker_image_id": None, "worker_image_created": None}
    return {
        "worker_image_id": _optional_str(_field(fingerprint, "image_id")),
        "worker_image_created": _optional_str(_field(fingerprint, "created")),
    }


def progress_from_cell_result(
    result: Any, *, cell: Any | None = None
) -> ProgressVector:
    """Map backgammon cell telemetry into a cumulative ProgressVector.

    Notes:
    - This accepts either real runtime objects or plain mappings for lightweight tests.
    - Any seam without a real source stays None so it is surfaced as missing telemetry.
    """

    # ABSENCE STAYS ABSENT. These read `_optional_*` rather than `_*_or_default`
    # so a signal the cell never reported arrives as None and registers on
    # `missing_telemetry_seams`, instead of arriving as a zero that a
    # lower-is-better curve reads as an excellent result.
    input_tokens = _optional_int(_field(result, "input_tokens"))
    output_tokens = _optional_int(_field(result, "output_tokens"))

    total_tokens_value = _field(result, "total_tokens")
    if total_tokens_value is _MISSING and cell is not None:
        total_tokens_value = _field(cell, "total_tokens")
    total_tokens = _optional_int(total_tokens_value)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        # ── EVERY TOKEN THE PROVIDER PROCESSED ─────────────────────────────
        #
        # This used to be `input + output`, which understated a cached run by
        # about 100x. Measured on run 1789076475: input 70,634 + output 107,486
        # = 178,120 reported, against 9,977,856 cache-read tokens the same cell
        # actually put through the provider. 98% of the work was invisible to
        # the number the benchmark scores on.
        #
        # WHY THAT WAS FATAL TO THE QUESTION BEING ASKED. An injected variant
        # makes the prompt BIGGER, and a bigger prompt is re-read on every turn —
        # which lands in cache read, the category being dropped. So the token axis
        # made the injected block look free, when the cost of the injected block is
        # precisely what it exists to measure.
        #
        # `output_tokens` already carries reasoning folded inside it, so
        # reasoning is NOT added again here — `reasoning_tokens` is the
        # recoverable share of output, not a fifth addend.
        #
        # Cache fields default to 0 on a path that cannot observe them, so a
        # provider without prompt caching sums exactly as it did before.
        total_tokens = (
            input_tokens
            + output_tokens
            + (_optional_int(_field(result, "cache_read_tokens")) or 0)
            + (_optional_int(_field(result, "cache_write_tokens")) or 0)
        )

    problems_before = _optional_int(_field(result, "problems_before"))
    problems_after = _problems_after_from_result(result)
    remaining_count = problems_after if problems_after is not None else None
    resolved_count = (
        problems_before - problems_after
        if problems_before is not None and problems_after is not None
        else None
    )

    contention_fields = _contention_fields(result)
    worker_image_fields = _worker_image_fields(result)

    build_chunks_value = _field(result, "build_chunks")
    build_chunks = [
        dict(row)
        for row in (build_chunks_value if isinstance(build_chunks_value, list) else [])
        if isinstance(row, Mapping)
    ]

    return ProgressVector(
        build_chunks=build_chunks,
        problems_before=problems_before,
        problems_after=problems_after,
        resolved_count=resolved_count,
        remaining_count=remaining_count,
        full_green=_str_or_default(_field(result, "verdict"), default="") == "PASS",
        attempts_to_green=_optional_int(_field(result, "attempts_to_green")),
        turns=_optional_int(_field(result, "turns")),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        wall_seconds=_optional_float(_field(result, "wall_seconds")),
        wall_cost_usd=_optional_float(_field(result, "wall_cost_usd")),
        consumer_injected_count=None,
        variant=_str_or_default(_field(result, "variant"), default=""),
        tool_calls=_optional_int(_field(result, "tool_calls")),
        test_invocations=_optional_int(_field(result, "test_invocations")),
        agentic_cycles=_optional_int(_field(result, "agentic_cycles")),
        termination_reason=_str_or_default(
            _field(result, "termination_reason"), default=""
        ),
        failed_gates=_str_list(_field(result, "failed_gates")),
        missing_telemetry_seams=list(MISSING_TELEMETRY_SEAMS),
        **contention_fields,
        **worker_image_fields,
    )


__all__ = ["progress_from_cell_result"]
