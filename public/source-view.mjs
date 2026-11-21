import { $, esc, link, icon, evidence, itemBadge, fmt, located, post, toast } from "./ui.mjs";

const filters = { general: "", bounty: "" };
const evidenceFilters = [["", "All reports"], ["corroborated", "Corroborated"], ["single-source", "Single source"], ["review", "Needs review"]];
const references = [
  ["Mission order and objectives", [
    ["PowerPyx walkthrough index","https://www.powerpyx.com/gta-6-full-walkthrough-all-missions/"],
    ["PC Gamer story list","https://www.pcgamer.com/games/grand-theft-auto/gta-6-mission-list/"],
    ["GamesRadar+ mission list","https://www.gamesradar.com/games/grand-theft-auto/gta-6-mission-list/"],
    ["GTABase story tasks","https://www.gtabase.com/gta-6/missions/"],
    ["GTA BOOM walkthroughs","https://www.gtaboom.com/gta-6-story-mode-guide-ba58"],
  ]],
  ["Rewards and completion", [
    ["PowerPyx in-game progress database","https://www.powerpyx.com/gta-6-collectible-guide-progress-database/"],
    ["Push Square regional guides","https://www.pushsquare.com/guides/gta-6-guide"],
    ["Key Lento collectibles","https://www.pushsquare.com/guides/gta-6-key-lento-collectibles-and-secrets-walkthrough"],
    ["GamesRadar+ gameplay guides","https://www.gamesradar.com/games/grand-theft-auto/gta-guides-walkthroughs/"],
  ]],
  ["Map and game updates", [
    ["Rockstar’s Leonida poster","https://www.rockstargames.com/VI/media"],
    ["PowerPyx game map","https://www.powerpyx.com/gta-6-full-world-map-revealed/"],
    ["GTADB source map and data","https://github.com/rolux/gtadb.org"],
    ["Rockstar game support","https://support.rockstargames.com/VI"],
  ]],
];
function sourceDirectory(sources) {
  const ordered = [...sources].sort((a,b) => (b.score || 0) - (a.score || 0) || a.name.localeCompare(b.name));
  const rows = ordered.map(s => {
    const description = [s.coverage, s.rankReason, s.error || (s.status === "ok" ? fmt(s.seen) + " read · " + fmt(s.matched) + " matched" : "")].filter(Boolean).join(" · ");
    return '<div class="entryrow"><div class="grow"><span class="name">' + link(s.url,s.name) + '</span><small>' + esc(description) +
      (s.discoveredFrom ? ' · ' + link(s.discoveredFrom,"Discovery source") : '') + '</small></div><span class="source-status">' +
      esc(s.status === "manual" ? "Browse manually" : s.status) + '</span></div>';
  });
  return '<details class="watch-health"><summary>Public source directory · ' + sources.length + '</summary>' + rows.join("") + '</details>';
}
function date(v) { return v ? new Date(v).toLocaleString(undefined, {dateStyle:"medium",timeStyle:"short"}) : "Pending"; }

