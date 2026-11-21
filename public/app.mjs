import { AtlasMap } from "./map.mjs";
import {
  $,
  categories,
  icon,
  esc,
  link,
  fmt,
  located,
  evidence,
  itemBadge,
  decorate,
  json,
  post,
  toast,
  safeRead,
  save,
} from "./ui.mjs";
import {
  readJournal,
  writeJournal,
  blank,
  validate,
  download,
  exportCsv,
} from "./journal.mjs";
import { roadNetwork } from "./routing.mjs";
import {
  distance,
  angle,
  compass,
  length as gridDistance,
  routeDirections,
} from "./directions.mjs";
import { showSettings } from "./settings.mjs";
import { renderManual } from "./field-manual.mjs";
import { renderDiscovery } from "./source-view.mjs";
import { renderGoals, addGoalForEntry, exportGoals, importGoals } from "./goals.mjs";
import { missionEntries, mergeMissionReports, renderMissions, selectBuild } from "./missions.mjs";
import { showExport } from "./export-center.mjs";
import { initThemes, themeControls, bindThemeControls } from "./themes.mjs";
import { screenshotLocator, followPosition, following } from "./gps.mjs";

let journal;
try {
  journal = readJournal();
} catch {
  journal = blank();
  toast(
    "The saved journal could not be read. Import a backup from Field journal.",
  );
}
let state = { reports: [], sources: [], interval: 24, provider: {} },
  guides = [],
  missions = [],
  bundledMissions = [],
  landmarks = [],
  catalog = [],
  filtered = [],
  lookup = new Map(),
  selected = null,
  view = "map",
  category = "activities",
  type = "",
  limit = 25,
  journalTab = "remaining",
  journalLimit = 60,
  placement = null,
  voteRevision = 0,
  routeRevision = 0;
let layers = [],
  layer = "community",
  style = "original",
  voteOrigin = "",
  routeNote = "",
  loading = true,
  polling = false,
  changedActivityIds = new Set();
