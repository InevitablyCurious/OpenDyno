#!/usr/bin/env python3
"""Record the reference baseline for the OpenDyno proof builds.

WHAT THIS IS. One JSON file per proof build, produced by CALLING the reference
implementation's own composition code — never by re-implementing it. Every
sentence, every ordering decision, every stage/layer gate in the output comes
out of the reference at `--reference`; this recorder only drives the call and
classifies the lines the reference emitted so a later comparison can name them.

THE CALL. For one report, one round (no priors — attempt 1 of a fresh build):

    view = player_view(problems, stages, is_infra=R._is_harness_infra_check,
                       layer=report["layer"], layer_map=layers)
    body = R._build_feedback_prompt(
        problems=view.visible, repeat_complaints=set(), repeat_parts=set(),
        withheld=view.withheld, unevaluated=view.unevaluated,
        regressions=_regressed_checks([report], view.visible),
        found=problems,                       # ALL report problems, not visible
        phase_index=phase_index, broke_earlier=set(), phase_work=phase_work,
        respec=R._respec_for(problems, view.visible, view.stage, stages))
    full = _FIRST_MESSAGE_PREAMBLE + "\n\n" + body

`phase_index` is the FIRST phase index carrying the report's layer, derived from
the reference's own phase plan (`_PACK.phases()`) — never hardcoded.

DETERMINISM. Running twice produces byte-identical output: no wall clock, no
dict iteration over unordered sets in emitted data, no absolute machine paths
in the emitted files (input paths are logical). `manifest["generated_at"]` is
the reference commit's own committer timestamp (`git log -1 --format=%cI`), so
it records when the reference was made and remains a pure function of that
reference — a wall-clock reading would defeat the re-run proof.

STDLIB ONLY. Only the standard library, plus the reference's own modules.

CLASSIFICATION. A report's message is split into its non-blank lines and each
line is named by ONE of: the finding it states (`finding_key`, e.g. `F91` or
`F30.short`, from the reference's `_finding_key`), or a constant block of the
reference's own message (`declared_class`: preamble, excuse eliminator, section
headers, team note, constraint block, respec excerpt), or the tester's filler
line. A line that matches neither is a bug and RAISES — it is never guessed. A
finding's line can span several message lines (the general line for a part
carries its own indented list of what it expects); every physical line is one
entry, and a continuation carries its label's identity, read from the
reference's text.

INDEX WORDING. `index.json` names, per (gate, aspect) key, the sentence the
reference produced and the builds that carried it. A few aspect sentences
interpolate what the grader MEASURED (F37.shape names the board's real width
ratio, F30.faint the points that were faint, F48.dim and F82 their numbers), so
such a key has as many sentences as it has sightings. The entry carries the
sentence from the first build (sorted id) that told the key plus
`wording_variants`, the count of distinct sentences, so interpolation is
visible rather than silently flattened; the per-build truth is in builds/*.json.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent

# The 72 testset cases this baseline pins. Named, not globbed-and-hoped: a
# missing or extra case is a drifted input, and a baseline over drifted inputs
# is a lie.
TESTSET_CASES = (
    "M38-controls-below",
    "M39-board-too-wide",
    "M40-board-too-narrow",
    "M43-board-short",
    "M45-board-right",
    "M53-tray-invisible",
    "M73-short-outward-triangles",
    "r000",
    "r001",
    "r002",
    "r003",
    "r004",
    "r005",
    "r006",
    "r007",
    "r008",
    "r009",
    "r010",
    "r011",
    "r012",
    "r013",
    "r014",
    "r015",
    "r016",
    "r018",
    "r019",
    "r020",
    "r021",
    "r022",
    "r023",
    "r024",
    "r026",
    "r027",
    "r033",
    "r035",
    "r037",
    "r038",
    "r039",
    "r042",
    "r043",
    "r044",
    "r050",
    "r057",
    "r064",
    "r065",
    "r067",
    "r068",
    "r069",
    "r070",
    "r072",
    "r075",
    "r078",
    "r080",
    "r082",
    "r084",
    "r086",
    "r088",
    "r089",
    "r090",
    "r102",
    "r104",
    "r107",
    "r108",
    "t16",
    "t17",
    "t18",
    "X-bar-too-wide",
    "X-blank-board",
    "X-centred-buttons-under",
    "X-faint-triangles",
    "X-pieces-in-first-layer",
    "X-tray-missing",
)

# The three matrix definition files, and how many ROWS each must declare. The
# row lists are the authority: `reports/splitlines/endturn-three-times-wide-report.json`
# is an orphan (a renamed row supersedes it) and is excluded by never appearing
# in ROWS.
MATRIX_FILES = (("legit", 7), ("splitlines", 14), ("visibility", 18))

# Every `declared_class` this recorder can emit, so the manifest counts a class
# with zero occurrences at 0 rather than omitting it.
DECLARED_CLASSES = (
    "constraint-block",
    "excuse-eliminator",
    "first-message-preamble",
    "general-part-lines",
    "respec-excerpts",
    "section-headers",
    "team-excuse-eliminator",
    "tester-filler",
)

NUMBERED = re.compile(r"^(\d+)\) (.*)$")


def fail(message: str) -> None:
    raise SystemExit(f"record_reference: {message}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_reference(root: Path) -> dict[str, object]:
    """Import the reference's own modules and hand back everything we call.

    The recipe is the one the reference's runner uses on itself. No fallbacks:
    an ImportError here is a deviation to report, never something to paper over
    with a local composer.
    """
    # The reference is READ-ONLY: importing it must not leave bytecode caches in
    # someone else's tree.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    from harness.adapters.challenge import ChallengeRunner as R
    from harness.adapters.challenge.constants import (
        _EXCUSE_ELIMINATOR,
        _FEEDBACK_HEADER_FIRST,
        _GRADER_DIR,
        _PACK,
        _TEAM_EXCUSE_ELIMINATOR,
        _TEAM_HEADER,
        _TEAM_HEADER_ALONE,
    )
    from harness.adapters.challenge.feedback import TOLD_LINE_CAP
    from harness.adapters.challenge.runner import (
        _FIRST_MESSAGE_PREAMBLE,
        _regressed_checks,
    )
    from harness.adapters.challenge.stages import (
        check_id,
        load_layers,
        load_stages,
        player_view,
    )

    stages = load_stages(_GRADER_DIR / "checks.json")
    layers = load_layers(_GRADER_DIR / "layers.json")

    first_phase_of_layer: dict[int, int] = {}
    for phase in _PACK.phases():
        if phase.layer is not None and phase.layer not in first_phase_of_layer:
            first_phase_of_layer[phase.layer] = phase.index

    return {
        "R": R,
        "stages": stages,
        "layers": layers,
        "first_phase_of_layer": first_phase_of_layer,
        "pack": _PACK,
        "check_id": check_id,
        "player_view": player_view,
        "regressed_checks": _regressed_checks,
        "preamble": _FIRST_MESSAGE_PREAMBLE,
        "excuse": _EXCUSE_ELIMINATOR,
        "first_header": _FEEDBACK_HEADER_FIRST,
        "team_header": _TEAM_HEADER,
        "team_header_alone": _TEAM_HEADER_ALONE,
        "team_excuse": _TEAM_EXCUSE_ELIMINATOR,
        "told_line_cap": TOLD_LINE_CAP,
    }


def reference_commit(root: Path) -> str:
    """The reference's full HEAD sha, read-only (`git rev-parse`, no writes)."""
    out = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def reference_committed_at(root: Path, commit: str) -> str:
    """When the reference's HEAD commit was committed, read-only.

    `git log -1 --format=%cI` is an ISO-8601 committer date, which names when the
    reference was made rather than when this recorder ran — a wall clock reading
    would defeat the re-run proof. The value is therefore a pure function of the
    reference, byte-identical across runs. If git cannot answer (no repo, a
    shallow-less export, a binary that is missing) the commit sha stands in: it
    identifies the same reference, and it is already in the manifest.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%cI"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return commit
    return out.stdout.strip() or commit


def load_rows(path: Path) -> list[dict]:
    """A matrix definition file's `ROWS`, imported the way the file declares it."""
    spec = importlib.util.spec_from_file_location(f"_matrix_{path.stem}", path)
    if spec is None or spec.loader is None:
        fail(f"cannot import matrix definitions from {path}")
    module: ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = getattr(module, "ROWS", None)
    if not isinstance(rows, list):
        fail(f"{path} declares no ROWS list")
    return rows


