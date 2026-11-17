# OpenDyno reference proof — 2026-11-17

The one command, run from the repo root against the checked-in data:

```
python3 tools/prove.py
```

## (a) Captured stdout, verbatim

```text
== (a) DETERMINISM
hashes      112/112 outputs match manifest sha256
re-record   skipped (no --reference given; hash check only)
== (b) INTEGRITY / TRACEABILITY
told lines  1237/1237 name exactly one of finding_key/declared_class (0 violations)
citations   192 finding<->line agreements (0 violations)
builds      111/111 present, 111 inputs pinned, commit-pinned (0 violations)
counts      11/11 manifest counts recomputed and equal (0 violations)
index       29 pairs, occurrences/builds recomputed (0 violations)
== (c) NEGATIVE CONTROL
reference against reference  undeclared=0 declared=0 word=0 finding=0
one text perturbed (M38-controls-below told[5])  undeclared=1 word=1 finding=0
reverted, reference against reference  undeclared=0 word=0 finding=0
VERDICT: PASS
```

The reference against itself: 0 undeclared differences, and a single perturbed line is still
caught. The hashes cover all 112 checked-in outputs; every told line names exactly one of a
finding or a declared block; all 111 builds are present and pinned to one reference commit.

## (b) FAITHFULNESS — what the recorded telling does and does not preserve

Measured against the reference's prior recording, of the **266** sentences it told across the 72
testset builds, the current recording reproduces **23** verbatim, **47** in changed wording, and
**196** not at all.

The cause is threefold. The player's stage order changed, and the reference's standing rule is that
the player hears only the failing checks of the earliest stage that has any — so findings told
before are now withheld (across the 72 builds, 70 findings are told and 307 are not). Some wording
keys changed: 43 of the 47 changed lines are one sentence-table key whose wording now interpolates
the grader's own board measurements, 3 are rewritten keys that now open with the same interpolation
and state the brief's requirement instead of the tester's complaint, and 1 is a build reclassified
to a different sentence. Keys were added: the sentence table now holds 526 gate keys where the
prior table held 462.

That is the reference's actual behavior, not a recorder bug: the recorder calls Learning-Index's
own `player_view` / `_build_feedback_prompt` and classifies the lines they emit.

The faithful count is **23 reproduced verbatim / 47 rewritten-or-reclassified / 196 no-longer-told**.

## (c) Provenance

This data is produced by running Learning-Index's own code — the reference at the commit recorded in
`reference-baseline/manifest.json` — over the input reports, never a re-implementation.
