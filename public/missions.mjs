import { esc, icon, link, located, safeRead, save } from "./ui.mjs";

const kinds = {story:"Story", optional:"Optional mission", side:"Side task", stranger:"Strangers & Freaks", discovery:"Discovered mission"};
const memory = {chapter:"", kind:"", status:"", query:"", current:""};
const guideIndex = "https://www.powerpyx.com/gta-6-full-walkthrough-all-missions/";
const chapterName = value => value == null || value === "" ? "Free roam / chapter unspecified" :
  String(value) === "0" || /^prologue$/i.test(value) ? "Prologue" :
  /^\d+$/.test(value) ? "Chapter " + value : String(value);

const venueKey = name => String(name || "").normalize("NFKC").trim().toLowerCase().replace(/[’‘]/g,"'");
const missionKey = name => venueKey(name).replace(/[^\p{L}\p{N} ]/gu,"").replace(/\s+/g," ");

export function mergeMissionReports(bundled, reports) {
  const byName = new Map(), bySource = new Map();
  const result = [...bundled];
  for (const [i, row] of bundled.entries()) {
    const labels = [row.title];
    if (row.actionLabel) labels.push(row.title + " (" + row.actionLabel + ")");
    for (const name of new Set(labels.map(missionKey)))
      byName.set(name, byName.has(name) ? null : i);
    if (row.source !== guideIndex) bySource.set(row.source, bySource.has(row.source) ? null : i);
  }
  const missionReports = reports.filter(row => row.category === "mission");
  // Apply corrections after enrichment, even if a feed returned its correction first.
  missionReports.sort((a, b) => Number(a.verification?.status === "review") - Number(b.verification?.status === "review"));
  for (const r of missionReports) {
    const name = r.missionName || r.title, chapter = r.chapter;
    const match = bySource.get(r.source) ?? byName.get(missionKey(name));
    if (Number.isInteger(match) && (chapter == null || bundled[match].chapter == null ||
        Number(chapter) === Number(bundled[match].chapter))) {
      const base = result[match];
      if (r.verification?.status === "review") {
        const affected = new Set([r.source, ...(r.verification.sources || []).map(s => s.url)]);
        if (affected.has(base.source) || (base.locationSource && affected.has(base.locationSource)))
          result[match] = {...base, x:null, y:null, verification:r.verification, liveSource:r.source};
        continue;
      }
      const updated = {...base, area:base.area || r.startingLocation, prerequisite:base.prerequisite || r.prerequisite,
        character:base.character || r.character};
      if (base.source === guideIndex || (!base.steps.length && r.steps?.length))
        Object.assign(updated, {source:r.source, sourceLabel:r.sourceName, liveSource:r.source,
          steps:r.steps?.length ? r.steps : base.steps});
      if (!located(base) && located(r) && base.chapter !== 0 && !["automatic","remote","unmarked"].includes(base.startMode))
        Object.assign(updated, {x:r.x, y:r.y, region:r.region || base.region, landmark:r.landmark || r.startingLocation,
          confidence:r.confidence || base.confidence, precision:r.precision, verification:r.verification,
          locationSource:r.source, liveSource:r.source});
      result[match] = updated;
      continue;
    }
    result.push({...r, title:name, chapterName:chapter == null ? "Community reports" : chapterName(chapter),
      kind:"discovery", kindLabel:"Discovered mission", area:r.startingLocation || (r.region === "Unresolved" ? null : r.region),
      notes:r.details, steps:r.steps || []});
  }
  return result;
}
export function missionEntries(rows, guides, landmarks, positions = {}) {
  const names = new Map();
  for (const place of landmarks) {
    if (place.nameOrigin !== "game" || ["region","district","natural"].includes(place.type) || !located(place)) continue;
    const key = venueKey(place.title);
    names.set(key, names.has(key) ? null : place);
  }
  return rows.map(mission => {
    const guide = guides.get(mission.guideId);
    const registration = positions[mission.id];
    const marker = ["automatic","remote","unmarked"].includes(mission.startMode) ? null :
      located(registration) ? registration : located(guide) ? guide :
      mission.chapter === 0 ? null : names.get(venueKey(mission.startVenue));
    const direct = mission.source !== guideIndex;
    return {...mission, category:"mission", confidence:"guide", chapterName:chapterName(mission.chapter),
      sourceLabel:mission.sourceLabel || "Mission walkthrough", kindLabel:kinds[mission.kind] || "Mission",
      region:mission.area || marker?.region || "Area pending",
      x:marker?.x ?? null, y:marker?.y ?? null, precision:marker?.precision || (marker ? "landmark" : null),
      locationSource:marker?.locationSource || marker?.source, landmark:marker?.landmark || marker?.title,
      sourceImage:marker?.sourceImage || mission.startImage,
      evidenceNote:marker?.evidenceNote || (marker ? "The guide identifies this venue as a starting area. Follow the in-game objective after arriving." : null),
      details:mission.notes || mission.area || (direct ? "Open the walkthrough for the mission sequence." : "This entry appears in the published mission index."),
      steps:mission.steps || []};
  });
}