def discover_inputs(testset: Path, matrix: Path) -> list[dict]:
    """The 111 input reports, as (build-id, logical path, absolute path)."""
    found = sorted(
        {p.parent.name for p in testset.glob("*/report.json")},
        key=str,
    )
    missing = sorted(set(TESTSET_CASES) - set(found))
    extra = sorted(set(found) - set(TESTSET_CASES))
    if missing or extra:
        fail(f"testset does not match the pinned 72 cases: missing={missing} extra={extra}")

    inputs: list[dict] = []
    for case in TESTSET_CASES:
        inputs.append(
            {
                "id": case,
                "kind": "testset",
                "matrix": None,
                "row": None,
                "logical": f"testset/{case}/report.json",
                "path": testset / case / "report.json",
            }
        )

    for name, expected_rows in MATRIX_FILES:
        rows = load_rows(matrix / f"{name}.py")
        if len(rows) != expected_rows:
            fail(
                f"{matrix / f'{name}.py'} declares {len(rows)} ROWS, "
                f"the baseline pins {expected_rows}"
            )
        for row in rows:
            row_name = row.get("name")
            if not isinstance(row_name, str) or not row_name:
                fail(f"{matrix / f'{name}.py'} has a row without a name: {row!r}")
            path = matrix / "reports" / name / f"{row_name}-report.json"
            if not path.is_file():
                fail(f"matrix row {name}/{row_name} has no report at {path}")
            inputs.append(
                {
                    "id": f"{name}/{row_name}",
                    "kind": "matrix",
                    "matrix": name,
                    "row": row_name,
                    "logical": f"matrix/{name}/{row_name}-report.json",
                    "path": path,
                }
            )

    seen: set[str] = set()
    for item in inputs:
        if item["id"] in seen:
            fail(f"duplicate build id {item['id']}")
        seen.add(item["id"])
    return inputs


