# OpenDyno

## What this is

OpenDyno is a dyno for the layers around a model. A dyno holds the engine still and measures one part at a time; OpenDyno does the same for the software that surrounds a model. It holds a set model and a set challenge still, swaps in the layer under test, and measures what that layer changes.

The layer under test is one thing: a harness, a memory system, an orchestration loop, a skill, or a plugin. The model and the challenge do not move while it is tested, so a difference in the result belongs to the layer and to nothing else.

Anyone can contribute a layer, or design a challenge for one. Both are the same kind of work: say plainly what the thing is, write down what it takes in and what it gives back, and let the dyno measure it. The aim is a bench that is easy to customise, easy to understand, and just works.

The first challenge is a browser backgammon game the model builds from a written brief, graded as a player would play it. OpenDyno grows out of [Learning-Index](https://github.com/InevitablyCurious/learning-index), whose grader it is replacing class by class.

## Why it exists

Testing a layer around a model is usually ad hoc. Someone writes a few prompts, reads the output, and forms an opinion. The grade and the words handed back to the model get tangled together, so nobody can say which part of the result came from which part of the test. A result like that is hard to trust, and harder to repeat.

OpenDyno keeps both halves of the experiment fixed — the model and the challenge — and changes one thing at a time. The layer is run off, then run on, and the difference between the two runs is what gets measured. When only one thing moved, a difference means something.

## How the grader speaks

The model never sees a test. After each grade it hears what went wrong from two voices, the way a real project hears it:

- **The player** says only what a person in front of the screen can see and do — what looks wrong, what doesn't respond, where.
- **The software team** reports what a person can't see: what the code underneath answers, the names their own software relies on, and exact measurements, quoted with the number the grader read.

A build is played through the challenge in a fixed order: the order a player would meet it, moment by moment, from the start. Both voices speak about the first moment that breaks.

Everything else is withheld until its moment comes. A finding that belongs to a later moment is not mentioned early and is not dumped at the end; it is said where the player would actually run into it. So the telling stays in the player's order, and each thing is said once, in the place it belongs.

## What works today

What exists today is small, and this section says exactly that.

The reference's telling is recorded as data. For every build in the reference set, the message the player was given — each line, and the finding that line reports — is checked in, so a telling can be read and compared without running anything. Those lines are the reference's, not ours: the recording is produced by running Learning-Index's own code at the reference commit — never re-implemented — and its commit, inputs and per-file hashes are recorded in `reference-baseline/manifest.json`.

A comparator diffs two tellings on two separate questions, and keeps them apart so neither can hide the other: finding by finding, which findings each side reports, and word by word, what each line actually says. A wording change cannot pass for a missing finding, and a missing finding cannot pass for a rewording.

One proof command checks the recorded baseline against itself and then checks that it can still fail: `python3 tools/prove.py`. It runs offline from the checked-in data, with nothing to install.

## What is coming

None of this is built yet. It is the shape the work is heading in.

The core, which runs a build with the layer off and with it on, and measures the difference between the two runs.

A challenge package that anyone can contribute or design: what the model is given, a reference build to test against, and the saved builds it is measured on.

The problem-matrix modules, where each module is the home of one fault class and the only place that measures it.

The sequencer, kept separate from the modules: it decides when each finding is told, in the player's fixed order, and never measures anything itself.

The checks themselves, ported one class at a time — each one proven against the reference before the next one is started, so the port never runs ahead of its proof.

## How to contribute

A contribution has the same shape every time. Start with one fault class: a single way a layer can be wrong, stated plainly enough that someone else could look for it. Write the cases that prove it — builds where that fault is present, and builds where it is absent, so the rule has something to be tested against. From those cases, state the shared rule the grader applies, in one place, once. Then prove it on everything: the rule has to hold across the whole reference set, not just the cases it was written from.

The full process is in CONTRIBUTING.md.

## How to run it

Prove the recorded baseline — this runs offline from the checked-in data and needs nothing installed:

```
python3 tools/prove.py
```

Re-record the baseline by running the reference's own code — this needs the Learning-Index tree and its testset and matrix inputs:

```
python3 tools/record_reference.py --reference <path> --testset <dir> --matrix <dir>
```

`--reference` names the Learning-Index tree; `--testset` names the directory of `<case>/report.json` inputs; `--matrix` names the directory holding the matrix definitions and their reports. Add `--out <dir>` to write to a temporary directory and leave the checked-in data untouched. `reference-baseline/manifest.json` records the commit and the input hashes the baseline was recorded from.
