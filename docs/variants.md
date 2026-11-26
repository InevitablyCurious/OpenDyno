# Variants

Variant A is the harness as it is. Variant B is the same harness with one change in. This page is how the change
gets in.

## Plugging a change in

| What | Setting | Reaches |
|---|---|---|
| The plugin | `BENCH_PLUGIN_DIR` (when the worker image is built) | the one worker image; loaded in variant B cells only |
| A route to its server | `BENCH_VARIANT_UPSTREAM` | variant B cells, through the cell's network sidecar |
| Its own settings | `BENCH_VARIANT_ENV` | variant B cells, by name |
| "Has it finished?" | `BENCH_VARIANT_READY_CMD` | runs on the host, around each variant B cell |
| "What has it spent?" | `BENCH_VARIANT_COST_CMD` | runs on the host, around each variant B cell |

Only the plugin is needed by every change. A change that lives in files or prompts needs nothing else. A change
with its own server and background work, like a memory system, uses all five.

**The plugin.** Today's agent harness is opencode, so a change comes in as an opencode plugin package. Its
`package.json` names the file opencode loads (`exports`, `module` or `main`), and that file must exist, built.
Building the worker image installs the package and prints what it loaded; a package with no loadable entry is
refused before the build starts.

**One image for both variants.** The plugin is installed in the worker image and both variants run on that
image. Only a variant B cell lists the plugin in its own opencode config; a variant A cell never loads it. The
image is part of every cell's fingerprint, so variant A must run on the same image as the variant B it's compared
with. Rebuild with a different plugin, or a different version of it, and the old variant A runs no longer count
as the baseline. A variant B cell on an image with no plugin refuses to start.

**The same worktree for both.** The change is switched on only in the cell's config, never by files the model
can see. Both variants start from the same files.

**The route.** Cells run on a network with no way out but their sidecar. `BENCH_VARIANT_UPSTREAM` is the change's
server as the sidecar reaches it (`scheme://host:port`); a variant B cell's sidecar forwards its port 4560 there.
A variant A cell has no such route.

**The settings.** `BENCH_VARIANT_ENV` names a file of the plugin's own settings, one `NAME=value` per line.
`{variant_url}` in a value becomes the address the cell reaches the server at. Values are handed over by name, so
they never show up in a command line or in `docker inspect`, and names that look secret (`KEY`, `TOKEN`,
`SECRET`, `PASSWORD`, `AUTH`) are masked wherever they are recorded. Names that decide what the cell is
(`HOME`, `PATH`, `OPENCODE_*`, `BENCH_*`, the proxy variables, the model keys, and the like) are refused, and so
are names shaped like secret material (a seed, a keystore, a password, a private key, a credential, a secret): the
model can read a cell's settings.

**Ready.** Some changes keep working after a cell ends; a memory system digests the cell's messages in the
background. `BENCH_VARIANT_READY_CMD` is a host command, run with `sh -c` from the repo root, that exits 0 once
that work is done. It is polled before each variant B cell, so every cell starts from finished work, and again
after, so the cell's own processing is counted against it. Both waits sit outside the cell's wall time. Still
busy after `BENCH_VARIANT_READY_TIMEOUT_S` (default 1800) and the next cell is refused.

**Cost.** `BENCH_VARIANT_COST_CMD` prints one JSON object of the change's running counters, like
`{"input_tokens": 120400, "output_tokens": 9310}`. It is read before and after each variant B cell and the growth
is recorded as the change's own cost. A counter that went down means a restart mid-cell and is recorded as such.

## A worked example

[variants/honcho/](../variants/honcho/) is a memory system set up as variant B: its settings file, its ready and
cost hooks, and a compose override to run its server beside the benchmark.

## Adding your own

1. Package the change as an opencode plugin with `package.json` naming the built entry. Bake it with
   `BENCH_PLUGIN_DIR` and rebuild the worker image.
2. If it has a server, run it on the benchmark machine, set `BENCH_VARIANT_UPSTREAM`, and put its settings in a
   file for `BENCH_VARIANT_ENV`.
3. If it works in the background, write a ready command. If it calls models of its own, write a cost command.
4. Put the files in `variants/<name>/`.
5. Run variant A a few times on the new image, then variant B.

The harness never looks inside the change. It keeps everything else the same and measures the difference.
