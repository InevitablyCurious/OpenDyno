#!/usr/bin/env python3
"""COMPARE ANY TWO TELLINGS, ON TWO INDEPENDENT AXES.

WHAT THIS IS. A "telling" is what a run actually says to the person whose work is
being graded:

    { build_id: [ told_line, ... ] }

where each told line is at least

    {"index": 1-based int, "text": str, "finding_key": str | None, "declared_class": str | None}

and EXACTLY ONE of `finding_key` / `declared_class` is set: a finding line reports
a finding (`finding_key`), a "furniture" line states a difference the contract
declares on purpose (`declared_class`). Blank separator lines are never recorded,
so the list is the ordered non-blank lines.

Two tellings can differ in *which* findings they report and in *what words* they
report them in. Those are independent questions, so this module answers them
separately and never lets one hide the other:

  1. FINDING BY FINDING. Per build, the finding_keys of each side (finding_key
     set and declared_class null; a repeated key counts at its first occurrence)
     are compared: a key only the right side has is MISSING, a key only the left
     side has is EXTRA, and a key both sides carry at a different position is
     REORDERED. A position is the index of the told line in that build's list
     (0-based), and entries within a build are ordered by position.

  2. WORD BY WORD. Per build, line positions are walked in parallel
     (0..max(len(left), len(right))-1): any position whose text differs —
     including a position only one side reaches — is a word-difference, reported
     with both texts so the change is visible rather than merely counted.

DECLARED DIFFERENCES. Declared-ness is carried per line, not by a side table: a
difference whose finding_key is null is a furniture line and is DECLARED, while a
difference whose finding_key is a real key is UNDECLARED. Every entry carries
`declared`, and the result rolls them up into `declared_count` /
`undeclared_count`. A declared difference never counts as a failure: the exit
status is 0 iff `undeclared_count == 0`.

USAGE. Import `compare_tellings`, or run this file:

    python3 tools/compare.py A.json B.json [--json]

`A` is the left/derived telling, `B` the right/recorded one. Declared-ness comes
from the per-line `declared_class` field carried by the telling itself. Stdlib
only, and deterministic — builds are walked in sorted order, field order is fixed,
and every bucket is ordered by position.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BUCKETS = ("finding_missing", "finding_extra", "finding_reordered", "word_differences")


def _line(line):
    """A told line as a dict; anything malformed degrades to an empty line."""
    return line if isinstance(line, dict) else {}


def _finding_key(line):
    """The finding identity a line reports, or None for a furniture line."""
    line = _line(line)
    key = line.get("finding_key")
    if not key or line.get("declared_class"):
        return None
    return key


def _text(line):
    return _line(line).get("text")


def _positions(lines):
    """First occurrence position per finding key, in list order."""
    positions = {}
    for position, line in enumerate(lines):
        key = _finding_key(line)
        if key is not None:
            positions.setdefault(key, position)
    return positions


def compare_tellings(a, b, *, declared_classes=frozenset()):
    """Compare two tellings and report their finding-axis and word-axis differences.

    `a` is the left/derived telling, `b` the right/recorded telling; each is a
    dict of build id -> list of told lines. A build present on only one side is
    compared against an empty build, so its whole content surfaces as MISSING
    (right only) or EXTRA (left only).
    """
    declared_classes = frozenset(declared_classes or ())

    def is_declared(key):
        return key is None or key in declared_classes

    finding_missing = []
    finding_extra = []
    finding_reordered = []
    word_differences = []

    for build in sorted(set(a) | set(b), key=str):
        left = list(a.get(build) or ())
        right = list(b.get(build) or ())
        left_pos = _positions(left)
        right_pos = _positions(right)

        for key in sorted(set(right_pos) - set(left_pos), key=lambda k: (right_pos[k], k)):
            finding_missing.append(
                {
                    "build": build,
                    "finding_key": key,
                    "right_position": right_pos[key],
                    "declared": is_declared(key),
                }
            )
        for key in sorted(set(left_pos) - set(right_pos), key=lambda k: (left_pos[k], k)):
            finding_extra.append(
                {
                    "build": build,
                    "finding_key": key,
                    "left_position": left_pos[key],
                    "declared": is_declared(key),
                }
            )
        for key in sorted(
            set(left_pos) & set(right_pos),
            key=lambda k: (left_pos[k], right_pos[k], k),
        ):
            if left_pos[key] == right_pos[key]:
                continue
            finding_reordered.append(
                {
                    "build": build,
                    "finding_key": key,
                    "left_position": left_pos[key],
                    "right_position": right_pos[key],
                    "declared": is_declared(key),
                }
            )

        for position in range(max(len(left), len(right))):
            left_line = left[position] if position < len(left) else None
            right_line = right[position] if position < len(right) else None
            left_text = _text(left_line)
            right_text = _text(right_line)
            if left_text == right_text:
                continue
            key = _finding_key(left_line)
            if key is None:
                key = _finding_key(right_line)
            word_differences.append(
                {
                    "build": build,
                    "position": position,
                    "finding_key": key,
                    "left_text": left_text,
                    "right_text": right_text,
                    "declared": is_declared(key),
                }
            )

    declared_count = 0
    undeclared_count = 0
    for bucket in (finding_missing, finding_extra, finding_reordered, word_differences):
        for difference in bucket:
            if difference["declared"]:
                declared_count += 1
            else:
                undeclared_count += 1

    return {
        "finding_missing": finding_missing,
        "finding_extra": finding_extra,
        "finding_reordered": finding_reordered,
        "word_differences": word_differences,
        "declared_count": declared_count,
        "undeclared_count": undeclared_count,
    }


def summarize(result):
    """One-line human summary of a comparison result."""
    finding_differences = sum(len(result[bucket]) for bucket in BUCKETS[:3])
    return (
        f"{result['undeclared_count']} undeclared difference(s) "
        f"({result['declared_count']} declared; "
        f"{finding_differences} finding, {len(result['word_differences'])} word)"
    )


def _load_telling(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(
            f"compare: {path} is not a telling (expected an object of build -> told lines)"
        )
    for build, lines in payload.items():
        if not isinstance(lines, list):
            raise SystemExit(f"compare: {path}: build {build!r} is not a list of told lines")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="compare.py",
        description="Compare two tellings on the finding axis and the word axis.",
    )
    parser.add_argument("a", help="left telling (JSON: build -> [told lines])")
    parser.add_argument("b", help="right telling (JSON: build -> [told lines])")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the full result as JSON instead of the human summary",
    )
    args = parser.parse_args(argv)

    left = _load_telling(args.a)
    right = _load_telling(args.b)
    declared_classes = frozenset()
    result = compare_tellings(left, right, declared_classes=declared_classes)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"builds: {len(set(left) | set(right))}")
        print(f"result: {summarize(result)}")
        for bucket in BUCKETS:
            if result[bucket]:
                print(f"  {bucket}: {len(result[bucket])}")
        print(f"declared: {result['declared_count']} undeclared: {result['undeclared_count']}")
        print("verdict: MATCH" if result["undeclared_count"] == 0 else "verdict: DIFFERS")

    return 0 if result["undeclared_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
