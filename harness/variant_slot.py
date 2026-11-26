"""The variant slot's host-side settings: what a variant B cell is given.

A variant enters the benchmark as an opencode plugin baked into the
worker image (BENCH_PLUGIN_DIR). Everything else it needs at run time comes
from the operator's environment and reaches variant B cells only:

- BENCH_VARIANT_UPSTREAM: the variant's server, as the egress sidecar
  reaches it (scheme://host:port, e.g. http://host.docker.internal:8000). It
  opens the sidecar's variant route (harness/egress.py). Unset: no route — a
  variant that keeps its state in files needs none.
- BENCH_VARIANT_ENV: a file of the plugin's own settings, one NAME=value per
  line, passed into the worker by name. ``{variant_url}`` in a value becomes the
  address the cell reaches the server at, e.g. ``HONCHO_BASE_URL={variant_url}``.
  A relative path is read from the repository root.

The benchmark reads these settings; it never interprets them. Which names a
plugin needs is the variant's business.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ENV_VARIANT_UPSTREAM = "BENCH_VARIANT_UPSTREAM"
ENV_VARIANT_ENV = "BENCH_VARIANT_ENV"

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The placeholder a settings value may use for the server's in-cell address.
VARIANT_URL_PLACEHOLDER = "{variant_url}"

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Names that decide what the cell is and what it measures, not what the variant
#: does: the benchmark sets them itself, the docker CLI that starts the cell
#: reads them (the settings travel in its env), or they reroute or reshape the
#: worker's runtime. A variant's settings may not use them.
_RESERVED = re.compile(
    r"^(HOME|PATH|XDG_.*|OPENCODE_.*|BENCH_.*|LOCAL_LLM_PROXY_API_KEY"
    r"|ORCAROUTER_API_KEY|REQUIRE_TODOS|NODE_PATH|NODE_OPTIONS|PLAYWRIGHT_.*"
    r"|DOCKER_.*|(HTTP|HTTPS|ALL|NO)_PROXY)$",
    re.IGNORECASE,
)

#: Settings whose values are never recorded or printed.
_SECRET = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|AUTH", re.IGNORECASE)

#: Names whose shape marks them as carrying identity or secret material — a
#: keystore, seed, mnemonic, private key or corpus — rather than a setting a
#: plugin reads. The refusal is by shape, not by brand, so whatever a project
#: names its secrets: none of them may arrive as a variant setting. Bare KEY,
#: TOKEN and AUTH are left out on purpose: the forwarded proxy and model keys
#: are settings, and refusing them would forbid what a variant legitimately
#: needs.
_SECRET_NAME = re.compile(
    r"KEYSTORE|SEED|MNEMONIC|PASSPHRASE|PASSWORD|CORPUS|IDENTITY|PRIVATE_KEY"
    r"|CREDENTIAL|SECRET",
    re.IGNORECASE,
)


def variant_upstream(env: dict | None = None) -> str:
    """The variant server's origin as the sidecar reaches it, or "" for none."""
    return (
        (env if env is not None else os.environ).get(ENV_VARIANT_UPSTREAM, "").strip()
    )


def is_secret_name(name: str) -> bool:
    """Whether a name carries identity or secret material, not a setting."""
    return bool(_SECRET_NAME.search(name))


def parse_settings(text: str) -> dict[str, str]:
    """NAME=value lines; blank lines, ``#`` comments and ``export`` are allowed.

    Raises ValueError on a malformed line, a reserved name, or a name that
    carries identity or secret material, naming the line.
    """
    settings: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        name, sep, value = line.partition("=")
        name = name.strip()
        if not sep or not _NAME.match(name):
            raise ValueError(f"line {number}: expected NAME=value, got {raw!r}")
        if _RESERVED.match(name):
            raise ValueError(
                f"line {number}: {name} is reserved by the benchmark and cannot "
                "be a variant setting"
            )
        if is_secret_name(name):
            raise ValueError(
                f"line {number}: {name} carries identity/secret material and "
                "cannot be a variant setting"
            )
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        settings[name] = value
    return settings


def variant_settings(variant_url: str, env: dict | None = None) -> dict[str, str]:
    """The plugin's settings from the BENCH_VARIANT_ENV file, placeholder filled.

    Unset: no settings. Set to a file that is not there: an error, because a
    variant B cell run without the settings its operator wrote would quietly
    measure a differently configured variant.
    """
    raw = (env if env is not None else os.environ).get(ENV_VARIANT_ENV, "").strip()
    if not raw:
        return {}
    path = REPO_ROOT / Path(raw).expanduser()  # an absolute path stays itself
    if not path.is_file():
        raise FileNotFoundError(f"{ENV_VARIANT_ENV}={raw} is not a file")
    settings = parse_settings(path.read_text(encoding="utf-8"))
    if not variant_url and any(VARIANT_URL_PLACEHOLDER in v for v in settings.values()):
        raise ValueError(
            f"{raw} uses {VARIANT_URL_PLACEHOLDER}, but {ENV_VARIANT_UPSTREAM} is "
            "not set: there is no variant server for it to name"
        )
    return {
        name: value.replace(VARIANT_URL_PLACEHOLDER, variant_url)
        for name, value in settings.items()
    }


def redacted(settings: dict[str, str]) -> dict[str, str]:
    """The settings as they may be recorded: secret-looking values masked."""
    return {
        name: ("***" if _SECRET.search(name) or is_secret_name(name) else value)
        for name, value in sorted(settings.items())
    }
