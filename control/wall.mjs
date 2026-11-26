// GATE WALL — the gate roster (gate-roster.json, write-once) read beside the
// test outcomes (manifest.status.jsonl gate_results) for ONE cell, and reduced
// to the two facts a surface actually consumes: the suite size (the
// denominator every result is scored against) and how many gates the runner
// explicitly published as not_run (the UNMEASURED ledger slot).
//
// Read-only: reads two files, never writes, spawns or signals.

import { promises as fs } from "node:fs";
import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

/** How long the enumerator may take before the suite is reported unknown. */
const ROSTER_ENUMERATE_TIMEOUT_MS = 60_000;

/** The contract version the board can assert against. */
export const WALL_CONTRACT_VERSION = 2;

/**
 * Last resort only, for a bench with no cell log: the caller resolves the
 * active run from the cell log. A missing directory is reported as an unknown
 * suite (total null), never as an empty one.
 */
export const DEFAULT_RUN_DIR = "cumulative";

/**
 * Resolve `?run_dir=` safely: confined to the runs root. Nested paths are
 * allowed (the tree layout); empty, `.` and `..` segments, backslashes, absolute
 * paths and NUL are refused, and the resolved path must sit under the root.
 */
export function resolveRunDir(runsRoot, raw) {
  const name = String(raw ?? "").trim() || DEFAULT_RUN_DIR;
  if (name.includes("\\") || name.includes("\0")) return null;
  if (name.startsWith("/")) return null;

  const segments = name.split("/");
  if (!segments.length) return null;
  for (const seg of segments) {
    if (seg === "" || seg === "." || seg === "..") return null;
  }

  const full = resolve(join(runsRoot, name));
  const rootWithSep = resolve(runsRoot) + sep;
  if (!full.startsWith(rootWithSep)) return null;
  return { name, path: full };
}

async function readJsonOrNull(path) {
  try {
    return JSON.parse(await fs.readFile(path, "utf8"));
  } catch {
    return null;
  }
}

/**
 * The suite, enumerated from the harness's own roster.mjs when no run has a
 * pinned roster yet (a wiped bench). Execution-free: it only lists tests.
 * Never written to disk (an unpinned copy could go stale), but memoized in
 * memory for 30s: at ~1.9s a call on every /api/wall it timed out the board's
 * control-plane read.
 */
const ROSTER_CACHE_TTL_MS = 30_000;
// Keyed by benchRoot: one root's suite must never answer for another.
const rosterCache = new Map(); // benchRoot -> { at, value }

async function enumerateSuite(benchRoot) {
  // Cached even when null, so a failing enumerator isn't retried every poll.
  const hit = rosterCache.get(benchRoot);
  if (hit && Date.now() - hit.at < ROSTER_CACHE_TTL_MS) return hit.value;
  const value = await enumerateSuiteUncached(benchRoot);
  rosterCache.set(benchRoot, { at: Date.now(), value });
  return value;
}

async function enumerateSuiteUncached(benchRoot) {
  const script = join(benchRoot, "grader", "roster.mjs");
  // Via a temp file, not stdout: roster.mjs exits right after writing, which
  // truncates an async stdout pipe.
  const out = join(
    tmpdir(),
    `bench-wall-roster-${process.pid}-${randomUUID()}.json`,
  );
  try {
    if (!(await fs.stat(script)).isFile()) return null;
    await execFileAsync("node", [script, "--out", out], {
      cwd: join(benchRoot, "grader"),
      timeout: ROSTER_ENUMERATE_TIMEOUT_MS,
      maxBuffer: 8 * 1024 * 1024,
    });
    const parsed = await readJsonOrNull(out);
    return Array.isArray(parsed?.gates) && parsed.gates.length > 0 ? parsed : null;
  } catch {
    // Never fabricate: an enumerator that cannot run leaves the suite unknown.
    return null;
  } finally {
    await fs.rm(out, { force: true }).catch(() => {});
  }
}

/**
 * Read the status stream, bounded. A truncated first line or an unparseable
 * line is skipped, never fatal.
 */
