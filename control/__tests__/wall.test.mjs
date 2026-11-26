// Extracted verbatim from control/control.test.mjs — WO-LI18 split A.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, utimesSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { newestLog } from "../runstate.mjs";
import { attemptRecords, foldGateStates, readStatusRecords, readWall, resolveRunDir } from "../wall.mjs";

import { BENCH } from "./_shared.mjs";

test("WALL: `unmeasured` counts stated non-results, never gates nobody reached", () => {
  // THE TWO ABSENCES ARE NOT THE SAME FACT. A gate the stream has not mentioned
  // is not reached yet — normal, and the whole suite looks like that early in a
  // cell. A gate the runner explicitly published as `not_run` is one it reached
  // the phase for and produced no verdict against: four of those, with their
  // siblings measured normally, is the fingerprint a grading worker leaves when
  // it dies mid-file. Counting them together would peg the UNMEASURED ledger
  // slot at the suite size for the first minutes of every healthy run.
  const att = (attempt, results) => ({ attempt, gate_results: results });

  // G01 measured, G02 explicitly not_run.
  const { unmeasured } = foldGateStates({
    attempts: [att(1, [{ id: "G01", status: "pass" }, { id: "G02", status: "not_run" }])],
  });
  assert.equal(unmeasured, 1, "only the stated non-result counts");

  // A RUN THAT HAS PUBLISHED NOTHING HAS NO UNMEASURED GATES — it has no
  // measurements at all, which is a different statement.
  assert.equal(foldGateStates({ attempts: [] }).unmeasured, 0);

  // THE LAST COMPLETED TEST RUN WINS: a gate the newer attempt measured is no
  // longer unmeasured, so the count follows the current state, not the history.
  assert.equal(
    foldGateStates({
      attempts: [
        att(1, [{ id: "G01", status: "not_run" }]),
        att(2, [{ id: "G01", status: "pass" }]),
      ],
    }).unmeasured,
    0,
  );
});

test("WALL: run_dir is confined to a child of the runs root", () => {
  // The value reaches an fs path. Traversal would let a caller read arbitrary
  // JSON off the host through a read-only endpoint.
  assert.equal(resolveRunDir("/runs", "../../etc"), null);
  assert.equal(resolveRunDir("/runs", "/etc/passwd"), null);
  // ── NESTED IS NOW LEGAL, TRAVERSAL IS STILL NOT ─────────────────────────
  //
  // The separator ban was correct for a flat layout where every run directory
  // was a direct child. Under the benchmark tree a campaign home IS a path
  // (`<tree>/<substrate>/<router>/<provider>/<model>`), so rejecting separators
  // outright would refuse every legitimate run_dir on a bench that is running
  // normally. The containment property is unchanged and asserted below.
  assert.equal(resolveRunDir("/runs", "a/b")?.name, "a/b", "a nested campaign home resolves");
  assert.equal(
    resolveRunDir("/runs", "1787310000/local/local-llm-proxy/omlx/model-x")?.name,
    "1787310000/local/local-llm-proxy/omlx/model-x",
    "a full tree path resolves",
  );
  // Every escape still refused — each segment is validated before resolution,
  // and the resolved path must still sit under the root.
  assert.equal(resolveRunDir("/runs", "a/../../etc"), null, "traversal through a nested path");
  assert.equal(resolveRunDir("/runs", "a/./b"), null, "a dot segment");
  assert.equal(resolveRunDir("/runs", "a//b"), null, "an empty segment");
  assert.equal(resolveRunDir("/runs", "/etc/passwd"), null, "an absolute path");
  assert.equal(resolveRunDir("/runs", ".."), null);
  assert.equal(resolveRunDir("/runs", "cumulative")?.name, "cumulative");
  assert.equal(resolveRunDir("/runs", "")?.name, "cumulative", "empty falls back to the default run dir");
});

// ── THE WIPE BOUNDARY ───────────────────────────────────────────────────────
//
// Cell logs are written to the runs ROOT; the run state they describe lives in
// `runs/<run_dir>/`. Archiving or wiping a run moves the directory and leaves
// the log, so the log outlives its own data.
//
// MEASURED 2026-08-13: after a wipe, `runs/a-cell-20260813T051334.log`
// remained at the root and every reader resolved it as the live run. /api/wall
// served `suite.total:null` (the run dir was gone) beside `grading.active:true
// phase:frontend stalled:true silent_s:4848` parsed out of that dead log — a
// wiped bench reporting a run in progress, which the operator could not clear
// without hand-deleting files after every wipe.

