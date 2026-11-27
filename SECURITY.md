# Security Policy

OpenDyno is under active development. It runs code a model wrote, on your machine: every cell lives in its own
containers, on a network whose only way out is its sidecar, and a build you play from the board runs in the
grader image with no internet and no host access. A way through any of that is the kind of report we most want.

## Reporting a vulnerability

**Do not open a public issue for a security vulnerability.**

Report it privately through GitHub:

**<https://github.com/InevitablyCurious/OpenDyno/security/advisories/new>**

That opens a private advisory visible only to you and the maintainers. It needs
no email address and no prior contact.

Please include what you have — a partial report is better than none:

- What the vulnerability is
- How to reproduce it
- Which component or file is affected
- A suggested mitigation, if you have one

**What to expect.** This is a small, actively developed project with a very
small maintainer group, so we are not going to promise a response time we
cannot honour. You will get an acknowledgement, and if the report is valid you
will be credited in the advisory unless you would rather not be. If you have
heard nothing after two weeks, please comment on the advisory — that is a lapse
on our side, not a judgement on your report.

## Supported versions

Only the latest commit on `main` receives security updates. There are no
released versions to backport to yet.

## Scope

In scope:

- Anything in this repository
- A cell, or a build played from the board, reaching the host, the network, another cell or a secret it should not
  see
- Model keys or router credentials leaking into a cell, a log or the board

Out of scope:

- Vulnerabilities in third-party dependencies — please report those upstream,
  though we do want to hear if we are using a dependency unsafely
- Denial of service achievable by a single client against a local development
  stack
- Issues that require physical access to a machine already running the software
- Findings that depend on the documented development defaults (the local
  `docker compose` stack ships deliberately weak credentials and is bound to
  loopback by default; LAN exposure is opt-in, per the board README's
  "Viewing from another machine" paragraph). The dashboard's play preview and the hold-review
  OPEN — which boot an untrusted model build — run it inside the grader image
  since 2026-10-23 (`harness/play_container.py`): an `--internal` network (no
  internet, no host), no host environment, files or Docker socket, a read-only
  worktree, and only a `127.0.0.1` port published by a forwarder.
