# Settings

Every environment variable OpenDyno reads, grouped by the part it controls, with the file that reads it. Most
have a working default; a fresh clone needs none of them set except a model key.

## Running and the control plane

| Name | Default | What it does | Read in |
|---|---|---|---|
| BENCH_CONTROL_PORT | 8718 | the control plane's port | control/state.mjs |
| BENCH_CONTROL_BENCH_ROOT | the repo | the checkout the control plane serves | control/state.mjs |
| BENCH_CONTROL_PYTHON | `.venv/bin/python` | the Python the control plane runs jobs with | control/state.mjs, control/tools.mjs |
| BENCH_TASK_DIR | task/backgammon | the challenge a run uses | control/routes/run.mjs, control/board/sources/ |
| BENCH_DEV_MODE | (unset) | pins dev mode on or off; pinned, the settings drawer can't change it | control/devmode.mjs |
| BENCH_DEV_MODE_FILE | config/devmode.json | where dev mode's on/off is kept | control/devmode.mjs |
| BENCH_NOTICES | set per run | the run's notices file; the harness appends, the board reads | harness/live_stream.py |
| BENCH_LIVE_STREAM | (unset) | a second place to write each cell's live record ([live-stream.md](live-stream.md)) | harness/live_stream.py, grader/report.mjs |
| BENCH_LIVE_STREAM_NS | (unset) | the namespace stamped on that record | harness/live_stream.py |
| BENCH_STATS_MANIFEST | (unset) | an outside source for the board's run statistics | control/runstats.mjs |
| BENCH_TOOLS_URL | (unset) | the custom-tools service behind the board's tool drawer ([custom-tools.md](custom-tools.md)) | control/tools.mjs |
| BENCH_LAUNCHD_LABEL | (unset) | the launchd job the control plane runs as; set, the board's refresh button can restart it | control/tools.mjs |
| BENCH_ENV_FILE | config/bench.env | a file of settings loaded before a run | harness/benv.py |
| BENCH_DOTENV | `.env` | the file model keys are read from | harness/spend_key.py |
| BENCH_MAX_STEPS_PER_ATTEMPT | no cap | the most agent steps in one attempt (a positive whole number) | scripts/run_cumulative/runner.py |
| BENCH_TURN_STALL_TIMEOUT_S | 600 | how long a turn may go silent before it's called stalled | harness/adapters/challenge/constants.py |
| BENCH_ALLOW_MISSING_RUN_CONTEXT | off | let a cell start without its run context instead of refusing | harness/cumulative/run_context.py |

## The variant

How variant B's change gets in. [variants.md](variants.md) explains each one.

| Name | Default | What it does | Read in |
|---|---|---|---|
| BENCH_PLUGIN_DIR | (unset: no plugin) | the plugin package baked into the worker image; variant B cells refuse to start without one | harness/worker_image.py |
| BENCH_VARIANT_UPSTREAM | (unset) | the change's server, as the cell's sidecar reaches it (`scheme://host:port`) | harness/variant_slot.py, images/sidecar/egress-sidecar.js |
| BENCH_VARIANT_ENV | (unset) | a file of the plugin's own `NAME=value` settings, handed to variant B cells by name | harness/variant_slot.py |
| BENCH_VARIANT_READY_CMD | (unset) | a host command that exits 0 once the change's background work is done | harness/variant_hooks.py |
| BENCH_VARIANT_READY_TIMEOUT_S | 1800 | how long the ready command may keep failing before the next cell is refused | harness/variant_hooks.py |
| BENCH_VARIANT_COST_CMD | (unset) | a host command printing the change's running counters as one JSON object | harness/variant_hooks.py |

## Models and keys

| Name | Default | What it does | Read in |
|---|---|---|---|
| BENCH_CONTROL_PROXY_URL | http://127.0.0.1:4545 | the local model proxy: where the model list comes from | control/state.mjs, harness/model_catalog.py |
| BENCH_PROXY_PURPOSE | bench | the purpose tag your proxy gives the models set aside for benchmarking; only a model carrying it can run a cell | harness/model_catalog.py, control/contract.mjs, scripts/bench_preflight.py |
| BENCH_CONTROL_RUNTIME_URL | http://127.0.0.1:1234 | a local model runtime (LM Studio) | control/state.mjs |
| LOCAL_LLM_PROXY_API_KEY | (unset) | the local proxy's key; set here, it wins over `.env` | harness/spend_key.py, harness/adapters/challenge/worker_config.py |
| ORCAROUTER_API_KEY | (unset) | the cloud router's key; set here, it wins over the key file | harness/spend_key.py, control/cloud.mjs |
| BENCH_CLOUD_KEY_FILE | config/cloud.env | where the board stores the cloud router's key | harness/spend_key.py, control/routers.mjs |
| BENCH_DASHBOARD_CONFIG | ~/.config/opendyno/dashboard.json | a shared settings file that can hold router keys, for a machine that keeps them in one place | harness/spend_key.py, control/routers.mjs |
| BENCH_SPEND_DB_DSN | a local Postgres | the spend meter's database | harness/spend_key.py |
| BENCH_WORKER_SPEND_PROXY_BASE_URL | worked out from the sidecar | the proxy address as a cell sees it | harness/spend_key.py |
| BENCH_PROXY_CHECKPOINT | (unset) | the proxy's price list, for cost | harness/adapters/challenge/constants.py |
| BENCH_PROXY_RUNS_DIR | ~/.opendyno/proxy-runs | where the proxy logs which run a request came from | scripts/run_cumulative/runner.py |
| BENCH_REASONING_EFFORT | (unset) | the agent's reasoning effort, for models that take one | harness/adapters/challenge/runner.py |