def constant_class_map(
    ref: dict[str, object], phase_index: int, respec: list[str]
) -> dict[str, str]:
    """Every constant string the reference can put in a one-round message.

    Each class's text is split into its non-blank lines and registered from the
    REFERENCE's own constants — never a copy of their text. Read in the order
    the message is built (preamble, excuse eliminator, headers, team note,
    constraints, respec); first registration wins, so a line two constants share
    is attributed to the earlier block in the message.
    """
    table: dict[str, str] = {}

    def add(text: str, label: str) -> None:
        for line in text.splitlines():
            if line.strip():
                table.setdefault(line, label)

    add(str(ref["preamble"]), "first-message-preamble")
    add(str(ref["excuse"]), "excuse-eliminator")
    add(str(ref["first_header"]), "section-headers")
    add(str(ref["team_header"]), "section-headers")
    add(str(ref["team_header_alone"]), "section-headers")
    add(str(ref["team_excuse"]), "team-excuse-eliminator")
    add(ref["R"]._constraints_for(phase_index), "constraint-block")
    for text in respec:
        add(text, "respec-excerpts")
    return table


def compose(ref: dict[str, object], report: dict) -> dict:
    """Run the reference's own composition for one one-round proof build."""
    R = ref["R"]
    problems = [p for p in (report.get("problems") or []) if isinstance(p, dict)]
    layer = report.get("layer")
    first_phase = ref["first_phase_of_layer"]
    if not isinstance(layer, int) or layer not in first_phase:
        fail(f"report layer {layer!r} names no phase in the reference's plan")
    phase_index = first_phase[layer]
    phase = ref["pack"].phase(phase_index)

    view = ref["player_view"](
        problems,
        ref["stages"],
        is_infra=R._is_harness_infra_check,
        layer=layer,
        layer_map=ref["layers"],
    )
    respec = R._respec_for(problems, view.visible, view.stage, ref["stages"])
    body = R._build_feedback_prompt(
        problems=view.visible,
        repeat_complaints=set(),
        repeat_parts=set(),
        withheld=view.withheld,
        unevaluated=view.unevaluated,
        regressions=ref["regressed_checks"]([report], view.visible),
        found=problems,
        phase_index=phase_index,
        broke_earlier=set(),
        phase_work=phase.work,
        respec=respec,
    )
    full = str(ref["preamble"]) + "\n\n" + body
    return {
        "phase_index": phase_index,
        "problems": problems,
        "visible": view.visible,
        "respec": respec,
        "full": full,
    }


