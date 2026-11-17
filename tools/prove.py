#!/usr/bin/env python3
"""THE ONE OFFLINE PROOF COMMAND OVER THE REFERENCE BASELINE.

WHAT THIS IS. `reference-baseline/` is the record of what Learning-Index's own
code told 111 builds: one JSON file per build under `builds/`, a wording table in
`index.json`, and a `manifest.json` that pins every input and output by sha256
and states the totals. This script proves three things about that record, and
exits 0 only if all three pass.

  (a) DETERMINISM. Every output the manifest lists is re-hashed and must carry the
      recorded sha256 — the checked-in data is the data the manifest describes.
      With `--reference` (plus `--testset`/`--matrix`, the dirs the recorder reads)
      the baseline is RE-RECORDED into a fresh temp dir by calling
      `tools/record_reference.py` and must come out byte-identical: the record is
      a pure function of the reference and its inputs, not a leftover artifact.

  (b) INTEGRITY / TRACEABILITY. The record must be internally consistent before
      anything is claimed from it: every told line names exactly one thing (a
      finding or a declared block), every finding told is cited by a line and
      every citing line maps back to a told finding, no build is missing, every
      build is pinned to the manifest's commit and to a listed input, and every
      count in the manifest and every `occurrences`/`builds` pair in the index is
      recomputed from the build files and must agree.

  (c) NEGATIVE CONTROL. A comparison that reports zero because it can report
      nothing is worthless. The recorded telling compared against itself must show
      zero undeclared differences; perturbing exactly one finding line's TEXT
      (identity untouched) must show exactly one undeclared word-difference and no
      finding-differences; reverting must restore zero.

RUNS OFFLINE. Stdlib only, from the checked-in data — no Learning-Index tree, no
network. `--reference`/`--testset`/`--matrix` are the only flags that reach
outside, and they exist to re-record:

    python3 tools/prove.py
    python3 tools/prove.py --reference <ref> --testset <dir> --matrix <dir>
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "reference-baseline"
BUILDS_DIR = BASELINE_DIR / "builds"
MANIFEST_PATH = BASELINE_DIR / "manifest.json"
INDEX_PATH = BASELINE_DIR / "index.json"
BASELINE_PREFIX = "reference-baseline/"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare_tellings

PERTURBATION = " "


# --------------------------------------------------------------------------
# pure helpers (module level: the tests import them, the proof never runs on
# import — everything below the helpers is guarded by __main__)
# --------------------------------------------------------------------------


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def finding_key(finding):
    """(gate, aspect) identity of a finding; the aspect is optional."""
    gate = finding.get("gate")
    aspect = finding.get("aspect")
    return f"{gate}.{aspect}" if aspect else gate


def traceability_violations(told_entries, where=""):
    """Told entries that do not name EXACTLY ONE thing.

    A told line is either a finding (`finding_key` set, `declared_class` null) or
    a declared block of the contract's own message (`declared_class` set,
    `finding_key` null). Both set is an ambiguous line; neither is an anonymous
    one. Either way the line cannot be traced, so it is reported, never guessed.
    """
    violations = []
    prefix = f"{where}: " if where else ""
    for position, entry in enumerate(told_entries):
        entry = entry if isinstance(entry, dict) else {}
        key = entry.get("finding_key")
        declared = entry.get("declared_class")
        if key and declared:
            violations.append(
                f"{prefix}told[{position}] names both finding_key={key!r} "
                f"and declared_class={declared!r}"
            )
        elif not key and not declared:
            violations.append(f"{prefix}told[{position}] names neither a finding nor a class")
    return violations


def load_builds(builds_dir=BUILDS_DIR):
    """Every build file, keyed by its id — the id is its path under builds/."""
    builds = {}
    for path in sorted(Path(builds_dir).rglob("*.json")):
        record = load_json(path)
        build_id = path.relative_to(builds_dir).with_suffix("").as_posix()
        if record.get("id") != build_id:
            raise SystemExit(
                f"prove: {path} records id {record.get('id')!r}, path says {build_id!r}"
            )
        builds[build_id] = record
    return builds


def told_identity_counts(builds):
    """(entries, violations) for the exactly-one-of rule across every build."""
    entries = 0
    violations = []
    for build_id in sorted(builds):
        told = builds[build_id]["told"]
        entries += len(told)
        violations.extend(traceability_violations(told, build_id))
    return entries, violations


def citation_counts(builds):
    """(agreements, violations) for finding <-> told-line traceability, both ways.

    A finding told to the person must be cited by a line carrying its key, and a
    line carrying a key must map back to a finding told in that same build. The
    two directions are counted separately because they fail differently: an
    uncited finding is a claim the record makes and then does not deliver; a
    citing line with no finding is a delivery with nothing behind it.
    """
    agreements = 0
    violations = []
    for build_id in sorted(builds):
        record = builds[build_id]
        cited = {entry["finding_key"] for entry in record["told"] if entry.get("finding_key")}
        told_findings = {finding_key(f) for f in record["findings"] if f.get("told")}
        for key in sorted(told_findings):
            if key in cited:
                agreements += 1
            else:
                violations.append(f"{build_id}: finding {key} is told but no told line cites it")
        for key in sorted(cited):
            if key in told_findings:
                agreements += 1
            else:
                violations.append(
                    f"{build_id}: told line cites {key} but no told finding has that key"
                )
    return agreements, violations


def _declared_classes():
    """The class vocabulary the recorder can emit, zero-count classes included."""
    from record_reference import DECLARED_CLASSES

    return DECLARED_CLASSES


def recount(builds, index):
    """Recompute every manifest count from the build files and index.json."""
    failed_tokens = [
        token for build_id in sorted(builds) for token in builds[build_id]["failed_gates"]
    ]
    classes = {name: 0 for name in _declared_classes()}
    for build_id in sorted(builds):
        for entry in builds[build_id]["told"]:
            name = entry.get("declared_class")
            if name:
                classes[name] = classes.get(name, 0) + 1
    return {
        "builds": len(builds),
        "testset": sum(1 for b in builds.values() if b["source"]["kind"] == "testset"),
        "matrix": sum(1 for b in builds.values() if b["source"]["kind"] == "matrix"),
        "told_lines": sum(len(b["told"]) for b in builds.values()),
        "findings": sum(len(b["findings"]) for b in builds.values()),
        "failed_gates_occurrences": len(failed_tokens),
        "distinct_gate_ids": len(set(failed_tokens)),
        "distinct_pairs": len(index["pairs"]),
        "pass_builds": sum(1 for b in builds.values() if b["verdict"] == "PASS"),
        "fail_builds": sum(1 for b in builds.values() if b["verdict"] != "PASS"),
        "declared_class_presence": dict(sorted(classes.items())),
    }


def count_violations(recounted, claimed):
    """(fields that agree, violations) between the recomputation and the manifest."""
    matched = 0
    violations = []
    for name in sorted(recounted):
        if name not in claimed:
            violations.append(
                f"counts.{name} missing from manifest (recomputed {recounted[name]!r})"
            )
        elif recounted[name] != claimed[name]:
            violations.append(
                f"counts.{name}: manifest {claimed[name]!r} != recomputed {recounted[name]!r}"
            )
        else:
            matched += 1
    for name in sorted(set(claimed) - set(recounted)):
        violations.append(f"counts.{name} in manifest but not recomputable from the builds")
    return matched, violations


def completeness_violations(builds, manifest):
    """Builds missing, unpinned, or not traceable to a manifest input."""
    violations = []
    claimed = manifest["counts"]["builds"]
    if len(builds) != claimed:
        violations.append(f"builds/: {len(builds)} files, manifest counts.builds {claimed}")
    inputs = {item["path"]: item["sha256"] for item in manifest["inputs"]}
    if len(inputs) != claimed:
        violations.append(f"manifest.inputs: {len(inputs)} entries, counts.builds {claimed}")
    commit = manifest["reference_commit"]
    for build_id in sorted(builds):
        record = builds[build_id]
        if record.get("reference_commit") != commit:
            violations.append(
                f"{build_id}: reference_commit {record.get('reference_commit')!r} != {commit}"
            )
        source = record["input"]
        if source["path"] not in inputs:
            violations.append(f"{build_id}: input {source['path']!r} is not in manifest.inputs")
        elif inputs[source["path"]] != source["sha256"]:
            violations.append(
                f"{build_id}: input sha256 disagrees with manifest.inputs for {source['path']!r}"
            )
    return violations


def index_violations(builds, index):
    """Every index pair's occurrences/builds recomputed from the build files."""
    occurrences = {}
    carriers = {}
    for build_id in sorted(builds):
        for entry in builds[build_id]["told"]:
            key = entry.get("finding_key")
            if not key:
                continue
            occurrences[key] = occurrences.get(key, 0) + 1
            carriers.setdefault(key, set()).add(build_id)
    violations = []
    for pair in index["pairs"]:
        key = pair["key"]
        if pair["occurrences"] != occurrences.get(key, 0):
            violations.append(
                f"index {key}: occurrences {pair['occurrences']} != recomputed {occurrences.get(key, 0)}"
            )
        expected = sorted(carriers.get(key, ()))
        if list(pair["builds"]) != expected:
            violations.append(f"index {key}: builds disagree with the build files")
    for key in sorted(set(occurrences) - {pair["key"] for pair in index["pairs"]}):
        violations.append(f"index: told key {key} has no pair entry")
    return violations


