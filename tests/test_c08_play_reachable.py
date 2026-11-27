"""C08 guard -- pure-read scanner for debug-route position seeding.

Class rule C08: a told check may write only a LEGAL START OF TURN through
``/api/debug/state`` -- phase "roll"/"openingRoll", no dice, no remainingDice,
no turnOver, default cube -- unless the site is listed with a reason it is
reachable by play (or is not judging a position).

This module is import-safe: only functions and immutable module constants are
defined at module level.  It reads the graded spec files and reports the write
sites whose payload contains a field a start of turn cannot carry.

Seeding mechanisms detected: ``setupState`` / ``postDebugState`` /
``debugSetState`` calls, raw ``/api/debug/state`` posts, and ``seedRolled`` (a
helper that seeds a position at the player's roll phase -- turn "white", phase
"roll", empty dice -- and lets the build's own ``/api/roll`` deal the dice).

Builder bases are hardcoded from
  grader/lib/harness.ts:621-651            (makeState)
  grader/frontend/edges.spec.ts:10-41      (fullState)
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

MAKE_STATE_BASE = {
    "turn": "white",
    "phase": "move",
    "dice": [],
    "remainingDice": [],
    "cube": {"value": 1, "owner": None},
    "difficulty": "medium",
    "score": {"white": 0, "black": 0},
    "winner": None,
    "winType": None,
    "pointsWon": 0,
    "doubleOfferedBy": None,
    "message": "",
    "turnOver": False,
}

# fullState has NO turnOver key.
FULL_STATE_BASE = {k: v for k, v in MAKE_STATE_BASE.items() if k != "turnOver"}

# (rel_file, gate_token) -> reason the non-position / play-reachable write stands.
ALLOWLIST = {
    ("backend/server-path-integrity.test.ts", "G39"): (
        "parked cube: the cube sits at 2 in the player's hands (reachable by play) "
        "so the computer cannot double during the judged turn; the write seeds no "
        "dice/remainingDice/turnOver"
    ),
    ("backend/server-path-integrity.test.ts", "G30"): (
        "parked cube: the cube sits at 2 in the player's hands (reachable by play) "
        "so the computer cannot double during the judged turn; the write seeds no "
        "dice/remainingDice/turnOver"
    ),
    ("backend/server-path-integrity.test.ts", "G28"): (
        "route-acceptance echo of turnOver/gamesPlayed; the check verifies the "
        "route honours them and judges no position"
    ),
    ("frontend/core.spec.ts", "F17"): (
        "route-acceptance scalar read-back of the score; no position judged"
    ),
    ("frontend/edges.spec.ts", "F12"): (
        "terminal announcement write (phase gameover + winner); judged only as "
        "the win message, not as a played position"
    ),
    ("frontend/edges.spec.ts", "F22"): (
        "seeded terminal state is scaffolding; every assertion is about the "
        "post-/api/new reset"
    ),
    ("frontend/edges.spec.ts", "F23"): (
        "judges navigation, not state; reads no seeded field"
    ),
}

_SKIP_HELPER_WRITES = frozenset({"setupState", "postDebugState", "debugSetState"})

_GATE_RE = re.compile(r"\[([A-Z]+[0-9]*)\]")
_WRITE_RE = re.compile(r"(?<![\w$.])(setupState|postDebugState|debugSetState|seedRolled)\s*\(")
_API_RE = re.compile(r"(?<![\w$.])api\s*\(\s*(['\"`])/api/debug/state\1")
_FUNC_RE = re.compile(
    r"(?m)^[ \t]*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("
)
_ARROW_RE = re.compile(
    r"(?m)^[ \t]*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s+)?\("
)
_TEST_RE = re.compile(r"(?m)^[ \t]*(?:test|it)\s*\(")

_PAIRS = {"(": ")", "[": "]", "{": "}"}
_UNKNOWN = object()


# ---------------------------------------------------------------------------
# Small JS-aware text helpers
# ---------------------------------------------------------------------------

def _skip_string(text, i):
    """Return the index just past the string starting at text[i]."""
    quote = text[i]
    i += 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == quote:
            return i + 1
        i += 1
    return n


def _match(text, i):
    """Index of the delimiter closing the one at text[i], or -1."""
    opener = text[i]
    closer = _PAIRS[opener]
    depth = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            i = _skip_string(text, i)
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top(text, start, end, sep=","):
    """Split text[start:end] on sep at bracket depth zero."""
    parts = []
    depth = 0
    last = start
    i = start
    while i < end:
        c = text[i]
        if c in "\"'`":
            i = _skip_string(text, i)
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(text[last:i])
            last = i + 1
        i += 1
    parts.append(text[last:end])
    return parts


def _strip_comments(text):
    """Blank // and /* */ comments, preserving every newline and offset."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            j = _skip_string(text, i)
            out.append(text[i:j])
            i = j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            if j == -1:
                j = n
            out.append(" " * (j - i))
            i = j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:j]))
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _split_args(text, open_idx):
    close = _match(text, open_idx)
    if close == -1:
        return [], -1
    parts = [p.strip() for p in _split_top(text, open_idx + 1, close, ",")]
    if len(parts) == 1 and parts[0] == "":
        parts = []
    return parts, close


