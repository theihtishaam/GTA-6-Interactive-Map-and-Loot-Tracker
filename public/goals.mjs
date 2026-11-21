import { categories, esc, evidence, icon, link, located, safeRead, save } from "./ui.mjs";
import { length as gameDistance } from "./directions.mjs";

const KEY = "goals-v1";
const MAX_GOALS = 24;
const MAX_TARGET = 999;
const ACTIVITY_CATEGORIES = [...new Set([...Object.keys(categories), "mission"])].filter((key) => key !== "landmark");
export const GOAL_CATEGORIES = {
  activities: "All activities",
  gear: "Gear · earbuds, gloves and bags",
  ...Object.fromEntries(ACTIVITY_CATEGORIES.map((key) => [key, categories[key]?.[0] || "Missions"])),
};
const ID = /^[A-Za-z0-9_.-]{1,128}$/;
const LEVELS = [
  [1, "Chapter 1"], [2, "Chapter 2"], [3, "Chapter 3"], [4, "Chapter 4"],
  [5, "Chapter 5"], [6, "Story complete"],
];
const ACTIVE = new WeakMap();
const blank = () => ({ version: 1, readiness: { chapter: null, character: "any" }, goals: [] });
const byTitle = (a, b) => a.title.localeCompare(b.title, "en", { sensitivity: "base" }) || a.id.localeCompare(b.id);
const text = (value, limit = 160) => (typeof value === "string" ? value.trim().slice(0, limit) : "");
const validId = (id) => typeof id === "string" && ID.test(id);

function validSource(value) {
  try {
    const u = new URL(value);
    return u.protocol === "https:" && !u.username && !u.password;
  } catch {
    return false;
  }
}

function normalizeGoal(raw) {
  if (!raw || !validId(raw.id) || !["entry", "count"].includes(raw.type))
    throw Error("A goal has an invalid identifier or type.");
  const name = text(raw.name, 96);
  if (raw.type === "entry") {
    if (!validId(raw.entryId)) throw Error("Choose a sourced activity for this goal.");
    return { id: raw.id, type: raw.type, entryId: raw.entryId, name };
  }
  if (!Object.hasOwn(GOAL_CATEGORIES, raw.category))
    throw Error("Choose an activity category.");
  if (!Number.isInteger(raw.target) || raw.target < 1 || raw.target > MAX_TARGET)
    throw Error("A target must be between 1 and " + MAX_TARGET + ".");
  return { id: raw.id, type: raw.type, category: raw.category, target: raw.target, name };
}

function normalizeState(raw) {
  if (!raw || raw.version !== 1 || !Array.isArray(raw.goals) || raw.goals.length > MAX_GOALS)
    throw Error("Choose a valid Goals backup (version 1).");
  const rawReadiness = raw.readiness ?? blank().readiness;
  const { chapter, character } = rawReadiness;
  if (
    (chapter !== null && !LEVELS.some(([level]) => level === chapter)) ||
    !["any", "jason", "lucia"].includes(character)
  ) throw Error("The goal backup has an invalid story chapter or character.");
  const goals = raw.goals.map(normalizeGoal);
  if (new Set(goals.map((goal) => goal.id)).size !== goals.length)
    throw Error("The backup has duplicate goal IDs.");
  return { version: 1, readiness: { chapter, character }, goals };
}

export function exportGoals() {
  try {
    return normalizeState(safeRead(KEY, blank()));
  } catch {
    return blank();
  }
}

export function importGoals(raw) {
  const current = exportGoals();
  if (raw === undefined || raw === null) return current;
  const incoming = normalizeState(raw);
  const merged = new Map(current.goals.map((goal) => [goal.id, goal]));
  for (const goal of incoming.goals) merged.set(goal.id, goal);
  const combined = normalizeState({ ...incoming, goals: [...merged.values()] });
  save(KEY, combined);
  return combined;
}

function writeGoals(state) {
  save(KEY, normalizeState(state));
}

export function isGoalActivity(row) {
  return Boolean(row && validId(row.id) && text(row.title) &&
    ACTIVITY_CATEGORIES.includes(row.category) && row.confidence !== "personal" && validSource(row.source));
}

function newId() {
  const uuid = globalThis.crypto?.randomUUID?.();
  return "goal-" + (uuid || Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12));
}

