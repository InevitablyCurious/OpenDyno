# CLASS : G32 LOADED the computer's stuck turn with its dice already
# rolled (phase "move"); the run's server, which rolls and says "No moves available" in one step in play,
# passed that loaded turn with an empty message and was told twice its message lacked the words.
# Fix (play, don't load): the computer rolls its stuck 6-5 itself, queued through /api/debug/roll.
QUIET = (
    "src/server.ts",
    "    game.message = `${lead} ${dl} — No moves available.`;",
    "    game.message = `${lead} ${dl}.`;",
)

ROWS = [
    {"name": "golden", "layer": 3, "expect": {"nothing": True}},
    {
        "name": "stuck-says-nothing",
        "layer": 3,
        "replace": [QUIET],
        "expect": {"has": [("T", "G32.wording")], "lacks": []},
    },
]
