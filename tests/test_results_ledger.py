"""WO-43a: results-ledger record shape + append behavior.

Builds a synthetic scorecard (real RunManifest / ConvergencePoint to_dict()
shape) plus a real StatusStream of per-cell attempt records, then asserts the
emitted JSONL line's exact fields: the A cell carries variant=="a", the B
cell variant=="b". WO-CONCUR-07: both
variants also carry the ``contention`` covariates sub-dict (None only when the
attempt published no progress). No
metrics are invented: every value flows from the
same surfaces a real run publishes.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from harness.cumulative.convergence import CONTENTION_FIELDS, ConvergencePoint
from harness.cumulative.progress import progress_from_cell_result
from harness.cumulative.results_ledger import (
    append_run_records,
    build_run_records,
    read_tree_id,
)
from harness.cumulative.run_artifacts import (
    RunManifest,
    StatusStream,
    default_status_stream_path,
)
from harness.cumulative.types import SessionRecord


def _manifest_to_dict() -> dict[str, Any]:
    return RunManifest(
        run_id="run-ledger-test",
        created_at="2026-08-29T12:00:00Z",
        served_model=None,
        requested_model="local/test-model",
        variant="mixed",
    ).to_dict()


def _point(sequence_index: int, session_fp: str) -> ConvergencePoint:
    return ConvergencePoint(
        sequence_index=sequence_index,
        session_fp=session_fp,
        problems_before=3,
        problems_after=1,
        resolved_count=2,
        remaining_count=1,
        full_green=True,
        attempts_to_green=2,
        turns=7,
        total_tokens=900,
        wall_seconds=12.5,
        wall_cost_usd=0.25,
        tool_calls=None,
        test_invocations=None,
        agentic_cycles=None,
    )


def _a_telemetry() -> dict[str, Any]:
    """ChallengeCellResult-shaped telemetry with only the core counters."""
    return {
        "problems_before": 3,
        "problems_final": ["problem-1"],
        "resolved_count": 2,
        "remaining_count": 1,
        "attempts_to_green": 2,
        "turns": 7,
        "input_tokens": 400,
        "output_tokens": 500,
        "total_tokens": 900,
        "wall_seconds": 12.5,
        "wall_cost_usd": 0.25,
        "verdict": "PASS",
        "termination_reason": "verdict_composed",
    }


def _contention() -> dict[str, Any]:
    """The contention covariates a cell publishes under ``contention``.

    Read by progress.py's ``_contention_fields`` (Mapping or attribute access)
    and published FLAT into the progress dict by ``ProgressVector.to_dict``.
    """
    return {
        "http_429_count": 5,
        "http_402_count": 1,
        "retry_count": 2,
        "upstream_error_count": 3,
        "max_request_ms": 1200,
        "median_request_ms": 800,
    }


def _write_attempt_records(
    manifest_path: Path,
    records: list[dict[str, Any]],
) -> str:
    stream_path = default_status_stream_path(str(manifest_path))
    stream = StatusStream(stream_path)
    for record in records:
        stream.append(record)
    return stream_path


def _scorecard(points: list[ConvergencePoint]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest": _manifest_to_dict(),
        "convergence": {
            "schema_version": 1,
            "points": [point.to_dict() for point in points],
            "sessions_completed": len(points),
            "sessions_green": sum(1 for p in points if p.full_green),
            "resolved_total": 2,
            "tokens_total": sum(p.total_tokens for p in points),
            "wall_seconds_total": 12.5,
            "wall_cost_usd_total": 0.25,
            "trend_hash": "deadbeef",
        },
    }


def test_a_cell_record_shape(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    stream_path = _write_attempt_records(
        manifest_path,
        [
            {
                "type": "attempt",
                "sequence_index": 0,
                "variant": "a",
                "served_model": None,
                "verdict": "PASS",
                "gate_totals": {"passed": 4, "failed": 0},
                "session_fp": "fp-a-cell",
                "session_id": "ses-a-cell",
                "progress": progress_from_cell_result(_a_telemetry()).to_dict(),
            }
        ],
    )
    scorecard = _scorecard([_point(0, "fp-a-cell")])

    records = build_run_records(
        tree_id="1787310000",
        task="backgammon",
        scorecard=scorecard,
        status_stream_path=stream_path,
        timestamp="2026-08-29T13:00:00Z",
    )
    assert len(records) == 1
    record = records[0]
    assert record["tree_id"] == "1787310000"
    assert record["run_id"] == "run-ledger-test"
    assert record["task"] == "backgammon"
    assert record["model"] == "local/test-model"
    assert record["variant"] == "a"
    assert record["sequence_index"] == 0
    assert record["verdict"] == "PASS"
    assert record["attempts_to_green"] == 2
    assert record["problems_before"] == 3
    assert record["problems_after"] == 1
    assert record["full_green"] is True
    assert record["gate_totals"] == {"passed": 4, "failed": 0}
    assert record["turns"] == 7
    assert record["tokens"] == 900
    assert record["wall_seconds"] == 12.5
    assert record["wall_cost_usd"] == 0.25
    # This fixture publishes no contention: the covariates stay per-field None
    # (not measured), never zero-filled — and the key itself is still present.
    assert record["contention"] == {field: None for field in CONTENTION_FIELDS}, (
        "unmeasured contention is a dict of Nones, never zero-filled"
    )
    assert record["session_fp"] == "fp-a-cell"
    assert record["session_id"] == "ses-a-cell"
    assert record["timestamp"] == "2026-08-29T13:00:00Z"


def test_convergence_point_carries_contention_covariates() -> None:
    """WO-CONCUR-07: a scored session's point surfaces the contention
    covariates it was gathered under — the 7 flat progress fields, nested."""
    telemetry = {**_a_telemetry(), "contention": _contention()}
    record = SessionRecord(
        sequence_index=0,
        model="local/test-model",
        provider_pin="local",
        variant="a",
        phase_group="a_baseline",
        phase="DONE",
        session_id="ses-a-cell",
        session_fp="fp-a-cell",
        progress=progress_from_cell_result(telemetry).to_dict(),
    )

    point = ConvergencePoint.from_session_record(record)
    assert point is not None
    assert point.contention == _contention()
    emitted = point.to_dict()["contention"]
    assert emitted == _contention()
    assert set(emitted) == set(CONTENTION_FIELDS)


def test_ledger_records_carry_contention_on_both_variants(tmp_path: Path) -> None:
    """WO-CONCUR-07: contention is NOT variant-gated (measured on B and A);
    it is None only when the attempt record published no progress mapping."""
    manifest_path = tmp_path / "manifest.json"
    stream_path = _write_attempt_records(
        manifest_path,
        [
            {
                "type": "attempt",
                "sequence_index": 0,
                "variant": "a",
                "verdict": "PASS",
                "session_fp": "fp-a-cell",
                "session_id": "ses-a-cell",
                "progress": progress_from_cell_result(
                    {**_a_telemetry(), "contention": _contention()}
                ).to_dict(),
            },
            {
                "type": "attempt",
                "sequence_index": 1,
                "variant": "b",
                "verdict": "PASS",
                "session_fp": "fp-b-cell",
                "session_id": "ses-b-cell",
                "progress": progress_from_cell_result(
                    {**_a_telemetry(), "contention": _contention()}
                ).to_dict(),
            },
            {
                "type": "attempt",
                "sequence_index": 2,
                "variant": "a",
                "verdict": "FAIL",
                "session_fp": "fp-no-progress",
                "session_id": "ses-no-progress",
                # No progress mapping: contention must be None, never invented.
            },
        ],
    )
    scorecard = _scorecard(
        [
            _point(0, "fp-a-cell"),
            _point(1, "fp-b-cell"),
            _point(2, "fp-no-progress"),
        ]
    )

    records = build_run_records(
        tree_id=None,
        task="backgammon",
        scorecard=scorecard,
        status_stream_path=stream_path,
        timestamp="2026-08-29T13:00:00Z",
    )
    assert len(records) == 3
    a, b, no_progress = records
    assert a["variant"] == "a"
    assert a["contention"] == _contention(), "carried on the A variant too"
    assert set(a["contention"]) == set(CONTENTION_FIELDS)
    assert b["variant"] == "b"
    assert b["contention"] == _contention()
    assert no_progress["contention"] is None, "no progress => None, not invented"


def test_append_writes_jsonl_accumulates_and_preserves_torn_line(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    stream_path = _write_attempt_records(
        manifest_path,
        [
            {
                "type": "attempt",
                "sequence_index": 0,
                "variant": "a",
                "verdict": "PASS",
                "session_fp": "fp-a-cell",
                "session_id": "ses-a-cell",
                "progress": progress_from_cell_result(_a_telemetry()).to_dict(),
            }
        ],
    )
    scorecard = _scorecard([_point(0, "fp-a-cell")])
    ledger_path = tmp_path / "data" / "results-ledger.jsonl"

    first = append_run_records(
        bench_root=tmp_path,
        tree_id="1787310000",
        task="backgammon",
        scorecard=scorecard,
        status_stream_path=stream_path,
    )
    assert first and ledger_path.exists()
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    # Canonical compact sorted-key JSON, one object per line.
    decoded = json.loads(lines[0])
    assert decoded["variant"] == "a"
    assert lines[0] == json.dumps(decoded, sort_keys=True, separators=(",", ":"))
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", decoded["timestamp"])

    # A run that died mid-write leaves a torn (unparseable) line; the next
    # run's records still append after it and nothing prior is rewritten.
    with open(ledger_path, "a", encoding="utf-8") as handle:
        handle.write('{"run_id": "torn"\n')  # newline landed, JSON did not
    second = append_run_records(
        bench_root=tmp_path,
        tree_id="1787310000",
        task="backgammon",
        scorecard=scorecard,
        status_stream_path=stream_path,
    )
    assert second
    lines_after = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after) == 3
    assert lines_after[0] == lines[0], "append-only: prior line byte-identical"
    assert json.loads(lines_after[2])["run_id"] == "run-ledger-test"
    # Reader tolerance (StatusStream.records semantics): the torn line is
    # skipped, the good records on either side of it survive.
    parsed = []
    for raw in lines_after:
        try:
            parsed.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    assert len(parsed) == 2
    assert all(r["run_id"] == "run-ledger-test" for r in parsed)


def test_point_without_attempt_record_is_skipped(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    stream_path = _write_attempt_records(manifest_path, [])
    scorecard = _scorecard([_point(0, "fp-unattributed")])

    records = build_run_records(
        tree_id=None,
        task="backgammon",
        scorecard=scorecard,
        status_stream_path=stream_path,
    )
    assert records == [], "a cell with no attempt record cannot be attributed"


def test_read_tree_id_absent_none_malformed_raises(tmp_path: Path) -> None:
    assert read_tree_id(tmp_path) is None, "absent pointer = legacy flat layout"
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "active-tree.json").write_text(
        json.dumps({"active": "not-a-tree-id"}), encoding="utf-8"
    )
    try:
        read_tree_id(tmp_path)
    except ValueError as exc:
        assert "not a unix-seconds tree id" in str(exc)
    else:
        raise AssertionError("malformed pointer must raise, never guess")


def test_a_concurrent_cell_appends_only_its_own_record(tmp_path: Path) -> None:
    """Each of N concurrent cells finishes against the SAME campaign scorecard,
    which holds every cell scored so far. Appending all of it from every
    process recorded a cell once per sibling that finished after it
    (2026-09-22: s0001 three times). A process that ran one cell appends one."""
    manifest_path = tmp_path / "manifest.json"
    stream_path = _write_attempt_records(
        manifest_path,
        [
            {
                "type": "attempt",
                "sequence_index": seq,
                "variant": "a",
                "verdict": "FAIL",
                "session_fp": f"fp-{seq}",
                "session_id": f"ses-{seq}",
                "progress": progress_from_cell_result(_a_telemetry()).to_dict(),
            }
            for seq in (0, 1, 2)
        ],
    )
    scorecard = _scorecard([_point(0, "fp-0"), _point(1, "fp-1"), _point(2, "fp-2")])
    ledger_path = tmp_path / "data" / "results-ledger.jsonl"
    for seq in (0, 1, 2):
        written = append_run_records(
            bench_root=tmp_path,
            tree_id="1790144847",
            task="backgammon",
            scorecard=scorecard,
            status_stream_path=stream_path,
            sequence_index=seq,
        )
        assert [r["sequence_index"] for r in written] == [seq]
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert sorted(json.loads(line)["sequence_index"] for line in lines) == [0, 1, 2]