export function addGoalForEntry(row) {
  if (!isGoalActivity(row)) return null;
  const state = exportGoals();
  const existing = state.goals.find((goal) => goal.type === "entry" && goal.entryId === row.id);
  if (existing) return existing.id;
  if (state.goals.length >= MAX_GOALS) return null;
  const goal = normalizeGoal({ id: newId(), type: "entry", entryId: row.id, name: "" });
  writeGoals({ ...state, goals: [...state.goals, goal] });
  return goal.id;
}

function activityIdentity(row, combineCategories) {
  // Different branches in one publisher guide have distinct titles or places.
  let uri;
  try {
    const parsed = new URL(row.source);
    // Publisher anchors and video IDs can identify different encounters. Ignore marketing query keys only.
    for (const name of [...parsed.searchParams.keys()]) {
      if (name.toLowerCase().startsWith("utm_") || ["fbclid", "gclid"].includes(name.toLowerCase()))
        parsed.searchParams.delete(name);
    }
    parsed.searchParams.sort();
    uri = parsed.href;
  } catch {
    return row.id;
  }
  return JSON.stringify([
    combineCategories ? "" : row.category, row.title.trim().toLocaleLowerCase("en").replace(/\s+/g, " "), uri,
    located(row) ? [row.x, row.y] : text(row.landmarkId || row.region),
  ]);
}

function catalogueEntries(catalog, done, combineCategories = false) {
  const byId = new Map();
  for (const row of catalog || []) if (isGoalActivity(row)) byId.set(row.id, row);
  const unique = new Map();
  for (const row of byId.values()) {
    const key = activityIdentity(row, combineCategories);
    const existing = unique.get(key);
    // Preserve completed state if a mirror ID is already checked off.
    if (!existing || (!done.has(existing.id) && (done.has(row.id) || (!located(existing) && located(row)))))
      unique.set(key, row);
  }
  return [...unique.values()];
}

function categorize(row, category) {
  if (category === "activities") return true;
  if (category === "gear") return ["earbuds", "gloves", "bag"].includes(row.category);
  return row.category === category;
}

function conditions(row) {
  const prereq = Array.isArray(row.prerequisite) ? row.prerequisite : [row.prerequisite];
  const notes = [row.details, ...prereq, ...(Array.isArray(row.steps) ? row.steps.slice(0, 10) : [])]
    .map((value) => text(value, 550)).join(" ");
  const exclusivity = /\b(?:only (?:available )?(?:in|during) chapter\s*(\d+)|chapter\s*(\d+)\s+only)\b/i.exec(notes);
  const earliest = /\b(?:requires chapter|(?:available|unlocks?|opens?) (?:after|from|in) chapter|chapter)\s*(\d+)\s+(?:only|exclusive|job|mission|story|unlock)|\b(?:requires chapter|(?:available|unlocks?|opens?) (?:after|from|in) chapter)\s*(\d+)\b/i.exec(notes);
  const characterMatch = /\b(?:only (?:playable |available )?(?:as|for) (Jason|Lucia)|(Jason|Lucia)[ -]only)\b/i.exec(notes);
  const specifiedCharacter = /^(Jason|Lucia)(?: only)?$/i.exec(text(row.character));
  const character = (specifiedCharacter?.[1] || characterMatch?.[1] || characterMatch?.[2] || "").toLowerCase();
  const only = Number(exclusivity?.[1] || exclusivity?.[2] || 0);
  const specifiedChapter = /^(?:chapter\s+)?(\d+)\b/i.exec(String(row.chapter ?? ""));
  const minimum = Number(specifiedChapter?.[1] || earliest?.[1] || earliest?.[2] || 0);
  const labels = [];
  if (only) labels.push("Chapter " + only + " only");
  else if (minimum) labels.push("See the Chapter " + minimum + " requirement in the guide");
  if (character) labels.push(character === "jason" ? "Jason only" : "Lucia only");
  if (/\brequires the Ultimate Edition\b|\bUltimate Edition only\b/i.test(notes))
    labels.push("Requires the Ultimate Edition");
  for (const label of prereq) if (text(label)) labels.push(text(label, 280));
  return { only, minimum, character, labels };
}

function readinessStatus(row, readiness) {
  const rule = conditions(row);
  if (readiness.chapter && rule.only && readiness.chapter !== rule.only)
    return { blocked: true, note: "Available only in Chapter " + rule.only + ".", labels: rule.labels };
  if (readiness.chapter && rule.minimum && readiness.chapter < rule.minimum)
    return { blocked: true, note: "The guide requires reaching Chapter " + rule.minimum + ".", labels: rule.labels };
  if (rule.character && readiness.character !== "any" && readiness.character !== rule.character)
    return { blocked: true, note: "This activity is for " + (rule.character === "jason" ? "Jason." : "Lucia."), labels: rule.labels };
  return { blocked: false, labels: rule.labels };
}

