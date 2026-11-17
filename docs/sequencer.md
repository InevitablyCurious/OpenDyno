# sequencer

**Contract:** The sequencer is separate and fixed per challenge — it pulls findings from the modules
and decides when each finding is told, one moment per round, in the order a player meets them — and
modules never decide timing while the sequencer never measures.

## The rules a later step MUST satisfy

- Be separate from the modules and fixed per challenge. One sequencer per challenge package, a part of
  that package, never shared across challenges.
- Be the only place that knows when a finding is told. Timing lives here and nowhere else.
- Pull findings from the modules (see `problem-matrix.md`). The sequencer reads what the modules
  produced and decides nothing about whether it is true.
- Tell one moment per round, in the fixed order for the challenge — the order a player meets them. The
  order is the player's order, and a challenge package supplies it; the order itself is fixed per
  challenge, never derived at run time.
- Respect the telling boundary it receives. The player is told only what a person can see; the
  software team's findings are told at the moment a player would meet them.
- Keep the boundary intact — what a person sees goes to the player, and everything else goes to the
  software team at its moment.
- Obey the repo ground rules: no legacy, no compat shims, no stubs, nothing ported "as is to tidy
  later".

## The sequencer MUST NOT

- Measure anything. No check, no assertion, no score, no verdict originates in the sequencer.
- Decide timing in a module or in the wording. Modules never decide timing; the sequencer never
  measures.
- Rearrange the order per finding, per module, or per run. The order is fixed per challenge.
- Invent findings. A finding exists only because a module produced it.
- Hold a second copy of the order anywhere else. A duplicated order is a broken order.
