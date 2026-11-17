# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com).

## [1.0.0] — in progress

### Added

- **The front door.** `README.md` states what the system is, what enters the harness as the object
  under test, and how the choreography is fixed.
- **The seven contract documents.** `docs/` holds one contract per part of the system: the core, the
  layer under test, the challenge package, the problem matrix, the sequencer, the words, and the
  proof. Each states what a later step must satisfy and must not violate.
- **The recorded reference baseline.** `reference-baseline/` holds the reference's telling as data:
  one build file per case, the wording index, and the manifest with the commit, the inputs and the
  hashes.
- **The comparator.** `python3 tools/compare.py` diffs two tellings on two axes — finding by finding,
  and word by word — and reports undeclared differences.
- **The proof command.** `python3 tools/prove.py` runs offline from checked-in data and proves
  determinism, traceability, and the negative control.
- **The recorder.** `python3 tools/record_reference.py --reference <path> --testset <dir> --matrix
  <dir>` records the reference by running Learning-Index's own code, so no machine-specific path is
  hardcoded.
- **Tests.** `python3 -m unittest discover -s tests` exercises the comparator and the proof's
  traceability rule.
- **Format and lint.** `ruff format --check .` and `ruff check .`, configured in `pyproject.toml`.
- **Continuous integration.** `.github/workflows/ci.yml` runs the format check, the lint, the tests,
  and the proof.