function caution(row) {
  if (row?.confidence === "area" || row?.precision === "area")
    return "Approximate area. Follow the source and find the actual interaction in the game.";
  if (row?.precision === "venue" || row?.precision === "landmark")
    return "Venue pin. The exact pickup or prompt may be inside or nearby.";
  if (row?.confidence === "reported" && row?.verification?.status !== "corroborated")
    return "Player-reported position. Check the source before travelling.";
  return "";
}

export function planGoal(input, catalog, completed, options = {}) {
  const goal = normalizeGoal(input);
  const done = new Set(completed || []);
  const readiness = { ...blank().readiness, ...options.readiness };
  const entries = goal.type === "entry"
    ? (catalog || []).filter((row) => row.id === goal.entryId && isGoalActivity(row)).slice(0, 1)
    : catalogueEntries((catalog || []).filter((row) => categorize(row, goal.category)), done,
        goal.category === "activities");
  const target = goal.type === "entry" ? 1 : goal.target;
  const checked = entries.filter((row) => done.has(row.id)).sort(byTitle);
  const count = checked.length;
  const remaining = Math.max(0, target - count);
  const pending = entries.filter((row) => !done.has(row.id));
  const choices = [];
  const excluded = { review: 0, unlocated: 0, prerequisites: 0, noInstructions: 0 };
  for (const row of pending) {
    if (row.verification?.status === "review") { excluded.review++; continue; }
    if (!located(row) || row.space === "poster") { excluded.unlocated++; continue; }
    const readinessCheck = readinessStatus(row, readiness);
    if (readinessCheck.blocked) { excluded.prerequisites++; continue; }
    const steps = Array.isArray(row.steps) ? row.steps.filter((step) => text(step)).slice(0, 8) : [];
    // A locator-only community excerpt can be routed as a lead when it contains actual source context.
    const details = text(row.details, 500);
    if (!steps.length && details.length < 30) { excluded.noInstructions++; continue; }
    choices.push({ row, steps, details, prerequisites: readinessCheck.labels, caution: caution(row) });
  }
  const fromPosition = located(options.origin);
  choices.sort((a, b) => {
    if (fromPosition) {
      const offset = gameDistance(options.origin, a.row) - gameDistance(options.origin, b.row);
      if (offset) return offset;
    } else if (Boolean(a.caution) !== Boolean(b.caution)) {
      return a.caution ? 1 : -1;
    }
    return byTitle(a.row, b.row);
  });
  const specific = goal.type === "entry" ? entries[0] || null : null;
  const specificReadiness = specific && readinessStatus(specific, readiness);
  return {
    goal, target, count, remaining, available: choices.length,
    shortfall: Math.max(0, remaining - choices.length), next: remaining ? choices[0] || null : null,
    complete: remaining === 0, excluded, specific, specificReadiness, checked,
  };
}

function readinessForm(profile) {
  return '<form class="goal-readiness" data-goal-readiness><fieldset><legend>Current playthrough</legend>' +
    '<label class="form-field"><span>Story progress</span><select name="chapter">' +
    '<option value="">Any chapter</option>' + LEVELS.map(([n, label]) =>
      '<option value="' + n + '"' + (profile.chapter === n ? " selected" : "") + ">" + esc(label) + "</option>").join("") +
    '</select></label><label class="form-field"><span>Character</span><select name="character">' +
    [["any", "Either character"], ["jason", "Jason"], ["lucia", "Lucia"]].map(([value, title]) =>
      '<option value="' + value + '"' + (profile.character === value ? " selected" : "") + ">" + title + "</option>").join("") +
    '</select></label></fieldset><p class="hint">These filters apply when the guide states a chapter or character requirement. Check each guide for mission unlocks.</p></form>';
}

