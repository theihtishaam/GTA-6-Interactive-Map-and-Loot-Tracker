import { esc, icon, link } from "./ui.mjs";

const equipment = "https://www.powerpyx.com/gta-6-all-equipment/";
const labFees = "https://www.powerpyx.com/gta-6-lab-fees-collect-brians-rent-walkthrough/";
const headphones = "https://www.gamesradar.com/games/grand-theft-auto/gta-6-headphones-music-radio-podcasts-how-to-use/";
const shops = "https://www.powerpyx.com/gta-6-all-electronics-stores-locations/";
const keyLento = "https://www.pushsquare.com/guides/gta-6-key-lento-collectibles-and-secrets-walkthrough";
const card = "https://www.powerpyx.com/gta-6-los-santos-panic-collectible-card-set-locations/";
const vicki = "https://www.powerpyx.com/gta-6-afternoon-delight-rob-vickis-boss-walkthrough/";
const meditation = "https://www.powerpyx.com/gta-6-all-meditation-spot-locations/";

const chapters = [
  {
    label: "First launch",
    title: "Get your bearings in Key Lento",
    intro: "Open the map beside your game. The starter area has a story unlock, a sculpture and a trading card within one island.",
    body: ({ action }) => `
      <h3>Find a place you recognize</h3>
      <p>Open Map index on a small screen, or press <kbd>/</kbd> on a keyboard. Search for <b>Key Lento</b>. Pick a place you can also see in the game's pause map. Open its entry and choose <b>Set as my position</b>.</p>
      <h3>Make a first stop</h3>
      <p>The Wonder Whale is a souvenir shop on Surfside Drive. Stand outside and point the in-game WAiNK scanner at the whale. You can tick the sculpture off as soon as it registers in your game.</p>
      <div class="fm-buttons">${action("openEntry", "Find the Wonder Whale", "guide-wonder-whale-scan", "collectible")}${action("openMap", "Explore the map", "", "map")}</div>
      <p class="fm-citation">${link(keyLento, "Push Square’s Key Lento walkthrough")}</p>`,
  },
  {
    label: "Starter gear",
    title: "Get the bag and a pair of earbuds",
    intro: "The bag unlocks through the story. Electronics stores handle your audio gear.",
    body: ({ action }) => `
      <h3>The first duffel bag</h3>
      <p>As Jason, finish <i>Gone Fishing</i> in Chapter 1. Choose <i>Collect Brian’s Rent</i> in Key Lento to start <i>Lab Fees</i>. The bag equips when Jason collects the mission items. Check <b>Progress → Equipment</b> afterward.</p>
      <div class="fm-buttons">${action("openEntry", "Show the mission start", "guide-duffel-bag", "bag")}</div>
      <p class="fm-citation">${link(labFees, "PowerPyx mission walkthrough")} ${link(equipment, "Equipment unlocks")}</p>
      <h3>Music on foot</h3>
      <p>Open <b>Style → Electronics</b> in the game’s map index to see shops by proximity. Game Horde is one option in Port Gellhorn. Buy a pair as the character who will wear it. Jason and Lucia each need their own.</p>
      <p>Use the headgear slot on the Items wheel to equip your purchase, then hold D-pad Left while walking to choose a station.</p>
      <div class="fm-buttons">${action("openEntry", "Find Game Horde", "guide-game-horde-earbuds", "earbuds")}</div>
      <p class="fm-citation">${link(headphones, "GamesRadar+ headphone controls")} ${link(shops, "PowerPyx store locations")}</p>`,
  },
  {
    label: "Choose a reward",
    title: "Pick a stop that fits your save",
    intro: "A nearby pin can still have a chapter requirement. Read the unlock conditions before setting a route.",
    body: ({ action }) => `
      <h3>A collectible before you leave home</h3>
      <p>In Chapter 1, read the fishing magazine in the workshop beneath Jason’s house. Push Square recommends visiting before the chapter ends. Mark it complete after you've read it.</p>
      <div class="fm-buttons">${action("openEntry", "Find Off the Hook", "guide-off-the-hook", "book")}</div>
      <p class="fm-citation">${link(keyLento, "Push Square’s Chapter 1 collectible route")}</p>
      <h3>A card at Kenton’s shop</h3>
      <p>Marquise Bernard belongs to the Los Santos Panic set. The pin takes you to Kenton’s shop in Key Lento. Look on the barrel outside, then check <b>Progress → Collections → Collectible Cards</b>.</p>
      <div class="fm-buttons">${action("openEntry", "Open Marquise’s card", "guide-marquise-card", "collectible")}</div>
      <p class="fm-citation">${link(card, "PowerPyx card walkthrough")}</p>
      <details class="fm-spoiler"><summary>Reveal a Chapter 2 cash reward</summary>
      <p>After <i>Coffee Break</i>, finish other pending story work until Vicki calls. Her job starts at Delights in Port Gellhorn. Its GTA$10,000 payment arrives through BuckMe the next in-game day.</p>
      <div class="fm-buttons">${action("openEntry", "Open Afternoon Delight", "guide-afternoon-delight", "heist")}</div>
      <p class="fm-citation">${link(vicki, "PowerPyx payout and prerequisites")}</p></details>`,
  },
  {
    label: "Plan a trip",
    title: "Build a route you can follow",
    intro: "Use a destination's pin for the approach and its guide for the final few steps.",
    body: ({ action }) => `
      <ol class="fm-steps"><li><b>Set your starting point.</b> Open a familiar place and choose <b>Set as my position</b>, or choose <b>Place my position</b> in the route planner.</li>
      <li><b>Pick a destination.</b> Choose <b>Route here</b> on its card. To extend the trip, use <b>Add waypoint</b> in the planner. Choosing Route here on another card replaces the current destination list.</li>
      <li><b>Check the line.</b> A solid line follows mapped roads. A dashed section connects a pin to a road or gives a direct bearing across unmapped terrain. Use the in-game map at junctions, bridges and entrances.</li></ol>
      <p>For a short practice run, start at Game Horde and route to Delights. Both are in Port Gellhorn. Open <b>GPS directions</b> in the route planner to read the cues.</p>
      <div class="fm-buttons">${action("openEntry", "Start at Game Horde", "guide-game-horde-earbuds", "earbuds")}${action("openEntry", "Find Delights", "guide-afternoon-delight", "heist")}${action("openRoutes", "Open route planner", "", "route")}</div>
      <details class="fm-spoiler"><summary>Reveal a late-game summit route</summary>
      <p>Mount Kalaga’s summit meditation appears on your game's map after the other meditations. The atlas gives a direct bearing to the stone circle. Plan the mountain approach yourself and check the purple in-game icon before making the climb.</p>
      <div class="fm-buttons">${action("openEntry", "Find the summit meditation", "guide-mount-kalaga-meditation", "collectible")}</div>
      <p class="fm-citation">${link(meditation, "PowerPyx meditation locations")}</p></details>`,
  },
  {
    label: "Bounties & new leads",
    title: "Decide whether a lead is worth a trip",
    intro: "Look for a named GTA VI activity, its district and a source that shows where it starts.",
    body: ({ action }) => `
      <h3>Read the position evidence</h3>
      <p>A shop or job marker refers to the selected icon in a source screenshot. A mission marker can point to a contact. A landmark can place you outside the building while the guide describes the object inside.</p>
      <h3>When the bounty list is empty</h3>
      <p>The bundled guidebook has no independently sourced bounty target or glove pickup. The relevant map filters also show new discoveries as they arrive. Check the linked report’s game, location and prerequisites before committing to the trip.</p>
      <p>If you find a lead in your own save, place a personal pin and record the chapter, district and map icon. A helpfulness vote records whether an existing guide worked for you.</p>
      <p>Open Bounty Watch to review its feeds, check now or schedule checks every 6, 12 or 24 hours. The local server checks for reports while it is running. Reading these guides, planning routes and refreshing the feeds all work with model inference turned off.</p>
      <div class="fm-buttons">${action("openBountyWatch", "Open bounty watch", "", "bounty")}${action("openCategory", "Bounty map filter", "bounty", "map")}${action("openCategory", "Check gloves", "gloves", "gloves")}${action("openSources", "Review sources", "", "signal")}</div>`,
  },
  {
    label: "Checklist & export",
    title: "Keep a record of the run",
    intro: "Tick an entry when its objective registers in your save. Two collectibles in one building can have separate checklist entries.",
    body: ({ action }) => `
      <h3>Keep track between sessions</h3>
      <p>Choose <b>Mark complete</b> on a guide, then use the map’s progress filter to see what remains. If you tick the wrong entry, reopen it and undo the completion. The journal keeps your checklist in this browser.</p>
      <h3>Plan a mission or a collection goal</h3>
      <p>Open Missions, find a title or chapter, and read the build. Check the starting area and requirements before setting off. Tick the objectives as you play. In Goals, pick one mission or a target number of activities. The planner updates when you complete an entry or discovery supplies a new eligible location.</p>
      <div class="fm-buttons">${action("openMissions", "Browse missions", "", "mission")}${action("openGoals", "Set a player goal", "", "target")}</div>
      <h3>Take your list with you</h3>
      <p>Set the category, search and progress filters before exporting. In Export center, choose the filtered list and download a printable offline field pack with the map and guide steps. CSV opens in a spreadsheet, and JSON carries structured location data. Use a journal backup to transfer your personal pins and completions to another browser.</p>
      <div class="fm-buttons">${action("openJournal", "Open field journal", "", "book")}${action("openExport", "Export options", "", "export")}</div>`,
  },
  {
    label: "Advanced GPS",
    title: "Position yourself from a pause map",
    intro: "Use this when you can see your player arrow but don’t know the name of the road.",
    body: ({ action }) => `
      <h3>Match a screenshot</h3>
      <p>Choose <b>Locate from screenshot</b> in the route planner. Use a pause-map image with several distinct road junctions or a clear coastline. Mark the tip of your player arrow, then confirm. The locator matches the map on this computer.</p>
      <p>For keyboard placement, focus the preview and use the arrow keys. Hold Shift to move farther, then press Enter. If the roads cannot be matched, zoom out a little in the game and capture a wider area, or place the point manually.</p>
      <h3>Use coordinates you already have</h3>
      <p>For a known grid point, enter <b>East / X</b> and <b>North / Y</b>. To follow a moving position, enable the local coordinate feed after connecting an integration that supplies the game's coordinates.</p>
      <div class="fm-buttons">${action("openRoutes", "Open route planner", "", "route")}${action("openMap", "Return to the map", "", "map")}</div>`,
  },
];

