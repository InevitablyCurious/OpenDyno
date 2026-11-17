# challenge package

A challenge package is everything one challenge carries: the spec (what the model is given), the
scaffold and reference build, the problem-matrix modules, the sequencer, the words, and the
saved-build set.

## The rules a later step must satisfy

- Carry all six parts: the spec, the scaffold and reference build, the problem-matrix modules, the
  sequencer, the words, and the saved-build set.
- State the spec in the package. It says what the model is given, and nothing about how the model is
  graded.
- Ship a scaffold and a reference build that a contributor rebuilds and runs before any layer is
  added.
- Supply the problem-matrix modules as the grader's unit (see `problem-matrix.md`).
- Supply the sequencer, fixed for this challenge (see `sequencer.md`).
- Supply the words once, keyed to findings (see `words.md`).
- Supply the saved-build set: the builds that the matrix rows and proof run against (see `proof.md`).
- Complete without touching the core. Anyone can write a package, and the core runs it unchanged.
- Keep the reference build and the reference apart: the reference build is this package's own build of
  the challenge, and the reference is the outside system that proof compares against.
- Prove the package against the reference in `proof.md`. The reference is Learning-Index at its current commit; its commit and inputs are recorded in reference-baseline/manifest.json.

## What a challenge package MUST NOT do

- It MUST NOT hold stage order or telling moments. Both live in the sequencer.
- It MUST NOT change how the core behaves, or teach the core that this package exists.
- It MUST NOT duplicate wording that the words table holds.
- It MUST NOT copy the reference as a template. The reference is compared against, never copied.
- It MUST NOT ship a part as a stub, a placeholder, or a copy of an older layout.
- It MUST NOT add a seventh part that the grader has to read.
