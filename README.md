# OpenDyno

A dyno for agent harnesses. You need an A/B test suite, but nothing meets the bar - until now. 

Bolt a harness on. Run it. Change one thing. Run it again. Same model, same task, same grader. The difference
between the two runs is what your change did.

## The idea

A harness is everything around the model: how context is kept or compacted, whether work goes to sub-agents,
the loop that plans and retries, the tools, the memory, the instructions, the way feedback comes back. Change any
of those and the agent gets better or worse at real work. OpenDyno measures by how much.

It does it with two things that never move between runs.

**A choreographed challenge.** The agent builds a real app, phase by phase, from a fixed spec. Each build is
graded by a fixed sequence of checks, run in the order a person meets the app: does it open, does the board look
right, do the pieces land, does a turn play, does the game end. The first thing wrong is the first thing said,
the way a player would hit it.

**Deterministic problem-speak.** Every failed check turns into the same plain report, word for word, every time
that fault shows up. It is told as a player's complaint ("I clicked my checker on the bar and no hints appeared")
or as an integration team's finding, with the number they measured ("hard won 3 of 25 games against easy's 20").
Never the grader's internals, never a guess.

Because the challenge and the words are fixed, a run is repeatable, and the only thing that changes between
variant A and variant B is the thing you changed.

## What you can put on the dyno

Anything that sits between the model and the work:

- Context: compaction on or off, when it fires, how it summarises, window size, prompt caching.
- Delegation: sub-agents against inline work, how much context they burn, manager and worker tiers.
- Loops: plan / act / check, retry and repair, self-critique, stop rules, loop guards.
- Memory: long-term memory, retrieval, notes files, skill libraries.
- The harness itself: tool sets and how they're described, hooks, permission modes, system prompts,
  instruction files, MCP servers.
- Feedback at inference time: what the agent is told after each attempt, in whose voice, how much detail.
- Spec style: one long brief against phased chunks.
- Models: swaps, sizes, quantisation, reasoning budget, local against cloud.
- Self-verification: agents that run their own tests or look at their own screen.
- Cost: tokens, cache hits and wall time per working build. Every run records all of it.

Variant B comes in as a plugin for the agent's harness. [docs/variants.md](docs/variants.md) shows how, with a
memory system as the worked example.

## How a run works

1. **Phases.** The agent builds the app in fixed phases: the engine, the server, the page in three layers (the
   board, the pieces, the gameplay), then wiring and a last check. Each phase gets its slice of the spec.
2. **Grading.** After every attempt the grader runs the whole suite against the agent's code, on a clean
   checkout, in a container.
3. **Conformance first.** The things every other check stands on go first: the app starts, the names and routes
   the spec fixes are there, and a position set through the debug route plays the same as one reached by play.
   If those fail, that is all the agent hears.
4. **One moment at a time.** Findings are staged by the moment a person meets them. The agent hears the earliest
   moment that still fails, fixes it, and moves on. A later fault waits its turn.
5. **The report.** The agent reads the problem-speak for that moment, plus the spec's own words when it keeps
   missing a rule, and gets another attempt. A phase passes when every check up to it passes.

Today's challenge is backgammon against a computer opponent: an engine, a server, a page, a doubling cube, an AI
with three difficulties. Big enough to need real work, small enough to finish, and nobody's novel invention, so
the agent is graded on building, not on guessing what we meant.

## Quick start

You need Docker, Python 3.11+, Node 22, and a model: local behind an OpenAI-compatible endpoint, or cloud.

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e '.[test]'
(cd grader && npm ci)
.venv/bin/python scripts/rebuild_worker_image.py
.venv/bin/python scripts/rebuild_grader_image.py
.venv/bin/python scripts/bench_preflight.py --model <alias>   # GO, or NO-GO with the fix
node control/server.mjs                                        # control plane, :8718
(cd dashboard && docker compose up -d)                         # the board, :8717
```

Open the board at http://127.0.0.1:8717.

- **Variant A:** `+ BASELINE` picks the model and the challenge and runs your harness as it is. Run it a few
  times. The spread between those runs is what chance alone does.
- **Variant B:** `+ run` on a baseline row runs the same thing with your change in. The board shows a difference
  once each side has three scored runs.
- **Results:** each run writes a folder under `runs/` with its fingerprint, its cost, the grader's report for
  every attempt, and a live record of every event.

More in [docs/operating.md](docs/operating.md).

## Contributing

The best way in: clone it, run it, and audit the grader.

Everything rests on one promise: every line the agent is told is true for the build it was told about. When a
line is wrong, the run is measuring the grader, not the harness. So the most useful work is checking that
pipeline, from a check, to its finding, to the words the agent reads. [CONTRIBUTING.md](CONTRIBUTING.md) shows
how, and [docs/problem-speak.md](docs/problem-speak.md) has the rules every line follows.

## Layout

```
harness/     runs the agent through the phases and records everything
grader/      the checks (conformance, backend, frontend) and the problem-speak lines
task/        the backgammon challenge: starting files, spec chunks, reference build (never shown)
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

## License

MIT. See [LICENSE](LICENSE).
