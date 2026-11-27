# Problem-speak

How a failed check becomes the words the agent reads, and the rules that keep every one of those words true.

## The promise

Every line the agent is told is true for the build it was told about, says what is wrong in terms the agent can
act on, and comes out the same way every time the same fault shows up. When a line breaks that promise, the run
measures the grader instead of the harness. Most of the machinery below exists to keep the promise.

## The choreography

Checks are grouped into **moments**, in the order a person meets the app: the game opens, the board's shape, the
buttons, the pieces, the first roll, the hints, moving a piece, the dice, the computer's turn, hitting, the bar,
bearing off, the doubling cube, game over, playing again (`grader/checks.json`, `stages`).

After each attempt the agent hears **only the earliest moment that still fails**. Later findings wait. A fault
deep in the game is not reported while the board itself is wrong, the same way a player never gets that far.

**Conformance comes first.** Before anything else: the app starts, the names, tags and routes the spec fixes are
there, and the debug route does what the spec says. Checks use the debug route only to set a legal start of a
turn, then play to the position they judge, with real rolls, moves and End Turn, so a build that keeps its own
record of the turn is never judged on a state it never produced (a guard holds every check to that). If the route
refuses a setup, that refusal is told first, once, by the team, instead of as twenty symptoms in later checks.

**Layers.** The page is built in three layers (board, pieces, gameplay). A grade during the board layer judges
board checks only. A check from a finished layer that breaks again later is told, under its own opener: it was
working, and it isn't now.

## Two voices

- **The player** says what a person sees and does on the page: "When I roll a double, more than two dice show
  up." No function names, no file names, no rule stated as a rule.
- **The software team** says what an integration team finds on the code underneath, and may name routes, fields
  and the brief's functions: "Their checks of your server: after the last move is played, with nothing left to
  play, your server's state still says turnOver is false."

A check that looks at code is the team's. A page check is the player's unless it is listed in
`grader/voices.json`.

## A line per situation

A check can fail in more than one way. Each way is an **aspect**, and each aspect has its own pair of lines: the
first time it is told, and a shorter repeat. An assertion names its aspect in its message:

```ts
expect(state.turnOver, "[aspect: stuckstate] a turn stuck on the bar answered turnOver false").toBe(true);
```

That finding is told with the lines in `task/backgammon/prompts/failures/<gate>.stuckstate.md` and
`…stuckstate-repeat.md`. A failing step with no aspect falls to the check's general line, so a step that can fail
for a reason the general line doesn't describe must carry an aspect of its own.

**Measured values.** A line can quote what the check measured with `{measured}`: the assertion message's first
line, markers removed. "hard won 3 of 25 games against easy's 20" beats "hard isn't stronger than easy". A model
that has been compacted can't look up what "the thresholds" were; the line gives the numbers.

**The spec's own words.** When an assertion judges a rule the spec states, it carries `[brief]`, and the spec's
passage for that check (`task/backgammon/prompts/respec/<gate>.md`) is handed back word for word alongside the
line. When the agent swings between two halves of one rule, the passage carries both halves.

## Steps that wait on other checks

- **`[needs: X Y]`**: this step only means something if checks X and Y pass. If either failed, this finding is
  held back and theirs is told instead. A needed check sits at the same or an earlier moment.
- **`[setup]`**: this step only sets the scene, and is never told. If the check that owns the step failed, the
  finding waits on it. If that check passed and the setup still failed, the grader itself is wrong: the run stops
  with a **grader alarm** instead of telling the agent anything.

## What is never told

- The grader's internals: requirement ids, test titles, assertion text, "expected … to be …".
- A check that didn't finish (a timeout says nothing about its subject).
- A vague line. There is no catch-all: a check with no line of its own is a build error. A failing grade with
  nothing true to tell stops the run with a grader alarm.

## The guards

`tests/` holds the rules above as tests, among them:

- player lines name no function and state no rule ("should be", "instead of"), and don't restate the check's
  title;
- every aspect in the suite has both lines;
- a needed check sits at the same or an earlier moment, with no cycles;
- every check has a moment and a voice;
- the lines files and `grader/feedback.json` agree.

## Adding or changing a line

1. Find the assertion, and give the situation its own `[aspect: name]` if it has none.
2. Write `<gate>.<aspect>.md` and `<gate>.<aspect>-repeat.md` under `task/backgammon/prompts/failures/` (the
   gate written `G-24`, `F-46`), and mirror them in `grader/feedback.json`.
3. Write what was seen or measured. For the player, what a person saw; for the team, the field or the number and
   the brief's rule.
4. Prove it on a class matrix ([CONTRIBUTING.md](../CONTRIBUTING.md)), then run the tests.