let directions = { total: 0, cues: [] };
const checklist = () => new Set(journal.done);
const route = () => (journal.routes.atlas ??= { origin: null, stops: [] });
initThemes();
decorate();
const map = new AtlasMap({
  select: (r) => inspect(r),
  pick: pickPoint,
  stack: openStack,
});
function open(title, html) {
  $("dialog-title").textContent = title;
  $("dialog-body").innerHTML = html;
  if (!$("dialog").open) $("dialog").showModal();
}
$("dialog-close").onclick = () => $("dialog").close();
$("dialog").addEventListener("click", (e) => {
  if (
    e.target === $("dialog") &&
    (e.clientX < $("dialog").getBoundingClientRect().left ||
      e.clientY < $("dialog").getBoundingClientRect().top ||
      e.clientX > $("dialog").getBoundingClientRect().right ||
      e.clientY > $("dialog").getBoundingClientRect().bottom)
  )
    $("dialog").close();
});
$("dialog").addEventListener("close", () => {
  $("dialog-body").replaceChildren();
});
function rebuild() {
  const done = checklist();
  const reports = combinedReports(state);
  missions = mergeMissionReports(bundledMissions, reports);
  catalog = [...guides, ...missions, ...reports.filter(r => r.category !== "mission"), ...journal.pins, ...landmarks].map(
    (r) => ({ ...r, done: done.has(r.id) }),
  );
  lookup = new Map(catalog.map((r) => [r.id, r]));
  const region = $("region-filter"), savedRegion = region.value;
  const regions = [...new Set(catalog.map(r => r.region).filter(Boolean))].sort((a,b) => a.localeCompare(b));
  region.replaceChildren(new Option("All regions", ""), ...regions.map(name => new Option(name,name)));
  if (regions.includes(savedRegion)) region.value = savedRegion;
  selected = lookup.get(selected?.id) || null;
  applyFilters();
}
function combinedReports(snapshot) {
  const items = new Map();
  for (const r of [...(snapshot.reports || []), ...(snapshot.bounty?.reports || [])]) {
    // Bounty Watch applies the more specific topic classification to shared sources.
    items.set(r.source || r.id, r);
  }
  return [...new Map([...items.values()].map(r => [r.id, r])).values()];
}
function updateState(s) {
  const oldIds = new Set(combinedReports(state).map((r) => r.id));
  if (!loading)
    for (const r of combinedReports(s))
      if (!oldIds.has(r.id)) changedActivityIds.add(r.id);
  state = s;
  const previous = selected;
  rebuild();
  if (previous && !selected) unselect();
  else if (selected && view === "map" && JSON.stringify(previous) !== JSON.stringify(selected)) inspect(selected, false);
  if (route().stops.some(s => s.entryId)) saveRoute(false, false);
  if (view === "sources" || view === "bounties") sourcesView();
  if (view === "journal") journalView();
  if (view === "goals") goalsView();
  if (view === "missions") missionsView();
}
function applyFilters() {
  const query = $("search").value.trim().toLowerCase(),
    words = query.split(/\s+/).filter(Boolean),
    region = $("region-filter").value,
    proof = $("evidence-filter").value,
    prog = $("progress-filter").value;
  filtered = catalog.filter(
    (r) =>
      (category === "all" ||
        (category === "activities" && r.category !== "landmark") ||
        category === r.category) &&
      (!type || r.type === type) &&
      (!region || r.region === region) &&
      (!proof || (proof === "mapped" ? located(r) : proof === "pending" ? !located(r) : r.confidence === proof || r.verification?.status === proof)) &&
      (prog === "all" || (prog === "done") === r.done) &&
      (!words.length || words.every(word =>
        [r.title, ...(r.aliases || []), r.region, r.type, r.category, categories[r.category]?.[0], r.id, r.details]
          .join(" ")
          .toLowerCase()
          .includes(word))),
  );
  if (words.length) {
    function relevance(r) {
      const title = r.title.toLowerCase();
      if (title === query) return 4;
      if (title.startsWith(query)) return 3;
      if (title.includes(query)) return 2;
      return words.some(word => title.includes(word)) ? 1 : 0;
    }
    filtered.sort((a,b) => relevance(b) - relevance(a));
  }
  const origin = route().origin;
  $("nearest-first").disabled = !origin;
  if ($("nearest-first").checked && origin) {
    const away = r => located(r) ? gridDistance(origin,r) : Infinity;
    filtered.sort((a,b) => away(a) - away(b));
  }
  if (selected && !filtered.some((r) => r.id === selected.id)) unselect();
  const counts = {};
  catalog.forEach((r) => (counts[r.category] = (counts[r.category] || 0) + 1));
  $("categories").innerHTML =
    '<div class="layer-scope"><button data-cat="all" aria-pressed="' +
    (category === "all") +
    '">All layers</button><button data-cat="activities" aria-pressed="' +
    (category === "activities") +
    '">Activities</button></div>' +
    Object.entries(categories)
      .map(
        ([id, [name, , color]]) =>
          '<button class="cat-btn" data-cat="' +
          id +
          '" aria-pressed="' +
          (category === id) +
          '" style="--cat:' +
          color +
          '">' +
          icon(id) +
          "<span>" +
          name +
          '</span><span class="qty">' +
          fmt(counts[id] || 0) +
          "</span></button>",
      )
      .join("") +
    (category === "landmark"
      ? '<label class="type-filter"><span class="fieldlabel">Building or place type</span><select id="place-type"><option value="">All place types</option>' +
        [...new Set(landmarks.map((r) => r.type))]
          .filter(Boolean)
          .sort()
          .map(
            (t) =>
              "<option " +
              (type === t ? "selected" : "") +
              ">" +
              esc(t) +
              "</option>",
          )
          .join("") +
        "</select></label>"
      : "");
  if ($("place-type"))
    $("place-type").onchange = (e) => {
      type = e.target.value;
      limit = 25;
      applyFilters();
    };
  $("map-stage").classList.toggle(
    "filtered",
    !["activities", "all"].includes(category) || !!query || !!region || !!proof || prog !== "all",
  );
  map.entries = filtered;
  map.selected = selected;
  map.queue();
  $("done-count").textContent = fmt(catalog.filter((r) => r.done).length);
  $("result-count").textContent = fmt(filtered.length);
  const mapped = filtered.filter(located).length;
  $("map-summary").textContent =
    fmt(mapped) +
    " mapped · " +
    fmt(filtered.length - mapped) +
    " awaiting a pin";
  $("results").innerHTML =
    filtered.slice(0, limit).map(rowButton).join("") ||
    '<div class="empty"><strong>No matching entries</strong>' +
      (Object.hasOwn(categories, category) && !counts[category]
        ? "No sourced " +
          esc(categories[category]?.[0]?.toLowerCase() || "") +
          " entries yet. New reports appear here after refresh."
        : "Try another layer, search term or checklist status.") +
      (Object.hasOwn(categories, category)
        ? '<div class="actions"><button class="action" id="record-pin">Add a personal ' +
          esc(categories[category][1].toLowerCase()) +
          " pin</button></div>"
        : "") +
      "</div>";
  if ($("record-pin")) $("record-pin").onclick = () => newPin();
  $("open-watch").hidden = category !== "bounty";
  $("more").hidden = filtered.length <= limit;
}
function rowButton(r) {
  return (
    '<button class="result ' +
    (selected?.id === r.id ? "selected" : "") +
    '" data-id="' +
    esc(r.id) +
    '">' +
    itemBadge(r.category) +
    '<span><span class="name">' +
    esc(r.title) +
    "</span><small>" +
    esc(r.region) +
    (located(r) && route().origin ? " · " + distance(gridDistance(route().origin,r)) : "") +
    (r.done ? " · Completed" : !located(r) ? " · Unmapped" : "") +
    "</small></span></button>"
  );
}
function resetFilters() {
  category = "all";
  type = "";
  limit = 25;
  $("search").value = "";
  $("progress-filter").value = "all";
  $("region-filter").value = $("evidence-filter").value = "";
  $("nearest-first").checked = false;
  applyFilters();
}
$("categories").onclick = (e) => {
  const b = e.target.closest("[data-cat]");
  if (!b) return;
  category = b.dataset.cat;
  type = "";
  limit = 25;
  applyFilters();
};
$("reset-filters").onclick = resetFilters;
$("search").oninput = () => {
  limit = 25;
  applyFilters();
};
$("progress-filter").onchange = () => {
  limit = 25;
  applyFilters();
};
$("region-filter").onchange = $("evidence-filter").onchange = $("progress-filter").onchange;
$("nearest-first").onchange = $("progress-filter").onchange;
$("more").onclick = () => {
  limit += 40;
  applyFilters();
};
$("results").onclick = (e) => {
  const b = e.target.closest("[data-id]");
  if (b) inspect(lookup.get(b.dataset.id));
};
$("mobile-index").onclick = () => {
  $("world").classList.toggle("index-open");
  const active = $("world").classList.contains("index-open");
  $("mobile-index").setAttribute("aria-expanded", String(active));
  $("mobile-index").firstElementChild.innerHTML = icon(active ? "x" : "layers");
  $("mobile-index").lastChild.textContent = $("world").classList.contains(
    "index-open",
  )
    ? "Close index"
    : "Map index";
};
function closeIndex() {
  $("world").classList.remove("index-open");
  $("mobile-index").setAttribute("aria-expanded","false");
  $("mobile-index").firstElementChild.innerHTML = icon("layers");
  $("mobile-index").lastChild.textContent = "Map index";
}
function openStack(group) {
  open(
    "Nearby map entries",
    '<p class="hint">Choose a place to highlight it and open its details.</p>' +
      group.map(rowButton).join(""),
  );
  $("dialog-body").onclick = (e) => {
    const b = e.target.closest("[data-id]");
    if (b) {
      $("dialog").close();
      inspect(lookup.get(b.dataset.id));
    }
  };
}
$("dialog").addEventListener("close", () => {
  $("dialog-body").onclick = null;
});
function unselect() {
  selected = null;
  map.selected = null;
  $("inspector").hidden = true;
  voteRevision++;
  map.queue();
}
function localCoord(r) {
  return located(r)
    ? "Grid " +
        Math.round(r.x * 13824 - 10240) +
        ", " +
        Math.round(10496 - r.y * 19456)
    : "Location pending";
}
function inspect(r, focus = true) {
  if (!r) return;
  selected = r;
  map.selected = r;
  closeIndex();
  if (focus && located(r)) map.focus(r, Math.max(map.zoom, 3.15));
  map.queue();
  const cat = categories[r.category] || categories.landmark,
    el = $("inspector");
  el.hidden = false;
  el.style.setProperty("--cat", cat[2]);
  el.scrollTop = 0;
  el.innerHTML =
    '<button class="icon-button" id="close-item" aria-label="Close entry">' +
    icon("x") +
    '</button><div class="entry-type">' +
    icon(r.category) +
    esc(cat[1]) +
    "</div><h2>" +
    esc(r.title) +
    "</h2>" +
    '<div class="meta-line">' +
    esc(r.region) +
    " · " +
    esc(evidence(r)) +
    '</div><p class="entry-text">' +
    esc(r.details || "Personal map location.") +
    "</p>" +
    (r.collectibleSet ? '<div class="collection-progress"><b>' + esc(r.collectibleSet) + '</b><span>' +
      catalog.filter(item => item.collectibleSet === r.collectibleSet && item.done).length + ' / ' + esc(r.setSize) +
      ' sites completed · Site ' + esc(r.collectibleIndex) + '</span></div>' : "") +
    (r.publishedAt ? '<p class="hint">Reported ' + esc(new Date(r.publishedAt).toLocaleDateString()) +
      (r.sourceName ? ' · ' + esc(r.sourceName) : '') + '</p>' : "") +
    (r.verification ? '<section class="claim-check" data-status="' + esc(r.verification.status) + '"><strong>' +
      esc(r.verification.label) + '</strong><p>' + esc(r.verification.reason) + '</p>' +
      '<div class="sources-inline">' + (r.verification.sources || []).map(s => link(s.url, s.name)).join(" ") +
      '</div></section>' : "") +
    ((r.steps || []).length
      ? '<details open><summary>How to complete</summary><ol class="steps">' +
        r.steps.map((s) => "<li>" + esc(s) + "</li>").join("") +
        "</ol></details>"
      : "") +
    '<p class="hint">' +
    esc(localCoord(r)) +
    (r.landmark ? " · " + esc(r.landmark) : "") +
    (r.nameOrigin === "counterpart"
      ? " · Name from real-world counterpart"
      : r.nameOrigin === "placeholder"
        ? " · Unnamed in source"
        : "") +
    "</p>" +
    (r.evidenceNote
      ? '<details><summary>Position evidence</summary><p class="hint">' +
        esc(r.evidenceNote) +
        "</p></details>"
      : "") +
    '<div class="sources-inline">' +
    link(r.source, r.sourceLabel || r.sourceName || "View source") +
    (r.secondarySource !== r.source
      ? link(r.secondarySource, "Supporting guide")
      : "") +
    (r.locationSource !== r.source
      ? link(r.locationSource, located(r) ? "Venue evidence" : "Area evidence")
      : "") +
    link(r.sourceImage, "Source screenshot") +
    "</div>" +
    (supportsImage(r) ? '<div class="evidence-media" id="evidence-media"></div>' : "") +
    (r.confidence !== "personal"
      ? '<div class="vote-box" id="vote-box"><span class="hint">Loading helpfulness votes…</span></div>'
      : "") +
    (located(r) ? '<div id="hero-distance" class="hero-distance"></div>' : "") +
    '<div class="actions"><button class="primary" id="complete">' +
    icon("check") +
    (r.done ? "Completed · undo" : "Mark complete") +
    "</button>" +
    (located(r)
      ? '<button class="action" id="navigate">' +
        icon("route") +
        "Route here</button>"
      : "") +
    "</div>" +
    (r.confidence === "personal" ? '<button class="action" id="edit-personal">Edit personal pin</button>' : "") +
    (hasMissionBuild(r) ? '<button class="action" id="open-build">Open mission build</button>' : "") +
    (r.category !== "landmark" && r.confidence !== "personal" ? '<button class="action" id="track-goal">' + icon("target") + ' Track as a goal</button>' : "") +
    '<button class="quiet share-card" id="share-field-card">' + icon("export") + ' Share a field card</button>' +
    '<button class="quiet" id="draft-report">' + icon("book") + ' Draft a community report</button>' +
    (located(r)
      ? '<button class="quiet" id="here">Set as my position</button>'
      : '<p class="hint">Directions unlock when a source identifies a map position.</p>');
  $("close-item").onclick = unselect;
  $("complete").onclick = () => toggleDone(r);
  if ($("open-build")) $("open-build").onclick = () => openBuild(r);
  if ($("track-goal")) $("track-goal").onclick = () => {
    if (addGoalForEntry(r)) switchView("goals");
    else toast("This entry cannot be added to your goals.");
  };
  $("draft-report").onclick = () => draftReport(r);
  updateHeroDistance();
  if ($("edit-personal")) $("edit-personal").onclick = () => newPin(r);
  $("share-field-card").onclick = () => exportCenter(r);
  if ($("navigate")) $("navigate").onclick = () => navigate(r);
  if ($("here"))
    $("here").onclick = () => {
      route().origin = { x: r.x, y: r.y, label: r.title };
      saveRoute();
      toast("Starting position set to " + r.title);
    };
  if (r.confidence !== "personal") showVotes(r);
  if ($("evidence-media")) showMedia(r);
  $("results")
    .querySelectorAll(".result")
    .forEach((b) => b.classList.toggle("selected", b.dataset.id === r.id));
}
function updateHeroDistance() {
  const box = $("hero-distance"), r = selected, origin = route().origin;
  if (!box || !located(r)) return;
  if (!origin) {
    box.innerHTML = icon("target") + '<div><b>Distance from your character</b><button class="quiet" id="set-hero-distance">Place my position on the map</button></div>';
    $("set-hero-distance").onclick = () => beginPlace({mode:"origin", inspectId:r.id}, "Click where your character is on the game map.");
    return;
  }
  const units = gridDistance(origin, r);
  box.innerHTML = icon("target") + '<div><b>' + (units < 1 ? "At your position" : esc(distance(units)) + " · " + esc(compass(angle(origin,r)))) +
    '</b><small>Direct distance from your character</small></div>';
}
function supportsImage(r) {
  if (r.discoveredVia && r.sourceId?.startsWith("auto-")) return true;
  try { return ["www.powerpyx.com","www.pushsquare.com","www.gamesradar.com","www.pcgamer.com"].includes(new URL(r.source).hostname); }
  catch { return false; }
}
async function showMedia(r) {
  const host = $("evidence-media");
  function draw(media) {
    if (!host.isConnected || selected?.id !== r.id) return;
    if (media && /^\/media\/[a-f0-9]{64}\.(png|jpeg|webp)$/.test(media.path)) {
      host.innerHTML = '<figure><a href="' + esc(media.path) + '" target="_blank" rel="noreferrer"><img loading="lazy" alt="' + esc(media.caption + " for " + r.title) + '" src="' + esc(media.path) + '"></a><figcaption>' +
        esc(media.caption) + ' · ' + link(media.source,"Publisher") + '</figcaption></figure>';
      return;
    }
    host.innerHTML = '<button class="quiet" type="button">Load source image</button>';
    host.firstElementChild.onclick = async e => {
      const button = e.currentTarget;
      button.disabled = true; button.textContent = "Looking for source image…";
      try {
        const result = await post("/api/media", {entry:r.id});
        if (result.media) draw(result.media);
        else button.textContent = "No cached image available · see source above";
      } catch { button.textContent = "Image lookup unavailable · retry"; button.disabled = false; }
    };
  }
  try { draw((await json("/api/media?entry=" + encodeURIComponent(r.id))).media); }
  catch { draw(null); }
}
function toggleDone(r) {
  const done = checklist();
  if (done.has(r.id)) done.delete(r.id);
  else done.add(r.id);
  journal.done = [...done];
  writeJournal(journal);
  rebuild();
  if (selected?.id === r.id) inspect(selected, false);
  if (view === "journal") journalView();
  if (view === "goals") goalsView();
  if (view === "missions") missionsView();
  toast(done.has(r.id) ? "Marked complete." : "Moved to remaining.");
}
let playerId = safeRead("ballot-id", null);
if (!playerId) {
  playerId = crypto.randomUUID();
  save("ballot-id", playerId);
}
function percent(up, down) {
  const n = up + down;
  return n
    ? Math.round((100 * up) / n) +
        "% positive · " +
        fmt(n) +
        (n === 1 ? " vote" : " votes")
    : "No votes yet";
}
async function showVotes(r) {
  const rev = ++voteRevision,
    base = voteOrigin + "/api/votes";
  const ext = r.communityVotes;
  const external = ext
    ? '<div class="vote-caption">GitHub reactions · ' +
      esc(percent(ext.up, ext.down)) +
      " " +
      link(ext.url, "View") +
      "</div>"
    : "";
  function draw(v) {
    const box = $("vote-box");
    if (!box || rev !== voteRevision || selected?.id !== r.id) return;
    box.innerHTML =
      '<div class="vote-row"><span class="vote-label">Was this helpful?</span><div class="vote-buttons"><button id="upvote" aria-pressed="' +
      (v.mine === 1) +
      '">Yes</button><button id="downvote" aria-pressed="' +
      (v.mine === -1) +
      '">No</button></div></div><div class="vote-caption">' +
      (voteOrigin ? "Shared atlas" : "This atlas") +
      " · " +
      esc(percent(v.up, v.down)) +
      "</div>" +
      external;
    async function cast(choice) {
      $("upvote").disabled = $("downvote").disabled = true;
      try {
        draw(
          await post(base, {
            id: r.id,
            player: playerId,
            vote: v.mine === choice ? 0 : choice,
          }),
        );
      } catch (e) {
        draw(v);
        toast(e.message);
      }
    }
    $("upvote").onclick = () => cast(1);
    $("downvote").onclick = () => cast(-1);
  }
  try {
    draw(
      await json(base + "?id=" + encodeURIComponent(r.id), {
        headers: { "X-Atlas-Player": playerId },
      }),
    );
  } catch {
    if (rev === voteRevision && $("vote-box"))
      $("vote-box").innerHTML =
        '<p class="hint">Atlas votes are unavailable.</p>' + external;
  }
}
function reveal(r) {
  if (!r) return;
  switchView("map");
  if (!filtered.some((o) => o.id === r.id)) resetFilters();
  inspect(r);
}
function switchView(name) {
  if (!["map", "journal", "goals", "missions", "sources", "bounties", "manual"].includes(name)) name = "map";
  view = name;
  const navName = name === "bounties" ? "sources" : name;
  closeIndex();
  $("world").hidden = name !== "map";
  $("sheet").hidden = name === "map";
  document.querySelectorAll("[data-view]").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === navName);
    b.setAttribute("aria-current", b.dataset.view === navName ? "page" : "false");
  });
  if (name === "journal") journalView();
  else if (name === "goals") goalsView();
  else if (name === "missions") missionsView();
  else if (navName === "sources") sourcesView();
  else if (name === "manual") renderManual($("sheet-content"), {
    openEntry: id => reveal(lookup.get(id)),
    openMap: () => switchView("map"),
    openSources: () => switchView("sources"),
    openBountyWatch: () => switchView("bounties"),
    openJournal: () => switchView("journal"),
    openGoals: () => switchView("goals"),
    openMissions: () => switchView("missions"),
    openRoutes: () => { switchView("map"); routePanel(); },
    openExport: () => { switchView("journal"); exportCenter(); },
    openCategory: id => {
      switchView("map"); resetFilters(); category = id; applyFilters();
      if (innerWidth <= 650) $("mobile-index").click();
    },
  });
  else map.queue();
  if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
  $("sheet").scrollTop = 0;
}
document
  .querySelectorAll("[data-view]")
  .forEach((b) => (b.onclick = () => switchView(b.dataset.view)));