def finding_map(ref: dict[str, object], composed: dict) -> dict[str, dict]:
    """The reference's own label for each visible problem -> its identity.

    `_told_label` with the same `among` the composer uses is the only way to
    know what line a finding is told as; `_general_part` says whether that line
    is a part-level general line (no per-finding key) or the finding's own.
    """
    R = ref["R"]
    problems = composed["problems"]
    table: dict[str, dict] = {}
    for record in composed["visible"]:
        label, _channel = R._told_label(record, pass_kind="first", among=problems)
        if len(label) > ref["told_line_cap"]:
            fail(
                "a told label exceeds the reference's TOLD_LINE_CAP "
                f"({ref['told_line_cap']}) and would be truncated in the message, "
                f"so this recorder could not match it: {label!r}"
            )
        part = R._general_part(record, problems)
        if part is not None:
            table[label] = {"finding_key": None, "declared_class": "general-part-lines"}
        else:
            table[label] = {"finding_key": R._finding_key(record), "declared_class": None}
    return table


def classify(composed: dict, labels: dict[str, dict], constants: dict[str, str]) -> list[dict]:
    """Split the reference's message into told entries, one per non-blank line.

    Each entry carries its 1-based `index` within this build's `told` list — the
    position of the physical line it names in the message the reference emitted,
    counting the non-blank lines — and the key order is fixed: index, text,
    finding_key, declared_class.

    A finding's line is not always ONE line: the reference's general line for a
    part can carry an indented list of what it expects ("The off tray isn't
    drawn right. Here's what I expect:" then four bullets). Each physical line
    is its own entry — the message is compared line by line downstream — and
    every line of a multi-line label carries that label's identity, read from
    the reference's own text rather than re-derived from its punctuation.
    """
    starts: dict[str, dict] = {}
    rest_of: dict[str, tuple[str, ...]] = {}
    for text, identity in labels.items():
        parts = text.splitlines()
        if not parts:
            continue
        starts[parts[0]] = identity
        if len(parts) > 1:
            rest_of[parts[0]] = tuple(parts[1:])

    told: list[dict] = []
    pending: tuple[tuple[str, ...], dict] | None = None
    for line in composed["full"].splitlines():
        if not line.strip():
            continue
        if pending and line == pending[0][0]:
            identity = dict(pending[1])
            remaining = pending[0][1:]
            pending = (remaining, pending[1]) if remaining else None
        else:
            pending = None
            numbered = NUMBERED.match(line)
            if numbered and numbered.group(2) in starts:
                body = numbered.group(2)
                identity = dict(starts[body])
                if body in rest_of:
                    pending = (rest_of[body], starts[body])
            elif numbered:
                # The one numbered line that names no finding: the tester's
                # filler, emitted when they have nothing they could put their
                # finger on.
                identity = {"finding_key": None, "declared_class": "tester-filler"}
            elif line in constants:
                identity = {"finding_key": None, "declared_class": constants[line]}
            else:
                fail(f"unclassified message line (a classification bug, not a guess): {line!r}")
        entry = {"index": len(told) + 1, "text": line, **identity}
        if (entry["finding_key"] is None) == (entry["declared_class"] is None):
            fail(f"told entry carries exactly one of finding_key/declared_class: {entry!r}")
        told.append(entry)

    non_blank = [line for line in composed["full"].splitlines() if line.strip()]
    if len(told) != len(non_blank):
        fail(f"classified {len(told)} of {len(non_blank)} non-blank lines")
    return told