def _line_of(text, offset):
    return text.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# Value / object parsing
# ---------------------------------------------------------------------------

def _parse_string(v):
    if len(v) < 2 or v[0] not in "\"'":
        return _UNKNOWN
    q = v[0]
    if v[-1] != q:
        return _UNKNOWN
    body = v[1:-1]
    mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "\"": "\"", "'": "'", "`": "`"}
    out = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n:
            nxt = body[i + 1]
            out.append(mapping.get(nxt, "\\" + nxt))
            i += 2
        elif c == q:
            return _UNKNOWN
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _top_level_colon(s):
    depth = 0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in "\"'`":
            i = _skip_string(s, i)
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ":" and depth == 0:
            return i
        i += 1
    return -1


def _parse_literal_object(text):
    t = text.strip()
    if not t.startswith("{"):
        return {}
    close = _match(t, 0)
    if close == -1:
        return {}
    inner = t[1:close]
    out = {}
    for entry in _split_top(inner, 0, len(inner), ","):
        e = entry.strip()
        if not e or e.startswith("..."):
            continue
        idx = _top_level_colon(e)
        if idx == -1:
            continue
        key = e[:idx].strip()
        val = e[idx + 1:].strip()
        if key.startswith("...") or key.startswith("["):
            continue
        if len(key) >= 2 and key[0] in "\"'" and key[-1] == key[0]:
            key = _parse_string(key)
            if key is _UNKNOWN:
                continue
        if not re.match(r"^[A-Za-z_$][\w$]*$", key):
            continue
        parsed = _parse_value(val)
        if parsed is _UNKNOWN:
            continue
        out[key] = parsed
    return out


def _parse_value(v):
    v = v.strip()
    if not v:
        return _UNKNOWN
    if v[0] in "\"'":
        return _parse_string(v)
    if v[0] == "`":
        return _UNKNOWN
    if v in ("true", "false"):
        return v == "true"
    if v == "null":
        return None
    if re.match(r"^-?\d+$", v):
        return int(v)
    if re.match(r"^-?\d+\.\d+$", v):
        return float(v)
    if v[0] == "[":
        close = _match(v, 0)
        if close == -1:
            return _UNKNOWN
        arr = []
        for part in _split_top(v, 1, close, ","):
            p = part.strip()
            if p == "":
                continue
            parsed = _parse_value(p)
            if parsed is _UNKNOWN:
                return _UNKNOWN
            arr.append(parsed)
        return arr
    if v[0] == "{":
        close = _match(v, 0)
        if close == -1 or v[close + 1:].strip():
            return _UNKNOWN
        return _parse_literal_object(v)
    return _UNKNOWN


def _resolve_payload(kind, arg_text):
    """Resolve a write's payload through its builder base plus literal overrides.

    ``kind`` is one of setup / post / debug / api.  Complex values (IIFEs,
    bare identifiers, spreads) are dropped rather than flagged.
    """
    base = {}
    if kind == "post":
        base = FULL_STATE_BASE
    literal_text = arg_text
    m = re.match(r"\s*(makeState|fullState)\s*\(", arg_text)
    if m:
        builder = m.group(1)
        open_idx = arg_text.index("(", m.start())
        args, _ = _split_args(arg_text, open_idx)
        if args:
            literal_text = args[0]
        base = MAKE_STATE_BASE if builder == "makeState" else FULL_STATE_BASE
    literal = _parse_literal_object(literal_text)
    payload = dict(base)
    for key, value in literal.items():
        if (
            key in ("cube", "score", "bar", "off")
            and isinstance(payload.get(key), dict)
            and isinstance(value, dict)
        ):
            merged = dict(payload[key])
            merged.update(value)
            payload[key] = merged
        else:
            payload[key] = value
    if kind == "seedRolled":
        # seedRolled forces a legal start of turn and lets the build's own roll
        # deal the dice (grader/lib/harness.ts seedRolled, grader/frontend/fixtures.ts seedRolled).
        payload["turn"] = "white"
        payload["phase"] = "roll"
        payload["dice"] = []
        payload["remainingDice"] = []
    return payload


