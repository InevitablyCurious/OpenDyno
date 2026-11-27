# OpenDyno

**A/B testing for AI agent harnesses.**

A dyno measures an engine under controlled load. OpenDyno measures an agent harness the same way: the same model, the same build task, the same grader, and the same feedback, twice. Change one thing between the runs. The difference — once it beats the noise — is what your change did.

## What it is

A **harness** is everything around the model: how context is kept or compacted, whether work goes to sub-agents, the loop that plans and retries, the tools, the memory, the instructions, and the way feedback comes back. Change any of those and the agent gets better or worse at real work. OpenDyno measures by how much.

- **Variant A** is the harness as it is today.
- **Variant B** is the same harness with one change in.

Both build the same app from the same spec, with the same model, grader and feedback. OpenDyno reports what changed: phases passed, attempts needed, checks still failing, tokens, cache, turns and wall time.

This is not a test runner with a leaderboard bolted on. The task, the checks and the words the agent reads are built as one instrument.

## What makes a difference a result

A benchmark can produce a number without producing evidence. These three conditions are not features; they are what the number has to satisfy before OpenDyno will call it a result.

**The same instrument.** Every cell records the challenge, spec, grader, feedback lines, worker image, model and its settings. Two runs are compared only when those match. This does not make the agent repeatable — it is stochastic, and no fingerprint changes that. It makes the comparison *admissible*: if you swapped the model, rebuilt the image, or edited the grader between A and B, the difference is not your change, and the board will not subtract the runs. It also catches silent drift — a provider updating a model behind an alias, a changed plugin version, a rebuilt image — that would otherwise look like a result.

**The same feedback, and no answer key.** The agent never sees the grader's assertion, selectors, check ids or expected values. It gets a stable, user-voice report of the fault instead. That keeps the feedback a constant across A and B and keeps the agent solving the user's problem rather than the grader's. The next section shows what that means in practice.

**Enough runs to separate signal from noise.** Variant A is not one run; it is three scored runs, and their spread is the noise floor. Variant B is compared with their average, and the board withholds the delta until each side has three scored runs. This is methodology, not a feature. It is here because it is a behaviour of the product: a single A and a single B will not produce a number, however tempting the difference looks. Agent runs vary enough that one run can look like a win; the board's job is not to report that as one.

## Why the agent never sees the test

A raw test failure is an answer key. It looks like this:

```text
F12 expected [data-testid="hint"] to have 3 children, found 0
```

That one line tells the agent the check id, the selector, the expected count, and the shape of the DOM. An agent optimised for passing checks can add a div with three children and never implement hints. The benchmark would then be measuring test-fitting, not building.

Problem-speak describes the same fault differently:

> I clicked my checker on the bar and no hints appeared.

The agent has to find the bar, trace the click, and implement the hint logic. That is the behaviour being measured. The advantage is not that it is plainer or friendlier; it is that it is a controlled, leak-free feedback stimulus. Four things follow from that:

- **No answer key.** The agent never sees the assertion, selector, check id or expected value. It sees the symptom a user or integration team would report, so it has to solve the user's problem instead of the grader's implementation.
- **A fixed feedback channel.** Feedback is part of the harness under test. If variant B's error messages are longer, shorter, or differently worded, that is a second independent variable. Fixed lines make the feedback a constant across A and B.
- **Stable units across runs and grader refactors.** If you refactor a check but the user-visible fault is the same, the line stays the same, so old runs remain comparable. Raw assertion text changes, and the baseline silently becomes a different experiment. Stable lines also let you count "this fault appeared in 4 of 6 runs" instead of parsing logs.
- **Construct validity and auditability.** The benchmark claims to measure "build the app from user feedback." A test report measures "fix the test." The voice is not cosmetic; it defines the task. And every line is a claim a human can check against the build in dev mode.

That is the curation. Every line is a fixed artifact, not a summary generated at runtime. It has to be true for the build it describes, actionable enough to fix, general enough not to hand over the implementation, and told at the moment a person would meet it.

The same fault produces the same words; measured values are included when a number is what the agent needs; the spec's own passage comes back when the agent keeps missing a rule. The lines never mention tests, graders, gates or scoring — a model that knows it is being measured is not the model you meant to measure. When a line fails any of those, the run is measuring the grader, not the harness. That is why the feedback is part of the instrument, not error copy.

