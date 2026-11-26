// SOURCE: status-stream — ONE CELL's manifest.status.jsonl, the authoritative
// per-attempt record (variant, verdict, progress). Records: `attempt`
// (variant, failed_gates, verdict, progress) and `turn_terminal` (per
// anomalous turn). Appended at attempt end (~30 min), so it is not the live
// pulse. It does not build the gate wall (that is GET /api/wall). Token totals
// are NOT read from these rows — an attempt's counters are that attempt's —
// they come from each cell's cost stamp (`cost.json` `phases.total`) below.
//
// Per cell only. The board-wide reads this source used to publish (a per-variant
// delta and a run history) had no renderer, and are gone.

import { join } from "node:path";
import { int, str } from "../contract.mjs";
import { readTail, parseJsonl, statOrNull } from "./_runtime.mjs";
import { readCellCost } from "../../baselines.mjs";

export const id = "status-stream";
/** What readCell adds to one cell's view. */
export const cellFields = ["run.variant", "run.attempt", "run.turns", "run.tokens", "honesty"];
export function describe() {
  return "append-only per-attempt status stream (RC-5) — authoritative for gates, variant, verdict";
}

/**
 * ONE CELL's own attempt records: its variant, attempt, turns, tokens and
 * transport honesty. Never the newest cell's, never a sum over cells.
 */
export async function readCell(ctx) {
  const path = join(ctx.runsRoot, ctx.cell.run_dir, "manifest.status.jsonl");
  const st = await statOrNull(path);
  if (!st?.isFile()) {
    return { ok: false, reason: "no manifest.status.jsonl yet — appended at attempt end (~30 min)" };
  }
  const records = parseJsonl(await readTail(path));
  const c = cellsFromRecords(records, ctx.cell.run_dir).find((x) => x.seq === ctx.cell.sequence_index);
  if (!c) return { ok: false, reason: "this cell has no attempt record yet — written at attempt end" };
  await attachCostStamp([c], join(ctx.runsRoot, ctx.cell.run_dir));
  const one = [c];

  return {
    ok: true,
    provenance: { path, mtime: st.mtimeMs, bytes: st.size, run: ctx.cell.run_dir },
    patch: {
      run: {
        variant: c.variant,
        cell_label: c.cell_label,
        org_id: c.org_id,
        attempt: { current: c.attempt, max: null },
        turns: c.turns,
        tokens: {
          input: c.input_tokens,
          output: c.output_tokens,
          reasoning: c.reasoning_tokens,
          cache_read: c.cache_read_tokens,
          cache_write: c.cache_write_tokens,
        },
      },
      honesty: {
        transport: {
          truncations: sum(one, "truncated_turns"),
          finalize_timeouts: sum(one, "finalize_timeouts"),
          finalize_timeout_turns: sum(one, "finalize_timeout_turns"),
          guard_aborts: sum(one, "guard_aborted_turns"),
        },
      },
    },
  };
}

function sum(cells, key) {
  return cells.reduce((acc, c) => acc + (c[key] ?? 0), 0);
}

/**
 * Fold a stream's records into per-cell state by sequence_index. An `attempt`
 * record that states an attempt number IS that attempt — the number is a fact
 * about the cell, not a property of the gate list beside it.
 */
function cellsFromRecords(records, dirName) {
  const by = new Map();

  for (const r of records) {
    const seq = int(r.sequence_index) ?? 0;
    const key = `${dirName}#${seq}`;
    if (!by.has(key)) {
      by.set(key, {
        cell_label: `${dirName}-${String(seq).padStart(4, "0")}`,
        seq,
        variant: null,
        org_id: null,
        attempt: null,
        verdict: null,
        complete: false,
        turns: null,
        wall_seconds: null,
        // The cell's token totals, attached from cost.json `phases.total` (one
        // read per cell). Never from an attempt row: those counters are the
        // attempt's, and the last attempt is not the cell.
        input_tokens: null,
        output_tokens: null,
        reasoning_tokens: null,
        cache_read_tokens: null,
        cache_write_tokens: null,
        truncated_turns: 0,
        guard_aborted_turns: 0,
        finalize_timeout_turns: 0,
        finalize_timeouts: 0,
        problems_before: null,
        problems_after: null,
        last_seen: 0,
      });
    }
    const c = by.get(key);

    if (r.type === "turn_terminal") {
      // Both relay stream-death kinds count in one tile.
      const reason = str(r.reason);
      if (reason === "stream_finalize_timeout" || reason === "relay_stream_incomplete") {
        c.finalize_timeouts += 1;
      }
      continue;
    }

    // Only `attempt` records (or legacy ones with no type) carry progress
    // state; other types are skipped.
    if (r.type !== undefined && r.type !== "attempt") continue;

    const attempt = int(r.attempt);
    if (attempt !== null) c.attempt = Math.max(c.attempt ?? 0, attempt);

    c.variant = str(r.variant) ?? c.variant;
    c.org_id = str(r.org_id) ?? c.org_id;
    c.verdict = str(r.verdict) ?? c.verdict;
    if (r.terminal_outcome === true || str(r.terminal_reason)) c.complete = true;

    const p = r.progress ?? {};
    c.turns = int(p.turns) ?? c.turns;
    c.wall_seconds = Math.round(Number(p.wall_seconds ?? 0)) || c.wall_seconds;
    c.truncated_turns = Math.max(c.truncated_turns, int(r.truncated_turns) ?? 0);
    c.guard_aborted_turns = Math.max(c.guard_aborted_turns, int(r.guard_aborted_turns) ?? 0);
    // Carried on the status stream; absent on older records stays 0.
    c.finalize_timeout_turns = Math.max(
      c.finalize_timeout_turns,
      int(r.finalize_timeout_turns) ?? 0,
    );
    c.problems_before = int(p.problems_before) ?? c.problems_before;
    c.problems_after = int(p.problems_after) ?? c.problems_after;
    c.last_seen += 1;
  }

  return [...by.values()];
}

/**
 * Attach the cell's own token totals from its cost stamp, in ONE read per cell.
 *
 * `phases.total` is the only place all five kinds exist, with
 * `output_tokens` generation-only and `reasoning_tokens` beside it. A status
 * row's `work_*` counters are per ATTEMPT, phase-scoped — reading them per cell
 * by last-write-wins reported the last attempt as the whole cell. An absent key
 * is null (unknown), never 0; a cell with no stamp shows null throughout.
 */
async function attachCostStamp(cells, runDir) {
  for (const c of cells) {
    const cellDir = join(
      runDir,
      `variant${String(c.variant ?? "unknown").toUpperCase()}`,
      `cell-${String(c.seq).padStart(4, "0")}`,
    );
    const cost = await readCellCost(cellDir);
    const total = cost?.phases?.total ?? null;
    c.input_tokens = int(total?.input_tokens);
    c.output_tokens = int(total?.output_tokens);
    c.reasoning_tokens = int(total?.reasoning_tokens);
    c.cache_read_tokens = int(total?.cache_read_tokens);
    c.cache_write_tokens = int(total?.cache_write_tokens);
  }
  return cells;
}