export function renderDiscovery(container, state, watch, controls) {
  const model = (watch ? state.bounty : state) || {};
  const sources = model.sources || [], reports = model.reports || [];
  const automated = sources.filter(s => s.status !== "manual");
  const failed = automated.filter(s => s.status === "error").length;
  const tab = watch ? "bounty" : "general";
  const name = watch ? "Bounty Watch" : "Live sources";
  const ready = !watch || Boolean(state.bounty);
  const sorted = [...reports].sort((a,b) => String(b.publishedAt || "").localeCompare(String(a.publishedAt || "")));
  const filtered = sorted.filter(r => !filters[tab] || r.verification?.status === filters[tab]);
  const feed = filtered.map(r =>
    '<div class="entryrow">' + itemBadge(r.category) + '<div class="grow"><span class="name">' + esc(r.title) +
    '</span><small>' + (controls.isNew(r.id) ? "New this visit · " : "") + esc(r.verification?.label || evidence(r)) + " · " +
    esc(r.sourceName || "Community report") + (located(r) ? " · Mapped" : " · Location pending") +
    '</small></div><button data-report="' + esc(r.id) + '">Details</button></div>').join("");
  container.innerHTML =
    '<div class="kicker"><span class="rule"></span> COMMUNITY DISCOVERY</div><h1>' + name + '</h1>' +
    '<div class="subnav" aria-label="Discovery feeds"><button id="general-tab" aria-pressed="' + !watch + '" class="' + (!watch ? "active":"") + '">All activities</button><button id="bounty-tab" aria-pressed="' + watch + '" class="' + (watch ? "active":"") + '">' + icon("bounty") + ' Bounty Watch</button></div>' +
    '<p class="sheet-intro">' + (watch ? "Find player reports of GTA VI bounty targets, wanted posters and payouts. Open the evidence before you travel." : "Find new heists, gear and rewards in public community reports and gameplay guides.") + '</p>' +
    '<div class="watch-stats"><div><b>' + fmt(automated.filter(s => s.status === "ok").length) + ' / ' + fmt(automated.length) + '</b><span>Feeds responding</span></div><div><b>' + fmt(reports.length) + '</b><span>Cached reports</span></div><div><b>' + (model.interval || 24) + 'h</b><span>Refresh interval</span></div></div>' +
    '<div class="watch-toolbar"><button class="primary" id="refresh" ' + (model.running || !ready ? 'disabled' : '') + '>' + icon("signal") + (model.running ? " Checking sources…" : " Check now") +
    '</button><label class="form-field"><span>Refresh schedule</span><select id="feed-interval">' +
    [6,12,24].map(n=>'<option value="' + n + '" ' + (n === (model.interval || 24) ? "selected" : "") + '>Every ' + n + ' hours</option>').join("") +
    '</select></label><button class="action" id="schedule"' + (ready ? "" : " disabled") + '>Save schedule</button></div>' +
    '<p class="hint">Last check ' + esc(date(model.lastRun)) + ' · Next check ' + esc(date(model.nextRun)) + '. Checks continue while the atlas server is running.</p>' +
    (model.cacheError ? '<p class="error">' + esc(model.cacheError) + '</p>' : '') +
    (failed ? '<p class="hint">' + fmt(failed) + ' feeds could not be reached. Saved reports stay available for the next check.</p>' : '') +
    '<h2>' + (watch ? "Bounty reports" : "Discovery feed") + '</h2>' +
    (reports.length ? '<label class="form-field"><span>Evidence level</span><select id="report-evidence">' + evidenceFilters.map(([id,title]) => '<option value="' + id + '"' + (filters[tab] === id ? ' selected' : '') + '>' + title + '</option>').join("") + '</select></label>' : '') +
    (feed || '<div class="source-summary"><strong>' + (reports.length ? "No reports match this evidence level" : watch ? "No qualifying bounty reports yet" : "No new reports in this feed yet") + '</strong><p class="hint">' + (reports.length ? "Choose All reports to see the complete feed." : watch ? "Leads without a position stay in this feed until a location can be established." : "Researched guides are already available in the map index.") + '</p></div>') +
    '<p>' + link("https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker/issues/new?template=location.md", "Contribute a location or correction") + '</p>' +
    sourceDirectory(sources) +
    '<h2>Research library</h2><p class="hint">Browse published references by topic. The directory above shows which feeds the scheduler reads.</p>' +
    references.map(([group,items]) => '<details class="watch-health"><summary>' + esc(group) + '</summary><ul>' +
      items.map(([title,url])=>'<li>' + link(url,title) + '</li>').join("") + '</ul></details>').join("");
  $("general-tab").onclick = () => controls.switchView("sources");
  $("bounty-tab").onclick = () => controls.switchView("bounties");
  if ($("report-evidence")) $("report-evidence").onchange = event => {
    filters[tab] = event.target.value;
    renderDiscovery(container, state, watch, controls);
  };
  async function change(button, path, payload, success) {
    button.disabled = true;
    try {
      const snapshot = await post((watch ? "/api/bounty/" : "/api/") + path, payload);
      controls.update(snapshot,watch);
      toast(success);
    } catch (e) { toast(e.message); button.disabled = false; }
  }
  $("refresh").onclick = e => change(e.currentTarget, "refresh", {}, name + " check started.");
  $("schedule").onclick = e => change(e.currentTarget, "settings", {interval:Number($("feed-interval").value)}, name + " schedule saved.");
  container.querySelectorAll("[data-report]").forEach(b => {
    b.onclick = () => controls.openReport(reports.find(r => r.id === b.dataset.report));
  });
}

