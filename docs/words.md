# words

**Contract:** Wording exists once, keyed to findings.

## The rules a later step MUST satisfy

- Exist once, keyed to findings. A finding is a check together with its aspect; a line addresses that
  key, and the line is stored once, in one form.
- Be the only wording table in the repo. The sequencer, the modules, and the challenge package refer to
  it; none of them carries wording of its own.
- Look every told line up from the table by its finding key — never derived from a test title, never
  written twice.
- Split the player-facing subset and the software-team subset by the finding's telling boundary, out of
  the same table, never out of a second table.
- Make a change to a finding's words happen in one place: edit the one line and every reference to it
  changes with it.
- Follow the repo ground rules: no legacy, no compat shims, no stubs, nothing ported "as is to tidy
  later".

## The wording table MUST NOT

- Keep more than one copy of a line.
- Derive wording from test titles. That leaks the rule being measured.
- Let a module, a sequencer moment, or a challenge package embed its own text for a finding.
- Add a line with no finding to key it to, or a finding that resolves to no line.
- Edit wording to make a comparison pass. A wording change is a declared difference — a
  `declared_class` on the told line (see `proof.md`) — never a silent edit.