const reading = new WeakMap();

export function renderManual(container, controls = {}) {
  let active = reading.get(container) ?? 0;
  const action = (name, label, value, symbol) =>
    typeof controls[name] === "function"
      ? `<button type="button" class="fm-action" data-fm-action="${esc(name)}" data-fm-value="${esc(value)}">${icon(symbol)}${esc(label)}</button>`
      : "";

  container.innerHTML = `<div class="fm">
    <div class="fm-cover">
      <div class="fm-cover-copy"><h1>Player field manual</h1><p>Find your first piece of gear, plan a run across Leonida and keep track of what you bring home.</p>
        <div class="fm-local-stops" role="group" aria-label="Open a Key Lento starter stop">
          ${action("openEntry", "Bag mission", "guide-duffel-bag", "bag")}
          ${action("openEntry", "Whale scan", "guide-wonder-whale-scan", "collectible")}
          ${action("openEntry", "Marquise card", "guide-marquise-card", "collectible")}
        </div>
      </div>
      <figure class="fm-map" aria-label="Key Lento starter area">
        <svg aria-hidden="true" viewBox="1530 3885 760 520" preserveAspectRatio="xMidYMid slice">
          <image href="/map.webp" width="3456" height="4864"/>
          <g stroke="#24201b" stroke-width="4"><circle fill="#ffc34b" cx="1825" cy="4182" r="10"/><circle fill="#81e2bd" cx="1826" cy="4229" r="9"/><circle fill="#d5b4ff" cx="2057" cy="4050" r="9"/></g>
        </svg>
        <figcaption><b>Key Lento</b><span>Starter area · YANIS v18</span></figcaption>
      </figure>
    </div>
    <div class="fm-layout">
      <div class="fm-contents" role="navigation" aria-label="Manual chapters">
        <h2>Contents</h2><ol>${chapters.map((c, i) => `<li><button type="button" data-fm-chapter="${i}"><span>${i + 1}</span>${esc(c.label)}</button></li>`).join("")}</ol>
        <label class="fm-select">Choose a chapter<select>${chapters.map((c, i) => `<option value="${i}">${i+1}. ${esc(c.label)}</option>`).join("")}</select></label>
      </div>
      <article class="fm-page" aria-labelledby="fm-title"></article>
    </div></div>`;

  const manual = container.firstElementChild;
  const article = manual.querySelector(".fm-page");
  const select = manual.querySelector(".fm-select select");
  function showChapter(index, focus = false) {
    const chapter = chapters[index];
    if (!chapter) return;
    active = index;
    reading.set(container, index);
    select.value = String(index);
    for (const button of manual.querySelectorAll("[data-fm-chapter]")) {
      button.setAttribute("aria-current", Number(button.dataset.fmChapter) === index ? "step" : "false");
    }
    article.innerHTML = `<div class="fm-chapter-count">Chapter ${index + 1} of ${chapters.length}</div>
      <h2 id="fm-title" tabindex="-1">${esc(chapter.title)}</h2><p class="fm-intro">${esc(chapter.intro)}</p>
      <div class="fm-body">${chapter.body({ action })}</div>
      <div class="fm-turn">${index > 0 ? '<button type="button" data-fm-turn="-1">← Previous</button>' : ""}
      ${index + 1 < chapters.length ? `<button type="button" data-fm-turn="1">Next · ${esc(chapters[index + 1].label)} ${icon("arrow")}</button>` : ""}</div>`;
    if (focus) {
      const title = article.querySelector("h2");
      title.focus({ preventScroll: true });
      title.scrollIntoView({ block: "nearest" });
    }
  }
  manual.onclick = (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.hasAttribute("data-fm-chapter")) showChapter(Number(button.dataset.fmChapter), true);
    if (button.hasAttribute("data-fm-turn")) showChapter(active + Number(button.dataset.fmTurn), true);
    if (button.hasAttribute("data-fm-action")) {
      const callback = controls[button.dataset.fmAction];
      if (typeof callback === "function") callback(...(button.dataset.fmValue ? [button.dataset.fmValue] : []));
    }
  };
  select.onchange = () => showChapter(Number(select.value), true);
  showChapter(active);
}
