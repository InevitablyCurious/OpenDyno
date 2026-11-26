// RESUME FROM A CHECK-POINT (dev loop step 6): the control plane's half.
// Dev mode only; a real check-point (under the runs root, or an absolute path
// anywhere); a known phase; bound into the confirmation token so a preview for
// one check-point cannot start another.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { confirmationToken, restatement } from "../contract.mjs";
import { resolveResume } from "../lib/validate.mjs";

function runsWithCheckpoint(meta) {
  const runs = mkdtempSync(join(tmpdir(), "resume-"));
  const cp = join(runs, "backups", "1794311852", "cell-0000", "checkpoints", "cp-01");
  mkdirSync(join(cp, "tree"), { recursive: true });
  writeFileSync(join(cp, "cp.json"), JSON.stringify({ attempt: 1, phase: "initial", ...meta }));
  return { runs, rel: join("backups", "1794311852", "cell-0000", "checkpoints", "cp-01") };
}

test("RESUME: refused outside dev mode", async () => {
  const { runs, rel } = runsWithCheckpoint({ build_phase: 4 });
  const out = await resolveResume({ checkpoint: rel }, { runsRoot: runs, devPause: false });
  assert.equal(out.refused?.code, "resume_needs_dev_mode");
});

test("RESUME: absent is no resume", async () => {
  const out = await resolveResume(undefined, { runsRoot: "/x", devPause: true });
  assert.deepEqual(out, { resume: null });
});

test("RESUME: the phase comes from the check-point, and a contradicting one is refused", async () => {
  const { runs, rel } = runsWithCheckpoint({ build_phase: 4 });
  const ok = await resolveResume({ checkpoint: rel }, { runsRoot: runs, devPause: true });
  assert.equal(ok.resume.phase, 4);
  assert.equal(ok.resume.rel, rel);
  const bad = await resolveResume({ checkpoint: rel, phase: 5 }, { runsRoot: runs, devPause: true });
  assert.equal(bad.refused?.code, "resume_phase_conflict");
});

test("RESUME: an old check-point needs its phase named", async () => {
  const { runs, rel } = runsWithCheckpoint({});
  const missing = await resolveResume({ checkpoint: rel }, { runsRoot: runs, devPause: true });
  assert.equal(missing.refused?.code, "resume_phase_unknown");
  const named = await resolveResume({ checkpoint: rel, phase: 4 }, { runsRoot: runs, devPause: true });
  assert.equal(named.resume.phase, 4);
});

test("RESUME: an absolute check-point outside the runs root is accepted; a non-check-point is refused structurally; a relative escape is still refused", async () => {
  const { runs } = runsWithCheckpoint({ build_phase: 4 });
  // An absolute path OUTSIDE the runs root that IS a valid check-point: accepted,
  // and named by its absolute path (not reduced to a runs-root-relative name).
  const outside = mkdtempSync(join(tmpdir(), "resume-outside-"));
  const cp = join(outside, "checkpoints", "cp-04");
  mkdirSync(join(cp, "tree"), { recursive: true });
  writeFileSync(join(cp, "cp.json"), JSON.stringify({ attempt: 4, phase: "feedback-3", build_phase: 6 }));
  const ok = await resolveResume({ checkpoint: cp }, { runsRoot: runs, devPause: true });
  assert.equal(ok.resume.phase, 6);
  assert.equal(ok.resume.checkpoint, resolve(cp));
  assert.equal(ok.resume.rel, resolve(cp));
  // The token names the absolute check-point it is resuming from.
  const token = confirmationToken({ model: "m", variant: "a", org: null, kind: "local", compact: false, devPause: true, resume: ok.resume });
  assert.ok(token.includes(`resume=${resolve(cp)}@6`), token);
  // An absolute path that is NOT a check-point: refused structurally.
  const notCp = await resolveResume({ checkpoint: "/etc" }, { runsRoot: runs, devPause: true });
  assert.equal(notCp.refused?.code, "resume_checkpoint_invalid");
  // A relative path inside the runs root that is not a check-point: refused structurally.
  const notCpRel = await resolveResume({ checkpoint: "backups" }, { runsRoot: runs, devPause: true });
  assert.equal(notCpRel.refused?.code, "resume_checkpoint_invalid");
  // A relative path escaping the runs root: still refused by containment.
  const escape = await resolveResume({ checkpoint: join("..", "outside") }, { runsRoot: runs, devPause: true });
  assert.equal(escape.refused?.code, "resume_checkpoint_outside");
});

test("RESUME: bound into the token and stated in the restatement", () => {
  const base = { model: "m", variant: "a", org: null, kind: "local", compact: true, devPause: true };
  const resume = { rel: "backups/x/cp-01", phase: 4 };
  const plain = confirmationToken(base);
  const resumed = confirmationToken({ ...base, resume });
  assert.notEqual(plain, resumed);
  assert.match(resumed, /resume=backups\/x\/cp-01@4/);
  assert.match(restatement({ ...base, resume }), /NOT a measurement/);
});