def telling(builds):
    """The recorded telling: {build id: [told line, ...]}."""
    return {build_id: list(builds[build_id]["told"]) for build_id in sorted(builds)}


def normalize_output_paths(manifest, out_root=None):
    """Manifest copy whose outputs[].path is root-relative, for cross-dir diffs.

    A re-record into a directory outside the repo emits absolute output paths
    (the recorder only relativises paths inside the repo), so the paths are
    normalised on both sides before the manifests are compared; nothing else in
    the manifest is touched.
    """
    normalized = copy.deepcopy(manifest)
    root = Path(out_root).resolve() if out_root is not None else None
    for output in normalized.get("outputs") or ():
        path = Path(output["path"])
        if root is not None and path.is_absolute() and root in path.resolve().parents:
            output["path"] = path.resolve().relative_to(root).as_posix()
        elif output["path"].startswith(BASELINE_PREFIX):
            output["path"] = output["path"][len(BASELINE_PREFIX) :]
    return normalized


# --------------------------------------------------------------------------
# the three proofs
# --------------------------------------------------------------------------


def prove_hashes(manifest):
    """(verified, violations) for every output the manifest pins."""
    verified = 0
    violations = []
    for output in manifest["outputs"]:
        path = REPO_ROOT / output["path"]
        if not path.is_file():
            violations.append(f"missing output {output['path']}")
            continue
        digest = sha256_file(path)
        if digest != output["sha256"]:
            violations.append(f"{output['path']}: sha256 {digest} != manifest {output['sha256']}")
        else:
            verified += 1
    return verified, violations


