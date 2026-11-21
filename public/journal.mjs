import { categories, located, safeRead, save } from "./ui.mjs";
export const blank = () => ({ version: 1, done: [], pins: [], routes: {}, builds: {} });
const idOK = (v) => typeof v === "string" && /^[A-Za-z0-9_.-]{1,128}$/.test(v);
const point = (v) =>
  located(v)
    ? { x: v.x, y: v.y, label: String(v.label || "Waypoint").slice(0, 160),
        ...(idOK(v.entryId) ? {entryId:v.entryId} : {}) }
    : null;
export function validate(input) {
  if (
    !input ||
    input.version !== 1 ||
    !Array.isArray(input.done) ||
    !Array.isArray(input.pins) ||
    typeof input.routes !== "object" ||
    !input.routes
  )
    throw Error("Choose a Loot Atlas journal backup (version 1).");
  const out = blank();
  if (input.done.length > 50000 || input.pins.length > 3000)
    throw Error("Journal exceeds the import size limit.");
  const ids = new Set();
  for (const p of input.pins) {
    if (
      !p ||
      !located(p) ||
      !idOK(p.id) ||
      !p.id.startsWith("personal-") ||
      typeof p.title !== "string" ||
      !p.title.trim() ||
      !Object.hasOwn(categories, p.category) ||
      !["atlas", "poster"].includes(p.space) ||
      ids.has(p.id)
    )
      throw Error("A personal pin has invalid or duplicate data.");
    ids.add(p.id);
    out.pins.push({
      id: p.id,
      title: p.title.trim().slice(0, 120),
      category: p.category,
      region: p.space === "poster" ? "Leonida poster" : "Leonida",
      x: p.x,
      y: p.y,
      space: p.space,
      confidence: "personal",
      details: String(p.details || "").slice(0, 2000),
      steps: Array.isArray(p.steps)
        ? p.steps.slice(0, 12).map((s) => String(s).slice(0, 500))
        : [],
    });
  }
  if (!input.done.every(idOK)) throw Error("Invalid completion ID.");
  out.done = [...new Set(input.done)];
  if (input.builds !== undefined) {
    if (!input.builds || Array.isArray(input.builds) || typeof input.builds !== "object" || Object.keys(input.builds).length > 2000)
      throw Error("Invalid mission build data.");
    for (const [id, steps] of Object.entries(input.builds)) {
      if (!/^(?:mission-[a-zA-Z0-9_-]+|[a-f0-9]{24})$/.test(id) || !Array.isArray(steps) || steps.length > 160 ||
          steps.some(s => typeof s !== "string" || s.length > 2000)) throw Error("Invalid mission objective.");
      out.builds[id] = [...new Set(steps)];
    }
  }
  for (const space of ["atlas", "poster"]) {
    const r = input.routes[space];
    if (!r) continue;
    if (
      (r.origin && !located(r.origin)) ||
      !Array.isArray(r.stops) ||
      r.stops.length > 100 ||
      !r.stops.every(located)
    )
      throw Error("A saved route has invalid waypoints.");
    out.routes[space] = { origin: point(r.origin), stops: r.stops.map(point) };
  }
  return out;
}
export function readJournal() {
  return validate(safeRead("journal", blank()));
}
export const writeJournal = (j) => save("journal", j);
export function download(name, value, type) {
  const a = document.createElement("a"),
    url = URL.createObjectURL(new Blob([value], { type }));
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
export function exportCsv(rows, done) {
  const columns = [
    "ID",
    "Title",
    "Category",
    "Region",
    "Status",
    "Confidence",
    "Normalized X",
    "Normalized Y",
    "Coordinate frame",
    "Source",
    "Details",
    "Steps",
    "Map data attribution",
    "Game grid X",
    "Game grid Y",
    "Position evidence",
    "Location source",
    "Supporting guide",
    "Published at",
    "Report verification",
    "Verification sources",
  ];
  function safeCell(val) {
    const raw = String(val ?? "");
    return (
      '"' +
      (typeof val === "string" && /^(?:\s*[=+@\-]|[\t\r\n])/.test(raw) ? "'" : "") +
      raw.replaceAll('"', '""') +
      '"'
    );
  }
  const lines = rows.map((r) => [
    r.id,
    r.title,
    r.category,
    r.region,
    done.has(r.id) ? "completed" : "remaining",
    r.confidence,
    r.x,
    r.y,
    located(r)
      ? r.space === "poster"
        ? "Rockstar poster"
        : "GTADB normalized (see map-meta.json)"
      : "",
    r.source,
    r.details,
    (r.steps || []).join(" | "),
    "GTADB and contributors · CC BY 4.0 · https://map.gtadb.org · https://creativecommons.org/licenses/by/4.0/",
    located(r) && r.space !== "poster" ? Math.round(r.x * 13824 - 10240) : "",
    located(r) && r.space !== "poster" ? Math.round(10496 - r.y * 19456) : "",
    r.evidenceNote || r.precision,
    r.locationSource,
    r.secondarySource,
    r.publishedAt,
    r.verification?.label,
    (r.verification?.sources || []).map(s => s.url).join(" | "),
  ]);
  download(
    "leonida-loot-export.csv",
    "\uFEFF" +
      [columns, ...lines]
        .map((row) => row.map(safeCell).join(","))
        .join("\r\n"),
    "text/csv;charset=utf-8",
  );
}