export function selectBuild(id) {
  memory.current = id;
  memory.chapter = memory.kind = memory.status = memory.query = "";
  save("active-build", id);
}

function startMap(mission) {
  if (!located(mission)) return "";
  const w = 3456, h = 4864, x = mission.x * w, y = mission.y * h;
  const left = Math.max(0,Math.min(w-790,x-395)), top = Math.max(0,Math.min(h-246,y-123));
  return '<button type="button" class="build-start-map" id="mission-map" aria-label="Show the starting waypoint on the world map">' +
    '<svg aria-hidden="true" viewBox="' + [left,top,790,246].join(" ") + '" preserveAspectRatio="xMidYMid meet">' +
    '<image href="/map.webp" width="3456" height="4864"/><circle cx="' + x + '" cy="' + y + '" r="21" fill="#ffacd1" opacity=".38"/>' +
    '<circle cx="' + x + '" cy="' + y + '" r="10" fill="#ff94c5" stroke="#251825" stroke-width="4"/></svg>' +
    '<span>Starting waypoint · Community map ' + icon("arrow") + '</span></button>';
}

export function renderMissions(container, actions) {
  const {missions, done, builds} = actions;
  const options = (pairs, active) => pairs.map(([value,label]) => '<option value="' + esc(value) + '"' +
    (active === value ? " selected" : "") + '>' + esc(label) + '</option>').join("");
  const chapterOptions = [...new Set(missions.map(m => m.chapterName))];
  container.innerHTML = '<div class="mission-heading"><div><div class="kicker"><span class="rule"></span> STORY &amp; SIDE ACTIVITIES</div>' +
    '<h1>Missions</h1><p class="sheet-intro">Choose a mission to see its start, objectives and route options. Later chapters contain spoilers.</p></div>' +
    '<div class="mission-count"><b>' + missions.filter(m=>done.has(m.id)).length + ' / ' + missions.length + '</b><span>missions complete</span></div></div>' +
    '<div class="mission-layout"><section class="mission-index" aria-label="Mission catalogue"><label class="form-field"><span>Find a mission</span><input id="mission-search" type="search" placeholder="Name, contact or area" value="' + esc(memory.query) + '"></label>' +
    '<div class="mission-filters"><label class="form-field"><span>Chapter</span><select id="mission-chapter">' +
    options([["","All chapters"],...chapterOptions.map(c=>[c,c])],memory.chapter) + '</select></label>' +
    '<label class="form-field"><span>Type</span><select id="mission-kind">' + options([["","All types"],...Object.entries(kinds)],memory.kind) + '</select></label></div>' +
    '<label class="form-field"><span>Progress</span><select id="mission-status">' + options([["","All missions"],["open","Remaining"],["done","Completed"]],memory.status) + '</select></label>' +
    '<div class="mission-list" id="mission-list"></div></section><article id="mission-build" class="mission-build" aria-live="polite"></article></div>' +
    '<p class="hint">' + missions.filter(m=>m.coverage === "walkthrough").length + ' entries have actionable published guidance. ' +
    missions.filter(located).length + ' have a supported waypoint. Some missions unlock in parallel. ' + link(guideIndex,"Mission index") + '</p>';
  const el = id => container.querySelector("#"+id);
  function draw() {
    const q = memory.query.trim().toLowerCase();
    const rows = missions.filter(m => (!memory.chapter || m.chapterName === memory.chapter) && (!memory.kind || m.kind === memory.kind) &&
      (!memory.status || done.has(m.id) === (memory.status === "done")) &&
      [m.title,m.area,m.character,m.contact,m.actionLabel].filter(Boolean).join(" ").toLowerCase().includes(q));
    const id = memory.current || safeRead("active-build","");
    const current = rows.find(m=>m.id === id) || rows[0];
    el("mission-list").innerHTML = rows.map(m=>'<button class="mission-row" type="button" data-mission="' + esc(m.id) + '" aria-pressed="' +
      (m === current) + '"><span>' + esc(m.title) + '<small>' + esc(m.chapterName) + ' · ' + esc(m.kindLabel) + '</small></span>' +
      icon(done.has(m.id) ? "check" : "arrow") + '</button>').join("");
    const build = el("mission-build");
    if (!current) {
      build.innerHTML = '<h2>No matching missions</h2><p>Try another chapter, type or search term.</p>';
      return;
    }
    const m = current, checked = new Set(builds[m.id] || []);
    const requirement = " " + missionKey(m.prerequisite) + " ";
    const related = missions.filter(other => other.id !== m.id && requirement.includes(" " + missionKey(other.title) + " ") &&
      missions.filter(candidate => missionKey(candidate.title) === missionKey(other.title)).length === 1);
    const info = [["Starting area",m.area || m.landmark || "Start location pending"],["Playable as",m.character],
      ["Quest giver",m.contact],["In-game label",m.actionLabel],["Available after",m.prerequisite],["Reward",m.reward]].filter(pair => pair[1]);
    build.innerHTML = '<div class="kicker"><span class="rule"></span> MISSION BUILD</div><h2 tabindex="-1">' + esc(m.title) +
      '</h2><p class="build-meta">' + esc(m.chapterName) + ' · ' + esc(m.kindLabel) + '</p>' + startMap(m) + '<dl>' +
      info.map(([k,v])=>'<div><dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd></div>').join("") + '</dl>' +
      (related.length ? '<div class="build-unlocks" aria-label="Related prerequisite missions">' + related.map(prior =>
        '<button class="quiet" data-unlock="' + esc(prior.id) + '">' + icon(done.has(prior.id) ? "check" : "mission") +
        esc(prior.title) + (done.has(prior.id) ? " · completed" : " · open build") + '</button>').join("") + '</div>' : '') +
      (m.notes ? '<p class="build-note">' + esc(m.notes) + '</p>' : '') +
      '<div class="actions">' + (located(m) ? '<button class="primary" id="mission-route">' + icon("route") + ' Route to start</button>' : '') +
      '<button class="action" id="mission-goal">' + icon("target") + ' Track as a goal</button></div>' +
      (!located(m) ? '<p class="hint">' + (m.verification?.status === "review" ? esc(m.verification.reason) : m.chapter === 0 ?
        "The prologue begins when you start a new game." : m.startMode === "automatic" ? "The story starts this mission automatically once its requirements are met." :
        m.startMode === "remote" ? "Use the in-game contact or interaction listed in the guide to start this task." :
        "Use the in-game mission list for this start. The atlas has no verified waypoint for it yet.") + '</p>' : '') +
      (m.coverage === "reference" ? '<h3>Reference note</h3><p class="hint">The source names this task or describes its activity. A full walkthrough is still pending.</p>' : '<h3>Objectives</h3>') +
      (m.steps.length ? '<ol class="build-steps">' + m.steps.map((s,i)=>'<li><label><input type="checkbox" data-step="' +
      i + '"' + (checked.has(s) ? " checked" : "") + '><span>' + esc(s) + '</span></label></li>').join("") + '</ol>' :
      '<p class="hint">Detailed objectives are pending. Open the source for the available account.</p>') +
      '<div class="actions"><button class="action" id="mission-complete">' + icon("check") + (done.has(m.id) ? " Completed · undo" : " Mark mission complete") +
      '</button>' + link(m.source,"Open source guide") +
      (m.locationSource && m.locationSource !== m.source ? link(m.locationSource,"Waypoint source") : "") +
      (m.startImage ? link(m.startImage,"Starting map screenshot") : "") + '</div>';
    if (el("mission-route")) el("mission-route").onclick = () => actions.routeTo(m);
    if (el("mission-map")) el("mission-map").onclick = () => actions.openMap(m);
    build.querySelectorAll("[data-unlock]").forEach(button => button.onclick = () => {
      selectBuild(button.dataset.unlock);
      renderMissions(container,actions);
      el("mission-build").querySelector("h2")?.focus();
    });
    el("mission-goal").onclick = () => actions.track(m);
    el("mission-complete").onclick = () => actions.toggleDone(m);
    build.querySelectorAll("[data-step]").forEach(input => input.onchange = () => actions.step(m, m.steps[Number(input.dataset.step)], input.checked));
  }
  el("mission-list").onclick = event => {
    const row = event.target.closest("[data-mission]");
    if (row) { memory.current = row.dataset.mission; save("active-build",memory.current); draw();
      el("mission-build").querySelector("h2")?.focus({preventScroll:false}); }
  };
  for (const [id,key] of [["chapter","chapter"],["kind","kind"],["status","status"],["search","query"]]) {
    el("mission-"+id).addEventListener(id === "search" ? "input" : "change", e => { memory[key] = e.target.value; draw(); });
  }
  draw();
}
