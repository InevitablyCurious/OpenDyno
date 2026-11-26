# CLASS : F52 took New Game as usable at the start of every game.
# The brief only has a button the player can't use greyed out; the run's page shut New Game on a fresh
# game and greyed it with Undo and End Turn, and was told twice its greyed buttons were no fainter than
# "the least clear usable one" — New Game itself (78 vs 78, then 52 vs 52). The model re-greyed its text.
# Fix: which buttons can be used is the page's own answer (a trial click); a shut New Game is judged with
# the buttons that can't be used, and the message names the buttons and the measure.
SHUT_NEW = (
    "public/app.js",
    '  $("endTurnBtn").classList.toggle("primary", !$("endTurnBtn").disabled);',
    '  $("newGameBtn").disabled = state.phase === "openingRoll";\n  $("endTurnBtn").classList.toggle("primary", !$("endTurnBtn").disabled);',
)
NOT_GREYED = (
    "public/style.css",
    ".btn:disabled { opacity: .3; cursor: not-allowed; filter: grayscale(1); }",
    ".btn:disabled { cursor: not-allowed; }",
)

ROWS = [
    {"name": "golden", "layer": 3, "expect": {"nothing": True}},
    {
        "name": "new-game-shut-at-start-greyed",
        "layer": 3,
        "replace": [SHUT_NEW],
        "expect": {
            "has": [("P", "F54.newgame")],
            "lacks": [("T", "F52"), ("P", "F54")],
        },
    },
    {
        "name": "greyed-not-fainter",
        "layer": 3,
        "replace": [NOT_GREYED],
        "expect": {"has": [("T", "F52")], "lacks": []},
    },
    {
        "name": "new-game-shut-not-greyed",
        "layer": 3,
        "replace": [SHUT_NEW, NOT_GREYED],
        "expect": {"has": [("T", "F52")], "lacks": []},
    },
]
