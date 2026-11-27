// SOURCE: run-manifest — the active run's manifest.json (written at start):
// provenance a skeptic checks first — model, seed, roster. policy_version
// and policy_anchor_status are always null now (the hub is no longer read).

import { str, int } from "../contract.mjs";
import { readJson, activeRun } from "./_runtime.mjs";

export const id = "run-manifest";
export const fields = ["provenance", "run.model"];
export function describe() {
  return "run manifest — model identity, seed, provenance (RC-5)";
}

export async function read(ctx) {
  // The active run's manifest, so provenance matches the gates on the wall.
  const run = await activeRun(ctx.runsRoot);
  if (!run?.manifestPath) return { ok: false, reason: "no manifest.json under runs root" };

  const m = await readJson(run.manifestPath);
  if (!m) return { ok: false, reason: "manifest.json unreadable or malformed" };

  const edge = m.run_context?.edge_policy ?? {};

  const schedule = Array.isArray(m.schedule) ? m.schedule : [];
  const roster = Array.isArray(m.roster) ? m.roster : [];
  const model =
    str(schedule[0]?.provider_pin) ??
    str(roster[0]?.provider_pin) ??
    str(roster[0]?.model);

  return {
    ok: true,
    provenance: {
      path: run.manifestPath,
      mtime: run.manifestStat?.mtimeMs ?? null,
      bytes: run.manifestStat?.size ?? null,
      run: run.name,
    },
    patch: {
      run: {
        model,
        started_at: Date.parse(str(m.created_at) ?? "") || null,
      },
      provenance: {
        policy_version: str(edge.version),
        policy_anchor_status: str(edge.anchor_status),
        seed: int(m.seed),
      },
    },
  };
}
