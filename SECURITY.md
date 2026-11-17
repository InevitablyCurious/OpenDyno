# Security Policy

## What this project holds

OpenDyno holds no secrets and no user data. The repository is a measurement harness: tools that run
offline from checked-in data, and the data they read. There is no server, no account, no credential,
and no stored record about any person. That keeps the risk surface small.

## Reporting a vulnerability

Report privately. Do not open a public issue for a vulnerability, because a public issue tells
everyone before there is a fix.

Report through the maintainers' private channel. If no private channel is published for this
repository, say so plainly in your own assessment and treat the exposure as low: the project holds
no secrets and no user data, so the worst case is a wrong measurement or a wrong proof, not a
leaked credential. Open a public issue only for problems that carry no exploitable detail.

Please include:

- the file and the command that shows the problem;
- what you expected the proof to report, and what it reported instead;
- the smallest input that reproduces it.

Do not include a proof of concept that attacks a third-party system. A failing case in this
repository is enough.

## In scope

- The code in this repository, and the proof tooling in `tools/` — the proof command, the recorder,
  and the comparator.
- The recorded reference data and the declared differences, to the extent that a defect there makes
  the proof claim something untrue.
- A mistake that lets the harness report a pass it did not earn, or a fail it cannot justify.

## Out of scope

- The layers the harness measures — a harness, a memory system, an orchestration loop, a skill, or a
  plugin. Each is a separate project with its own policy.
- The environment you run the tools in: your Python installation, your shell, your machine.
- Anything requiring an account, a service, or a network path this project does not use. The tools
  run offline.
- Reports that amount to "the reference data disagrees with some other dataset". The reference is
  the thing being reproduced.

## What you can expect

We will confirm the report, say whether it is in scope, and tell you what we intend to do. Because
the project holds no secrets and no user data, there is no breach to contain and no notification
list to run.
