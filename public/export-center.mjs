import { $, esc, link, fmt, located, evidence, categories, toast } from "./ui.mjs";
import { download, exportCsv } from "./journal.mjs";
import { activityType } from "./activity-types.mjs";
const repo = "https://github.com/theihtishaam/GTA-6-Interactive-Map-and-Loot-Tracker";
const choices = [
  ["filtered","Current map filters"], ["activities","All activities"], ["bounty","Bounties"],
  ["done","Completed entries"], ["personal","My personal pins"], ["all","Entire atlas"],
];
export function exportRows(scope, data) {
  switch (scope) {
    case "entry": return data.entry ? [data.entry] : [];
    case "all": return data.catalog;
    case "activities": return data.catalog.filter(r => r.category !== "landmark" || r.confidence === "personal");
    case "bounty": return data.catalog.filter(r => r.category === "bounty");
    case "done": return data.catalog.filter(r => data.done.has(r.id));
    case "personal": return data.catalog.filter(r => r.confidence === "personal");
    default: return data.filtered;
  }
}
function grid(r, meta) {
  if (!located(r) || r.space === "poster") return "";
  const f = meta.coordinateFrame;
  return Math.round(f.minX + r.x * (f.maxX - f.minX)) + ", " + Math.round(f.maxY - r.y * (f.maxY - f.minY));
}
function record(r, done, meta) {
  return {...r, activityType:activityType(r), status:done.has(r.id) ? "completed" : "remaining", evidence:evidence(r), gameGrid:grid(r, meta) || null};
}
function fieldMap(rows, image, data, includeRoute) {
  const {meta,track,route} = data;
  const w = 1000, h = w * meta.height / meta.width;
  function point(p) { return (p.x*w).toFixed(2) + "," + (p.y*h).toFixed(2); }
  const lines = includeRoute ? (track || []).map(s =>
    '<polyline points="' + s.points.filter(located).map(point).join(" ") + '" fill="none" stroke="' +
    (s.road ? "#ffd060" : "#fff") + '" stroke-width="3" ' + (s.road ? "" : 'stroke-dasharray="8 5"') + '/>').join("") : "";
  const marks = rows.map((r,i) => {
    if (!located(r) || r.space === "poster") return "";
    const x = r.x*w, y = r.y*h;
    const color = Object.hasOwn(categories,r.category) ? categories[r.category][2] : "#fff";
    return '<g><title>' + esc(r.title) + '</title><circle cx="' + x + '" cy="' + y + '" r="' + (rows.length>200 ? 3 : 7) +
      '" fill="' + color + '" stroke="#191c20" stroke-width="2"/>' + (rows.length <= 75 ? '<text x="' + (x+8) + '" y="' + (y+2) + '">' + (i+1) + '</text>' : "") + '</g>';
  }).join("");
  const stops = includeRoute ? [route.origin,...route.stops].filter(located).map((p,i) =>
    '<g transform="translate(' + point(p) + ')"><circle r="9" fill="#222" stroke="#ffd060"/><text x="11">' + (i===0?"Start":"Stop "+i) + '</text></g>').join("") : "";
  let viewBox = [0,0,w,h];
  if (data.entry && rows.length === 1 && located(rows[0]) && rows[0].space !== "poster" && !includeRoute) {
    const r = rows[0], width = 265, height = 167;
    viewBox = [Math.max(0,Math.min(w-width,r.x*w-width/2)),Math.max(0,Math.min(h-height,r.y*h-height/2)),width,height];
  }
  return '<svg aria-label="Leonida map with selected locations" role="img" viewBox="' + viewBox.join(" ") + '"><image width="' +
    w + '" height="' + h + '" href="' + image + '"/>' + lines + marks + stops + '</svg>';
}
export function fieldPack(rows, data, image, includeRoute, exportedAt) {
  const meta = data.meta;
  // Accept only an embedded copy of the bundled, openly licensed community map.
  if (!/^data:image\/webp;base64,[a-zA-Z0-9+/=]+$/.test(image)) throw Error("The offline map could not be embedded.");
  const shared = data.entry && rows.length === 1 && rows[0].id === data.entry.id;
  const heading = shared ? rows[0].title : "GTA 6 Loot Map · Field pack";
  const articles = rows.map((r,i) => {
    const sources = [...new Set([r.source,r.locationSource,r.secondarySource,r.sourceImage,...(r.verification?.sources || []).map(s=>s.url)].filter(Boolean))];
    const status = data.done.has(r.id) ? "Completed" : "Remaining";
    const coords = grid(r,meta);
    return '<article><h3>' + (i+1) + '. ' + esc(r.title) + '</h3><small>' +
      [status,categories[r.category]?.[1] || r.category,activityType(r),r.region,evidence(r),coords ? "Grid "+coords : "Position pending or separate map frame"].filter(Boolean).map(esc).join(' · ') +
      '</small><p>' + esc(r.details) + '</p>' + (r.verification ? '<p><strong>' + esc(r.verification.label) + '</strong> · ' + esc(r.verification.reason) + '</p>' : '') +
      (r.steps?.length ? '<ol>' + r.steps.map(s=>'<li>'+esc(s)+'</li>').join("")+'</ol>' : '') +
      '<p>' + sources.map((u,i)=>link(u,i ? "Supporting source "+i : "Original source")).join(" · ") + '</p></article>';
  }).join("");
  const itinerary = includeRoute && data.route.origin ? '<section><h2>Planned route</h2><p>Start · ' +
    esc(data.route.origin.label) + '</p><ol>' + data.route.stops.map(p=>'<li>'+esc(p.label)+' · '+grid(p,meta)+'</li>').join("") +
    '</ol>' + (data.directions.cues.length ? '<h3>Directions</h3><ol>' + data.directions.cues.map(c=>'<li>'+esc(c.text)+'</li>').join("")+'</ol>' : '') +
    '<p>Solid lines follow traced roads. Dashed lines show direct bearings.</p></section>' : "";
  return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(heading) +
    '</title><style>*{box-sizing:border-box}body{max-width:900px;margin:0 auto;padding:24px;color:#172526;font:16px/1.5 system-ui,sans-serif;background:#faf9f4}h1,h2,h3{line-height:1.2}figure{margin:1rem 0}figure svg{max-width:100%;max-height:85vh;background:#23363e}svg text{fill:white;font:bold 14px sans-serif;paint-order:stroke;stroke:#18222b;stroke-width:3px}.icon{width:12px;height:12px}article{border-top:1px solid #a0adaa;padding:8px 0}small,figcaption{color:#435353}a{color:#0b5659}@media print{body{background:white;padding:0}article,figure{break-inside:avoid}figure svg{height:17cm}}</style><style>body.card{background:#132625;color:#eef5ef;max-width:850px;border-top:6px solid #ff9b9b}body.card h1{font:750 clamp(2rem,7vw,4.2rem)/1.04 system-ui,sans-serif;letter-spacing:-.035em;margin:1rem 0 .55rem}body.card figure{border:1px solid #44655d;background:#1c3231}body.card figure svg{width:100%;height:auto;display:block}body.card small,body.card figcaption{color:#b7d4c8}body.card figcaption{padding:9px 12px;font-size:.78rem}body.card a{color:#a5f1d9}body.card article{border-color:#44655d}@media print{body.card{background:white;color:black;border:none}body.card small,body.card figcaption,body.card a{color:#273b35}}</style><body class="' + (shared ? "card" : "pack") + '"><h1>' +
    esc(heading) + '</h1><p>' + (shared ? 'GTA 6 field card · '+esc(categories[rows[0].category]?.[1])+' · '+esc(rows[0].region) : fmt(rows.length) + (rows.length===1?' entry':' entries')) + ' · Exported ' + esc(exportedAt) + ' · Created by ' + link(repo,"The Ihtisham") + '</p><figure>' +
    fieldMap(rows,image,data,includeRoute) + '<figcaption>' + esc(meta.attribution) + ' · ' + link(meta.source,"Map source") + ' · ' +
    link(meta.licenseUrl,meta.license) + ' · Cropped community map with atlas markers.</figcaption></figure>' + itinerary + (shared ? '' : '<h2>Location checklist</h2>') +
    (articles || '<p>No entries matched this export.</p>') + '</body></html>';
}
async function embeddedMap() {
  const response = await fetch("/map.webp");
  if (!response.ok) throw Error("Could not read the bundled community map.");
  const blob = await response.blob();
  return new Promise((resolve,reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(Error("Could not read the map image."));
    reader.readAsDataURL(new Blob([blob],{type:"image/webp"}));
  });
}
export function showExport(open, data) {
  const scopes = data.entry ? [["entry",data.entry.title], ...choices] : choices;
  open(data.entry ? "Share a field card" : "Export center", (data.entry ? '<p class="hint">Save this location as a file you can send to another player. The HTML card opens offline with a local map, steps and evidence links.</p>' : '<p class="hint">Take a checklist, a map with directions, or source-linked coordinates into your next session.</p>') +
    '<div class="export-fields"><label class="form-field"><span>Include entries</span><select id="export-scope">' + scopes.map(([v,n])=>'<option value="'+v+'">'+esc(n)+'</option>').join("") +
    '</select></label><label class="form-field"><span>File format</span><select id="export-format"><option value="html">Offline field pack · HTML</option><option value="csv">Spreadsheet · CSV</option><option value="json">Map data · JSON</option></select></label></div>' +
    '<div class="export-preview" aria-live="polite" id="export-preview"></div>' +
    '<label class="checkline" id="route-export-label"><input type="checkbox" id="export-route" checked>Include my current route</label>' +
    '<button type="button" class="primary" id="export-download">Download export</button>');
  const scope = $("export-scope"), format = $("export-format"), routeCheck = $("export-route");
  if (data.entry) routeCheck.checked = false;
  function preview() {
    const rows = exportRows(scope.value,data);
    $("export-preview").innerHTML = '<strong>' + fmt(rows.length) + (rows.length === 1 ? ' entry · ' : ' entries · ') + fmt(rows.filter(located).length) +
      ' mapped</strong><p class="hint">' + ({html:"A printable, single-file pack with the community map, instructions, and source links. Opens offline.",csv:"A spreadsheet with progress, coordinates, steps and sources.",json:"Structured entries, coordinate frame, source revision and attribution."})[format.value] + '</p>';
    $("route-export-label").hidden = format.value === "csv" || !data.route.origin;
  }
  scope.onchange = format.onchange = preview;
  preview();
  $("export-download").onclick = async e => {
    const button = e.currentTarget, rows = exportRows(scope.value,data), wanted = format.value;
    const when = new Date().toISOString(), includeRoute = Boolean(routeCheck.checked && data.route.origin);
    button.disabled = true;
    try {
      if (wanted === "csv") exportCsv(rows,data.done);
      else if (wanted === "html") download(scope.value === "entry" ? "gta6-location-card.html" : "gta6-field-pack.html",fieldPack(rows,data,await embeddedMap(),includeRoute,when),"text/html;charset=utf-8");
      else {
        const meta = data.meta;
        const pack = {version:1,exportedAt:when,creator:"The Ihtisham",repository:repo,coordinateFrame:meta.coordinateFrame,
          mapSource:meta.source,mapRevision:meta.revision,mapAttribution:meta.attribution,mapLicense:meta.licenseUrl,
          entries:rows.map(r=>record(r,data.done,meta))};
        if (includeRoute) pack.route = {...data.route,segments:data.track,directions:data.directions};
        download("gta6-map-loot.json",JSON.stringify(pack,null,2),"application/json");
      }
      toast("Export downloaded.");
    } catch (err) {toast(err.message);}
    finally {button.disabled = false;}
  };
}

