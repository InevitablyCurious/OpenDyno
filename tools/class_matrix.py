"""CLASS MATRIX — run the grader against every way a problem class can go wrong,
before a model ever builds one of them. When a told line turns out false or vague,
the fix is for the whole class: plant every way it can go wrong into copies of the
reference build, and prove the reference stays silent while every plant is told
once, at the right moment, in true words.

Each row is a copy of the CURRENT golden with one planted variation (CSS appended,
or exact text replaced), the page checks it is graded with, and what a player-true
telling must be: the stage told, and for each told line its voice and key. The
report is rendered with the CURRENT harness (stages + voices + lines), exactly the
message a model would get.

usage: class_matrix.py <matrix.py> [--only NAME ...] [--jobs 2]
       a matrix file defines ROWS = [ {name, css?, replace?, layer?, expect} ]
       expect = {"told": [(voice, key), ...]} | {"told_any": [[...], [...]]} | {"nothing": True}
              | {"has": [...], "lacks": [...]}   (a real build, told other true lines too)
       base = a saved build to start from instead of the golden
       voice is "P" or "T"; key is a gate or gate.aspect ("REQ-RENDER/blank-board" too)
"""

import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "task/backgammon/golden"
GRADER = ROOT / "grader"
WORK = Path(
    os.environ.get("MATRIX_WORK", Path(tempfile.gettempdir()) / "opendyno-class-matrix")
)


def build_variant(row: dict) -> Path:
    dest = WORK / row["name"]
    if dest.exists():
        shutil.rmtree(dest)
    # A row starts from the golden, or from a saved build (a model's own copy the class was seen on).
    src = Path(row.get("base", GOLDEN))
    shutil.copytree(
        src, dest, ignore=shutil.ignore_patterns("node_modules", ".git"), symlinks=True
    )
    if (src / "node_modules").exists():
        (dest / "node_modules").symlink_to(src / "node_modules")
    for rel, old, new in row.get("replace", []):
        f = dest / rel
        text = f.read_text()
        if text.count(old) != 1:
            raise SystemExit(
                f"{row['name']}: replace target found {text.count(old)} times in {rel}: {old[:60]}"
            )
        f.write_text(text.replace(old, new))
    if row.get("css"):
        css = dest / "public/style.css"
        css.write_text(
            css.read_text()
            + f"\n/* CLASS MATRIX {row['name']} */\n"
            + row["css"]
            + "\n"
        )
    return dest


def grade(row: dict, port: int) -> list[dict]:
    """The grader's own pipeline (report.mjs): every gate of the row's layer, the
    render-blocked ladder and all — the report a run would write."""
    target = build_variant(row)
    out = WORK / f"{row['name']}-report.json"
    if out.exists():
        out.unlink()
    env = dict(os.environ, BENCH_PORT=str(port), BENCH_WORKERS="2")
    env.pop("BENCH_LAYER", None)
    cmd = ["node", "report.mjs", "--target", str(target), "--out", str(out)]
    if row.get("layer"):
        roster = WORK / "roster.json"
        if not roster.exists():
            subprocess.run(
                ["node", "roster.mjs", "--out", str(roster), "--force"],
                cwd=GRADER,
                check=True,
                stderr=subprocess.DEVNULL,
            )
        cmd += ["--roster", str(roster), "--layer", str(row["layer"])]
    with (WORK / f"{row['name']}-grade.log").open("w") as fh:
        subprocess.run(
            cmd, cwd=GRADER, env=env, stdout=fh, stderr=subprocess.STDOUT, timeout=1800
        )
    if not out.exists():
        raise SystemExit(
            f"{row['name']}: the grader wrote no report (see {row['name']}-grade.log)"
        )
    return json.loads(out.read_text()).get("problems") or []


def told(problems: list[dict]) -> tuple[int | None, list[tuple[str, str, str]]]:
    sys.path.insert(0, str(ROOT))
    from harness.adapters.challenge.runner import ChallengeRunner as R
    from harness.adapters.challenge.stages import load_stages, player_view

    stages = load_stages(GRADER / "checks.json")
    view = player_view(problems, stages, is_infra=R._is_harness_infra_check)
    if view.stage is None:
        return None, []
    lines = []
    for p in view.visible:
        check = p["check"].split("\n")[0]
        m = re.match(r"\[([A-Z]+\d+)\]", check)
        gate = m.group(1) if m else check.split(" ")[0]
        aspect = R._complaint_aspect(p)
        key = f"{gate}.{aspect}" if aspect else gate
        voice = "T" if R.feedback_channel(check, aspect) == "team" else "P"
        lines.append((voice, key, p["observed"].split("\n")[0][:150]))
    return view.stage.number, lines


def judge(row: dict, stage, lines) -> tuple[bool, str]:
    exp = row["expect"]
    got = [(v, k) for v, k, _ in lines]
    if exp.get("nothing"):
        return (not got), "nothing told"
    # A real build is told other true lines besides the class's own: say only what must and must not be there.
    if "has" in exp or "lacks" in exp:
        has, lacks = (
            [tuple(x) for x in exp.get("has", [])],
            [tuple(x) for x in exp.get("lacks", [])],
        )
        ok = all(x in got for x in has) and not any(x in got for x in lacks)
        return ok, "has " + ", ".join(
            f"{v} {k}" for v, k in has
        ) + "; lacks " + ", ".join(f"{v} {k}" for v, k in lacks)
    options = exp.get("told_any") or [exp["told"]]
    for opt in options:
        if sorted(map(tuple, opt)) == sorted(got):
            return True, " | ".join(f"{v} {k}" for v, k in opt)
    return False, " or ".join(" | ".join(f"{v} {k}" for v, k in opt) for opt in options)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()
    ns: dict = {}
    exec(Path(a.matrix).read_text(), ns)
    rows = [r for r in ns["ROWS"] if not a.only or r["name"] in a.only]
    WORK.mkdir(parents=True, exist_ok=True)
    results = {}
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        base = int(os.environ.get("MATRIX_PORT_BASE", "8600"))
        futs = {pool.submit(grade, r, base + 20 * i): r for i, r in enumerate(rows)}
        for f in cf.as_completed(futs):
            results[futs[f]["name"]] = f.result()
    ok_all = True
    for r in rows:
        stage, lines = told(results[r["name"]])
        ok, want = judge(r, stage, lines)
        ok_all &= ok
        print(f"{'OK  ' if ok else 'MISS'} {r['name']:34} stage {stage}  want: {want}")
        for v, k, obs in lines:
            print(f"        {v} {k:28} {obs}")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