# ---------------------------------------------------------------------------
# Decision rule
# ---------------------------------------------------------------------------

def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    try:
        return json.dumps(v, separators=(",", ":"), sort_keys=True)
    except TypeError:
        return str(v)


def decide(payload):
    """Return the forbidden-field strings; empty means a legal start of turn."""
    forbidden = []
    if "phase" in payload:
        phase = payload["phase"]
        if phase is not None and phase not in ("roll", "openingRoll"):
            forbidden.append("phase=" + _fmt(phase))
    if "dice" in payload:
        dice = payload["dice"]
        if isinstance(dice, list) and dice:
            forbidden.append("dice=" + _fmt(dice))
    if "remainingDice" in payload:
        dice = payload["remainingDice"]
        if isinstance(dice, list) and dice:
            forbidden.append("remainingDice=" + _fmt(dice))
    if payload.get("turnOver") is True:
        forbidden.append("turnOver=true")
    if "cube" in payload:
        cube = payload["cube"]
        if not isinstance(cube, dict) or cube.get("value") != 1 or cube.get("owner") is not None:
            forbidden.append("cube=" + _fmt(cube))
    if payload.get("winner") is not None:
        forbidden.append("winner=" + _fmt(payload["winner"]))
    if payload.get("winType") is not None:
        forbidden.append("winType=" + _fmt(payload["winType"]))
    points_won = payload.get("pointsWon")
    if points_won is not None and points_won != 0:
        forbidden.append("pointsWon=" + _fmt(points_won))
    if payload.get("doubleOfferedBy") is not None:
        forbidden.append("doubleOfferedBy=" + _fmt(payload["doubleOfferedBy"]))
    games_played = payload.get("gamesPlayed")
    if games_played is not None:
        forbidden.append("gamesPlayed=" + _fmt(games_played))
    if "score" in payload:
        score = payload["score"]
        if not isinstance(score, dict) or score.get("white", 0) != 0 or score.get("black", 0) != 0:
            forbidden.append("score=" + _fmt(score))
    return forbidden


# ---------------------------------------------------------------------------
# Span discovery
# ---------------------------------------------------------------------------

def _find_function_body(text, close_paren):
    i = close_paren + 1
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i < n and text[i] == "{":
        return i
    if i < n and text[i] == ":":
        depth = 0
        i += 1
        while i < n:
            c = text[i]
            if c in "\"'`":
                i = _skip_string(text, i)
                continue
            if c in "([<":
                depth += 1
            elif c in ")]":
                depth -= 1
            elif c == ">":
                if depth > 0:
                    depth -= 1
            elif c == "{":
                if depth == 0:
                    return i
                depth += 1
            elif c == "}":
                if depth > 0:
                    depth -= 1
            elif c == ";" and depth == 0:
                return -1
            i += 1
    return -1


def _find_helpers(text):
    """Return (name, decl_start, body_open, body_close) for each helper."""
    helpers = []
    for m in _FUNC_RE.finditer(text):
        name = m.group(1)
        open_idx = m.end() - 1
        close = _match(text, open_idx)
        if close == -1:
            continue
        body = _find_function_body(text, close)
        if body == -1:
            continue
        body_close = _match(text, body)
        if body_close == -1:
            continue
        helpers.append((name, m.start(), body, body_close))
    for m in _ARROW_RE.finditer(text):
        name = m.group(1)
        open_idx = m.end() - 1
        close = _match(text, open_idx)
        if close == -1:
            continue
        arrow = text.find("=>", close)
        if arrow == -1:
            continue
        j = arrow + 2
        while j < len(text) and text[j].isspace():
            j += 1
        if j >= len(text) or text[j] != "{":
            continue
        body_close = _match(text, j)
        if body_close == -1:
            continue
        helpers.append((name, m.start(), j, body_close))
    return helpers


