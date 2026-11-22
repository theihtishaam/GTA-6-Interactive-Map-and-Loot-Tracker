const paths = {
  follow: '<circle cx="9" cy="7" r="3.5"/><path d="M2.5 20v-2a6.5 6.5 0 0 1 13 0v2M19 8v7m-3.5-3.5h7"/>',
  mission: '<path d="M5 21V3m0 1c5-3 9 4 15 0l-2 5 2 4c-6 4-10-3-15 0"/>',
  manual: '<path d="M2 5c4-1.5 7-1 10 1.5C15 4 18 3.5 22 5v14c-4-1.5-7-1-10 1.5C9 18 6 17.5 2 19zM12 6.5v14"/>',
  map: '<path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2zM9 3v16M15 5v16"/>',
  book: '<path d="M4 4h14a2 2 0 0 1 2 2v14H6a2 2 0 0 1-2-2zM4 16h16M8 7h7"/>',
  signal:
    '<circle cx="12" cy="12" r="1.5"/><path d="M8.5 8.5a5 5 0 0 0 0 7m7-7a5 5 0 0 1 0 7M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/>',
  settings:
    '<path d="M3 7h6m4 0h8M3 17h10m4 0h4"/><circle cx="11" cy="7" r="2"/><circle cx="15" cy="17" r="2"/>',
  layers: '<path d="m2 9 10-6 10 6-10 6zM3 13l9 5 9-5M3 17l9 5 9-5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  heist:
    '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V4h8v3M3 11l9 3 9-3m-9 1v4"/>',
  bounty:
    '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4"/>',
  reward: '<path d="m3 8 4-4h10l4 4-9 12zM3 8h18M8 8l4 12 4-12"/>',
  leisure: '<circle cx="12" cy="12" r="8.8"/><circle cx="12" cy="12" r="4.7"/><path d="M10.6 11c0-1.6 2.8-1.6 2.8 0 0 .9-2.8 1.1-2.8 2.2 0 1.7 2.8 1.7 2.8 0 0-1.1-2.8-1.3-2.8-2.2z"/>',
  collectible:
    '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',
  earbuds:
    '<path d="M6 4a3 3 0 1 0 3 3V4zM9 7v10a2 2 0 0 1-4 0v-3M18 3a3 3 0 1 1-3 3V3zM15 6v13a2 2 0 0 0 4 0v-3"/>',
  gloves:
    '<path d="M7 11V6a1.5 1.5 0 0 1 3 0v4-6a1.5 1.5 0 0 1 3 0v6-5a1.5 1.5 0 0 1 3 0v6-3a1.5 1.5 0 0 1 3 0v6c0 4-2 7-6 7h-2c-2 0-3-1-4-3l-4-6c-1-2 1-3 2-2z"/>',
  bag: '<rect x="5" y="6" width="14" height="15" rx="4"/><path d="M9 6V4a3 3 0 0 1 6 0v2M5 13h14m-10 3h6"/>',
  landmark:
    '<path d="M19 10c0 5-7 11-7 11s-7-6-7-11a7 7 0 1 1 14 0z"/><circle cx="12" cy="10" r="2.4"/>',
  plus: '<path d="M12 4v16M4 12h16"/>',
  minus: '<path d="M4 12h16"/>',
  fit: '<path d="M3 9V3h6m6 0h6v6m0 6v6h-6m-6 0H3v-6"/>',
  route:
    '<circle cx="5" cy="18" r="2"/><circle cx="19" cy="5" r="2"/><path d="M7 18h7a3 3 0 0 0 0-6h-4a3 3 0 0 1 0-6h6"/>',
  north:
    '<path d="m12 2 7 19-7-5-7 5z" fill="currentColor" stroke="none"/><path d="M12 2v14l7 5z" fill="#76756e" stroke="none"/>',
  x: '<path d="m6 6 12 12M18 6 6 18"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  external: '<path d="M14 4h6v6m0-6L10 14m0-9H5v14h14v-5"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  arrow: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
  export: '<path d="M12 3v12m-4-4 4 4 4-4M4 15v5h16v-5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  thumb:
    '<path d="M3 10h4v10H3zM7 11l5-8c2-.5 3 1 2.5 3l-1 4H19c2 0 2.7 1 2 3l-2 6c-.3 1-1 1-2 1H7"/>',
  target:
    '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M2 12h3m14 0h3M12 2v3m0 14v3"/>',
};
export const categories = {
  mission: ["Missions", "Mission", "#ff9bbf"],
  heist: ["Heists", "Heist", "#ffad79"],
  bounty: ["Bounties", "Bounty", "#ff8798"],
  reward: ["Rewards", "Reward", "#f4cf72"],
  leisure: ["Sports & games", "Leisure activity", "#7cdeb3"],
  collectible: ["Collectibles", "Collectible", "#c6a2ff"],
  earbuds: ["Earbuds", "Earbuds", "#81cfff"],
  gloves: ["Gloves", "Gloves", "#9ccab3"],
  bag: ["Bags", "Bag", "#eda2d6"],
  landmark: ["Landmarks", "Landmark", "#89d4d3"],
};
export const icon = (name) =>
  '<svg class="icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' +
  (paths[name] || paths.landmark) +
  "</svg>";
export function decorate(root = document) {
  root
    .querySelectorAll("[data-icon]")
    .forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
}
export const $ = (id) => document.getElementById(id);
export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export function link(url, label) {
  try {
    const u = new URL(url);
    if (!["http:", "https:"].includes(u.protocol) || u.username || u.password)
      return "";
    return (
      '<a href="' +
      esc(u.href) +
      '" rel="noreferrer" target="_blank">' +
      esc(label) +
      " " +
      icon("external") +
      "</a>"
    );
  } catch {
    return "";
  }
}
export const fmt = (value) => Number(value).toLocaleString();
export const located = (p) =>
  p &&
  Number.isFinite(p.x) &&
  Number.isFinite(p.y) &&
  p.x >= 0 &&
  p.y >= 0 &&
  p.x <= 1 &&
  p.y <= 1;
export function evidence(r) {
  if (r.verification?.status === "review") return "Location under review";
  if (r.confidence === "guide" && r.precision === "mission-marker")
    return "Guide · mission start or contact";
  if (r.confidence === "guide" && r.precision === "landmark")
    return "Guide · landmark anchor";
  if (r.confidence === "guide" && r.precision === "map-marker")
    return "Guide · in-game map marker";
  if (r.confidence === "guide" && r.precision === "area")
    return "Guide · approximate area";
  return (
    {
      community: "Community landmark",
      guide: located(r) ? "Guide · venue pin" : "Guide · location pending",
      lead: "Community lead",
      area: "Approximate area",
      reported: "Player-reported coordinates",
      personal: "Personal pin",
    }[r.confidence] || "Reported location"
  );
}
export function itemBadge(cat) {
  const c = categories[cat] || categories.landmark;
  return (
    '<span class="badge-icon" style="--cat:' +
    c[2] +
    '">' +
    icon(cat) +
    "</span>"
  );
}
let toastTimer;
export function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 4500);
}
export async function json(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let msg;
    try {
      msg = (await res.json()).error;
    } catch {}
    throw Error(msg || "Request failed (" + res.status + ")");
  }
  return res.json();
}
export const post = (url, body) =>
  json(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export function safeRead(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem("loot-atlas." + key)) ?? fallback;
  } catch {
    return fallback;
  }
}
export function save(key, value) {
  try {
    localStorage.setItem("loot-atlas." + key, JSON.stringify(value));
  } catch {
    toast("Storage is full or disabled. Export your journal before closing.");
  }
}
