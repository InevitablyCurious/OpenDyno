# Contributing

OpenDyno is only as good as its grader. A harness change can't be measured against a grader that tells the agent
something untrue, so the most valuable contribution is finding where it does, and closing it for good.

## Get it running

Follow the quick start in the [README](README.md). Run a baseline with your own model. Then run the tests:

```bash
.venv/bin/python -m pytest -m "not slow" -q
.venv/bin/ruff format --check .
(cd control && node --test) && (cd dashboard && node --test)
```

They test the instrument, never the agent: the staging, the voices, the line guards, the control plane, the board.

## Audit the grader → problem-speak pipeline

Every attempt the agent makes is graded, and what it is told comes out of three steps: a check fails, the failure
becomes a finding, the finding becomes a line. A wrong line can come from any of the three.

1. **Run the benchmark in dev mode.** The run pauses after every grade. The board's hold view shows exactly what
   the agent is about to be told and lets you play the exact build that was graded.
2. **Check every line against the build.** Play it. Read the code. Ask: is this true of *this* build? Does it say
   what to fix? Would a person playing see it?
3. **When a line is false or vague, name its class, not just the line.** Most bad lines belong to a pattern that
   shows up across many checks: a check that measures the page's markup instead of what's drawn, a step that
   falls to a general line that describes a different fault, a position loaded instead of played, a number read
   before the page settled. Fixing one instance leaves the class alive somewhere else.
4. **Prove the fix on a class matrix.** Plant every way the class can go wrong into copies of the reference
   build, and show the reference stays silent while every plant is told once, at the right moment, in true words:

   ```bash
   .venv/bin/python tools/class_matrix.py tools/matrices/traysplit.py --jobs 2
   ```

   The files in [tools/matrices/](tools/matrices/) are worked examples. A matrix row is a planted variation and
   what a true telling must be.
5. **Check what else it touches.** Re-grade your saved builds (every attempt leaves its code under
   `runs/…/checkpoints/`) with the new grader and read every line that changed.

[docs/problem-speak.md](docs/problem-speak.md) has the rules a line must follow, and the guards in `tests/` hold
most of them.

## Other ways in

- **Put a harness on the dyno** and share the result: what changed, the fingerprints, the runs.
  [docs/variants.md](docs/variants.md).
- **Write a new challenge.** Start from [challenges/TEMPLATE](challenges/TEMPLATE/README.md). A good challenge
  is something capable developers know how to build, big enough to need real work, and checkable without
  judgement.

## Pull requests

- One problem per pull request, with the class named and the matrix that proves it.
- Tests and formatting green.
- A new player line is written the way a player would say it: what they saw, never the rule or the fix.