document.querySelector(".brand").onclick = (e) => {
  e.preventDefault();
  switchView("map");
};
$("open-journal").onclick = () => switchView("journal");
$("open-watch").onclick = () => switchView("bounties");
window.addEventListener("hashchange", () => { if (!loading) switchView(location.hash.slice(1)); });
$("settings").onclick = () => showSettings(state, open, updateState);
function goalsView() {
  renderGoals($("sheet-content"), {
    catalog, done: checklist(), origin: route().origin, openEntry: row => hasMissionBuild(row) ? openBuild(row) : reveal(row),
    routeTo: row => { reveal(row); navigate(row); },
    toggleDone, openBounties: () => switchView("bounties"),
  });
}

function hasMissionBuild(row) {
  return row.category === "mission" && missions.some(mission => mission.id === row.id);
}

function openBuild(row) {
  selectBuild(row.id);
  switchView("missions");
}

function missionsView() {
  renderMissions($("sheet-content"), {
    missions, done: checklist(), builds: journal.builds || {}, toggleDone, openMap:reveal,
    routeTo: row => { reveal(row); navigate(row); },
    track: row => { if (addGoalForEntry(row)) switchView("goals"); },
    step: (row, step, checked) => {
      const builds = journal.builds ??= {}, done = new Set(builds[row.id] || []);
      if (checked) done.add(step); else done.delete(step);
      if (done.size) builds[row.id] = [...done]; else delete builds[row.id];
      writeJournal(journal);
    },
  });
}