def _find_tests(text):
    """Return (call_start, call_end, gate_token) for each test/it call."""
    tests = []
    for m in _TEST_RE.finditer(text):
        open_idx = m.end() - 1
        close = _match(text, open_idx)
        if close == -1:
            continue
        i = open_idx + 1
        while i < close and text[i].isspace():
            i += 1
        if i >= close or text[i] not in "\"'`":
            continue
        j = _skip_string(text, i)
        title = text[i + 1:j - 1]
        gate = _GATE_RE.search(title)
        if not gate:
            continue
        tests.append((open_idx, close, gate.group(1)))
    return tests


def _find_writes(text):
    """Return (kind, offset, payload_arg_text) for every debug-state write call."""
    writes = []
    for m in _WRITE_RE.finditer(text):
        name = m.group(1)
        open_idx = text.index("(", m.start())
        args, _ = _split_args(text, open_idx)
        if name == "setupState":
            if len(args) >= 2:
                writes.append(("setup", m.start(), args[1]))
        elif name == "postDebugState":
            if len(args) >= 2:
                writes.append(("post", m.start(), args[1]))
        elif name == "seedRolled":
            # Backend seedRolled(makeState({...}), dice) passes the payload as
            # args[0]; frontend seedRolled(page, body, dice) as args[1].
            if args and re.match(r"(makeState|fullState)\s*\(", args[0]):
                writes.append(("seedRolled", m.start(), args[0]))
            elif len(args) >= 3:
                writes.append(("seedRolled", m.start(), args[1]))
        else:
            if len(args) >= 1:
                writes.append(("debug", m.start(), args[0]))
    for m in _API_RE.finditer(text):
        open_idx = text.index("(", m.start())
        args, _ = _split_args(text, open_idx)
        if len(args) >= 2:
            writes.append(("api", m.start(), args[1]))
    return writes


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

def _closure(start, calls):
    seen = set()
    stack = list(start)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack.extend(calls.get(name, ()))
    return seen


def _name_called(pattern_name, haystack):
    return re.search(r"(?<![\w$.])" + re.escape(pattern_name) + r"\s*\(", haystack) is not None


def _attribute(rel, offset, text, tests, helpers, calls, test_helpers):
    for start, end, gate in tests:
        if start <= offset <= end:
            return {gate}
    enclosing = [h for h in helpers if h[1] <= offset <= h[3]]
    if not enclosing:
        return set()
    name, _decl, _body, body_close = min(enclosing, key=lambda h: h[3] - h[1])
    tokens = set()
    for (start, end, gate), direct in test_helpers.items():
        if name in _closure(direct, calls):
            tokens.add(gate)
    return tokens


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def _repo_root():
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "grader").is_dir():
            return candidate
    raise RuntimeError("could not locate the repository root (a directory holding grader/)")


def find_findings(allowlist=None):
    """Return the forbidden debug-state write sites (allowlisted ones removed)."""
    allow = ALLOWLIST if allowlist is None else allowlist
    grader = _repo_root() / "grader"
    files = []
    backend = grader / "backend"
    if backend.is_dir():
        files.extend(sorted(backend.rglob("*.test.ts")))
    files.extend(sorted((grader / "frontend").glob("*.spec.ts")))
    files.extend(sorted((grader / "conformance").glob("*.ts")))

    findings = []
    seen = set()
    for path in files:
        rel = path.relative_to(grader).as_posix()
        text = _strip_comments(path.read_text(encoding="utf-8"))
        helpers = _find_helpers(text)
        tests = _find_tests(text)
        helper_names = {h[0] for h in helpers}
        calls = {}
        for name, _decl, body_open, body_close in helpers:
            body = text[body_open:body_close]
            calls[name] = {
                other
                for other in helper_names
                if other != name and _name_called(other, body)
            }
        test_helpers = {}
        for start, end, gate in tests:
            span = text[start:end]
            test_helpers[(start, end, gate)] = {
                name for name in helper_names if _name_called(name, span)
            }
        for kind, offset, arg_text in _find_writes(text):
            if any(
                h[0] in _SKIP_HELPER_WRITES and h[1] <= offset <= h[3]
                for h in helpers
            ):
                continue
            payload = _resolve_payload(kind, arg_text)
            forbidden = decide(payload)
            if not forbidden:
                continue
            for gate in _attribute(rel, offset, text, tests, helpers, calls, test_helpers):
                if (rel, gate) in allow:
                    continue
                line = _line_of(text, offset)
                key = (rel, gate, line, tuple(forbidden))
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    {
                        "file": rel,
                        "gate": gate,
                        "line": line,
                        "forbidden": list(forbidden),
                        "payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    }
                )
    findings.sort(key=lambda f: (f["file"], f["line"], f["gate"]))
    return findings