def prove_rerecord(reference, testset, matrix, manifest):
    """Re-record into a temp dir and diff every artifact against the check-in."""
    import record_reference

    with tempfile.TemporaryDirectory(prefix="opendyno-rerecord-") as tmp:
        out = Path(tmp) / "reference-baseline"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            status = record_reference.main(
                [
                    "--reference",
                    str(reference),
                    "--testset",
                    str(testset),
                    "--matrix",
                    str(matrix),
                    "--out",
                    str(out),
                ]
            )
        if status != 0:
            return 0, [f"recorder exited {status}: {buffer.getvalue().strip()[-400:]}"]

        violations = []
        compared = 0
        recorded_builds = out / "builds"
        for path in sorted(BUILDS_DIR.rglob("*.json")):
            relative = path.relative_to(BUILDS_DIR)
            fresh = recorded_builds / relative
            compared += 1
            if not fresh.is_file():
                violations.append(f"re-record did not emit builds/{relative.as_posix()}")
            elif fresh.read_bytes() != path.read_bytes():
                violations.append(
                    f"builds/{relative.as_posix()} differs between re-record and check-in"
                )
        for fresh in sorted(recorded_builds.rglob("*.json")):
            if not (BUILDS_DIR / fresh.relative_to(recorded_builds)).is_file():
                violations.append(
                    f"re-record emitted extra build {fresh.relative_to(recorded_builds).as_posix()}"
                )

        compared += 1
        if (out / "index.json").read_bytes() != INDEX_PATH.read_bytes():
            violations.append("index.json differs between re-record and check-in")

        compared += 1
        fresh_manifest = normalize_output_paths(load_json(out / "manifest.json"), out)
        checked_manifest = normalize_output_paths(manifest)
        fresh_text = json.dumps(fresh_manifest, indent=2, sort_keys=True, ensure_ascii=False)
        checked_text = json.dumps(checked_manifest, indent=2, sort_keys=True, ensure_ascii=False)
        if fresh_text != checked_text:
            differing = [
                key
                for key in sorted(set(fresh_manifest) | set(checked_manifest))
                if fresh_manifest.get(key) != checked_manifest.get(key)
            ]
            violations.append(f"manifest.json differs between re-record and check-in: {differing}")
        return compared, violations


