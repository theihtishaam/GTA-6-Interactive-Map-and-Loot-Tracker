const STORAGE = "leonida.appearance";
const PALETTES = {
  vice: { label: "Vice Neon", colors: ["#ffa693", "#80e6d5", "#251923"] },
  ocean: { label: "Ocean Drive", colors: ["#92e8ff", "#9ff0c8", "#132631"] },
  gold: { label: "Field Gold", colors: ["#f7cf82", "#cdc196", "#292318"] },
};
const DEFAULTS = { palette: "vice", glow: "vivid" };
let choice = { ...DEFAULTS };

function readAppearance() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE));
    return {
      palette: Object.hasOwn(PALETTES, saved?.palette) ? saved.palette : DEFAULTS.palette,
      glow: ["subtle", "vivid"].includes(saved?.glow) ? saved.glow : DEFAULTS.glow,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

function applyAppearance() {
  document.documentElement.dataset.uiTheme = choice.palette;
  document.documentElement.dataset.uiGlow = choice.glow;
}

export function initThemes() {
  choice = readAppearance();
  applyAppearance();
}

export function themeControls() {
  const options = Object.entries(PALETTES).map(([key, palette]) => {
    const [accent, signal, background] = palette.colors;
    return (
      '<label class="theme-choice" style="--sample-accent:' + accent +
      ';--sample-signal:' + signal + ';--sample-bg:' + background + '">' +
      '<input type="radio" name="atlas-ui-theme" value="' + key + '"' +
      (choice.palette === key ? " checked" : "") +
      '><span class="theme-preview" aria-hidden="true"><b></b><i></i></span><span>' +
      palette.label + "</span></label>"
    );
  }).join("");
  return (
    '<div class="theme-settings" data-theme-settings><fieldset><legend>Interface palette</legend>' +
    '<div class="theme-choices">' + options + '</div></fieldset>' +
    '<label class="theme-glow-control">Marker glow<select name="atlas-ui-glow">' +
    '<option value="subtle"' + (choice.glow === "subtle" ? " selected" : "") + '>Subtle</option>' +
    '<option value="vivid"' + (choice.glow === "vivid" ? " selected" : "") + '>Vivid</option>' +
    "</select></label></div>"
  );
}

export function bindThemeControls(root = document) {
  const controls = root.querySelector("[data-theme-settings]");
  if (!controls) return;
  controls.onchange = (event) => {
    const { name, value } = event.target;
    if (name === "atlas-ui-theme" && Object.hasOwn(PALETTES, value)) choice.palette = value;
    else if (name === "atlas-ui-glow" && ["subtle", "vivid"].includes(value)) choice.glow = value;
    else return;
    applyAppearance();
    try {
      localStorage.setItem(STORAGE, JSON.stringify(choice));
    } catch {
      // The preview remains available when browser storage is disabled.
    }
  };
}