def build_record(ref: dict[str, object], item: dict, report: dict, commit: str) -> dict:
    """One build's reference record: the composition plus its classification."""
    R = ref["R"]
    check_id = ref["check_id"]
    verdict = report.get("verdict")
    problems = [p for p in (report.get("problems") or []) if isinstance(p, dict)]
    layer = report.get("layer")

    failed_gates: list[str] = []
    for entry in report.get("failed_gates") or []:
        raw = str(entry)
        failed_gates.append(check_id(raw) or raw.split("\n", 1)[0].strip())

    if verdict == "PASS":
        # A pass composes no repair feedback: the runner tells nothing, so there
        # is no message to split and no finding to carry.
        told: list[dict] = []
        findings: list[dict] = []
    else:
        composed = compose(ref, report)
        labels = finding_map(ref, composed)
        constants = constant_class_map(ref, composed["phase_index"], composed["respec"])
        told = classify(composed, labels, constants)
        told_keys = {e["finding_key"] for e in told if e["finding_key"]}
        findings = []
        for index, problem in enumerate(problems):
            key = R._finding_key(problem)
            findings.append(
                {
                    "gate": check_id(str(problem.get("check", ""))),
                    "aspect": R._complaint_aspect(problem),
                    "problem_index": index,
                    "told": key in told_keys if key else False,
                }
            )

    return {
        "id": item["id"],
        "source": {
            "kind": item["kind"],
            "matrix": item["matrix"],
            "row": item["row"],
        },
        "input": {
            "path": item["logical"],
            "sha256": sha256_file(item["path"]),
        },
        "reference_commit": commit,
        "layer": layer,
        "verdict": verdict,
        "render_blocked": report.get("render_blocked"),
        "failed_gates": failed_gates,
        "findings": findings,
        "told": told,
    }


def index_entries(
    ref: dict[str, object], records: list[dict], problems_by_id: dict[str, list[dict]]
) -> list[dict]:
    """The distinct (gate, aspect) keys the reference told, with their wording.

    THE WORDING IS NOT ALWAYS ONE SENTENCE (measured, not assumed). A few aspect
    lines interpolate what the grader measured — F37.shape names the board's
    actual width ratio (12 distinct sentences across the 111 builds), F30.faint
    names which points were faint, F48.dim and F82 name their measurements. The
    reference resolves those per build, so "one canonical wording per key" is
    false for exactly those keys. The entry therefore carries the sentence from
    the FIRST build (sorted id) that told the key — deterministic, and the same
    text a reader sees in that build's file — plus `wording_variants`, the count
    of distinct sentences seen, so a measurement-bearing wording is visible
    rather than silently flattened. Per-build truth lives in builds/*.json.
    """
    R = ref["R"]
    wordings: dict[str, str] = {}
    variants: dict[str, set[str]] = {}
    occurrences: dict[str, int] = {}
    builds: dict[str, set[str]] = {}
    for record in records:
        for entry in record["told"]:
            key = entry["finding_key"]
            if not key:
                continue
            occurrences[key] = occurrences.get(key, 0) + 1
            builds.setdefault(key, set()).add(record["id"])

    # Ask `_told_label` with the same `among` the composer used, and skip the
    # findings of a build whose round is told as a part's general line (those
    # are not told under their own key). Records are walked in build-id order so
    # the representative wording is a pure function of the inputs.
    for record in sorted(records, key=lambda r: r["id"]):
        problems = problems_by_id[record["id"]]
        for problem in problems:
            key = R._finding_key(problem)
            if not key or key not in occurrences:
                continue
            if R._general_part(problem, problems) is not None:
                continue
            label = R._told_label(problem, pass_kind="first", among=problems)[0]
            variants.setdefault(key, set()).add(label)
            wordings.setdefault(key, label)

    missing = sorted(set(occurrences) - set(wordings))
    if missing:
        fail(f"no wording resolved for told keys: {missing}")

    pairs = []
    for key in sorted(occurrences):
        gate, _, aspect = key.partition(".")
        pairs.append(
            {
                "key": key,
                "gate": gate,
                "aspect": aspect or None,
                "wording": wordings[key],
                "wording_variants": len(variants[key]),
                "occurrences": occurrences[key],
                "builds": sorted(builds[key]),
            }
        )
    return pairs