function goalForm(edit, catalogue, limitReached, draft) {
  if (limitReached && !edit) return '<p class="goal-empty">You have ' + MAX_GOALS + ' goals. Remove one before adding another.</p>';
  const fields = draft || edit;
  const kind = fields?.type || "entry";
  const options = [...catalogue].sort(byTitle).map((row) =>
    '<option value="' + esc(row.id) + '"' + (fields?.entryId === row.id ? " selected" : "") + ">" +
      esc(row.title + (row.region ? " · " + row.region : "")) + "</option>").join("");
  const unresolved = edit?.entryId && !catalogue.some((row) => row.id === edit.entryId)
    ? '<option value="' + esc(edit.entryId) + '" selected>Saved activity currently unavailable</option>' : "";
  return '<form data-goal-form class="goal-editor"><h2>' + (edit ? "Edit goal" : "Add a goal") + '</h2>' +
    '<div class="goal-fields"><label class="form-field"><span>Goal type</span><select name="type">' +
    '<option value="entry"' + (kind === "entry" ? " selected" : "") + '>Specific mission or activity</option>' +
    '<option value="count"' + (kind === "count" ? " selected" : "") + '>Target count by category</option></select></label>' +
    '<label class="form-field"><span>Name (optional)</span><input name="name" maxlength="96" placeholder="Weekend loot run" value="' +
    esc(fields?.name || "") + '"></label></div>' +
    '<div data-entry-fields class="goal-fields"><label class="form-field"><span>Sourced activity</span><select name="entryId">' +
    '<option value="">Choose an activity</option>' + unresolved + options + '</select></label></div>' +
    '<div data-count-fields class="goal-fields"><label class="form-field"><span>Category</span><select name="category">' +
    Object.entries(GOAL_CATEGORIES).map(([key, label]) =>
      '<option value="' + key + '"' + ((fields?.category || "collectible") === key ? " selected" : "") + ">" +
      esc(label) + "</option>").join("") +
    '</select></label><label class="form-field"><span>Target</span><input type="number" name="target" min="1" max="' +
    MAX_TARGET + '" step="1" value="' + esc(fields?.target ?? 3) + '"></label></div>' +
    '<p class="hint" data-count-fields>Counts matching journal entries once each, including entries completed before the goal was created.</p>' +
    '<div class="actions"><button class="primary" type="submit">' + (edit ? "Save changes" : "Create goal") + '</button>' +
    (edit ? '<button type="button" class="action" data-goal-action="cancel">Cancel edits</button>' : "") +
    '<span data-goal-form-status role="status"></span></div></form>';
}

function shortfallText(plan) {
  if (plan.complete || !plan.shortfall) return "";
  if (plan.available) {
    return "There " + (plan.available === 1 ? "is 1 sourced stop" : "are " + plan.available + " sourced stops") +
      " you can route to now. " + plan.shortfall + (plan.shortfall === 1 ? " more is" : " more are") +
      " needed to finish this goal.";
  }
  const { review, unlocated, prerequisites, noInstructions } = plan.excluded;
  if (plan.specificReadiness?.blocked) return plan.specificReadiness.note;
  if (plan.goal.type === "entry" && !plan.specific) return "This activity is missing from the current catalogue.";
  if (!review && !unlocated && !prerequisites && !noInstructions)
    return "The atlas has no more eligible sourced activities for this goal.";
  return "There are no eligible map stops right now. " + [
    unlocated && unlocated + " awaiting a map position",
    review && review + " under review",
    prerequisites && prerequisites + " outside your selected playthrough",
    noInstructions && noInstructions + " without usable instructions",
  ].filter(Boolean).join(" · ") + ".";
}

function goalSteps(steps) {
  return steps.length ? '<details class="goal-steps"><summary>How to complete</summary><ol>' +
    steps.map((step) => "<li>" + esc(step) + "</li>").join("") + "</ol></details>" : "";
}

function goalRequirements(prerequisites) {
  return prerequisites?.length ? '<p class="goal-requirements"><strong>Prerequisites</strong> ' +
    esc(prerequisites.join(" · ")) + "</p>" : "";
}

