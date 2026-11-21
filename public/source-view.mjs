import { $, esc, link, icon, evidence, itemBadge, fmt, located, post, toast } from "./ui.mjs";

function sourceRow(s) {
  const manual = s.status === "manual";
  const summary = manual ? s.coverage : [
    s.coverage,
    s.rankReason,
    s.error || (s.status === "ok" ? fmt(s.seen) + " read · " + fmt(s.matched) + " matched" : ""),
  ].filter(Boolean).join(" · ");
  return '<div class="entryrow"><div class="grow"><span class="name">' + link(s.url, s.name) +
    '</span><small>' + esc(summary) + (s.discoveredFrom ? ' · ' + link(s.discoveredFrom,"Discovery source") : "") + '</small></div><span class="source-status ' +
    (s.status === "error" ? "bad" : "") + '">' + esc(manual ? "Browse" : s.status) + '</span></div>';
}
function date(v) { return v ? new Date(v).toLocaleString(undefined, {dateStyle:"medium",timeStyle:"short"}) : "Pending"; }

export function renderDiscovery(container, state, watch, controls) {
  const model = (watch ? state.bounty : state) || {};
  const sources = model.sources || [], reports = model.reports || [];
  const auto = sources.filter(s => s.status !== "manual");
  const discovered = auto.filter(s => s.sourceType === "feed" && s.qualified).sort((a,b) => (b.score || 0) - (a.score || 0));
  const candidates = auto.filter(s => s.sourceType === "feed" && !s.qualified);
  const scheduled = auto.filter(s => s.sourceType !== "feed");
  const manual = sources.filter(s => s.status === "manual");
  const name = watch ? "Bounty Watch" : "Live sources";
  const ready = !watch || Boolean(state.bounty);
  const sorted = [...reports].sort((a,b) => String(b.publishedAt || "").localeCompare(String(a.publishedAt || "")));
  const feed = sorted.slice(0,100).map(r =>
    '<div class="entryrow">' + itemBadge(r.category) + '<div class="grow"><span class="name">' + esc(r.title) +
    '</span><small>' + (controls.isNew(r.id) ? "New this visit · " : "") + esc(evidence(r)) + " · " +
    esc(r.sourceName || "Community report") + (located(r) ? " · Mapped" : " · Location pending") +
    '</small></div><button data-report="' + esc(r.id) + '">Details</button></div>').join("");
  container.innerHTML =
    '<div class="kicker"><span class="rule"></span> COMMUNITY DISCOVERY</div><h1>' + name + '</h1>' +
    '<div class="subnav" aria-label="Discovery feeds"><button id="general-tab" aria-pressed="' + !watch + '" class="' + (!watch ? "active":"") + '">All activities</button><button id="bounty-tab" aria-pressed="' + watch + '" class="' + (watch ? "active":"") + '">' + icon("bounty") + ' Bounty Watch</button></div>' +
    '<p class="sheet-intro">' + (watch ? "Find player reports of GTA VI bounty targets, wanted posters and payouts. Open the evidence before you travel." : "Find new heists, gear and rewards in public community reports and gameplay guides.") + '</p>' +
    '<div class="watch-stats"><div><b>' + auto.filter(s=>s.status === "ok").length + ' / ' + auto.length + '</b><span>Feeds responding</span></div><div><b>' + fmt(reports.length) + '</b><span>Cached reports</span></div><div><b>' + (model.interval || 24) + 'h</b><span>Refresh interval</span></div></div>' +
    '<div class="watch-toolbar"><button class="primary" id="refresh" ' + (model.running || !ready ? 'disabled' : '') + '>' + icon("signal") + (model.running ? " Checking sources…" : " Check now") +
    '</button><label class="form-field"><span>Refresh schedule</span><select id="feed-interval">' +
    [6,12,24].map(n=>'<option value="' + n + '" ' + (n === (model.interval || 24) ? "selected" : "") + '>Every ' + n + ' hours</option>').join("") +
    '</select></label><button class="action" id="schedule"' + (ready ? "" : " disabled") + '>Save schedule</button></div>' +
    '<p class="hint">Last check ' + esc(date(model.lastRun)) + ' · Next check ' + esc(date(model.nextRun)) + '. Checks continue while the atlas server is running.</p>' +
    (model.cacheError ? '<p class="error">' + esc(model.cacheError) + '</p>' : '') +
    '<h2>' + (watch ? "Bounty reports" : "Discovery feed") + '</h2>' +
    (feed || '<div class="source-summary"><strong>' + (watch ? "No qualifying bounty reports yet" : "No new reports in this feed yet") + '</strong><p class="hint">' + (watch ? "A report needs game-specific evidence. Leads without a position stay in this feed until a location can be established." : "Researched guides are already available in the map index.") + '</p></div>') +
    '<p>' + link("https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker/issues/new?template=location.md", "Contribute a location or correction") + '</p>' +
    (watch ? "" : '<h2>Discovered resources</h2><p class="hint">Feeds found through public search are ranked by recent reports that passed the atlas evidence checks.</p>' +
      (discovered.length ? discovered.map(sourceRow).join("") : '<p class="hint">No additional feeds have qualified in this run.</p>') +
      (candidates.length ? '<details class="watch-health"><summary>Other candidates checked · ' + candidates.length + '</summary>' + candidates.map(sourceRow).join("") + '</details>' : "")) +
    '<h2>Source coverage</h2><details class="watch-health" open><summary>Scheduled sources · ' + scheduled.length + '</summary>' + scheduled.map(sourceRow).join("") + '</details>' +
    (manual.length ? '<details class="watch-health" open><summary>Browse communities manually · ' + manual.length + '</summary>' + manual.map(sourceRow).join("") + '</details>' : "") +
    '<h2>Map references</h2><p class="hint">' + [link("https://www.rockstargames.com/VI/media", "Rockstar’s Leonida poster"),link("https://www.powerpyx.com/gta-6-full-world-map-revealed/","PowerPyx game map"),link("https://github.com/rolux/gtadb.org","GTADB cartography")].join(" · ") + '</p>';
  $("general-tab").onclick = () => controls.switchView("sources");
  $("bounty-tab").onclick = () => controls.switchView("bounties");
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

