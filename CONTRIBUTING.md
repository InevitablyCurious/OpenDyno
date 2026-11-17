# Contributing to OpenDyno

OpenDyno is a dyno for the layers around a model. It measures one object under test against a
recorded reference, offline, from checked-in data. Contributions follow the same shape as the
measurement: state the fault, prove it first, then make the rule general.

## Setup

You need Python 3.11. That is the whole setup.

The tools are standard-library only. There are no runtime dependencies to install, no virtual
environment to activate, and no package step before you run anything. Run the tools from the repo
root.

## Running the proof

The proof runs offline from checked-in data. It needs no network and no service:

```
python3 tools/prove.py
```

It prints the three parts — determinism, integrity and traceability, and the negative control. The
negative control says the harness can still fail. A change is not done until this command still
reports the recorded telling reproduced exactly.

Two more commands are part of the same kit:

- `python3 tools/record_reference.py --reference <path> --testset <dir> --matrix <dir>` records the
  reference by running Learning-Index's own code. `<path>` names the Learning-Index tree; `<dir>` names
  its testset reports and matrix definitions. Nothing machine-specific is hardcoded — every path is an
  argument. Add `--out <dir>` to write to a temporary directory and leave the checked-in data
  untouched.
- `python3 tools/compare.py A.json B.json` compares two tellings on two axes — finding by finding, and
  word by word — and reports undeclared differences.

## The shape of a contribution

A contribution is one change that earns its place in this order:

1. **Name the fault class.** Say what kind of mistake the code can make. A fault class is a class,
   not a one-off bug report.
2. **Add the matrix rows that prove it first.** The rows come before the fix. A row that fails now
   and passes after the change is what shows the change did something.
3. **Write the shared rule.** One rule, in one place, that covers the whole fault class. Not a
   branch for this input and another for that one.
4. **Prove it on everything.** Run the proof against the full reference. The change holds only if
   the recorded telling is still reproduced exactly, with declared differences only.

Work in that order. A fix that lands before its rows has nothing measuring it.

## What will not be accepted

- A patch that special-cases one build. If a case is odd, say why in one general rule.
- A change that makes the code agree with the doc, or the doc agree with the code, without
  surfacing the disagreement. When prose and code disagree, the code is the answer and the
  disagreement gets reported. Quiet reconciliation hides a defect instead of fixing it.
- A fallback, a shim, or a compatibility path. There is one path. Pick the right one.

## Commits

Use conventional commits:

```
type(scope): description
```

For example `fix(sequencer): tell a finding once per line` or `docs(proof): state the negative
control`. Keep the subject in the imperative and in lower case. Say what changed and why in the
body when the subject cannot carry it.

## Tests and formatting

Run the tests and the format checks locally before you open a pull request:

```
python3 -m unittest discover -s tests
ruff format --check .
ruff check .
```

Continuous integration runs the same three commands, then the proof (`python3 tools/prove.py`). See
`.github/workflows/ci.yml`.

## Licence

OpenDyno is MIT licensed. See [LICENSE](LICENSE). By contributing, you agree that your contribution
is licensed under the same terms.
