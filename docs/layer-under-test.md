# layer under test

The layer under test is any one harness, memory system, orchestration loop, skill or plugin, and each
one plugs in through the same small documented contract.

## The rules a later step must satisfy

- Admit any one harness, memory system, orchestration loop, skill or plugin, and no second kind of
  input.
- Use one contract for all of them: the same entry points, the same inputs, the same outputs.
- Turn the layer off and on through that contract, and change nothing else about the run.
- Document the contract in one place, so a contributor builds a layer without reading the core.
- Pass the layer only what the contract gives it. It stays blind to the challenge it runs on.
- Keep the contract small enough to read in one sitting. A layer that needs a second contract is not
  one layer yet.
- Expect the result to be judged by proof, which compares OpenDyno's telling against the reference (see `proof.md`). The reference is Learning-Index at its current commit; its commit and inputs are recorded in reference-baseline/manifest.json.

## What the layer under test MUST NOT do

- It MUST NOT special-case a kind of system. No per-kind branch, no type-specific path.
- It MUST NOT widen the contract for one kind. A second contract is a broken contract.
- It MUST NOT score anything, decide timing, or hold wording. Measurement belongs to the core, timing
  to the sequencer, wording to the words table.
- It MUST NOT read the challenge, the problem matrix, or the words table.
- It MUST NOT carry a loader, a compatibility shim, or a fallback path for older layers.