def _selftest():
    assert decide(
        {
            "phase": "roll",
            "dice": [],
            "remainingDice": [],
            "turnOver": False,
            "cube": {"value": 1, "owner": None},
            "winner": None,
        }
    ) == [], "legal start of turn was flagged"

    got = decide({"phase": "move", "dice": [6, 5]})
    assert any(x.startswith("phase=") for x in got), "phase=move not flagged"
    assert any(x.startswith("dice=") for x in got), "dice not flagged"

    payload = _resolve_payload("debug", 'makeState({ turn: "white" })')
    assert payload["phase"] == "move", "makeState base phase was not inherited"
    assert "dice" in payload, "makeState base dice was not inherited"
    assert any(x.startswith("phase=") for x in decide(payload)), "inherited phase not flagged"

    assert "turnOver=true" in decide({"phase": "roll", "dice": [], "turnOver": True})

    assert any(x.startswith("cube=") for x in decide({"cube": {"value": 2, "owner": "black"}}))
    assert decide({"cube": {"value": 1, "owner": None}}) == [], "default cube was flagged"

    seeded = _resolve_payload("seedRolled", 'makeState({ cube: { value: 2, owner: "white" } })')
    assert seeded["phase"] == "roll", "seedRolled did not force a roll phase"
    assert seeded["dice"] == [] and seeded["remainingDice"] == [], "seedRolled did not force empty dice"
    assert any(x.startswith("cube=") for x in decide(seeded)), "parked cube via seedRolled not flagged"
    assert decide(_resolve_payload("seedRolled", "makeState({})")) == [], "a default-cube seedRolled was flagged"
    return "PASS"


def _main(argv):
    allow = {} if "--empty" in argv else None
    findings = find_findings(allow)
    try:
        selftest = _selftest()
    except AssertionError as error:  # pragma: no cover - only on a broken edit
        selftest = "FAIL: " + str(error)

    lines = ["SELFTEST: " + selftest]
    lines.extend(
        "{}:{} {} {}".format(f["file"], f["line"], f["gate"], f["payload"])
        for f in findings
    )
    lines.append("TOTAL: {} findings".format(len(findings)))
    output = "\n".join(lines)
    print(output)

    if "--save" in argv:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        log = _repo_root() / "dev" / "runs" / "c08-guard" / ("bite-proof-" + stamp + ".log")
        log.write_text(output + "\n", encoding="utf-8")
        print("SAVED: " + str(log))


if __name__ == "__main__":
    _main(sys.argv[1:])


# ── pytest guards ──────────────────────────────────────────────────────────

_FIXED_C08_GATES = frozenset(
    {
        "G24", "G35", "G33", "G39", "G30",
        "F33", "F39", "F09", "F11", "F86", "F59", "F51", "F53", "F90", "F18", "F21", "F20",
    }
)

_EXPECTED_EMPTY_SITES = frozenset(
    {
        ("backend/server-path-integrity.test.ts", "G28"),
        ("backend/server-path-integrity.test.ts", "G39"),
        ("backend/server-path-integrity.test.ts", "G30"),
        ("frontend/core.spec.ts", "F17"),
        ("frontend/edges.spec.ts", "F12"),
        ("frontend/edges.spec.ts", "F22"),
        ("frontend/edges.spec.ts", "F23"),
    }
)


def test_no_unallowlisted_findings_on_the_current_tree() -> None:
    assert find_findings() == []


def test_synthetic_self_tests_pass() -> None:
    assert _selftest() == "PASS"


def test_empty_allowlist_flags_exactly_the_known_sites() -> None:
    sites = {(f["file"], f["gate"]) for f in find_findings({})}
    assert sites == _EXPECTED_EMPTY_SITES


def test_no_fixed_c08_gate_is_flagged_for_move_phase_or_dice() -> None:
    bad = []
    for f in find_findings({}):
        if f["gate"] not in _FIXED_C08_GATES:
            continue
        for fb in f["forbidden"]:
            if fb.startswith(("phase=", "dice=", "remainingDice=", "turnOver=")):
                bad.append((f["file"], f["gate"], fb))
    assert bad == []