function routePanel(plan, index) {
  if (!plan.next) {
    const source = plan.specific ? link(plan.specific.source, "Open source guide") : "";
    if (!source && plan.goal.category !== "bounty") return "";
    const textDetails = text(plan.specific?.details, 500);
    const steps = Array.isArray(plan.specific?.steps) ? plan.specific.steps.filter((step) => text(step)).slice(0, 8) : [];
    const notes = plan.specific && !plan.complete
      ? (textDetails ? "<p>" + esc(textDetails) + "</p>" : "") +
        goalRequirements(plan.specificReadiness?.labels) + goalSteps(steps)
      : "";
    return notes + '<div class="actions">' + source +
        (plan.specific ? '<button type="button" class="action" data-goal-action="view-specific" data-goal-plan="' +
          index + '">Activity details</button>' : "") +
        (plan.specific && !plan.complete ? '<button type="button" class="quiet" data-goal-action="finish-specific" data-goal-plan="' +
          index + '">Mark complete</button>' : "") +
        (plan.goal.category === "bounty" ? '<button type="button" class="action" data-goal-action="bounties">Open Bounty Watch</button>' : "") +
        "</div>";
  }
  const { row, details, steps, prerequisites, caution: warning } = plan.next;
  return '<section class="goal-next" aria-label="Next eligible stop">' +
    '<div class="goal-next-heading"><span class="goal-tag">Next eligible stop</span><h4>' + esc(row.title) +
    '</h4><p class="hint">' + esc([row.region, evidence(row)].filter(Boolean).join(" · ")) + "</p></div>" +
    (details ? "<p>" + esc(details) + "</p>" : "") +
    goalRequirements(prerequisites) +
    (warning ? '<p class="goal-caution">' + esc(warning) + "</p>" : "") +
    goalSteps(steps) +
    '<div class="actions"><button type="button" class="primary" data-goal-action="route" data-goal-plan="' + index +
    '">' + icon("route") + ' Route here</button><button type="button" class="action" data-goal-action="open" data-goal-plan="' + index +
    '">Map details</button><button type="button" class="quiet" data-goal-action="done" data-goal-plan="' + index +
    '">' + icon("check") + ' Mark complete</button>' + link(row.source, row.sourceLabel || row.sourceName || "Source") + "</div></section>";
}

function completedList(plan, index) {
  if (!plan.checked.length) return "";
  const visible = plan.checked.slice(0, 12);
  return '<details class="goal-steps"><summary>Completed entries · ' + plan.checked.length + '</summary><ul class="goal-checked">' +
    visible.map((row, position) => '<li><span>' + esc(row.title) + '</span>' +
      '<button type="button" class="quiet" data-goal-action="undo" data-goal-plan="' + index +
      '" data-completed-index="' + position + '" aria-label="Undo completion of ' + esc(row.title) + '">Undo</button></li>').join("") +
    '</ul>' + (plan.checked.length > visible.length ? '<p class="hint">More completions are available in Field journal.</p>' : "") +
    '</details>';
}

function goalCard(plan, index) {
  const goal = plan.goal;
  const label = goal.type === "entry" ? plan.specific?.title || "Saved activity" : GOAL_CATEGORIES[goal.category];
  const title = goal.name || (goal.type === "entry" ? label : "Complete " + goal.target + " · " + label);
  const ratio = Math.min(plan.count, plan.target);
  const deficit = shortfallText(plan);
  return '<article class="goal-card' + (plan.complete ? " goal-complete" : "") + '"><div class="goal-card-top"><div>' +
    '<h3>' + esc(title) + '</h3><p class="hint">' + esc((goal.name ? label + " · " : "") +
      (plan.complete ? "Goal complete" : plan.remaining + " remaining")) +
    '</p></div><div class="goal-edit-actions"><button type="button" class="quiet" data-goal-action="edit" data-goal-plan="' +
    index + '">Edit</button><button type="button" class="quiet" data-goal-action="remove" data-goal-plan="' + index +
    '">Remove</button></div></div><div class="goal-meter"><progress value="' + ratio + '" max="' + plan.target +
    '" aria-label="' + esc(title + " progress") + '"></progress><span>' + ratio + ' / ' + plan.target + '</span></div>' +
    (deficit ? '<p class="goal-empty">' + esc(deficit) + "</p>" : "") +
    routePanel(plan, index) + completedList(plan, index) + "</article>";
}