def dump(path: Path, payload: dict) -> str:
    """Write one deterministic JSON artifact and return its sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n").encode(
        "utf-8"
    )
    path.write_bytes(data)
    return sha256_bytes(data)


def prune(out: Path, keep: set[Path]) -> None:
    """Drop build files a previous run wrote and this one does not.

    The output directory is an exact function of the inputs: a stale build file
    left behind would make two runs of the recorder disagree with a fresh one.
    """
    builds = out / "builds"
    if not builds.is_dir():
        return
    stale = sorted(p for p in builds.rglob("*.json") if p not in keep)
    for path in stale:
        path.unlink()
    for directory in sorted((p for p in builds.rglob("*") if p.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record the reference baseline by calling Learning-Index's own code."
    )
    parser.add_argument("--reference", required=True, type=Path, help="reference tree to import")
    parser.add_argument("--testset", required=True, type=Path, help="dir of <case>/report.json")
    parser.add_argument(
        "--matrix", required=True, type=Path, help="dir holding <matrix>.py + reports/"
    )
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "reference-baseline", help="output directory"
    )
    args = parser.parse_args(argv)

    for flag, path in (
        ("--reference", args.reference),
        ("--testset", args.testset),
        ("--matrix", args.matrix),
    ):
        if not path.is_dir():
            fail(f"{flag} is not a directory: {path}")

    ref = load_reference(args.reference.resolve())
    commit = reference_commit(args.reference.resolve())
    generated_at = reference_committed_at(args.reference.resolve(), commit)
    inputs = discover_inputs(args.testset, args.matrix)

    records: list[dict] = []
    problems_by_id: dict[str, list[dict]] = {}
    for item in inputs:
        report = json.loads(item["path"].read_text(encoding="utf-8"))
        problems_by_id[item["id"]] = [
            p for p in (report.get("problems") or []) if isinstance(p, dict)
        ]
        records.append(build_record(ref, item, report, commit))

    pairs = index_entries(ref, records, problems_by_id)

    out = args.out.resolve()
    written: dict[Path, str] = {}
    keep: set[Path] = set()
    for record in records:
        path = out / "builds" / f"{record['id']}.json"
        keep.add(path)
        written[path] = dump(path, record)
    prune(out, keep)
    index_path = out / "index.json"
    written[index_path] = dump(index_path, {"pairs": pairs})

    def rel(path: Path) -> str:
        try:
            return path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    classes: dict[str, int] = {name: 0 for name in DECLARED_CLASSES}
    told_lines = 0
    for record in records:
        for entry in record["told"]:
            told_lines += 1
            # A line keyed to a finding carries no class; a class line carries no
            # key (asserted at classification time), so this counts each once.
            if entry["declared_class"]:
                classes[entry["declared_class"]] = classes.get(entry["declared_class"], 0) + 1

    failed_gate_tokens = [token for record in records for token in record["failed_gates"]]
    counts = {
        "builds": len(records),
        "testset": sum(1 for r in records if r["source"]["kind"] == "testset"),
        "matrix": sum(1 for r in records if r["source"]["kind"] == "matrix"),
        "told_lines": told_lines,
        "findings": sum(len(r["findings"]) for r in records),
        "failed_gates_occurrences": len(failed_gate_tokens),
        # Gate ids as the REPORTS spell them (failed_gates tokens, which include
        # setup checks like REQ-RENDER/blank-board); distinct_pairs counts the
        # keys the reference actually TOLD, which is the smaller, staged set.
        "distinct_gate_ids": len(set(failed_gate_tokens)),
        "distinct_pairs": len(pairs),
        "pass_builds": sum(1 for r in records if r["verdict"] == "PASS"),
        "fail_builds": sum(1 for r in records if r["verdict"] != "PASS"),
        "declared_class_presence": dict(sorted(classes.items())),
    }

    manifest = {
        "reference_commit": commit,
        "generated_at": generated_at,
        "command": (
            "python3 tools/record_reference.py "
            "--reference <reference> --testset <testset> --matrix <matrix>"
        ),
        "inputs": [
            {"path": item["logical"], "sha256": sha256_file(item["path"])}
            for item in sorted(inputs, key=lambda i: i["logical"])
        ],
        "outputs": [
            {"path": rel(path), "sha256": digest}
            for path, digest in sorted(written.items(), key=lambda kv: rel(kv[0]))
        ],
        "counts": counts,
        "statement": (
            "This data is produced by running Learning-Index's own code (the reference "
            f"at {commit}) over the input reports — never a re-implementation."
        ),
    }
    manifest_path = out / "manifest.json"
    manifest_sha = dump(manifest_path, manifest)

    print(f"reference_commit {commit}")
    print(f"builds {len(records)} -> {out}")
    print("counts " + json.dumps(counts, sort_keys=True))
    print(f"manifest {manifest_path} sha256 {manifest_sha}")
    print(f"index {index_path} sha256 {written[index_path]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
