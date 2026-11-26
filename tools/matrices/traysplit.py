# CLASS : the grader measured only the FIRST element tagged off-tray.
# The build drew its tray as two stacked pieces (one per row, 320 px each, at the same right-hand end):
# a player sees one full-height strip, and was about to be told "The off tray doesn't run the full
# height of the board" (F32.short: "the off tray is 320 px tall; the rows of points span 640 px").
# Fix: the tray is what a player sees — the tagged pieces stacked at one end, read as one (readOffTray).
SPLIT = (
    "public/app.js",
    "  pf.appendChild(trayDiv);",
    '  trayDiv.style.gridRow = "1";\n  pf.appendChild(trayDiv);\n  const trayLow = trayDiv.cloneNode(true);\n  trayLow.style.gridRow = "2";\n  pf.appendChild(trayLow);',
)
SPLIT_LOW_HIDDEN = (
    "public/app.js",
    "  pf.appendChild(trayDiv);",
    '  trayDiv.style.gridRow = "1";\n  pf.appendChild(trayDiv);\n  const trayLow = trayDiv.cloneNode(true);\n  trayLow.style.gridRow = "2";\n  trayLow.style.visibility = "hidden";\n  pf.appendChild(trayLow);',
)
F32 = [
    ("P", "F32"),
    ("P", "F32.short"),
    ("P", "F32.overlap"),
    ("P", "F32.side"),
    ("P", "F32.offboard"),
]

ROWS = [
    {"name": "golden-L1", "layer": 1, "expect": {"has": [("P", "F91")], "lacks": F32}},
    {
        "name": "split-tray",
        "layer": 1,
        "replace": [SPLIT],
        "expect": {"has": [("P", "F91")], "lacks": F32},
    },
    {
        "name": "split-tray-lower-hidden",
        "layer": 1,
        "replace": [SPLIT_LOW_HIDDEN],
        "expect": {"has": [("P", "F32.short")], "lacks": []},
    },
]
