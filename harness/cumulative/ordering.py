"""Append-per-click session ordering for cumulative benchmark runs.

ONE CLICK APPENDS ONE CELL. Nothing is precomputed: there is no seeded B
order, no A budget, no cursor. A run's identity is its own cell — variant, model,
config fingerprint — not a position in a schedule someone planned before the
work existed.

That is a correction, not a simplification. A precomputed schedule had to be
rebuilt on every launch (the A prefix, then the seeded B band), so the plan
was a function of the OPERATOR'S LAUNCH ARGUMENTS rather than of what the
campaign had recorded, and a control-plane restart re-seeded a cursor into the
past — handing out indices that had already run. Appending cannot drift that
way: the next cell's index is the length of the log that already exists.

``sequence_index`` stays a monotonic contiguous 0-based counter (the append
ordinal). It is the cell's address everywhere — ``cell-<seq4>`` directories,
the status stream, the results ledger — so it must never be anything else.
"""

from __future__ import annotations

from collections.abc import Sequence

from .types import PhaseGroup, RosterEntry, ScheduledSession

VARIANTS: tuple[str, ...] = ("a", "b")


def _require_non_empty_roster(roster: list[RosterEntry]) -> None:
    if not roster:
        raise ValueError("roster must not be empty")


def append_session(
    roster: list[RosterEntry],
    *,
    existing: Sequence[ScheduledSession],
    variant: str,
) -> ScheduledSession:
    """Return the ONE session this click appends to the campaign's log.

    One manifest carries one model (``--model`` replaces the whole roster and
    ``roster_hash`` guards resume), so the appended cell takes ``roster[0]``'s
    model and provider pin. The pin is the roster entry's, never inferred from
    the model slug, so the cell records the provider the campaign was pinned to.

    The variant is the operator's choice at click time: an A cell is a point of
    the baseline floor, a B cell is one measurement against it. Neither variant
    replicates here — N of a configuration is N clicks, and the log records each
    one as its own cell.
    """
    _require_non_empty_roster(roster)
    mode = str(variant or "").strip().lower()
    if mode not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}, got {variant!r}")

    entry = roster[0]
    return ScheduledSession(
        sequence_index=len(existing),
        model=entry.model,
        provider_pin=entry.provider_pin,
        variant=mode,
        phase_group=(
            PhaseGroup.A_BASELINE.value if mode == "a" else PhaseGroup.B.value
        ),
        roster_index=0,
    )


__all__ = ["append_session"]
