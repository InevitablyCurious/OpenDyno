"""Cell-telemetry scan leaves for the challenge adapter.

Extracted verbatim from harness/adapters/challenge/__init__.py
(WO-LI15-I1B STAGE 1B) and re-exported there, so every name stays
resolvable as harness.adapters.challenge.<name>.

_LOG is this module's own logger -- importing the package-level one would
be circular. The logger name changes from harness.adapters.challenge to
harness.adapters.challenge.telemetry; the consumers are the fail-open
warnings in the TelemetryMixin scan methods.

STAGE 2B (WO-LI15-I2B) adds TelemetryMixin: the in-cell telemetry method
group moved out of ChallengeRunner, which inherits the mixin, so every
self./cls. cross-call resolves through the MRO. DECLARED_TEST_COMMANDS moved
here with its consumer (_extract_event_counts) -- the same pattern as
_MODEL_PRICING_USD_PER_1M moving to pricing.py in STAGE 2A -- and is
re-exported by the package __init__, so
harness.adapters.challenge.DECLARED_TEST_COMMANDS stays resolvable. This
module must not import from the package __init__.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sqlite3
import time

from harness.outcomes.predicate_emitter import walk_manifest

from .constants import _SPEC

_LOG = logging.getLogger(__name__)


def _snapshot_state_hash(worktree: Path) -> str | None:
    """Fingerprint the graded code for ONE attempt, at the moment it was graded.

    A cell keeps only its final worktree on disk, so a later reader cannot
    recover what the code looked like at attempt 1 or 2. Captured here, while
    that state still exists, each attempt's gate results stay bound to the code
    they actually ran against.

    Returns None on any failure: an unhashable worktree is recorded as having
    no snapshot, never as some other attempt's hash.
    """
    try:
        return walk_manifest(worktree)[1]
    except Exception:
        return None


# Harness-declared verification/test commands for the challenge.
# Gate runner = `node report.mjs` (grader/). Worker-invoked
# test commands are observed via bash tool_use events. test_invocations counts
# bash tool_use events whose command contains any declared string.
DECLARED_TEST_COMMANDS: tuple[str, ...] = _SPEC.test_commands


class TelemetryMixin:
    def _emit_cost_target_warning_if_reached(
        self,
        *,
        run_label: str,
        phase: str,
        cumulative_cost_usd: float,
    ) -> None:
        if self.cost_target_usd is None:
            return
        if cumulative_cost_usd < self.cost_target_usd:
            return
        self._progress(
            f"WARNING run_label={run_label} step=cost-target phase={phase} "
            f"reason=cost_target_reached cumulative_cost_usd={cumulative_cost_usd:.4f} "
            f"target_usd={self.cost_target_usd:.4f}"
        )

    def _append_user_event(
        self,
        *,
        run_label: str,
        sidecar_path: Path,
        attempt: int,
        text: str,
        kind: str = "feedback",
    ) -> None:
        """Record, VERBATIM, every message the model is told a user sent.

        THIS FILE IS THE TRUTH (WO-FEEDBACK-1). It is the only place the exact
        bytes handed to the model are preserved — the PROGRESS log carries a
        length and a fingerprint but not the text, and the worker's own event
        stream shows the message only as it was consumed. The control plane
        serves this file so the TUI and the event feed show the operator what
        the model was actually told, not a reconstruction of it.

        `kind` distinguishes the three voices: `chunk` (the task itself),
        `pass_verdict` ("that fixed it"), `feedback` ("still failing"). The UI
        needs that separation — a chunk prompt and a failure report are not the
        same kind of message and must not render identically.

        Append-only, one JSON object per line: a run that dies mid-write leaves
        every earlier message intact and parseable.
        """
        payload = {
            "type": "user",
            "kind": str(kind),
            "timestamp": int(time.time() * 1000),
            "attempt": int(attempt),
            "chars": len(str(text)),
            "text_fp": self._fingerprint_text(text),
            "text": str(text),
        }
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        with sidecar_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
        # The marker stays a fingerprint + length, never the body: this text is
        # multi-line and a single-line log record cannot carry it without
        # corrupting either the text or the log.
        self._progress(
            f"PROGRESS run_label={run_label} step=user-event-sidecar attempt={attempt} "
            f"kind={kind} chars={len(text)} text_fp={self._fingerprint_text(text)} "
            f"path={sidecar_path}"
        )

    def _extract_event_counts(
        self, session_db_path: Path
    ) -> tuple[int | None, int | None]:
        """Return (tool_calls, test_invocations) from the exported session DB.

        RE-POINTED 2026-09-04. This read the stdout transport's
        ``<worktree>.events.jsonl``, whose writer was deleted in the serve-only
        migration — so it returned ``(None, None)`` on every real cell and both
        numbers were permanently blank. The same facts survive in the per-cell
        session DB, which teardown exports BEFORE this runs: one ``part`` row
        per tool call, carrying the tool name and its input.

        ``test_invocations`` counts ``bash`` tool parts whose
        ``state.input.command`` contains any DECLARED_TEST_COMMANDS entry
        (plain case-sensitive substring match), unchanged from the old shape.

        ABSENCE IS STILL ABSENCE: a missing or unreadable DB returns
        ``(None, None)`` with a warning, never ``(0, 0)``. Zero tool calls is a
        real and different fact from "the source could not be read".
        """
        if not session_db_path.is_file():
            _LOG.warning(
                "challenge tool telemetry unavailable path=%s reason=absent",
                session_db_path,
            )
            return None, None

        malformed_rows = 0
        tool_calls = 0
        test_invocations = 0

        # READ-ONLY, AND NEVER THE LIVE FILE. `mode=ro` on a file: URI so the
        # connection cannot create or modify the DB, and cannot recover a hot
        # journal — this is the exported copy of a quiesced database, not the
        # one a container is writing.
        try:
            conn = sqlite3.connect(
                f"file:{session_db_path}?mode=ro", uri=True, timeout=5.0
            )
        except sqlite3.Error as exc:
            _LOG.warning(
                "challenge tool telemetry unavailable path=%s error_class=%s",
                session_db_path,
                exc.__class__.__name__,
            )
            return None, None

        try:
            rows = conn.execute("SELECT data FROM part").fetchall()
        except sqlite3.Error as exc:
            _LOG.warning(
                "challenge tool telemetry unreadable path=%s error_class=%s",
                session_db_path,
                exc.__class__.__name__,
            )
            return None, None
        finally:
            conn.close()

        for (raw,) in rows:
            try:
                payload = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                malformed_rows += 1
                continue

            if not isinstance(payload, dict):
                malformed_rows += 1
                continue

            if payload.get("type") != "tool":
                continue

            tool_calls += 1
            if payload.get("tool") != "bash":
                continue

            state = (
                payload.get("state") if isinstance(payload.get("state"), dict) else {}
            )
            tool_input = (
                state.get("input") if isinstance(state.get("input"), dict) else {}
            )
            command = tool_input.get("command")
            if not isinstance(command, str):
                continue

            if any(declared in command for declared in DECLARED_TEST_COMMANDS):
                test_invocations += 1

        if malformed_rows > 0:
            _LOG.warning(
                "challenge tool telemetry malformed_rows=%d path=%s",
                malformed_rows,
                session_db_path,
            )

        return tool_calls, test_invocations

    def _extract_agentic_cycles(self, user_events_path: Path) -> int | None:
        """Return number of context-submission cycles from user-events jsonl.

        One cycle equals one user context submission (initial prompt plus each
        feedback injection). When attempt fields exist, cycles are counted as
        distinct attempt values; if parsed user lines have no attempt fields,
        fallback is the number of parsed user lines.
        """
        malformed_lines = 0
        user_line_count = 0
        attempts: set[int] = set()
        saw_attempt_field = False

        try:
            with user_events_path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        malformed_lines += 1
                        continue

                    if not isinstance(payload, dict):
                        malformed_lines += 1
                        continue
                    if payload.get("type") != "user":
                        continue

                    user_line_count += 1
                    if "attempt" not in payload:
                        continue

                    attempt = payload.get("attempt")
                    try:
                        attempts.add(int(attempt))
                        saw_attempt_field = True
                    except (TypeError, ValueError):
                        continue
        except OSError as exc:
            _LOG.warning(
                "challenge user-event telemetry unavailable path=%s error_class=%s",
                user_events_path,
                exc.__class__.__name__,
            )
            return None

        if malformed_lines > 0:
            _LOG.warning(
                "challenge user-event telemetry malformed_lines=%d path=%s",
                malformed_lines,
                user_events_path,
            )

        if saw_attempt_field:
            return len(attempts)
        return user_line_count