export async function readStatusRecords(path, { bytes = 4 * 1024 * 1024 } = {}) {
  let text;
  try {
    const st = await fs.stat(path);
    if (!st.isFile()) return null;
    const fh = await fs.open(path, "r");
    try {
      const start = Math.max(0, st.size - bytes);
      const len = st.size - start;
      const buf = Buffer.alloc(len);
      await fh.read(buf, 0, len, start);
      text = buf.toString("utf8");
      if (start > 0) text = text.slice(text.indexOf("\n") + 1);
    } finally {
      await fh.close().catch(() => {});
    }
  } catch {
    return null;
  }

  const out = [];
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (!t.startsWith("{")) continue;
    try {
      out.push(JSON.parse(t));
    } catch {
      /* fragment — skip, never abort */
    }
  }
  return out;
}

/** Attempt records, oldest first, with a usable attempt number. */
export function attemptRecords(records) {
  return (records ?? [])
    .filter((r) => r?.type === "attempt")
    .map((r) => ({ ...r, attempt: Number.isFinite(Number(r.attempt)) ? Number(r.attempt) : 1 }))
    .sort((a, b) => a.attempt - b.attempt);
}

/**
 * Fold the test outcomes to the ONE derived count the wall serves: gates the
 * runner explicitly published as `not_run`. The latest result per gate wins (a
 * later measurable attempt clears an earlier non-result), and a gate the stream
 * never mentions is NOT counted — unmeasured is a stated non-result, not
 * "not reached yet".
 *
 * No per-gate projection: the wall's former renderer was retired, and its
 * trajectory/state fields had no reader left.
 */
export function foldGateStates({ attempts }) {
  // gate id → latest status (attempts scanned oldest → newest).
  const latest = new Map();

  for (const record of attempts) {
    const results = Array.isArray(record.gate_results) ? record.gate_results : null;
    if (!results) continue;
    for (const result of results) {
      if (!result?.id) continue;
      latest.set(result.id, result.status);
    }
  }

  const unmeasured = [...latest.values()].filter((status) => status === "not_run").length;

  return { unmeasured };
}

/**
 * Assemble GET /api/wall. Never 500, never fabricate: a run with no roster
 * returns ok:true with suite.total:null — the suite size is unknowable, which
 * is a different fact from zero.
 *
 * ONE CELL. The status stream holds every cell of the campaign; the wall folds
 * only the records of `sequenceIndex`. Folding them all let one cell's
 * non-results answer for another. No cell given = the roster with no outcomes
 * folded, never a mix.
 */
export async function readWall({ runsRoot, runDir, sequenceIndex = null, benchRoot = null, upToAttempt = null }) {
  const target = resolveRunDir(runsRoot, runDir);
  if (!target) {
    return {
      ok: false,
      code: "bad_run_dir",
      reason: `run_dir must be a single directory name under the runs root; got ${JSON.stringify(String(runDir ?? ""))}`,
    };
  }

  // The run's own pinned roster wins; the live enumeration is only for no run.
  let roster = await readJsonOrNull(join(target.path, "gate-roster.json"));
  if (!roster && benchRoot) roster = await enumerateSuite(benchRoot);
  const cell = Number.isInteger(sequenceIndex) && sequenceIndex >= 0 ? sequenceIndex : null;
  // A missing status file reads null: no attempt yet, never an error.
  const records = cell === null ? [] : ((await readStatusRecords(join(target.path, "manifest.status.jsonl"))) ?? []);
  // The wall AS IT STOOD after attempt N, when asked (the board's attempt tabs):
  // the same fold over the attempts up to N, never a mix with later ones.
  const upTo = Number.isInteger(upToAttempt) && upToAttempt >= 1 ? upToAttempt : null;
  const attempts = attemptRecords(records.filter((r) => Number(r?.sequence_index) === cell)).filter(
    (a) => upTo === null || a.attempt <= upTo,
  );

  // The true enumerated count, or null. A roster that states a total answers
  // with it; otherwise the gates it lists do. Nothing knowable is null — never
  // 0, which would read as a healthy measurement of an empty suite.
  const stated = roster?.total;
  const listed = Array.isArray(roster?.gates) ? roster.gates.length : 0;
  const total = Number.isFinite(Number(stated)) && stated !== null && stated !== ""
    ? Number(stated)
    : listed > 0 ? listed : null;

  const folded = roster ? foldGateStates({ attempts }) : { unmeasured: null };

  return {
    ok: true,
    suite: { total },
    // Gates the runner published as not_run. A subset of untested; never 0 for
    // an unknown suite.
    unmeasured: folded.unmeasured ?? null,
  };
}