## What you can put on the dyno

Anything that sits between the model and the work:

- **Context** — compaction on or off, when it fires, how it summarises, window size, prompt caching.
- **Delegation** — sub-agents against inline work, how much context they burn, manager and worker tiers.
- **Loops** — plan / act / check, retry and repair, self-critique, stop rules, loop guards.
- **Memory** — long-term memory, retrieval, notes files, skill libraries.
- **The harness itself** — tool sets and how they are described, hooks, permission modes, system prompts, instruction files, MCP servers.
- **Feedback at inference time** — what the agent is told after each attempt, in whose voice, how much detail.
- **Spec style** — one long brief against phased chunks.
- **Models** — swaps, sizes, quantisation, reasoning budget, local against cloud.
- **Self-verification** — agents that run their own tests or look at their own screen.
- **Cost** — tokens, cache hits and wall time per working build. Every run records all of it.

Variant B arrives as a plugin for the agent's harness. [docs/variants.md](docs/variants.md) shows how, with a memory system as the worked example.

## How a run works

1. **Isolate.** A fresh worktree from the challenge's starting files, in its own containers, on a network that only reaches the model and — for variant B — the change's own server.
2. **Build in phases.** The agent gets its slice of the spec for each phase: the engine, the server, the page in three layers (board, pieces, gameplay), then wiring and a last check.
3. **Grade.** After every attempt the grader runs the whole suite against the agent's code, on a clean checkout, in a container.
4. **Conformance first.** The things every other check stands on go first: the app starts, the names and routes the spec fixes are there, and a position set through the debug route plays the same as one reached by play. If those fail, that is all the agent hears.
5. **One moment at a time.** Findings are staged by the moment a person meets them. The agent hears the earliest moment that still fails, fixes it, and moves on. A later fault waits its turn.
6. **Tell, retry, checkpoint.** The agent reads the problem-speak for that moment, plus the spec's own words when it keeps missing a rule, and gets another attempt. Every graded attempt leaves its code under `checkpoints/`, so it can be replayed, played on the board, or resumed.

A phase passes when every check up to it passes.

## Quick start

### You need

- Docker with Compose v2.
- Python 3.11+.
- Node 22+.
- A model: local behind an OpenAI-compatible endpoint, or cloud through OrcaRouter.
- Several GB of disk for the worker and grader images, plus run artifacts.

### 1. Install

```bash
git clone https://github.com/InevitablyCurious/OpenDyno.git
cd OpenDyno

python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
(cd grader && npm ci)

.venv/bin/python scripts/rebuild_worker_image.py
.venv/bin/python scripts/rebuild_grader_image.py
```

`npm ci` installs the host-side tools preflight and the class matrix use; the grading itself runs inside the grader image. The grader build also grades the reference build and refuses to promote an image that cannot pass its own checks, so the first build takes a while.

### 2. Connect a model

**Local.** The model must be served through the local model proxy on `:4545`, tagged for benchmark use. Put its key in `.env`:

```bash
cp .env.example .env
# set LOCAL_LLM_PROXY_API_KEY
```

Then check the setup:

```bash
.venv/bin/python scripts/bench_preflight.py --model <alias>
```

**Cloud.** Put an OrcaRouter key in the environment or in `config/cloud.env`:

```bash
export ORCAROUTER_API_KEY=...
# or: echo 'ORCAROUTER_API_KEY=...' > config/cloud.env
```

Then:

```bash
.venv/bin/python scripts/bench_preflight.py --cloud --provider <provider> --model <model>
```

Preflight checks the images, grader tools, model endpoint, ports and disk. It prints **GO** with the exact launch command, or **NO-GO** naming the fix. Use `--variant b` when checking a variant B setup.

### 3. Start the control plane

In one terminal, from the repo root:

```bash
node control/server.mjs
```

Leave it running. It is the only process that writes.

### 4. Start the board

In a second terminal:

```bash
(cd dashboard && docker compose up -d)
```