## The cell

| Name | Default | What it does | Read in |
|---|---|---|---|
| BENCH_WORKER_CPUS | 8 | CPUs a cell's container may use | harness/adapters/docker_worker.py |
| BENCH_WORKER_MEMORY | 4g | memory a cell's container may use | harness/adapters/docker_worker.py |
| BENCH_WORKER_PIDS_LIMIT | 512 | processes a cell's container may run | harness/adapters/docker_worker.py |
| BENCH_SERVE_HOST_PORT | a free port | the host port the live terminal view is published on | harness/free_port.py |
| BENCH_SERVE_CONTAINER_PORT | 4096 | that view's port inside the container | harness/adapters/challenge/runner.py |
| BENCH_INGRESS_CELL_HOST | set per cell | the cell the sidecar lets the live view reach | images/sidecar/egress-sidecar.js |
| BENCH_INGRESS_PORT | 4096 | the port of that route | images/sidecar/egress-sidecar.js |
| BENCH_LOOP_KILL_MARKER_DIR | set per cell | where the sidecar marks a request loop it stopped | images/sidecar/egress-sidecar.js |
| BENCH_TOOL_TIMEOUT_S | 90 | how long one shell command the agent runs may take | images/sidecar/supervised-shell.js |
| BENCH_TOOL_TIMEOUT_MARKER_DIR | (unset) | where a timed-out command is marked | images/sidecar/supervised-shell.js |
| BENCH_PLAY_MAX_S | 21600 | how long a build the board serves for playing may stay up | harness/play_container.py |

## The grader

| Name | Default | What it does | Read in |
|---|---|---|---|
| BENCH_TARGET | task/backgammon/golden | the build being graded | grader/report.mjs, grader/lib/harness.ts |
| BENCH_LAYER | set per grade | the phase being graded; only that phase's checks run | grader/conformance/pregate.ts, grader/frontend/ |
| BENCH_PORT | 8002 | the first port a graded build's server gets; each grading worker adds its number | grader/lib/harness.ts |
| BENCH_WORKERS | from CPU and memory | how many grading workers run at once | grader/lib/workers.mjs |
| BENCH_WORKER_TARGET | 0.7 | the share of the machine grading may use, when the count isn't forced | grader/lib/workers.mjs |
| BENCH_RUNNER_TIMEOUT_MS | 900000 | the limit for one suite of checks | grader/report.mjs |
| BENCH_SUITE_BUDGET_MS | 3300000 | the limit for a whole grade, kept under the harness's own so a report is always written | grader/report.mjs |
| BENCH_ATTEMPT, BENCH_CAPTURE_DIR | set per grade | where the board screenshot of an attempt is saved | grader/capture/board-capture.spec.ts |
| DEBUG_API | off | turns on the challenge's debug route, which the grader uses to set up a position | task/backgammon/golden/src/server.ts |
| PORT | 8002 | the port a build's server listens on | task/backgammon/golden/src/server.ts |
| TEST_PARALLEL_INDEX, VITEST_POOL_ID | set by the test runner | which worker a check runs on, for its port | grader/lib/harness.ts |

## The board

| Name | Default | What it does | Read in |
|---|---|---|---|
| BENCH_DASH_PORT | 8717 | the board's port | dashboard/server.mjs |
| BENCH_DASH_HOST | 127.0.0.1 (0.0.0.0 in the image) | the address the board listens on | dashboard/server.mjs |
| BENCH_DASH_CONTROL_URL | http://127.0.0.1:8718 | the control plane the board reads from | dashboard/server.mjs |
| BENCH_DASH_ALLOWED_HOSTS | (unset) | extra host names the board may be opened by, comma-separated; addresses and localhost always pass | dashboard/server.mjs |

## Tools and checks

| Name | Default | What it does | Read in |
|---|---|---|---|
| MATRIX_PORT_BASE | 8600 | the first port a class matrix uses; give each matrix run its own | tools/class_matrix.py |
| MATRIX_WORK | a temp folder | where a class matrix builds its broken copies | tools/class_matrix.py |
| SEAM_RUNS_ROOT, SLOT_RUNS_ROOT, SLOT_SUBJECT | set by preflight | handed to preflight's own probes | scripts/preflight/ |

## Set inside the images

The worker and grader images set the usual runtime switches for opencode, Node, npm, apt and Playwright
(`OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`, `XDG_CONFIG_HOME`, `NODE_PATH`, `PLAYWRIGHT_BROWSERS_PATH`,
`NPM_CONFIG_*`, `DEBIAN_FRONTEND`). See `images/worker/Dockerfile` and `images/grader/Dockerfile`; they are not
meant to be changed.