test("WIPE: a cell log whose run directory is gone is not resolved as the live run", async () => {
  const root = mkdtempSync(join(tmpdir(), "wipe-"));
  try {
    const runs = join(root, "runs");
    mkdirSync(runs, { recursive: true });
    // The exact post-wipe shape: the run dir archived away, the log left behind.
    mkdirSync(join(runs, "cumulative.wiped-sim", "sessions"), { recursive: true });
    writeFileSync(
      join(runs, "a-cell-orphan.log"),
      "PROGRESS step=worktree-git-init path=" +
        join(runs, "cumulative", "sessions", "cell", "worktree") +
        "\nPROGRESS step=gate-phase-start phase=frontend\n",
    );

    assert.equal(
      await newestLog(runs),
      null,
      "an orphan log describes a run that no longer exists and is not live",
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("WIPE: a cell log whose run directory still exists IS resolved as live", async () => {
  const root = mkdtempSync(join(tmpdir(), "wipe-"));
  try {
    const runs = join(root, "runs");
    mkdirSync(join(runs, "cumulative", "sessions"), { recursive: true });
    writeFileSync(
      join(runs, "a-cell-live.log"),
      "PROGRESS step=worktree-git-init path=" +
        join(runs, "cumulative", "sessions", "cell", "worktree") +
        "\n",
    );

    const log = await newestLog(runs);
    assert.ok(log, "a log whose run dir exists is still the live run");
    assert.equal(log.run_dir, "cumulative");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("WIPE: a fresh log that has not yet named a run dir is live, not orphaned", async () => {
  const root = mkdtempSync(join(tmpdir(), "wipe-"));
  try {
    const runs = join(root, "runs");
    mkdirSync(runs, { recursive: true });
    // A just-launched cell prints banner lines before any artifact path.
    writeFileSync(join(runs, "a-cell-new.log"), "This is mini-swe-agent version 2.4.5.\n");

    const log = await newestLog(runs);
    assert.ok(log, "a log that has not named a run dir yet must not be discarded");
    assert.equal(log.run_dir, undefined);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("WIPE: an orphan is skipped in favour of an older log that is still live", async () => {
  const root = mkdtempSync(join(tmpdir(), "wipe-"));
  try {
    const runs = join(root, "runs");
    mkdirSync(join(runs, "cumulative", "sessions"), { recursive: true });

    const livePath = join(runs, "a-cell-live.log");
    writeFileSync(
      livePath,
      "PROGRESS step=worktree-git-init path=" + join(runs, "cumulative", "s", "w") + "\n",
    );
    // Newer by mtime, but its run dir is gone: recency must not beat existence.
    const orphanPath = join(runs, "a-cell-orphan.log");
    writeFileSync(
      orphanPath,
      "PROGRESS step=worktree-git-init path=" + join(runs, "cumulative.gone", "s", "w") + "\n",
    );
    utimesSync(livePath, new Date(1000), new Date(1000));
    utimesSync(orphanPath, new Date(9000), new Date(9000));

    const log = await newestLog(runs);
    assert.equal(log?.name, "a-cell-live.log", "the newest LIVE log wins, not the newest log");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("WALL: a wiped bench shows the suite defined, with no measurements", async () => {
  const root = mkdtempSync(join(tmpdir(), "wiped-"));
  try {
    const runs = join(root, "runs");
    mkdirSync(runs, { recursive: true });

    const wall = await readWall({ runsRoot: runs, runDir: null, benchRoot: BENCH });

    assert.equal(wall.ok, true);
    // The count is whatever the harness enumerates — asserted as a real number
    // rather than a literal, so adding a gate does not fail this test.
    assert.ok(wall.suite.total > 0, "the suite size is known");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("WALL: the suite denominator is never fabricated when the harness cannot be reached", async () => {
  const root = mkdtempSync(join(tmpdir(), "noharness-"));
  try {
    const runs = join(root, "runs");
    mkdirSync(runs, { recursive: true });
    // benchRoot with no gates dir: the enumerator cannot run.
    const wall = await readWall({ runsRoot: runs, runDir: null, benchRoot: root });

    assert.equal(wall.ok, true, "a missing enumerator is a state, not a 500");
    assert.equal(wall.suite.total, null, "unknowable stays null, never 0 (invariant I-2)");
    assert.equal(wall.unmeasured, null, "an unknown suite has no unmeasured count either");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("WALL: a run's own pinned roster wins over live enumeration", async () => {
  const root = mkdtempSync(join(tmpdir(), "pinned-"));
  try {
    const runs = join(root, "runs");
    mkdirSync(join(runs, "cumulative"), { recursive: true });
    // A roster pinned to this run describes the suite it was GRADED against and
    // must not be replaced by today's suite, or every comparison re-baselines.
    writeFileSync(
      join(runs, "cumulative", "gate-roster.json"),
      JSON.stringify({
        schema_version: 1,
        total: 2,
        suite_fingerprint: "sha256:pinned",
        gates: [
          { id: "G01", phase: "backend", tier: "core" },
          { id: "G02", phase: "backend", tier: "core" },
        ],
      }),
    );

    const wall = await readWall({ runsRoot: runs, runDir: "cumulative", benchRoot: BENCH });
    assert.equal(wall.suite.total, 2);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("WALL: a truncated status stream yields every intact record before the tear", async () => {
  const dir = mkdtempSync(join(tmpdir(), "wall-"));
  try {
    const path = join(dir, "manifest.status.jsonl");
    writeFileSync(
      path,
      '{"type":"attempt","attempt":1,"gate_results":[]}\n' +
        '{"type":"turn_terminal"}\n' +
        '{"type":"attempt","attempt":2,"gate_r',
    );
    const records = await readStatusRecords(path);
    assert.equal(records.length, 2, "the intact records survive");
    assert.equal(attemptRecords(records).length, 1, "the torn attempt record is not invented");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

