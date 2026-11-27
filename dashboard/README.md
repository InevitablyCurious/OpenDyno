# The board

OpenDyno's live view: every run, every check, what the agent was told, and the difference between variant A and
variant B.

```bash
docker compose up -d          # http://127.0.0.1:8717
node server.mjs               # or on the host, no install (Node 22+)
```

It is read-only. Every panel reads from the control plane on `:8718`, the only process that reads run files or
changes anything. It keeps "not measured", "not connected" and "measured, and zero" apart, counts invalid runs as
excluded rather than as zero, and shows no difference between the variants below three scored runs on each side.

**No dependencies and no build step.** If this ever needs a package manager to start, something has been added
that shouldn't have been. Two libraries are vendored in `vendor/` (xterm.js for the terminal mirror, diff2html for
the history page's diffs), each with its licence.

**Tests** run on Node's own test runner:

```bash
node --test
```

A panel test imports `board.js` and `create.js` bare: the board boots only when both `document` and
`EventSource` exist, so under Node the import is inert. Stub `EventSource` or `window` and the boot fires and
crashes.

**Viewing from another machine** on your network: `docker-compose.lan.yml` adds a second published address. Set
`LAN_ADDRESS` in `dashboard/.env` to this machine's address and add the board's host name to
`BENCH_DASH_ALLOWED_HOSTS`.
