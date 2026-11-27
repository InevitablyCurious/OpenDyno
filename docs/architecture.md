# How it's built

## The parts

| Part | What it does |
|---|---|
| `harness/` | Runs a **cell**: one agent session building the app through every phase, graded after every attempt. Isolation, fingerprints, cost, the live record, checkpoints. |
| `grader/` | The checks: `conformance/` (the names, routes and debug route the spec fixes), `backend/` (vitest, against the engine and the server), `frontend/` (Playwright, against the page). `report.mjs` runs them and writes one report. The only part that grades against the reference build. |
| `task/` | The bundled challenge (backgammon): the starting files, the spec in chunks (`prompts/chunk-*.md`), the told lines (`prompts/failures/`), the spec passages handed back (`prompts/respec/`), and the reference build (`golden/`, never shown to the agent). |
| `challenges/` | The template for writing your own challenge. A challenge is its own git repo; backgammon is the worked example that ships here. |
| `control/` | The control plane (`:8718`), the only process that reads run files or changes anything: start, stop, pause, resume, reset, rebuild. |
| `dashboard/` | The board (`:8717`), read-only; every panel reads from the control plane. |
| `images/` | The worker image (the agent's harness) and the grader image; the network sidecar that is a cell's only way out. |
| `variants/` | Example kits for variant B. |
| `tools/` | The class-matrix tool for auditing the grader. |

## A cell, start to finish

1. A fresh worktree from the challenge's starting files, in its own containers, with a network that only reaches
   the model and, for variant B, the change's server.
2. **Phase by phase.** Each phase hands the agent its chunk of the spec. The agent writes code until it says it's
   done or a limit stops it.
3. **Grade.** The grader runs on a clean copy of the agent's code. The report lists every failing check with
   what it observed.
4. **Stage and tell.** The findings are staged by moment ([problem-speak](problem-speak.md)), the earliest
   failing moment is turned into lines, and the agent gets them and another attempt. A phase passes when its
   checks pass, and the next phase starts.
5. **Checkpoint.** Every graded attempt leaves its code under `checkpoints/cp-NN/tree`, so any attempt can be
   replayed, played on the board, or resumed from.
6. The cell ends when the last phase passes, or a limit is reached.

In **dev mode** the cell pauses after every grade, before the agent is told anything, so the lines can be checked
against the build. The board's hold view plays the exact build that was graded.

## Where a run writes

```
runs/<tree>/
  manifest.json                        the campaign: every cell, both variants
  local/<provider>/<backend>/<model>/
    variantA/cell-NNNN/                the baseline cells
    variantB/cell-NNNN/                the cells with the change in
```

Each cell folder holds `fingerprint.json` (everything the result depends on), `cost.json` (tokens in every
category, cache included, and wall time), `live.jsonl` (every event, as it happened), `attempt-N-report.json`
and `attempt-N-board.png` for every grade, the per-suite grader logs, and `checkpoints/`.

## Measuring

- **Fixed:** the challenge, the spec, the grader, the lines, the worker image, the model alias and compaction
  mode. Those, plus the harness code, source commit, opencode version and grader image, are in the fingerprint;
  cells only compare when their fingerprints match.
- **What it cannot see:** a provider changing the weights behind a model alias, or the proxy's live context
  window and output limit. A matching fingerprint makes a comparison admissible; it does not prove the grader
  is right.
- **Variant A** is run three times first. Their spread is the noise floor.
- **Variant B** is compared with the average of variant A on the same fingerprint. The board shows a difference
  only once each side has three scored runs.
- **What's compared:** whether each phase passed and in how many attempts, the checks still failing, tokens,
  cache, turns and wall time.
- **Invalid runs** (an infrastructure fault, a grader alarm) are counted as excluded, never as zero.
