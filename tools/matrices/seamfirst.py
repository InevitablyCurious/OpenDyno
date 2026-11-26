# CLASS (WO-LI-SEAM-CHART, 2026-11-24): the debug route is conformance . A setup the
# route refused was told at its gate's own moment, behind earlier symptoms: 0 of 35 corpus builds whose
# route refused a setup were told so, and one refusal broke 23 checks on average. A seeded turn that
# plays unlike a played one (G35) was told at the cube's moment.
# Fix: a SETUP REFUSED finding is staged at the first moment (stages.py is_refused); G35 sits at the
# first moment and compares the seeded turn with the same turn reached by play.
# Judge by the printed stage (must be 1) and the told lines (team, about the route) — the tool does not
# assert the stage.

ROWS = [
    {"name": "golden", "layer": 3, "expect": {"nothing": True}},
    {
        "name": "route-drops-cube",
        "layer": 3,
        "replace": [
            (
                "src/server.ts",
                "      (game as any)[key] = body[key];",
                '      if (key !== "cube") (game as any)[key] = body[key];',
            )
        ],
        "expect": {"has": [], "lacks": []},
    },
    {
        "name": "route-drops-difficulty",
        "layer": 3,
        "replace": [
            (
                "src/server.ts",
                "      (game as any)[key] = body[key];",
                '      if (key !== "difficulty") (game as any)[key] = body[key];',
            )
        ],
        "expect": {"has": [], "lacks": []},
    },
]