def prove_control(builds):
    """Self-compare, one-text perturbation, revert — in that order."""
    recorded = telling(builds)
    snapshot = copy.deepcopy(recorded)

    self_result = compare_tellings(snapshot, recorded)

    target = None
    for build_id in sorted(recorded):
        for position, entry in enumerate(recorded[build_id]):
            if entry.get("finding_key"):
                target = (build_id, position)
                break
        if target:
            break
    if target is None:
        return self_result, None, None, None

    build_id, position = target
    original_text = recorded[build_id][position]["text"]
    recorded[build_id][position]["text"] = original_text + PERTURBATION
    control_result = compare_tellings(snapshot, recorded)
    recorded[build_id][position]["text"] = original_text
    reverted_result = compare_tellings(snapshot, recorded)
    return self_result, control_result, reverted_result, target


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="prove.py",
        description="Prove the reference baseline: determinism, traceability, negative control.",
    )
    parser.add_argument(
        "--reference", type=Path, help="Learning-Index reference tree to re-record from"
    )
    parser.add_argument(
        "--testset", type=Path, help="dir of <case>/report.json (required with --reference)"
    )
    parser.add_argument(
        "--matrix", type=Path, help="dir holding <matrix>.py + reports/ (required with --reference)"
    )
    args = parser.parse_args(argv)

    if args.reference and not (args.testset and args.matrix):
        parser.error("--reference also needs --testset and --matrix (the dirs the recorder reads)")
    if not args.reference and (args.testset or args.matrix):
        parser.error("--testset/--matrix are only meaningful with --reference")

    manifest = load_json(MANIFEST_PATH)
    index = load_json(INDEX_PATH)
    builds = load_builds()

    # -- (a) determinism ----------------------------------------------------
    print("== (a) DETERMINISM")
    verified, hash_violations = prove_hashes(manifest)
    print(f"hashes      {verified}/{len(manifest['outputs'])} outputs match manifest sha256")
    for violation in hash_violations:
        print(f"  FAIL {violation}")

    rerecord_compared = 0
    rerecord_violations = []
    if args.reference:
        missing = [
            flag
            for flag, path in (
                ("--reference", args.reference),
                ("--testset", args.testset),
                ("--matrix", args.matrix),
            )
            if not path.is_dir()
        ]
        if missing:
            rerecord_violations = [f"not a directory: {', '.join(missing)}"]
        else:
            rerecord_compared, rerecord_violations = prove_rerecord(
                args.reference, args.testset, args.matrix, manifest
            )
        verdict = "byte-identical" if not rerecord_violations else "DIFFERS"
        print(f"re-record   {rerecord_compared} artifacts vs check-in: {verdict}")
        for violation in rerecord_violations:
            print(f"  FAIL {violation}")
    else:
        print("re-record   skipped (no --reference given; hash check only)")

    # -- (b) integrity / traceability --------------------------------------
    print("== (b) INTEGRITY / TRACEABILITY")
    entries, identity_violations = told_identity_counts(builds)
    print(
        f"told lines  {entries - len(identity_violations)}/{entries} name exactly one of "
        f"finding_key/declared_class ({len(identity_violations)} violations)"
    )
    for violation in identity_violations:
        print(f"  FAIL {violation}")

    agreements, citation_violations = citation_counts(builds)
    print(
        f"citations   {agreements} finding<->line agreements ({len(citation_violations)} violations)"
    )
    for violation in citation_violations:
        print(f"  FAIL {violation}")

    completeness = completeness_violations(builds, manifest)
    print(
        f"builds      {len(builds)}/{manifest['counts']['builds']} present, "
        f"{len(manifest['inputs'])} inputs pinned, commit-pinned ({len(completeness)} violations)"
    )
    for violation in completeness:
        print(f"  FAIL {violation}")

    recounted = recount(builds, index)
    matched_counts, tally_violations = count_violations(recounted, manifest["counts"])
    print(
        f"counts      {matched_counts}/{len(recounted)} manifest counts "
        f"recomputed and equal ({len(tally_violations)} violations)"
    )
    for violation in tally_violations:
        print(f"  FAIL {violation}")

    pairs = index_violations(builds, index)
    print(
        f"index       {len(index['pairs'])} pairs, occurrences/builds recomputed "
        f"({len(pairs)} violations)"
    )
    for violation in pairs:
        print(f"  FAIL {violation}")

    integrity_violations = (
        identity_violations + citation_violations + completeness + tally_violations + pairs
    )

    # -- (c) negative control ----------------------------------------------
    print("== (c) NEGATIVE CONTROL")
    self_result, control_result, reverted_result, target = prove_control(builds)
    print(
        f"reference against reference  undeclared={self_result['undeclared_count']} "
        f"declared={self_result['declared_count']} word={len(self_result['word_differences'])} "
        f"finding={sum(len(self_result[b]) for b in ('finding_missing', 'finding_extra', 'finding_reordered'))}"
    )

    control_ok = False
    if control_result is not None:
        build_id, position = target
        finding_differences = sum(
            len(control_result[b])
            for b in ("finding_missing", "finding_extra", "finding_reordered")
        )
        print(
            f"one text perturbed ({build_id} told[{position}])  "
            f"undeclared={control_result['undeclared_count']} "
            f"word={len(control_result['word_differences'])} finding={finding_differences}"
        )
        reverted_differences = sum(
            len(reverted_result[b])
            for b in ("finding_missing", "finding_extra", "finding_reordered")
        )
        print(
            f"reverted, reference against reference  undeclared={reverted_result['undeclared_count']} "
            f"word={len(reverted_result['word_differences'])} finding={reverted_differences}"
        )
        control_ok = (
            self_result["undeclared_count"] == 0
            and control_result["undeclared_count"] == 1
            and len(control_result["word_differences"]) == 1
            and finding_differences == 0
            and reverted_result["undeclared_count"] == 0
            and len(reverted_result["word_differences"]) == 0
            and reverted_differences == 0
        )
        if not control_ok:
            print("  FAIL control: expected 0 -> exactly 1 undeclared word-difference -> 0")
    else:
        print("  FAIL control: no build carries a told line with a finding_key")

    # -- verdict ------------------------------------------------------------
    determinism_ok = not hash_violations and not rerecord_violations
    reasons = []
    if hash_violations:
        reasons.append(f"{len(hash_violations)} hash mismatches")
    if rerecord_violations:
        reasons.append(f"re-record not byte-identical ({len(rerecord_violations)} differences)")
    if integrity_violations:
        reasons.append(f"{len(integrity_violations)} integrity violations")
    if not control_ok:
        reasons.append("negative control did not show 0 -> 1 -> 0")

    passed = determinism_ok and not integrity_violations and control_ok
    print("VERDICT: " + ("PASS" if passed else "FAIL — " + "; ".join(reasons)))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
