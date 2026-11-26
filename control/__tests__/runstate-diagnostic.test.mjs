// ─────────────────────────────────────────────────────────────────────────────
// RUN-STATE DIAGNOSTIC TESTS — split VERBATIM from control/control.test.mjs
// (lines 2912–3258; shared treeFixture/campaignAt live in ./_shared.mjs).
// Extracted verbatim from control/control.test.mjs — WO-LI18 split A.
// Local helper kept here: NODE_WARNING_STDERR.
// Run: cd control && node --test
// ─────────────────────────────────────────────────────────────────────────────

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { campaignDirName } from "../campaign.mjs";
import { initLedger, registerRun, evictRun } from "../run-ledger.mjs";
import { readRunState, STARTUP_GRACE_MS } from "../runstate.mjs";
import { readWall } from "../wall.mjs";
import { firstMeaningfulLine, runnerFailureObserved } from "../../grader/gate-results.mjs";
import { BENCH, writeCampaignCell } from "./_shared.mjs";

test("RUN STATE: the resolved run directory is PUBLISHED, not dropped as null", async () => {
  const root = mkdtempSync(join(tmpdir(), "rundir-"));
  try {
    const runs = join(root, "runs");
    const dir = campaignDirName("minimax/minimax-m3");
    writeCampaignCell(runs, dir, {
      gates: [{ id: "CONF" }],
      results: [{ id: "CONF", status: "pass" }],
    });

    // A LIVE run publishes its resolved directory: per-run in runs[] and on the
    // top-level mirror of the newest live run. Enumeration is the durable
    // record + the process scan — never log files — so the live run is an
    // injected record, and scan: async () => null (a failed scan is
    // indeterminate) makes every injected record live-by-default.
    const state = await readRunState({
      runsRoot: runs,
      launchers: [
        {
          run_id: "run-a",
          sequence_index: 0,
          model: "m-a",
          variant: "a",
          kind: "local",
          org: null,
          context: null,
          manifest_arg: null,
          pid: process.pid,
          started_at: Date.now(),
          log_path: null,
          run_dir: dir,
          finished: false,
          terminal_status: null,
          terminal_ok: null,
        },
      ],
      scan: async () => null,
      heartbeatProbe: async () => 1000,
    });
    assert.equal(state.runs.length, 1);
    assert.equal(
      state.runs[0].run_dir,
      dir,
      "the durable record carries its run directory and the contract declares the field — publishing null " +
        "forces every run-scoped reader back onto a default that a per-model campaign invalidates",
    );
    assert.equal(state.run_dir, dir, "the top-level mirror carries the newest live run's directory");

    // AN ABANDONED RUN DROPS OUT. No durable record and an empty (successful)
    // scan is not a live run: runs[] is empty at once, and with nothing live
    // the top level is the idle shape — run_dir null is correct THERE because
    // there is no run.
    const dead = await readRunState({
      runsRoot: runs,
      launchers: [],
      scan: async () => ({ bound: [], other: [] }),
    });
    assert.deepEqual(dead.runs, [], "a killed run is not a live run and never re-enters the set");
    assert.equal(dead.live_count, 0);
    assert.equal(dead.state, "idle");
    assert.equal(dead.run_dir, null);
    assert.equal(dead.can_start, true);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("RUN STATE: a recorded cell whose process is gone is listed ENDED, not silently dropped", async () => {
  const root = mkdtempSync(join(tmpdir(), "runstate-ended-"));
  const runs = join(root, "runs");
  try {
    // initLedger binds module state (RUNS_ROOT) for the process lifetime —
    // there is no unbind. The record is evicted in finally, so no live slot
    // leaks into the tests below (none of them touch the real ledger).
    initLedger(runs);
    registerRun({
      run_id: "r-ended",
      run_dir: "cumulative",
      sequence_index: 0,
      model: "m-a",
      variant: "a",
      kind: "local",
      org: null,
      context: null,
      manifest_arg: null,
      pid: 999999,
      started_at: Date.now(),
      log_path: null,
      finished: false,
      terminal_status: null,
      terminal_ok: null,
    });

    // A SUCCESSFUL scan that does not contain the recorded pid: the cell ended
    // without an observed exit. The reconcile ends it durably ("exit not
    // observed"), evicts the cache slot, and the ended record is LISTED —
    // every ended cell appears in ended[], never silently dropped.
    const state = await readRunState({
      runsRoot: runs,
      scan: async () => ({ bound: [], other: [] }),
    });

    assert.equal(state.runs.length, 0, "a dead process is not a live run");
    assert.ok(
      state.ended.some((e) => e.run_id === "r-ended" && e.ended?.reason === "exit not observed"),
      "the ended cell is listed with its reason — never silently dropped",
    );
    assert.equal(state.can_start, true, "nothing live: the launch gate clears");
  } finally {
    evictRun("r-ended");
    rmSync(root, { recursive: true, force: true });
  }
});

test("RUN STATE: a cell just spawned is starting, not ended, while its pid lives", async () => {
  // Run 1793876536 cell 2 was ended "exit not observed" 11 ms after launch —
  // its interpreter had not exec'd a harness argv yet — and the board lost a
  // cell that ran on for hours. A live recorded pid inside the startup grace
  // is starting; past the grace, a live non-harness pid is a reused pid.
  const root = mkdtempSync(join(tmpdir(), "runstate-starting-"));
  const runs = join(root, "runs");
  const record = (run_id, started_at) => ({
    run_id,
    run_dir: "cumulative",
    sequence_index: 0,
    model: "m-start",
    variant: "a",
    kind: "local",
    org: null,
    manifest_arg: null,
    pid: process.pid,
    started_at,
    log_path: null,
    finished: false,
    terminal_status: null,
    terminal_ok: null,
  });
  try {
    initLedger(runs);
    registerRun(record("r-starting", Date.now()));
    registerRun(record("r-reused", Date.now() - STARTUP_GRACE_MS - 1000));
    const state = await readRunState({
      runsRoot: runs,
      scan: async () => ({ bound: [], other: [] }),
    });
    assert.ok(
      !state.ended.some((e) => e.run_id === "r-starting"),
      "a live pid inside the startup grace is never ended",
    );
    assert.ok(
      state.ended.some((e) => e.run_id === "r-reused" && e.ended?.reason === "exit not observed"),
      "past the grace, a live pid that is not a harness is a reused pid: ended",
    );
  } finally {
    evictRun("r-starting");
    evictRun("r-reused");
    rmSync(root, { recursive: true, force: true });
  }
});

test("WALL: a per-model campaign's outcomes are served, never a zeroed suite", async () => {
  const root = mkdtempSync(join(tmpdir(), "wall-campaign-"));
  try {
    const runs = join(root, "runs");
    const dir = campaignDirName("minimax/minimax-m3");
    writeCampaignCell(runs, dir, {
      gates: [{ id: "CONF" }, { id: "A" }, { id: "B" }],
      results: [
        { id: "CONF", status: "pass" },
        { id: "A", status: "fail" },
        { id: "B", status: "not_run" },
      ],
    });

    // What the server now passes: the run directory of the newest live run. The
    // run must be LIVE to resolve — an abandoned record drops out of runs[] and
    // the mirror goes idle, which is the drop-out truth pinned in the test above.
    const runDir = (
      await readRunState({
        runsRoot: runs,
        launchers: [
          {
            run_id: "run-w",
            sequence_index: 0,
            model: "m-a",
            variant: "a",
            kind: "local",
            org: null,
            context: null,
            manifest_arg: null,
            pid: process.pid,
            started_at: Date.now(),
            log_path: null,
            run_dir: dir,
            finished: false,
            terminal_status: null,
            terminal_ok: null,
          },
        ],
        scan: async () => null,
        heartbeatProbe: async () => 1000,
      })
    ).run_dir;
    const wall = await readWall({ runsRoot: runs, runDir, sequenceIndex: 0 });

    assert.equal(wall.suite.total, 3, "the pinned roster's three gates are the denominator");

    // AND THE DEFAULT ALONE IS NOT THE ANSWER. Naming no run directory falls
    // back to `cumulative`, which this campaign never wrote — the read must
    // report an unknowable suite rather than a suite nobody passed.
    const stale = await readWall({ runsRoot: runs, runDir: null });
    assert.equal(
      stale.suite.total,
      null,
      "an absent run directory is unknowable, never a wall of zeroes",
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// REGRESSION: 53 UNMEASURED GATES, EXPLAINED BY A NODE WARNING.
//
// When a runner exits nonzero with no failing test, the suite did not finish and
// every gate it never reached is recorded `not_run`. That string is the ONLY
// account of why. On the 2026-08-17 minimax-m3 cell it was
// "(node:43741) PromiseRejectionHandledWarning: ... (rejection id: 19)" —
// stderr's first line, and pure boilerplate — recorded against 53 gates, twice.
// ─────────────────────────────────────────────────────────────────────────────

/** Verbatim stderr from that cell's aborted backend phase. */
const NODE_WARNING_STDERR = [
  "(node:43741) PromiseRejectionHandledWarning: Promise rejection was handled asynchronously (rejection id: 19)",
  "(Use `node --trace-warnings ...` to show where the warning was created)",
  "(node:43741) PromiseRejectionHandledWarning: Promise rejection was handled asynchronously (rejection id: 250)",
].join("\n");

test("DIAGNOSTIC: Node's own warnings are never mistaken for the failure", () => {
  assert.equal(
    firstMeaningfulLine(NODE_WARNING_STDERR),
    "",
    "a stderr made entirely of Node boilerplate yields NO explanation, rather than a confident wrong one",
  );
  assert.equal(
    firstMeaningfulLine(`${NODE_WARNING_STDERR}\nError: listen EADDRINUSE :::8002`),
    "Error: listen EADDRINUSE :::8002",
    "the real line is selected even when warnings precede it",
  );
});

test("DIAGNOSTIC: an aborted runner reports how it died and how far it got", () => {
  const observed = runnerFailureObserved(
    "backend",
    { status: 1, signal: null, stderr: NODE_WARNING_STDERR },
    { reported: 7, expected: 56 },
  );

  assert.match(observed, /runner exited 1/, "how the process ended");
  assert.match(observed, /reported 7 of 56 gate results/, "how far it got — the gap IS the finding");
  assert.match(observed, /no test failed/, "and that nothing was measured as failing");
  assert.ok(
    !observed.includes("PromiseRejectionHandledWarning"),
    "the warning that used to be the entire explanation does not appear",
  );
});

test("DIAGNOSTIC: a KILLED runner is not reported as one that merely exited", () => {
  const killed = runnerFailureObserved(
    "backend",
    { status: null, signal: "SIGKILL", stderr: "" },
    { reported: 0, expected: 56 },
  );
  assert.match(killed, /killed by SIGKILL/);

  const exited = runnerFailureObserved("backend", { status: 2, signal: null, stderr: "" }, {});
  assert.match(exited, /exited 2/);
  assert.ok(!exited.includes("killed"), "and the two are never conflated");
});

test("DIAGNOSTIC: a spawn failure names itself rather than the exit code", () => {
  const observed = runnerFailureObserved(
    "frontend",
    { error: new Error("spawn npx ENOENT"), stderr: "" },
    {},
  );
  assert.match(observed, /spawn failed: spawn npx ENOENT/);
});

// ── PER-FILE BACKEND INVOCATION ─────────────────────────────────────────────

test("REPORT: the backend phase spawns one runner PER FILE, under one phase marker", () => {
  const src = readFileSync(join(BENCH, "grader", "lib", "backend.mjs"), "utf8");
  const body = src.slice(src.indexOf("function runBackendPhase()"));

  assert.match(body, /for \(const file of backendTestFiles\(\)\)/, "the suite is invoked file by file");
  assert.match(body, /spawnRunner\(`backend \$\{file\}`/, "each file gets its own process");
  assert.ok(
    !/spawnPhase\(/.test(body),
    "and NOT via spawnPhase — a second `[report] phase=backend` opener would tell the board a new phase began",
  );

  // Exactly one open and one close for the whole set: the python adapter turns
  // these two lines into the board's gate-phase-start / gate-phase-end events.
  assert.equal((body.match(/\[report\] phase=backend target=/g) ?? []).length, 1, "one phase opener");
  assert.equal((body.match(/\[report\] phase=backend status=/g) ?? []).length, 1, "one phase closer");
});



