# problem matrix

Problem-matrix modules are the unit of the grader: each module is the home of one fault class, with
its measurement, its checks, its findings, and the matrix rows that prove it, and a finding is data —
a check and its aspect as a field — never text inside an assertion.

## The rules a later step must satisfy

- Make the module the grader's unit: one module, one fault class, complete in itself.
- Give each module four parts: the measurement it rests on, the checks that use that measurement, its
  findings, and the matrix rows that prove it.
- Keep a finding a record with a check and an aspect as fields. A check says which rule broke; an
  aspect names the part of the fault the finding speaks to. Code reads the record, and never parses
  prose.
- Carry the telling boundary in the finding: the player is told only what a person sees, and
  everything else is stripped from the player and told by the software team.
- Rest every module on the one shared measurement layer, so a measurement is defined once and
  measured before it is applied.
- Prove each module with rows of three kinds: a fault on either side of its limit, a correct build
  told nothing, and a combination where the bigger picture wins.
- Fix a fault this way and no other: the fault class, its rows first, then the shared rule, then the
  proof across everything.
- Feed the matrix rows to proof (see `proof.md`). The reference is Learning-Index at its current commit; its commit and inputs are recorded in reference-baseline/manifest.json.

## What a problem-matrix module MUST NOT do

- It MUST NOT state a finding as prose inside an assertion.
- It MUST NOT decide when a finding is told. Timing belongs to the sequencer.
- It MUST NOT carry an aspect that no code reads.
- It MUST NOT measure in a private way. The shared measurement layer is the only place a measurement
  is defined.
- It MUST NOT treat a passing row as proof of a fault class with no failing row beside it.
- It MUST NOT hold two fault classes. That is two modules.
