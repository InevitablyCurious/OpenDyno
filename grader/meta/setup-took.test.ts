// assertSetupTook compares only the POSITION-DEFINING fields of a setup against
// its echo. A correct build recomputes derived fields (pip, legalMoves,
// canDouble, turnOver, pointsWon) and may rewrite display text (message), so an
// echo that differs there is not a setup that did not take; an echo that differs
// on a defining field is refused, and named.
import { describe, expect, it } from "vitest";
import { assertSetupTook } from "../lib/harness.ts";

describe("assertSetupTook", () => {
  it("passes when every defining field took, though derived fields differ or are absent", () => {
    const sent = {
      points: [0, 2, 0],
      bar: { white: 0, black: 0 },
      off: { white: 0, black: 0 },
      turn: "white",
      phase: "move",
      dice: [3, 1],
      remainingDice: [3, 1],
      cube: { value: 1, owner: null },
      difficulty: "medium",
      score: { white: 0, black: 0 },
      // Derived: the build may recompute or drop these on the way back.
      pip: 167,
      legalMoves: [{ from: 1, to: 4 }],
      canDouble: false,
      turnOver: true,
      pointsWon: 2,
    };
    const echo = {
      ...sent,
      // Same wiring, different derived values.
      pip: 25,
      legalMoves: [],
      canDouble: true,
      turnOver: false,
      pointsWon: 0,
    };
    expect(() => assertSetupTook(sent, echo)).not.toThrow();
    // An echo that omits the derived fields altogether is not a refusal either.
    const bare = {
      points: sent.points,
      bar: sent.bar,
      off: sent.off,
      turn: sent.turn,
      phase: sent.phase,
      dice: sent.dice,
      remainingDice: sent.remainingDice,
      cube: sent.cube,
      difficulty: sent.difficulty,
      score: sent.score,
    };
    expect(() => assertSetupTook(sent, bare)).not.toThrow();
  });

  it("refuses a defining field that did not take, and names only defining fields", () => {
    const sent = { points: [0, 2, 0], difficulty: "hard", message: "hi", turnOver: true };
    const echo = { points: [0, 2, 0], difficulty: "easy", message: "hi", turnOver: false };
    expect(() => assertSetupTook(sent, echo)).toThrow(/SETUP REFUSED/);
    expect(() => assertSetupTook(sent, echo)).toThrow(/did not take difficulty/);
    let said = "";
    try {
      assertSetupTook(sent, echo);
    } catch (error) {
      said = (error as Error).message;
    }
    // The "(sent …)" parenthetical names the defining fields, not display text
    // or a derived field the build recomputes.
    expect(said).toContain("(sent points, difficulty)");
    expect(said).not.toMatch(/message|turnOver/);
  });

  it("checks score only when it was written", () => {
    const sent = { points: [0, 2, 0], score: { white: 1, black: 0 } };
    const echo = { points: [0, 2, 0], score: { white: 0, black: 0 } };
    expect(() => assertSetupTook(sent, echo)).toThrow(/did not take score/);

    // A writing that omits score never mentions it, whatever the echo holds.
    const noScore = { points: [0, 2, 0] };
    expect(() => assertSetupTook(noScore, { points: [0, 2, 0], score: { white: 3, black: 1 } })).not.toThrow();
  });

  it("never checks message, which the app may rewrite as the state changes", () => {
    const sent = { points: [0, 2, 0], message: "x" };
    const echo = { points: [0, 2, 0], message: "y" };
    expect(() => assertSetupTook(sent, echo)).not.toThrow();
  });
});
