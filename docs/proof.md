# proof

**Contract:** The proof is differential against the reference — word for word, except declared
differences — and it is a command, not a claim.

The reference is Learning-Index at its current commit; its commit and inputs are recorded in
`reference-baseline/manifest.json`.

## The rules a later step MUST satisfy

The proof has three parts, and all three run.

- **(a) Determinism — every checked-in file matches its recorded hash, and the recording reproduces
  byte-identical.** Each file the manifest lists is re-hashed and must equal the sha256 the manifest
  records for it. With `--reference` given, the recorder is re-run into a fresh temporary directory
  and the result must match the checked-in data byte for byte — the record is a pure function of the
  reference and its inputs, not a leftover artifact.
- **(b) Integrity and traceability — every told line names exactly one thing, and the counts
  reconcile.** Each told line names exactly one of a finding or a declared class. Every told finding
  is cited by a line and every citing line maps back to a told finding; no build is missing; every
  build is pinned to the manifest's commit and to a listed input; and every count in the manifest and
  every occurrence in the index is recomputed from the build files and must agree.
- **(c) Negative control — the proof can still fail.** The recording compared against itself shows
  zero undeclared differences. Perturb one finding line's text, leaving its identity untouched, and
  the comparison shows exactly one undeclared word-difference and no finding-differences; revert it
  and zero returns.

Beyond those three parts:

- Compare the telling against the reference word for word, except for declared differences. A
  divergence that is not declared is a failure.
- Keep declared differences in data — the `declared_class` on each told line, summarised in
  `reference-baseline/manifest.json` — never in prose. This document does not restate them.
- Prove by running the command `python3 tools/prove.py` from the repo root, offline, with no
  arguments. Its exit status is the verdict.
- Run on every proof build. A build outside the challenge's proof set is not proof.
- Cite the reference where it is the thing being replaced: cite it, never copy it as a template.
- Obey the repo ground rules: no legacy, no compat shims, no stubs, nothing ported "as is to tidy
  later".

## The proof MUST NOT

- Merge OpenDyno's telling with the reference silently. Every divergence is declared, or it is a
  failure.
- Count a declared difference as a failure.
- Declare a difference with no recorded class behind it, or list the declared classes in prose.
- Widen the reference to whatever currently passes.
- Restate the counts in this document. Counts live in `reference-baseline/manifest.json` and
  `reference-baseline/PROOF.md`; here the rule is stated, not the figures.
- Report a pass it did not run. The command runs, and its exit status is the proof.
