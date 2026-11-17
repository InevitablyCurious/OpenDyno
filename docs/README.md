# OpenDyno contracts

These documents are the contracts for OpenDyno: each one states what a single part must do and must
not do.

## The seven contracts

- `core.md` — the challenge-agnostic part that runs a set model on a set challenge with the layer under test off and on, and measures the difference.
- `layer-under-test.md` — the one small contract that a harness, a memory system, an orchestration loop, a skill or a plugin plugs in through.
- `challenge-package.md` — everything one challenge carries: the spec, the scaffold and reference build, the problem-matrix modules, the sequencer, the words, and the saved-build set.
- `problem-matrix.md` — the grader's unit: one module per fault class, holding the measurement, the checks, the findings and the rows that prove it.
- `sequencer.md` — the fixed order that decides when each finding is told.
- `words.md` — the one wording table, keyed to findings.
- `proof.md` — the comparison that shows OpenDyno tells the same lines as the reference, except for declared differences.

## The dependency chain

`core.md` comes first. `challenge-package.md` rests on it. `problem-matrix.md` rests on the package.
`sequencer.md` and `words.md` follow the matrix together, and `proof.md` comes last, because it reads
what all of them produce and adds no authority of its own.

`layer-under-test.md` sits outside that chain: the core takes the layer through that one contract, so
the core depends on it and it depends on nothing else here.

The reference is Learning-Index at its current commit; its commit and inputs are recorded in reference-baseline/manifest.json.

Declared differences are recorded as data — a `declared_class` on each told line, summarised in `reference-baseline/manifest.json` — never in prose.

## How to read a contract

Each contract opens with one sentence that states its job. The rules a later step must satisfy follow,
in the present tense. A short list of what the part must not do ends it. Where prose and code
disagree, code is the answer and the disagreement is surfaced.
