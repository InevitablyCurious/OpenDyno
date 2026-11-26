"""The per-cell variant record (harness/adapters/challenge/variant_record.py)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from harness.adapters.challenge.variant_record import (
    VARIANT_RECORD_FILENAME,
    VariantRecordMixin,
    first_prompt_tokens,
    read_variant_route,
    tool_calls_by_name,
)
from harness.adapters.docker_worker import LOOP_KILL_MARKER_DIRNAME, BakedPlugin
from harness.variant_hooks import (
    ENV_VARIANT_COST_CMD,
    ENV_VARIANT_READY_CMD,
    VariantNotReady,
)


def _session_db(run_dir: Path, messages: list[dict], parts: list[dict]) -> Path:
    db = run_dir / "session-db" / "opencode.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, "
            "time_created INTEGER, data TEXT)"
        )
        conn.execute(
            "CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, "
            "session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT)"
        )
        for i, data in enumerate(messages):
            conn.execute(
                "INSERT INTO message VALUES (?, ?, ?, ?)",
                (f"msg_{i}", "ses_1", 100 + i, json.dumps(data)),
            )
        for i, data in enumerate(parts):
            conn.execute(
                "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
                (f"part_{i}", "msg_1", "ses_1", 100 + i, 100 + i, json.dumps(data)),
            )
        conn.commit()
    finally:
        conn.close()
    return db


MESSAGES = [
    {"role": "user"},
    {"role": "assistant", "tokens": {"input": 0, "cache": {"read": 0, "write": 0}}},
    {
        "role": "assistant",
        "tokens": {"input": 120, "cache": {"read": 9000, "write": 30}},
    },
    {"role": "assistant", "tokens": {"input": 999, "cache": {"read": 99999}}},
]
PARTS = [
    {"type": "text", "text": "hi"},
    {"type": "tool", "tool": "bash"},
    {"type": "tool", "tool": "honcho_search"},
    {"type": "tool", "tool": "bash"},
]


def test_the_first_prompt_is_the_first_request_that_reported_tokens(
    tmp_path: Path,
) -> None:
    db = _session_db(tmp_path, MESSAGES, PARTS)
    assert first_prompt_tokens(db) == 120 + 9000 + 30


def test_tool_calls_are_counted_by_name(tmp_path: Path) -> None:
    db = _session_db(tmp_path, MESSAGES, PARTS)
    assert tool_calls_by_name(db) == {"bash": 2, "honcho_search": 1}


def test_a_missing_session_db_reads_as_unknown_not_zero(tmp_path: Path) -> None:
    db = tmp_path / "session-db" / "opencode.db"
    assert first_prompt_tokens(db) is None
    assert tool_calls_by_name(db) is None


def test_the_sidecar_traffic_count_is_read_from_the_marker_dir(tmp_path: Path) -> None:
    assert read_variant_route(tmp_path) is None
    markers = tmp_path / LOOP_KILL_MARKER_DIRNAME
    markers.mkdir()
    (markers / "variant-route.json").write_text('{"requests": 4, "unreachable": 0}')
    assert read_variant_route(tmp_path) == {"requests": 4, "unreachable": 0}


class _Cell(VariantRecordMixin):
    def __init__(self, variant: str) -> None:
        self.variant = variant
        self.progress: list[str] = []
        self._progress = self.progress.append
        self._baked_plugin = BakedPlugin(
            entry="/opt/bench-plugin/dist/index.js",
            identity="@honcho-ai/opencode-honcho@0.2.1",
        )


@pytest.fixture
def counters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "counters.json"
    path.write_text('{"input_tokens": 1000, "output_tokens": 100}')
    monkeypatch.setenv(ENV_VARIANT_READY_CMD, "true")
    monkeypatch.setenv(ENV_VARIANT_COST_CMD, f"cat {path}")
    return path


def test_a_variant_b_cell_records_waits_cost_route_and_delivery(
    tmp_path: Path, counters: Path
) -> None:
    run_dir = tmp_path / "cell-0001"
    cell = _Cell("b")
    cell._variant_begin(run_label="cell-0001")
    # The cell runs: the plugin talks to its server, the server spends tokens.
    _session_db(run_dir, MESSAGES, PARTS)
    cell._variant_config = {"upstream": "http://host.docker.internal:8000"}
    (run_dir / LOOP_KILL_MARKER_DIRNAME).mkdir()
    (run_dir / LOOP_KILL_MARKER_DIRNAME / "variant-route.json").write_text(
        '{"requests": 7, "unreachable": 0, "answered": {"2xx": 7}}'
    )
    counters.write_text('{"input_tokens": 4000, "output_tokens": 350}')
    cell._variant_finish(run_label="cell-0001", run_dir=run_dir)

    record = json.loads((run_dir / VARIANT_RECORD_FILENAME).read_text())
    assert record["variant"] == "b"
    assert record["plugin"] == "@honcho-ai/opencode-honcho@0.2.1"
    assert record["variant_config"] == {"upstream": "http://host.docker.internal:8000"}
    assert record["first_prompt_tokens"] == 9150
    assert record["tool_calls"] == {"bash": 2, "honcho_search": 1}
    assert record["variant_route"]["requests"] == 7
    assert record["ready_before"]["ready"] is True
    assert record["ready_after"]["ready"] is True
    assert record["cost"] == {"counters": {"input_tokens": 3000, "output_tokens": 250}}
    assert any("step=variant-record" in line for line in cell.progress)


def test_a_variant_a_cell_records_delivery_only(tmp_path: Path, counters: Path) -> None:
    run_dir = tmp_path / "cell-0002"
    cell = _Cell("a")
    cell._variant_begin(run_label="cell-0002")
    _session_db(run_dir, MESSAGES, PARTS)
    cell._variant_finish(run_label="cell-0002", run_dir=run_dir)

    record = json.loads((run_dir / VARIANT_RECORD_FILENAME).read_text())
    assert record == {
        "variant": "a",
        "first_prompt_tokens": 9150,
        "tool_calls": {"bash": 2, "honcho_search": 1},
    }


def test_a_busy_variant_stops_the_cell_before_it_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_VARIANT_READY_CMD, "false")
    monkeypatch.setattr("harness.variant_hooks.READY_POLL_S", 0.0)
    monkeypatch.setenv("BENCH_VARIANT_READY_TIMEOUT_S", "0.01")
    with pytest.raises(VariantNotReady):
        _Cell("b")._variant_begin(run_label="busy")
