import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { addGoalForEntry, exportGoals, importGoals, planGoal } from "../public/goals.mjs";

const url = "https://game-guides.example/locations";
const fixture = (id, attributes = {}) => ({
  id, title: "Spot " + id, source: url, category: "collectible", confidence: "guide",
  x: .6, y: .6, details: "Find the prompt next to the designated picnic table.",
  steps: ["Approach the table and use the prompt."], ...attributes,
});
const countGoal = (category = "collectible", target = 3) => ({ id: "goal-count", type: "count", category, target });
const entryGoal = (entryId) => ({ id: "goal-single", type: "entry", entryId });

test("uses app checklist progress and nearest eligible sourced waypoint", () => {
  const done = fixture("done", { x: .4, y: .4 });
  const nearest = fixture("near", { x: .41, y: .41, confidence: "area" });
  const farther = fixture("far", { x: .65 });
  const questioned = fixture("questionable", { x: .4001, y: .4001, verification: { status: "review" } });
  const unmapped = fixture("unknown", { x: null, y: null });
  const localPin = fixture("personal-pin", { x: .4, y: .4, confidence: "personal" });
  const ungrounded = fixture("missing-source", { x: .4, y: .4, source: "javascript:alert(0)" });
  const bare = fixture("bare", { steps: [], details: "Ping" });
  const records = [done, nearest, farther, questioned, unmapped, localPin, ungrounded, bare];
  const plan = planGoal(countGoal(), records, [done.id], { origin: { x: .4, y: .4 } });
  assert.equal(plan.count, 1);
  assert.equal(plan.remaining, 2);
  assert.equal(plan.next.row.id, nearest.id);
  assert.match(plan.next.caution, /Approximate area/);
  assert.equal(plan.excluded.review, 1);
  assert.equal(plan.excluded.unlocated, 1);
  assert.equal(plan.excluded.noInstructions, 1);
  assert.equal(plan.shortfall, 0);
  const following = planGoal(countGoal(), records, [done.id, nearest.id], { origin: { x: .4, y: .4 } });
  assert.equal(following.next.row.id, farther.id);
  const completed = planGoal(countGoal(), records, [done.id, nearest.id, farther.id]);
  assert.equal(completed.complete, true);
  assert.equal(completed.next, null);
});

test("preserves sourced text-only missions, explicit requirements and contested locations", () => {
  const mission = fixture("mission-test", {
    category: "mission", chapter: 4, character: "Lucia",
    prerequisite: "Complete the preceding story mission.",
  });
  const locked = planGoal(entryGoal(mission.id), [mission], [], { readiness: { chapter: 2, character: "lucia" } });
  assert.equal(locked.next, null);
  assert.equal(locked.excluded.prerequisites, 1);
  assert.match(locked.specificReadiness.note, /Chapter 4/);
  assert.equal(locked.specific.title, mission.title);
  assert.ok(locked.specificReadiness.labels.includes(mission.prerequisite));
  const wrongCharacter = planGoal(entryGoal(mission.id), [mission], [], { readiness: { chapter: 4, character: "jason" } });
  assert.match(wrongCharacter.specificReadiness.note, /Lucia/);
  const ready = planGoal(entryGoal(mission.id), [mission], [], { readiness: { chapter: 4, character: "lucia" } });
  assert.equal(ready.next.row.id, mission.id);
  assert.deepEqual(ready.next.steps, mission.steps);
  const unlocated = { ...mission, x: null, y: null };
  const textOnly = planGoal(entryGoal(mission.id), [unlocated], []);
  assert.equal(textOnly.next, null);
  assert.equal(textOnly.specific.details, unlocated.details);
  const completed = planGoal(entryGoal(mission.id), [unlocated], [mission.id]);
  assert.equal(completed.complete, true);
  assert.deepEqual(completed.checked.map((entry) => entry.id), [mission.id]);
});

test("handles chapter-only activities and honest no-bounty shortfalls", () => {
  const one = fixture("missable", { details: "Chapter 1 only. Visit the balcony when the lesson appears." });
  const tooLate = planGoal(entryGoal(one.id), [one], [], { readiness: { chapter: 2 } });
  assert.equal(tooLate.next, null);
  assert.match(tooLate.specificReadiness.note, /only in Chapter 1/);
  const empty = planGoal(countGoal("bounty", 5), [one], []);
  assert.equal(empty.next, null);
  assert.equal(empty.shortfall, 5);
  assert.equal(empty.available, 0);
  const pending = fixture("bounty", { category: "bounty", x: null, y: null });
  assert.equal(planGoal(countGoal("bounty", 5), [pending], []).excluded.unlocated, 1);
});

test("retains separate same-publisher branches but counts exact aliases only once", () => {
  const first = fixture("branch-a", { category: "earbuds", title: "Aural Expert" });
  const second = fixture("branch-b", { category: "earbuds", title: "Tech Point (Tequesta)" });
  const alias = { ...first, id: "branch-a-mirror", source: first.source + "?utm_source=feed" };
  const bag = fixture("bag", { category: "bag" });
  const completed = [first.id, alias.id, bag.id];
  const plan = planGoal(countGoal("gear"), [first, second, alias, bag], completed);
  assert.equal(plan.count, 2);
  assert.equal(plan.next.row.id, second.id);
  assert.equal(plan.complete, false);
  const oldId = planGoal(countGoal("gear"), [first, second, alias, bag], [alias.id]);
  assert.equal(oldId.count, 1);
  assert.equal(oldId.checked[0].id, alias.id);
  const sameId = planGoal(countGoal("gear"), [first, { ...first }, alias], completed);
  assert.equal(sameId.count, 1);
});

test("shipped electronics store guides sharing a link remain distinct", () => {
  const guides = JSON.parse(readFileSync(new URL("../public/guides.json", import.meta.url), "utf8").replace(/^\uFEFF/, ""));
  const audio = guides.filter((row) => row.category === "earbuds");
  assert.ok(audio.length > 2 && new Set(audio.map((row) => row.source)).size < audio.length);
  const result = planGoal(countGoal("earbuds", audio.length), audio, audio.map((row) => row.id));
  assert.equal(result.count, audio.length);
  assert.equal(result.complete, true);
});

test("supports repeatable goal backup restore, same-ID edits and legacy journal no-op", () => {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, value),
  };
  const sample = fixture("sample");
  assert.deepEqual(exportGoals().goals, []);
  const key = addGoalForEntry(sample);
  assert.ok(key.startsWith("goal-"));
  assert.equal(addGoalForEntry(sample), key);
  const snapshot = exportGoals();
  const imported = importGoals({
    version: 1, readiness: { chapter: 3, character: "jason" },
    goals: [{ ...snapshot.goals[0], name: "Sunset route" }, { ...countGoal("bounty", 8), name: "Bounty list" }],
  });
  assert.equal(imported.goals.length, 2);
  assert.equal(imported.goals[0].name, "Sunset route");
  assert.deepEqual(importGoals(undefined), imported);
  assert.throws(() => importGoals({ ...imported, goals: [imported.goals[0], imported.goals[0]] }), /duplicate/);
  assert.throws(() => importGoals({ ...imported, goals: [{ ...countGoal("bounty"), target: 0 }] }), /target/);
  assert.deepEqual(exportGoals(), imported);
  delete globalThis.localStorage;
});
