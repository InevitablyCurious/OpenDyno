# AGENTS.md — OpenDyno

Ground rules for anyone, person or agent, changing this repository. Read it before you write.

## Shape

A challenge is a package. Modules are by problem matrix, one fault class each. The sequencer is separate and fixed:
it decides when a finding is told, and never measures. A finding is data — a check and its aspect as fields — never
text inside an assertion. Wording exists once, keyed to a finding.

## Who speaks

The player says only what a person in front of the screen can see and do, at the moment they meet it. Everything
else — the code underneath, the names other software relies on, exact measurements — is the software team's, told at
that same moment.

## No fallbacks, no shims, no stubs

No compatibility shims, no stubs, no dead patterns, nothing ported "as is" to be tidied later. If it is not right in
the shape it must live in, it does not enter.

## No re-implementations of the reference

The reference's behaviour is recorded by running the reference's own code, never by rewriting its logic here. The
reference (Learning-Index) is read-only: record it, prove against it.

## Fixes follow the fix system

A fault class, its matrix rows first (the fault either side of its limit, correct builds that must be told nothing,
combinations where the bigger picture wins), then the one shared rule, then prove it on everything. Never a patch for
the single case that showed it. Matrix rows are never deleted or loosened to get green.

## Claims of a negative need evidence

"Unchanged", "no differences", "under the limit", "not present" are assertions, not observations. Each needs a
`file:line` or a command's output. A text match is not evidence.

## Code beats prose

When prose and code disagree, the code is the answer, and the disagreement is surfaced — not quietly resolved by
editing one to match the other.

## Docs say what is true now

No history of how a decision was made: no reviewer names, no superseded proposals. Docs say what is true today and
how to use it. History lives in git and the changelog.

## Declared differences are data

Any accepted difference from the reference is recorded in the baseline data with the matrix rows that prove it.
A silent difference is a defect.

## One proof command

    python3 tools/prove.py

If it does not pass, nothing else counts.
