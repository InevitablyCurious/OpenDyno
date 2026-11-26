# Operating it

## Bring it up

Install once and build the two images (see the [README](../README.md) quick start), then:

```bash
.venv/bin/python scripts/bench_preflight.py --model <alias>   # GO, or NO-GO naming the fix
node control/server.mjs                                        # control plane, http://127.0.0.1:8718
(cd dashboard && docker compose up -d)                         # board, http://127.0.0.1:8717
```

Preflight checks everything a run needs (images, grader tools, the model's endpoint, ports, disk) and refuses
with the fix instead of letting a run fail halfway. The control plane is the only process that writes; the board
only reads from it.

## Models

A model is an alias with an OpenAI-compatible endpoint: local (oMLX, LM Studio, vLLM, llama.cpp behind a proxy)
or cloud. Its context window and settings are part of every cell's fingerprint, so a run on a different model, or
the same model with different settings, is a different baseline.

## Running

- **`+ BASELINE`** starts variant A: pick local or cloud, the model and the challenge; the preflight checklist
  runs before anything starts.
- **`+ run`** on a baseline row starts variant B with the plugin baked into the worker image
  ([variants](variants.md)).
- **Stop** ends the running cell and tears its containers down. A cell that was stopped is counted as excluded.

## Dev mode: checking the grader while it runs

Turn **dev mode** on in the settings drawer. The cell then pauses after every grade, before the agent hears
anything:

- the **hold view** shows the lines the agent is about to be told and serves the exact build that was graded, so
  you can play it;
- **release** sends the lines and the run carries on.

If a line is wrong, stop the run, fix the grader, prove the fix ([CONTRIBUTING](../CONTRIBUTING.md)), rebuild the
grader image (refused while a run is in flight, paused ones included), and resume from the checkpoint of the
attempt that would have been told the wrong line. The agent never hears it.

## Resuming

Every graded attempt leaves a checkpoint. A run can resume from any of them: give the checkpoint folder, relative
to `runs/` or as an absolute path anywhere on disk. The resumed cell starts a fresh session on that code, with the
whole spec, and is marked as not a measurement.

## Reset and restore

**Reset** moves every run into a backup and starts a clean tree; **restore** brings a backup back. Both show a
preview first and need a confirmation. The board's history page reads the backups.

## The settings drawer

Refresh the worker image, the grader image, the control plane or the board; the custom tools; how much of the
machine grading may use; dev mode; router credentials.

## Reference

- [env-vars.md](env-vars.md): every setting, with the line that reads it.
- [live-stream.md](live-stream.md): the per-cell event record, `live.jsonl`.
- [custom-tools.md](custom-tools.md): adding your own buttons to the board's tool drawer.
- [architecture.md](architecture.md): the parts, a cell from start to finish, where a run writes.
