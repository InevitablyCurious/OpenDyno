# core

The core is challenge-agnostic: it holds a set model on a set challenge, runs that challenge with the
layer under test off and then on, and measures the difference.

## The rules a later step must satisfy

- Hold the set model fixed and the set challenge fixed. The layer under test is the only thing that
  changes between the two runs.
- Run the same challenge twice: once with the layer under test off, once with it on.
- Measure the difference between those two runs. That difference is the result, and there is no other
  kind of result.
- Hold no challenge-specific knowledge. The core runs any challenge package the same way.
- Take the layer under test only through the one contract in `layer-under-test.md`.
- Provide the single shared measurement layer that the problem-matrix modules rest on, and hand its
  measurements over without deciding what a finding means.
- Read code as the answer when prose and code disagree, and surface the disagreement.
- Leave the comparison to proof, which compares OpenDyno's telling against the reference (see `proof.md`). The reference is Learning-Index at its current commit; its commit and inputs are recorded in reference-baseline/manifest.json.

## What the core MUST NOT do

- It MUST NOT depend on any one challenge, or name an example challenge in its logic.
- It MUST NOT know about stages, findings, or words. Those belong to the sequencer, the modules, and
  the words table.
- It MUST NOT special-case a kind of layer under test.
- It MUST NOT treat a compile, a green build, or an unproven assertion as a result.
- It MUST NOT become the home of a fault class, a check, or a sentence.
- It MUST NOT keep a second path for older behaviour, a compatibility shim, or a stub.