export function renderGoals(container, options) {
  const state = exportGoals();
  const interaction = ACTIVE.get(container) || { editId: null };
  ACTIVE.set(container, interaction);
  const edit = state.goals.find((goal) => goal.id === interaction.editId);
  const currentDone = new Set(options.done || []);
  const catalogue = catalogueEntries(options.catalog, currentDone);
  // The editor also includes an activity that already has a goal under an alias ID.
  const available = new Map(catalogue.map((row) => [row.id, row]));
  for (const row of options.catalog || []) {
    if (state.goals.some((goal) => goal.entryId === row.id) && isGoalActivity(row)) available.set(row.id, row);
  }
  const plans = state.goals.map((goal) =>
    planGoal(goal, options.catalog, currentDone, { origin: options.origin, readiness: state.readiness }));
  const active = document.activeElement;
  const focused = active?.closest("[data-goal-form]") && container.contains(active) ? active.name : null;
  const selection = focused === "name" ? [active.selectionStart, active.selectionEnd] : null;
  container.innerHTML = '<div class="kicker">' + icon("target") + ' FIELD JOURNAL</div><h1>Goals</h1>' +
    '<p class="sheet-intro">Choose a mission or set a target count. Goals use your journal checklist and suggest a sourced stop you can route to next.</p>' +
    readinessForm(state.readiness) + goalForm(edit, [...available.values()], state.goals.length >= MAX_GOALS, interaction.draft) +
    '<section aria-label="Saved goals" class="goal-saved"><h2>Saved goals</h2>' +
    (plans.length ? plans.map(goalCard).join("") : '<p class="goal-empty">You have no goals yet.</p>') + '</section>';

  const redraw = () => renderGoals(container, options);
  const readiness = container.querySelector("[data-goal-readiness]");
  readiness.onchange = (event) => {
    const fields = new FormData(readiness);
    writeGoals({
      ...state,
      readiness: { chapter: Number(fields.get("chapter")) || null, character: fields.get("character") },
    });
    redraw();
    container.querySelector("[data-goal-readiness] [name=" + (event.target.name === "character" ? "character" : "chapter") + "]").focus();
  };
  const form = container.querySelector("[data-goal-form]");
  if (form) {
    const kind = form.elements.namedItem("type");
    const act = form.elements.namedItem("entryId");
    const count = form.elements.namedItem("target");
    const show = () => {
      const entryMode = kind.value === "entry";
      for (const field of form.querySelectorAll("[data-entry-fields]")) field.hidden = !entryMode;
      for (const field of form.querySelectorAll("[data-count-fields]")) field.hidden = entryMode;
      act.required = entryMode;
      act.disabled = !entryMode;
      count.required = !entryMode;
      count.disabled = entryMode;
    };
    const captureDraft = () => {
      interaction.draft = Object.fromEntries(["type", "name", "entryId", "category", "target"].map((name) =>
        [name, form.elements.namedItem(name).value]));
    };
    form.oninput = captureDraft;
    kind.onchange = () => { show(); captureDraft(); };
    show();
    if (focused) {
      const replacement = form.elements.namedItem(focused);
      replacement?.focus({ preventScroll: true });
      if (selection && replacement) replacement.setSelectionRange(...selection);
    }
    form.onsubmit = (event) => {
      event.preventDefault();
      const fields = new FormData(form);
      try {
        const goal = normalizeGoal({
          id: edit?.id || newId(), type: fields.get("type"), name: fields.get("name"),
          entryId: fields.get("entryId"), category: fields.get("category"), target: Number(fields.get("target")),
        });
        if (goal.type === "entry" && !available.has(goal.entryId) && goal.entryId !== edit?.entryId)
          throw Error("This activity is not available in the sourced catalogue.");
        if (!edit && state.goals.length >= MAX_GOALS) throw Error("Remove a goal before creating another.");
        const next = edit ? state.goals.map((row) => row.id === edit.id ? goal : row) : [...state.goals, goal];
        writeGoals({ ...state, goals: next });
        interaction.editId = null;
        interaction.draft = null;
        redraw();
        container.querySelector(".goal-saved h2").setAttribute("tabindex", "-1");
        container.querySelector(".goal-saved h2").focus();
      } catch (error) {
        form.querySelector("[data-goal-form-status]").textContent = error.message;
      }
    };
  }

  for (const button of container.querySelectorAll("button[data-goal-action]")) {
    button.onclick = () => {
      const plan = plans[Number(button.dataset.goalPlan)];
      switch (button.dataset.goalAction) {
        case "edit":
          interaction.editId = plan.goal.id;
          interaction.draft = null;
          redraw();
          container.querySelector("[data-goal-form] [name=type]").focus();
          break;
        case "cancel":
          interaction.editId = null;
          interaction.draft = null;
          redraw();
          break;
        case "remove":
          writeGoals({ ...state, goals: state.goals.filter((goal) => goal.id !== plan.goal.id) });
          if (interaction.editId === plan.goal.id) {
            interaction.editId = null;
            interaction.draft = null;
          }
          redraw();
          break;
        case "open": options.openEntry?.(plan.next.row); break;
        case "view-specific": options.openEntry?.(plan.specific); break;
        case "route": options.routeTo?.(plan.next.row); break;
        case "done": options.toggleDone?.(plan.next.row); break;
        case "finish-specific": options.toggleDone?.(plan.specific); break;
        case "undo": options.toggleDone?.(plan.checked[Number(button.dataset.completedIndex)]); break;
        case "bounties": options.openBounties?.(); break;
      }
    };
  }
}