Open [http://127.0.0.1:8717](http://127.0.0.1:8717).

## Your first comparison

1. **`+ BASELINE`** picks the model and the challenge and runs your harness as it is. Run it three times. That spread is your noise floor.
2. **`+ run`** on a baseline row runs the same thing with your change in. Run it three times too.
3. **Read the board.** Once each side has three scored runs, it shows the difference: phases passed and in how many attempts, checks still failing, tokens and cache, turns and wall time.
4. **Change one thing.** A/B testing only works when one thing changes. Change one model-facing thing per run.

Use **Stop** to end a cell and tear down its containers. Use **dev mode** to pause after every grade and inspect exactly what the agent is about to be told. Any graded attempt can be resumed from its checkpoint. [docs/operating.md](docs/operating.md) covers all three.

## What to expect

- **Time.** One local cell in our sample run took about 22 minutes on a 35B model, with four grades of 245 checks. A first comparable result needs three baseline cells and three variant B cells, so budget hours, not minutes.
- **Cost.** Every cell records tokens by category, cache reads and writes, turns and wall time in `cost.json`. A variant B with its own server can also report its own running cost, recorded separately.
- **Output.** Each run writes under `runs/<tree>/`: the campaign manifest, one folder per cell, the fingerprint, the cost, the report and board image for every attempt, the live event record, and checkpoints.
- **Invalid runs.** An infrastructure fault or grader alarm is counted as excluded, never as a zero.

## The bundled challenge

Today's challenge is backgammon against a computer opponent: an engine, a server, a page, a doubling cube, and an AI with three difficulties. It is big enough to need real work, small enough to finish, and nobody's novel invention, so the agent is graded on building, not on guessing what we meant.

It is the worked example, not the product. To write your own challenge — its spec, scaffold, reference solution and grading suite — start from [challenges/TEMPLATE](challenges/TEMPLATE/README.md).

## Glossary

| Term | Meaning |
|---|---|
| **Dyno** | The metaphor: a rig that measures something under controlled load. Here, a harness under a fixed build task. |
| **Harness** | Everything around the model: context, delegation, loops, tools, memory, prompts, feedback. |
| **Variant A** | The harness as it is today. The baseline. |
| **Variant B** | The same harness with one change in. |
| **Cell** | One agent session building the app through every phase, graded after every attempt. |
| **Challenge** | The app the agent builds, with its spec, scaffold, reference build and grading suite. |
| **Phase** | One stage of the build, with its own slice of the spec and its own checks. |
| **Moment** | The point where a person first meets a fault, in the order they would meet it. |
| **Problem-speak** | The deterministic line the agent is told when a check fails. |
| **Fingerprint** | Everything a result depends on. Cells only compare when their fingerprints match. |
| **Baseline** | The average of the scored variant A cells on one fingerprint. |

## Documentation

| Page | What it covers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | The parts, a cell from start to finish, where a run writes. |
| [docs/operating.md](docs/operating.md) | Running, stopping, resuming, dev mode, reset and restore. |
| [docs/variants.md](docs/variants.md) | How a variant B change gets in, including its server, settings and cost hooks. |
| [docs/problem-speak.md](docs/problem-speak.md) | How a failed check becomes the words the agent reads, and the rules every line follows. |
| [docs/env-vars.md](docs/env-vars.md) | Every setting, with the line that reads it. |
| [docs/live-stream.md](docs/live-stream.md) | The per-cell event record, `live.jsonl`. |
| [docs/custom-tools.md](docs/custom-tools.md) | Adding your own buttons to the board's tool drawer. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Auditing the grader and proving a fix. |

## Repository layout

```
harness/     runs the agent through the phases and records everything
grader/      the checks (conformance, backend, frontend) and the problem-speak lines
task/        the bundled backgammon challenge: starting files, spec chunks, reference build (never shown)
challenges/  a template for writing your own challenge
variants/    example variant kits (a memory system today)
control/     the control plane, the only process that writes
dashboard/   the board, read-only
images/      worker and grader containers
scripts/     entry points: run, rebuild, preflight
tools/       the class-matrix tool and example matrices, for auditing the grader
tests/       the instrument's own tests
docs/        how it's built, the problem-speak rules, operating it, variants
```

## Contributing

The best way in: clone it, run it, and audit the grader.

Everything rests on one promise: every line the agent is told is true for the build it was told about. When a line is wrong, the run is measuring the grader, not the harness. So the most useful work is checking that pipeline, from a check, to its finding, to the words the agent reads. [CONTRIBUTING.md](CONTRIBUTING.md) shows how, and [docs/problem-speak.md](docs/problem-speak.md) has the rules every line follows.

## License

MIT. See [LICENSE](LICENSE).