function draftReport(row) {
  open("Draft a community report",
    '<label class="form-field"><span>What did you find, or what needs correcting?</span><textarea id="report-observation" maxlength="1100" rows="5"></textarea></label>' +
    (located(row) && row.space !== "poster" ? '<label class="checkline"><input type="checkbox" id="report-grid">I checked this point in-game. Include its grid as my reported location.</label>' : "") +
    '<p class="hint">The draft includes the activity name, its original source when available, and your observation. You can edit it on GitHub before posting.</p>' +
    '<button class="primary" id="prepare-report">Prepare GitHub draft</button><div id="report-preview" aria-live="polite"></div>');
  $("prepare-report").onclick = () => {
    const observation = $("report-observation").value.trim();
    if (!observation) { $("report-observation").focus(); return; }
    const url = new URL("https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker/issues/new");
    url.searchParams.set("title", ("GTA VI " + categories[row.category][1] + " · " + row.title).slice(0,180));
    const body = [observation, "Activity: " + row.title, "Area: " + (row.region || "Unknown")];
    if (row.source) body.push("Original source: " + row.source);
    if (located(row) && row.space !== "poster") body.push("Atlas reference: " + localCoord(row) + " (" + evidence(row) + ")");
    if ($("report-grid")?.checked) body.push("ATLAS_GTA6_GRID=(" + Math.round(row.x * 13824 - 10240) + "," + Math.round(10496 - row.y * 19456) + ")");
    url.searchParams.set("body", body.join("\n\n"));
    $("report-preview").innerHTML = '<p>' + link(url.href,"Review draft on GitHub") + '</p>';
    $("report-observation").oninput = () => $("report-preview").replaceChildren();
    if ($("report-grid")) $("report-grid").onchange = () => $("report-preview").replaceChildren();
  };
}
function journalView() {
  const activities = catalog.filter(
      (r) => r.category !== "landmark" || r.confidence === "personal",
    ),
    done = catalog.filter((r) => r.done).length;
  let rows =
    journalTab === "done"
      ? catalog.filter((r) => r.done)
      : journalTab === "pins"
        ? catalog.filter((r) => r.confidence === "personal")
        : activities.filter((r) => !r.done);
  $("sheet-content").innerHTML =
    '<div class="kicker"><span class="rule"></span> PLAYER LOG</div><h1>Field journal</h1><p class="sheet-intro">Your checklist, personal map pins and exportable discoveries.</p>' +
    '<div class="statline"><strong>' +
    fmt(done) +
    "</strong> completed <strong>" +
    fmt(activities.filter((r) => !r.done).length) +
    "</strong> activities remaining</div>" +
    '<div class="sheet-actions"><button class="primary" id="new-pin">' +
    icon("plus") +
    ' Add personal pin</button><button class="action" id="export-center">Export center</button><button class="action" id="csv">' +
    icon("export") +
    ' Export filtered CSV</button><button class="action" id="loot-json">Export loot JSON</button><button class="action" id="backup">Back up journal</button><button class="action" id="restore">Import backup</button><input id="restore-file" type="file" accept=".json,application/json" hidden></div>' +
    '<p class="hint">Loot exports include ' +
    fmt(filtered.length) +
    " entries matching the map filters. Your journal backup includes completion, goals, personal pins and routes.</p>" +
    '<div class="subnav">' +
    [
      ["remaining", "Remaining activities"],
      ["done", "Completed"],
      ["pins", "My pins"],
    ]
      .map(
        ([id, s]) =>
          '<button data-tab="' +
          id +
          '" class="' +
          (id === journalTab ? "active" : "") +
          '">' +
          s +
          "</button>",
      )
      .join("") +
    "</div>" +
    rows
      .slice(0, journalLimit)
      .map(
        (r) =>
          '<div class="entryrow">' +
          itemBadge(r.category) +
          '<div class="grow"><span class="name">' +
          esc(r.title) +
          "</span><small>" +
          esc(r.region) +
          " · " +
          esc(evidence(r)) +
          '</small></div><button data-open="' +
          esc(r.id) +
          '">Details</button><button data-done="' +
          esc(r.id) +
          '">' +
          (r.done ? "Undo" : "Complete") +
          "</button></div>",
      )
      .join("") +
    (rows.length
      ? ""
      : '<div class="empty">No entries in this view yet.</div>') +
    (rows.length > journalLimit
      ? '<button class="more" id="journal-more">Show more</button>'
      : "");
  $("new-pin").onclick = () => newPin();
  $("export-center").onclick = () => exportCenter();
  $("csv").onclick = () => exportCsv(filtered, checklist());
  $("loot-json").onclick = () => {
    const meta = layers.find((l) => l.key === "community").meta;
    download(
      "leonida-loot.json",
      JSON.stringify(
        {
          version: 1,
          exportedAt: new Date().toISOString(),
          coordinateFrame: meta.coordinateFrame,
          mapSource: meta.source,
          mapRevision: meta.revision,
          mapAttribution: meta.attribution,
          mapLicense: meta.licenseUrl,
          entries: filtered,
        },
        null,
        2,
      ),
      "application/json",
    );
  };
  $("backup").onclick = () =>
    download(
      "leonida-field-journal.json",
      JSON.stringify({ ...journal, goals: exportGoals() }, null, 2),
      "application/json",
    );
  $("restore").onclick = () => $("restore-file").click();
  $("restore-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      if (f.size > 6_000_000) throw Error("Backup is larger than 6 MB.");
      const backup = JSON.parse(await f.text());
      const incoming = validate(backup);
      importGoals(backup.goals);
      const pins = new Map(
        [...journal.pins, ...incoming.pins].map((r) => [r.id, r]),
      );
      journal = {
        version: 1,
        done: [...new Set([...journal.done, ...incoming.done])],
        pins: [...pins.values()],
        routes: { ...journal.routes, ...incoming.routes },
        builds: { ...(journal.builds || {}), ...Object.fromEntries(Object.entries(incoming.builds || {}).map(
          ([id, steps]) => [id, [...new Set([...(journal.builds?.[id] || []), ...steps])]])) },
      };
      writeJournal(journal);
      rebuild();
      saveRoute();
      journalView();
      toast("Backup merged. Saved route restored.");
    } catch (err) {
      toast(err.message);
    }
  };
  $("sheet-content")
    .querySelectorAll("[data-tab]")
    .forEach(
      (b) =>
        (b.onclick = () => {
          journalTab = b.dataset.tab;
          journalLimit = 60;
          journalView();
        }),
    );
  $("sheet-content")
    .querySelectorAll("[data-open]")
    .forEach((b) => (b.onclick = () => reveal(lookup.get(b.dataset.open))));
  $("sheet-content")
    .querySelectorAll("[data-done]")
    .forEach((b) => (b.onclick = () => toggleDone(lookup.get(b.dataset.done))));
  if ($("journal-more"))
    $("journal-more").onclick = () => {
      journalLimit += 60;
      journalView();
    };
}
function newPin(existing = null) {
  open(
    existing ? "Edit personal pin" : "Add a personal pin",
    '<form id="pin-form"><label class="form-field"><span>Location name</span><input id="pin-name" required maxlength="120" placeholder="Name this spot"></label><label class="form-field"><span>Category</span><select id="pin-cat">' +
      Object.entries(categories)
        .map(([id, n]) => '<option value="' + id + '">' + n[1] + "</option>")
        .join("") +
      '</select></label><label class="form-field"><span>Field note or reward</span><textarea id="pin-note" maxlength="2000" rows="3"></textarea></label><label class="form-field"><span>Completion steps · one per line</span><textarea id="pin-steps" maxlength="2000" rows="3"></textarea></label><button class="primary">Choose spot on map</button></form>',
  );
  if (Object.hasOwn(categories, category)) $("pin-cat").value = category;
  if (existing) {
    $("pin-name").value = existing.title;
    $("pin-cat").value = existing.category;
    $("pin-note").value = existing.details || "";
    $("pin-steps").value = (existing.steps || []).join("\n");
    const save = $("pin-form").querySelector("button");
    save.textContent = "Save changes";
    save.insertAdjacentHTML("afterend", ' <button class="action" value="move">Move pin on map</button>');
  }
  $("pin-form").onsubmit = (e) => {
    e.preventDefault();
    const title = $("pin-name").value.trim();
    if (!title) return;
    const note = {
      title,
      category: $("pin-cat").value,
      details: $("pin-note").value,
      space: "atlas",
      region: "Leonida",
      confidence: "personal",
      steps: $("pin-steps")
        .value.split(/\r?\n/)
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 12),
      id: existing?.id || "personal-" + crypto.randomUUID(),
    };
    $("dialog").close();
    switchView("map");
    if (existing && e.submitter?.value !== "move") {
      savePersonal({ ...existing, ...note });
      return;
    }
    beginPlace({ mode: "note", note }, "Choose the location for your pin.");
  };
}
function sourcesView() {
  renderDiscovery($("sheet-content"), state, view === "bounties", {
    switchView, isNew: id => changedActivityIds.has(id),
    update: (snapshot, watch) => updateState(watch ? { ...state, bounty: snapshot } : snapshot),
    openReport: r => {
      if (!r) return;
      const row = lookup.get(r.id) || catalog.find(item => item.source === r.source || item.liveSource === r.source);
      if (row) reveal(row);
      else { switchView("map"); inspect(r, false); }
    },
  });
}
function exportCenter(entry = null) {
  showExport(open, {
    catalog, filtered, done: checklist(), route: route(), track: map.track,
    directions, entry, meta: layers.find(l => l.key === "community").meta,
  });
}
function beginPlace(job, msg) {
  unselect();
  closeIndex();
  placement = job;
  map.placing = true;
  $("map-surface").classList.add("placing");
  $("instruction").hidden = false;
  $("instruction").innerHTML =
    esc(msg) + ' <button id="cancel-place">Cancel</button>';
  $("cancel-place").onclick = stopPlace;
  $("map-surface").focus();
}
function stopPlace() {
  placement = null;
  map.placing = false;
  $("map-surface").classList.remove("placing");
  $("instruction").hidden = true;
}
function savePersonal(item) {
  const index = journal.pins.findIndex(p => p.id === item.id);
  if (index < 0) journal.pins.unshift(item);
  else journal.pins[index] = item;
  writeJournal(journal);
  rebuild();
  reveal(lookup.get(item.id));
  toast("Personal pin saved.");
}
function pickPoint(p) {
  if (!placedOK(p) || !placement) return;
  const job = placement;
  stopPlace();
  if (job.mode === "note") {
    savePersonal({ ...job.note, ...p });
    return;
  }
  if (job.mode === "origin") {
    route().origin = { ...p, label: "My position" };
    if (job.goal) route().stops = [job.goal];
  } else {
    if (route().stops.length >= 100) {
      toast("A route can hold 100 stops.");
      return;
    }
    route().stops.push({
      ...p,
      label: "Waypoint " + (route().stops.length + 1),
    });
  }
  saveRoute(Boolean(job.goal));
  if (job.inspectId) inspect(lookup.get(job.inspectId), false);
  toast(job.mode === "origin" ? "Starting position set." : "Waypoint added.");
}
const placedOK = located;
function navigate(r) {
  const current = lookup.get(r.id);
  if (!located(current) || current.verification?.status === "review") {
    toast("This activity needs a supported location before routing.");
    return;
  }
  const goal = { x: current.x, y: current.y, label: current.title, entryId: current.id };
  if (!route().origin) {
    beginPlace(
      { mode: "origin", goal },
      "Choose your current in-game position.",
    );
    return;
  }
  route().stops = [goal];
  saveRoute(true);
  unselect();
}
async function saveRoute(notify = false, persist = true) {
  const stops = route().stops;
  const refreshed = stops.flatMap(stop => {
    if (!stop.entryId) return [stop];
    const row = lookup.get(stop.entryId);
    if (!located(row) || row.verification?.status === "review") return [];
    if (row.x === stop.x && row.y === stop.y && row.title === stop.label) return [stop];
    return [{ ...stop, x: row.x, y: row.y, label: row.title }];
  });
  if (!loading && (refreshed.length !== stops.length || refreshed.some((s,i) => s !== stops[i]))) {
    route().stops = refreshed;
    persist = true;
    if (refreshed.length < stops.length) toast("A route stop lost its location evidence and was removed.");
  }
  if (persist) writeJournal(journal);
  const rev = ++routeRevision,
    r = route();
  map.origin = r.origin;
  if (!loading) applyFilters();
  map.stops = r.stops;
  map.track = [];
  map.queue();
  routeNote = "";
  directions = { total: 0, cues: [] };
  updateRouteStatus();
  updateHeroDistance();
  if (!r.origin || !r.stops.length) return;
  let graph;
  try {
    graph = await roadNetwork();
  } catch {}
  if (rev !== routeRevision) return;
  let cur = r.origin,
    unlinked = 0,
    roadLegs = 0;
  const segments = [];
  for (const next of r.stops) {
    const path = graph?.path(cur, next);
    if (path?.length) {
      segments.push(
        { road: false, points: [cur, path[0]] },
        { road: true, points: path },
        {
          road: false,
          arrival: true,
          label: next.label,
          points: [path.at(-1), next],
        },
      );
      roadLegs++;
    } else {
      segments.push({
        road: false,
        direct: true,
        label: next.label,
        points: [cur, next],
      });
      unlinked++;
    }
    cur = next;
  }
  directions = routeDirections(segments);
  map.track = segments;
  map.queue();
  routeNote =
    distance(directions.total) +
    " estimated · " +
    roadLegs +
    " road " +
    (roadLegs === 1 ? "leg" : "legs") +
    (unlinked
      ? " · " + unlinked + " direct bearing" + (unlinked > 1 ? "s" : "")
      : "") +
    (unlinked
      ? " · no connected road trace for dashed legs."
      : " · dashed ends connect to the nearest traced road.");
  $("route-tools").title = routeNote;
  updateRouteStatus();
  if (notify) {
    map.fitPoints(segments.flatMap((s) => s.points));
    toast(routeNote);
  }
  if ($("route-summary")) routePanel();
}
function updateRouteStatus() {
  let s = $("route-status");
  if (!s) {
    s = document.createElement("div");
    s.id = "route-status";
    $("map-stage").append(s);
  }
  s.hidden = !route().origin || !route().stops.length || !routeNote;
  if (s.hidden) { s.replaceChildren(); return; }
  const target = route().stops[0];
  const immediate = directions.cues.find(c => c.at >= 0 && !c.text.startsWith("Join the mapped road"));
  s.innerHTML = '<div class="gps-heading">' + icon("route") + '<span>GPS · Next stop</span></div><strong>' + esc(target.label) +
    '</strong><div class="gps-readout"><b>' + distance(directions.total) + '</b> itinerary · ' + distance(gridDistance(route().origin,target)) +
    ' direct to stop</div>' + (immediate ? '<div class="gps-cue">' + esc(immediate.text) + '</div>' : "") +
    '<small>' + esc(routeNote) + '</small>';
}
function heroPanel() {
  const origin = route().origin;
  if (!origin) {
    beginPlace({mode:"origin"}, "Click where your character is on the game map.");
    return;
  }
  open("My position", '<div class="hero-distance">' + icon("target") + '<div><b>' + esc(origin.label) +
    '</b><small>' + esc(localCoord(origin)) + '</small></div></div><p class="hint">Move this point as your character travels. Open any mapped entry to see its distance and direction.</p>' +
    '<div class="actions"><button class="primary" id="center-hero">Show on map</button><button class="action" id="near-hero">Nearby activities</button><button class="action" id="move-hero">Move my position</button><button class="action" id="hero-route-options">GPS options</button></div>');
  $("center-hero").onclick = () => { $("dialog").close(); unselect(); map.focus(origin,Math.max(3,map.zoom)); };
  $("move-hero").onclick = () => { $("dialog").close(); beginPlace({mode:"origin"}, "Choose your character’s new location."); };
  $("hero-route-options").onclick = routePanel;
  $("near-hero").onclick = () => {
    $("dialog").close(); unselect(); resetFilters(); category = "activities";
    $("progress-filter").value = "remaining"; $("nearest-first").checked = true; applyFilters();
    if (innerWidth <= 650 && !$("world").classList.contains("index-open")) $("mobile-index").click();
  };
}
$("hero-position").onclick = heroPanel;
function routePanel() {
  const r = route();
  open(
    "Route planner",
    '<p class="hint">Place your position from the in-game map. Solid lines follow traced roads. Dashed lines show a bearing or the connection from a pin to the road.</p>' +
      '<div class="dialog-section"><h3>Starting position</h3><p>' +
      esc(
        r.origin
          ? r.origin.label + " · " + localCoord(r.origin)
          : "Choose a starting spot.",
      ) +
      '</p><div class="actions"><button class="action" id="place-start">Place my position</button><button class="action" id="use-screenshot">Locate from screenshot</button></div></div>' +
      '<details><summary>Live position feed</summary><p class="hint">Follow coordinates supplied by a local integration. The atlas can also use your manually placed position.</p><label class="checkline"><input id="follow-position" type="checkbox" ' +
      (following() ? "checked" : "") +
      '> Follow local coordinate feed</label><p class="hint" id="gps-feed-status">' +
      (following() ? "Listening on this computer." : "Feed paused.") +
      "</p></details>" +
      '<details><summary>Enter in-game grid coordinates</summary><form id="grid-form"><div class="grid-pair"><label class="form-field"><span>East / X</span><input id="grid-x" type="number" min="-10240" max="3584" step="any" required></label><label class="form-field"><span>North / Y</span><input id="grid-y" type="number" min="-8960" max="10496" step="any" required></label></div><button class="action">Update position</button></form></details>' +
      '<div class="dialog-section"><h3>Waypoints</h3><ol class="route-list">' +
      r.stops.map((s) => "<li>" + esc(s.label) + "</li>").join("") +
      '</ol><p class="hint" id="route-summary">' +
      esc(
        routeNote ||
          "Choose Route here on a location, or place waypoints on the map.",
      ) +
      "</p>" +
      (directions.cues.length
        ? "<details><summary>GPS directions · " +
          directions.cues.length +
          ' cues</summary><ol class="route-list">' +
          directions.cues
            .map(
              (c) =>
                "<li><b>" + distance(c.at) + "</b> · " + esc(c.text) + "</li>",
            )
            .join("") +
          "</ol></details>"
        : "") +
      (r.origin && r.stops.length
        ? '<div class="actions"><button class="action" id="arrived">Reached first stop</button><button class="action" id="show-route">Fit entire route</button></div>'
        : "") +
      '<div class="actions"><button class="primary" id="place-stop">Add waypoint</button><button class="action" id="undo-stop" ' +
      (!r.stops.length ? "disabled" : "") +
      '>Undo last stop</button><button class="action" id="clear-route">Clear route</button></div></div>',
  );
  $("place-start").onclick = () => {
    $("dialog").close();
    beginPlace({ mode: "origin" }, "Choose your current in-game position.");
  };
  $("use-screenshot").onclick = () =>
    screenshotLocator(open, (p) => {
      r.origin = { x: p.x, y: p.y, label: p.label };
      saveRoute();
      map.focus(p);
    });
  $("follow-position").onchange = (e) => {
    const enabled = e.target.checked;
    if ($("gps-feed-status"))
      $("gps-feed-status").textContent = enabled
        ? "Listening on this computer."
        : "Feed paused.";
    followPosition(
      enabled,
      (p) => {
        const active = route();
        active.origin = { x: p.x, y: p.y, label: p.label };
        const arrived =
          active.stops.length > 0 && gridDistance(p, active.stops[0]) <= 12;
        if (arrived) {
          const stop = active.stops.shift();
          toast("Reached " + stop.label);
        }
        saveRoute(false, arrived);
        map.focus(p, Math.max(3, map.zoom));
      },
      (s) => {
        if ($("gps-feed-status")) $("gps-feed-status").textContent = s;
      },
    );
  };
  $("grid-form").onsubmit = (e) => {
    e.preventDefault();
    r.origin = {
      x: (Number($("grid-x").value) + 10240) / 13824,
      y: (10496 - Number($("grid-y").value)) / 19456,
      label: "Grid position",
    };
    map.focus(r.origin);
    saveRoute();
    routePanel();
  };
  if ($("arrived"))
    $("arrived").onclick = () => {
      r.origin = r.stops.shift();
      saveRoute();
      routePanel();
      toast("Waypoint reached.");
    };
  if ($("show-route"))
    $("show-route").onclick = () => {
      map.fitPoints([
        r.origin,
        ...r.stops,
        ...map.track.flatMap((s) => s.points),
      ]);
      $("dialog").close();
    };
  $("place-stop").onclick = () => {
    $("dialog").close();
    beginPlace(
      { mode: r.origin ? "stop" : "origin" },
      r.origin
        ? "Choose the next waypoint."
        : "Place your starting position first.",
    );
  };
  $("undo-stop").onclick = () => {
    r.stops.pop();
    saveRoute();
    updateRouteStatus();
    routePanel();
  };
  $("clear-route").onclick = () => {
    journal.routes.atlas = { origin: null, stops: [] };
    saveRoute();
    updateRouteStatus();
    $("dialog").close();
    toast("Route cleared.");
  };
}
$("route-tools").onclick = routePanel;
function styles() {
  open(
    "Map appearance",
    '<h3>Map source</h3><div class="subnav">' +
      layers
        .map(
          (l) =>
            '<button class="' +
            (l.key === layer ? "active" : "") +
            '" data-layer="' +
            l.key +
            '">' +
            esc(l.label) +
            "</button>",
        )
        .join("") +
      '</div><p class="hint">' +
      esc(layers.find((l) => l.key === layer)?.meta.attribution || "") +
      "</p>" +
      '<div class="dialog-section"><h3>Map style</h3>' +
      [
        ["original", "Original colors"],
        ["night", "Dark mode"],
        ["contrast", "High contrast"],
      ]
        .map(
          ([id, label]) =>
            '<button data-style="' +
            id +
            '" class="style-option ' +
            (id === style ? "active" : "") +
            '"><span class="swatch ' +
            id +
            '"></span>' +
            label +
            (id === style ? " " + icon("check") : "") +
            "</button>",
        )
        .join("") +
      "</div>" + themeControls(),
  );
  bindThemeControls();
  $("dialog-body")
    .querySelectorAll("[data-layer]")
    .forEach(
      (b) =>
        (b.onclick = () => {
          setAppearance(b.dataset.layer, style);
          styles();
        }),
    );
  $("dialog-body")
    .querySelectorAll("[data-style]")
    .forEach(
      (b) =>
        (b.onclick = () => {
          setAppearance(layer, b.dataset.style);
          $("dialog").close();
        }),
    );
}
function setAppearance(k, s) {
  const info = layers.find((l) => l.key === k) || layers[0];
  if (!info) return;
  layer = info.key;
  style = ["original", "night", "contrast"].includes(s) ? s : "original";
  if (map.meta !== info.meta) {
    const old = map.meta && map.unproject(map.center),
      z = map.zoom;
    map.load(info.meta);
    if (old && located(old)) map.focus(old, z);
  }
  $("map-stage").dataset.style = style;
  $("map-stage").style.setProperty("--sea", info.sea);
  $("style-toggle").querySelector("span").textContent =
    style === "original"
      ? info.label
      : style === "night"
        ? "Dark map"
        : "High contrast";
  $("map-credit").innerHTML =
    '<span id="zoom-level">1×</span> · ' +
    link(info.meta.source, info.label) +
    " · " +
    (k === "poster"
      ? "© Rockstar Games · "
      : k === "game"
        ? "© Rockstar Games / PowerPyx · "
        : "") +
    "Pins " +
    link("https://map.gtadb.org", "GTADB & contributors") +
    " · " +
    link("https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0");
  save("appearance", { layer, style });
  map.queue();
}
$("style-toggle").onclick = styles;
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (placement) stopPlace();
    else if (!$("dialog").open) {
      closeIndex();
      unselect();
    }
  }
  if (
    e.key === "/" &&
    !$("dialog").open &&
    !["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)
  ) {
    e.preventDefault();
    switchView("map");
    if (innerWidth <= 650 && !$("world").classList.contains("index-open")) $("mobile-index").click();
    $("search").focus();
  }
});
async function boot() {
  const [data, positions, collectibles, places, missionData, missionPositions, m, st, community, ...optional] =
    await Promise.all([
      json("/guides.json"),
      json("/guide-positions.json"),
      json("/collectible-guides.json"),
      json("/landmarks.json"),
      json("/missions.json"),
      json("/mission-positions.json"),
      json("/map-meta.json"),
      json("/api/state"),
      json("/community.json"),
      ...["game", "day", "official"].map(async (k) => {
        try {
          const meta = await json("/" + k + "-map-meta.json");
          const res = await fetch(meta.image, { method: "HEAD" });
          return res.ok ? meta : null;
        } catch {
          return null;
        }
      }),
    ]);
  guides = data.map((r) => ({ ...r, ...(positions[r.id] || {}) }));
  const byId = new Map(guides.map(r => [r.id,r]));
  for (const r of collectibles) {
    const old = byId.get(r.id);
    byId.set(r.id, old && old.title !== r.title ? {...r,aliases:[old.title]} : r);
  }
  guides = [...byId.values()];
  landmarks = places;
  bundledMissions = missionEntries(missionData, byId, places, missionPositions);
  state = st;
  if (/^https:\/\/[a-zA-Z0-9.-]+(:\d+)?$/.test(community.origin))
    voteOrigin = community.origin;
  layers = [
    { key: "game", label: "In-game map", sea: "#51afca", meta: optional[0] },
    { key: "day", label: "Street map", sea: "#2f90af", meta: optional[1] },
    {
      key: "poster",
      label: "Rockstar poster",
      sea: "#dfd1b2",
      meta: optional[2],
    },
    { key: "community", label: "Community map", sea: "#2c68a6", meta: m },
  ].filter((l) => l.meta);
  const pref = safeRead("appearance", {});
  setAppearance(
    layers.some((l) => l.key === pref.layer) ? pref.layer : layers[0].key,
    pref.style || "original",
  );
  loading = false;
  rebuild();
  switchView(location.hash.slice(1) || "map");
  saveRoute(false, false);
  updateRouteStatus();
  let lastPoll = Date.now();
  const poll = async () => {
    if (document.hidden || polling) return;
    polling = true;
    try {
      const s = await json("/api/state");
      if (JSON.stringify(state) !== JSON.stringify(s)) {
        const before = state.reports.length;
        updateState(s);
        if (s.reports.length > before)
          toast(s.reports.length - before + " new community discoveries.");
      }
    } catch {
    } finally {
      polling = false;
    }
  };
  setInterval(() => {
    const interval = state.running || state.bounty?.running ? 3000 : 60000;
    if (!document.hidden && Date.now() - lastPoll >= interval) {
      lastPoll = Date.now();
      poll();
    }
  }, 3000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) poll();
  });
  window.addEventListener("storage", (e) => {
    if (view === "goals" && e.key?.startsWith("loot-atlas.goal")) goalsView();
    if (e.key !== "loot-atlas.journal") return;
    try {
      journal = readJournal();
      rebuild();
      saveRoute(false, false);
      if (view === "journal") journalView();
      else if (view === "goals") goalsView();
      else if (view === "missions") missionsView();
      else if (selected) inspect(selected, false);
    } catch {
      toast("Could not read the updated journal.");
    }
  });
}
boot().catch((err) => {
  const msg = "Could not load the atlas. " + err.message;
  $("map-summary").textContent = msg;
  toast(msg);
});
