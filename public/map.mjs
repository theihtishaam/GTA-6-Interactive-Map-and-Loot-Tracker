import { $, categories, esc, fmt, icon, located } from "./ui.mjs";

const mapCategory = (entry) =>
  Object.hasOwn(categories, entry.category) ? entry.category : "landmark";

function mapCenter(entries) {
  return {
    x: entries.reduce((sum, entry) => sum + entry.x, 0) / entries.length,
    y: entries.reduce((sum, entry) => sum + entry.y, 0) / entries.length,
  };
}

function groupLabel(group) {
  const count = fmt(group.length);
  const places = group.filter((entry) => entry.category === "landmark").length;
  const label = places === group.length ? "places" : places ? "entries" : "activities";
  return count + " nearby " + label;
}

function packMarkers(bins, position, separation) {
  const groups = [];
  for (const bin of bins) {
    let entries = bin;
    let [x, y] = position(mapCenter(entries));
    let neighbor = groups.findIndex((other) => Math.hypot(x - other.x, y - other.y) < separation);
    while (neighbor >= 0) {
      entries = groups.splice(neighbor, 1)[0].entries.concat(entries);
      [x, y] = position(mapCenter(entries));
      neighbor = groups.findIndex((other) => Math.hypot(x - other.x, y - other.y) < separation);
    }
    groups.push({ x, y, entries });
  }
  return groups;
}

export class AtlasMap {
  constructor({ pick, select, stack }) {
    Object.assign(this, { pick, select, stack });
    this.el = $("map-surface");
    this.el.setAttribute("aria-label",
      "Map. Arrow keys pan, plus and minus zoom. Enter focuses a marker, then use arrows to move between markers.");
    this.pins = $("pins");
    this.pointer = new Map();
    this.center = { x: 0.5, y: 0.5 };
    this.zoom = 1;
    this.entries = [];
    this.track = [];
    this.selected = null;
    this.placing = false;
    this.meta = null;
    this.groups = [];
    this.coarsePointer = window.matchMedia("(pointer: coarse)");
    this.coarsePointer.addEventListener("change", () => this.queue());
    this.addMapControls();
    new ResizeObserver(() => this.queue()).observe(this.el);
    this.el.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        this.scale(e.deltaY < 0 ? 1.25 : 0.8, this.local(e));
      },
      { passive: false },
    );
    this.el.addEventListener("pointerdown", (e) => this.down(e));
    this.el.addEventListener("pointermove", (e) => this.move(e));
    this.el.addEventListener("pointerup", (e) => this.up(e, false));
    this.el.addEventListener("pointercancel", (e) => this.up(e, true));
    this.el.addEventListener("keydown", (e) => {
      if (e.target !== this.el) return;
      if (["+", "=", "-"].includes(e.key)) {
        this.scale(e.key === "-" ? 0.8 : 1.25);
        e.preventDefault();
      }
      if (e.key === "Enter" && this.meta) {
        e.preventDefault();
        if (this.placing) {
          const p = this.unproject(this.center);
          if (located(p)) this.pick(p);
        } else {
          this.focusMarker();
        }
      }
      const pan = {
        ArrowUp: [0, -64],
        ArrowDown: [0, 64],
        ArrowLeft: [-64, 0],
        ArrowRight: [64, 0],
      }[e.key];
      if (pan && this.meta) {
        e.preventDefault();
        this.closeGroup();
        const v = this.box();
        this.center.x += pan[0] / v.w;
        this.center.y += pan[1] / v.h;
        this.queue();
      }
    });
    this.pins.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b || this.placing || (e.detail && this.draggedFromPin)) return;
      const g = this.groups[Number(b.dataset.group)];
      if (!g) return;
      if (g.length === 1) {
        this.closeGroup();
        this.closeKey();
        this.select(g[0]);
        return;
      }
      this.previewGroup(g, b);
    });
    this.pins.addEventListener("keydown", (e) => this.markerKeys(e));
    $("zoom-in").onclick = () => this.scale(1.4);
    $("zoom-out").onclick = () => this.scale(1 / 1.4);
    $("fit").onclick = () => this.fit();
  }
  addMapControls() {
    this.stage = $("map-stage");
    const button = document.createElement("button");
    button.type = "button";
    button.id = "map-key-toggle";
    button.title = "Map legend";
    button.setAttribute("aria-label", "Map legend");
    button.setAttribute("aria-controls", "map-key-panel");
    button.setAttribute("aria-expanded", "false");
    button.innerHTML = icon("book");
    this.stage.querySelector(".map-tools").append(button);

    const panel = document.createElement("aside");
    panel.id = "map-key-panel";
    panel.className = "atlas-map-popover map-key-panel";
    panel.setAttribute("aria-labelledby", "map-key-title");
    panel.hidden = true;
    panel.innerHTML =
      '<header><h3 id="map-key-title">Map legend</h3><button type="button" data-close-key aria-label="Close map legend">' +
      icon("x") +
      '</button></header><ul class="map-key-list">' +
      Object.entries(categories)
        .map(([kind, [label, , color]]) => '<li><span class="legend-glyph" data-kind="' + kind + '" style="--cat:' + color + '">' + icon(kind) + "</span>" + esc(label) + "</li>")
        .join("") +
      '</ul><p class="map-key-states"><span><b class="map-key-selected"></b>Selected</span><span><b class="map-key-count">3</b>Group</span><span><b class="map-key-done">' + icon("check") + '</b>Completed</span></p>' +
      '<label class="map-key-size"><input type="checkbox" id="map-large-markers"> Larger markers</label>' +
      '<button type="button" class="map-key-fit" id="map-fit-results">' + icon("fit") + " Fit filtered results</button>";
    this.stage.append(panel);
    this.keyButton = button;
    this.keyPanel = panel;

    this.groupPanel = document.createElement("section");
    this.groupPanel.className = "atlas-map-popover map-group-panel";
    this.groupPanel.id = "map-group-preview";
    this.groupPanel.setAttribute("aria-labelledby", "map-group-title");
    this.groupPanel.hidden = true;
    this.stage.append(this.groupPanel);

    const large = $("map-large-markers");
    try {
      large.checked = localStorage.getItem("leonida.large-markers") === "true";
    } catch {
      large.checked = false;
    }
    const setSize = () => {
      this.largeMarkers = large.checked;
      this.stage.classList.toggle("large-markers", this.largeMarkers);
      this.queue();
    };
    setSize();
    large.addEventListener("change", () => {
      setSize();
      try {
        localStorage.setItem("leonida.large-markers", String(large.checked));
      } catch {
        // The current size still applies when browser storage is unavailable.
      }
    });
    button.addEventListener("click", () => {
      if (!panel.hidden) {
        this.closeKey();
        return;
      }
      this.closeGroup();
      panel.hidden = false;
      button.setAttribute("aria-expanded", "true");
      panel.querySelector("button").focus();
    });
    panel.querySelector("[data-close-key]").onclick = () => this.closeKey(true);
    $("map-fit-results").onclick = () => {
      this.closeKey(true);
      this.fitPoints(this.entries.filter(located));
    };
    this.stage.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (!this.groupPanel.hidden) this.closeGroup(true);
      else if (!panel.hidden) this.closeKey(true);
      else return;
      e.stopPropagation();
    });
  }
  closeKey(restoreFocus = false) {
    this.keyPanel.hidden = true;
    this.keyButton.setAttribute("aria-expanded", "false");
    if (restoreFocus) this.keyButton.focus();
  }
  closeGroup(restoreFocus = false) {
    if (this.groupPanel.hidden) return;
    const trigger = this.groupTrigger;
    this.groupPanel.hidden = true;
    this.groupTrigger = null;
    trigger?.setAttribute("aria-expanded", "false");
    if (restoreFocus) {
      if (trigger?.isConnected) trigger.focus();
      else this.focusMarker();
    }
  }
  previewGroup(group, trigger) {
    if (!this.groupPanel.hidden && this.groupTrigger === trigger) {
      this.closeGroup(true);
      return;
    }
    this.closeKey();
    this.closeGroup();
    const groupKinds = new Map();
    for (const entry of group) {
      const kind = mapCategory(entry);
      groupKinds.set(kind, (groupKinds.get(kind) || 0) + 1);
    }
    const nextZoom = Math.min(30, this.zoom * 2.15);
    this.groupPanel.innerHTML =
      '<header><h3 id="map-group-title">' + groupLabel(group) +
      '</h3><button type="button" data-close-group aria-label="Close nearby entries">' + icon("x") +
      '</button></header><p>' +
      [...groupKinds].map(([kind, count]) => esc(categories[kind][0]) + " " + fmt(count)).join(" · ") +
      '</p><div class="map-group-actions"><button type="button" data-browse-group>' + icon("book") +
      ' Browse entries</button><button type="button" data-zoom-group' + (nextZoom === this.zoom ? " disabled" : "") +
      ">" + icon("plus") + " Zoom in</button></div>";
    this.groupTrigger = trigger;
    this.groupEntries = this.entries;
    this.groupPanel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    const x = Number.parseFloat(trigger.style.left);
    const y = Number.parseFloat(trigger.style.top);
    const maximumX = this.stage.clientWidth - this.groupPanel.offsetWidth - 9;
    const bottom = this.stage.querySelector(".map-bottom");
    const bottomSpace = bottom?.offsetHeight ? this.stage.clientHeight - bottom.offsetTop + 8 : 34;
    const maximumY = this.stage.clientHeight - this.groupPanel.offsetHeight - bottomSpace;
    const top = y + 22 > maximumY ? y - 22 - this.groupPanel.offsetHeight : y + 22;
    this.groupPanel.style.left = Math.max(9, Math.min(x + 24, maximumX)) + "px";
    this.groupPanel.style.top = Math.max(8, Math.min(top, maximumY)) + "px";
    this.groupPanel.querySelector("[data-close-group]").onclick = () => this.closeGroup(true);
    const browse = this.groupPanel.querySelector("[data-browse-group]");
    browse.onclick = () => {
      this.closeGroup(true);
      this.stack(group);
    };
    this.groupPanel.querySelector("[data-zoom-group]").onclick = () => {
      this.closeGroup();
      this.focus(mapCenter(group), nextZoom);
      this.el.focus({ preventScroll: true });
    };
    browse.focus({ preventScroll: true });
  }
  focusMarker(from, direction) {
    const x = from ? Number.parseFloat(from.style.left) : this.el.clientWidth / 2;
    const y = from ? Number.parseFloat(from.style.top) : this.el.clientHeight / 2;
    let closest, nearest = Infinity;
    for (const button of this.pins.children) {
      if (button === from) continue;
      const dx = Number.parseFloat(button.style.left) - x;
      const dy = Number.parseFloat(button.style.top) - y;
      if (x + dx < 10 || x + dx > this.el.clientWidth - 10
          || y + dy < 10 || y + dy > this.el.clientHeight - 10) continue;
      const forward = direction && dx * direction[0] + dy * direction[1];
      if (direction && forward <= 0) continue;
      const lateral = direction ? Math.abs(dx * direction[1] - dy * direction[0]) : 0;
      const distance = Math.hypot(dx, dy) + lateral / 2;
      if (distance < nearest) {
        closest = button;
        nearest = distance;
      }
    }
    if (!closest) return;
    this.pins.querySelector('[tabindex="0"]')?.setAttribute("tabindex", "-1");
    closest.tabIndex = 0;
    closest.focus({ preventScroll: true });
  }
  markerKeys(e) {
    if (!e.target.matches(".pin") || this.placing) return;
    const direction = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] }[e.key];
    if (direction) {
      e.preventDefault();
      this.closeGroup();
      this.focusMarker(e.target, direction);
    } else if (e.key === "Escape" && this.groupPanel.hidden) {
      this.el.focus({ preventScroll: true });
    }
  }
  load(meta) {
    this.closeGroup();
    this.meta = meta;
    this.center = { x: 0.5, y: 0.5 };
    this.zoom = 1;
    $("map-img").src = meta.image;
    this.queue();
  }
  local(e) {
    const rect = this.el.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }
  box() {
    const w0 = this.el.clientWidth,
      h0 = this.el.clientHeight;
    const fit = Math.min(w0 / this.meta.width, h0 / this.meta.height);
    const w = fit * this.meta.width * this.zoom,
      h = fit * this.meta.height * this.zoom;
    return {
      w,
      h,
      left: w0 / 2 - this.center.x * w,
      top: h0 / 2 - this.center.y * h,
      w0,
      h0,
    };
  }
  fromScreen(p) {
    const b = this.box();
    return { x: (p.x - b.left) / b.w, y: (p.y - b.top) / b.h };
  }
  project(p) {
    const m = this.meta.registration?.matrix;
    if (!m) return { x:p.x, y:p.y };
    const u = p.x * this.meta.registration.inputWidth,
      v = p.y * this.meta.registration.inputHeight;
    return {
      x: (m[0][0] * u + m[0][1] * v + m[0][2]) / this.meta.width,
      y: (m[1][0] * u + m[1][1] * v + m[1][2]) / this.meta.height,
    };
  }
  unproject(p) {
    const m = this.meta.registration?.matrix;
    if (!m) return { x:p.x, y:p.y };
    const u = p.x * this.meta.width - m[0][2],
      v = p.y * this.meta.height - m[1][2],
      det = m[0][0] * m[1][1] - m[0][1] * m[1][0];
    return {
      x: (m[1][1] * u - m[0][1] * v) / det / this.meta.registration.inputWidth,
      y: (m[0][0] * v - m[1][0] * u) / det / this.meta.registration.inputHeight,
    };
  }
  fit() {
    this.closeGroup();
    this.center = { x: 0.5, y: 0.5 };
    this.zoom = 1;
    this.queue();
  }
  focus(p, zoom = Math.max(this.zoom, 3)) {
    if (!located(p)) return;
    this.closeGroup();
    this.center = this.project(p);
    this.zoom = zoom;
    this.queue();
  }
  fitPoints(points) {
    if (!points.length || !this.meta) return;
    this.closeGroup();
    let left = Infinity,
      right = -Infinity,
      top = Infinity,
      bottom = -Infinity;
    for (const p of points) {
      const projected = this.project(p);
      left = Math.min(left, projected.x);
      right = Math.max(right, projected.x);
      top = Math.min(top, projected.y);
      bottom = Math.max(bottom, projected.y);
    }
    const b = this.box(),
      baseWidth = b.w / this.zoom,
      baseHeight = b.h / this.zoom;
    this.center = { x: (left + right) / 2, y: (top + bottom) / 2 };
    this.zoom = Math.max(
      0.65,
      Math.min(
        14,
        (b.w0 * 0.76) / (Math.max(0.02, right - left) * baseWidth),
        (b.h0 * 0.68) / (Math.max(0.02, bottom - top) * baseHeight),
      ),
    );
    this.queue();
  }
  scale(ratio, p) {
    if (!this.meta) return;
    this.closeGroup();
    const b = this.box();
    if (!b.w) return;
    p ??= { x: b.w0 / 2, y: b.h0 / 2 };
    const world = this.fromScreen(p);
    this.zoom = Math.min(30, Math.max(0.65, this.zoom * ratio));
    const next = this.box();
    this.center = {
      x: world.x - (p.x - next.w0 / 2) / next.w,
      y: world.y - (p.y - next.h0 / 2) / next.h,
    };
    this.queue();
  }
  down(e) {
    if (!this.meta || e.button !== 0) return;
    const onPin = e.target.closest(".pin") && !this.placing;
    if (!this.pointer.size) this.draggedFromPin = false;
    if (onPin && e.pointerType !== "touch") return;
    const p = this.local(e);
    if (!onPin) {
      this.closeGroup();
      this.closeKey();
      this.el.setPointerCapture(e.pointerId);
    }
    this.pointer.set(e.pointerId, p);
    if (this.pointer.size === 1) {
      this.start = p;
      this.dragged = false;
      this.pressedPin = !!onPin;
    } else this.dragged = true;
  }
  move(e) {
    if (!this.pointer.has(e.pointerId)) return;
    const prev = this.pointer.get(e.pointerId),
      p = this.local(e);
    const other = [...this.pointer.entries()].find(
      ([id]) => id !== e.pointerId,
    )?.[1];
    const v = this.box();
    if (!v.w) return;
    if (this.pressedPin) {
      if (!other && Math.hypot(p.x - this.start.x, p.y - this.start.y) <= 4)
        return;
      this.pressedPin = false;
      this.draggedFromPin = true;
      this.closeGroup();
      this.closeKey();
      this.el.setPointerCapture(e.pointerId);
    }
    if (other) {
      const distance = (q) => Math.hypot(other.x - q.x, other.y - q.y);
      const oldDist = distance(prev),
        newDist = distance(p);
      if (oldDist > 3 && newDist > 3) {
        this.scale(newDist / oldDist, {
          x: (other.x + prev.x) / 2,
          y: (other.y + prev.y) / 2,
        });
        const b = this.box();
        this.center.x -= (p.x - prev.x) / (2 * b.w);
        this.center.y -= (p.y - prev.y) / (2 * b.h);
      }
    } else {
      this.center.x -= (p.x - prev.x) / v.w;
      this.center.y -= (p.y - prev.y) / v.h;
      if (Math.hypot(p.x - this.start.x, p.y - this.start.y) > 4)
        this.dragged = true;
    }
    this.pointer.set(e.pointerId, p);
    this.queue();
  }
  up(e, cancelled) {
    if (!this.pointer.has(e.pointerId)) return;
    this.pointer.delete(e.pointerId);
    if (!cancelled && !this.dragged && !this.pointer.size && this.placing) {
      const p = this.unproject(this.fromScreen(this.local(e)));
      if (located(p)) this.pick(p);
    }
    if (!this.pointer.size) this.pressedPin = false;
  }
  queue() {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      this.draw();
    });
  }
  draw() {
    if (!this.meta || !this.el.clientWidth || !this.el.clientHeight) return;
    this.center.x = Math.max(-0.05, Math.min(1.05, this.center.x));
    this.center.y = Math.max(-0.05, Math.min(1.05, this.center.y));
    const b = this.box(),
      plane = $("map-plane");
    plane.style.width = b.w + "px";
    plane.style.height = b.h + "px";
    plane.style.transform = "translate(" + b.left + "px," + b.top + "px)";
    $("zoom-level").textContent = Number(this.zoom.toFixed(1)) + "×";
    const pos = (r) => {
      const p = this.project(r);
      return [b.left + p.x * b.w, b.top + p.y * b.h];
    };
    const bins = new Map();
    this.groups = [];
    const markers = [];
    const touch = this.coarsePointer.matches || this.largeMarkers;
    $("map-fit-results").disabled = !this.entries.some(located);
    if (this.groupEntries !== this.entries || this.placing) this.closeGroup();
    const collect = (entry, key) => {
      if (!bins.has(key)) bins.set(key, []);
      bins.get(key).push(entry);
    };
    for (const r of this.entries) {
      if (!located(r) || r.id === this.selected?.id) continue;
      const [x, y] = pos(r);
      if (x < -32 || y < -32 || x > b.w0 + 32 || y > b.h0 + 32) continue;
      const isPlace = r.category === "landmark",
        cell = isPlace ? 66 : touch ? 46 : 38;
      collect(
        r,
        (isPlace ? "p" : "a") +
          Math.round(x / cell) +
          "," +
          Math.round(y / cell),
      );
    }
    const packed = packMarkers(bins.values(), pos, touch ? 48 : 36);
    if (located(this.selected)) {
      const [x, y] = pos(this.selected);
      packed.push({ x, y, entries: [this.selected], selected: true });
    }
    for (const { x, y, entries: group, selected } of packed) {
      const entry = group[0];
      const cluster = group.length > 1;
      const kind = mapCategory(group.find((row) => row.category !== "landmark") || entry);
      const finished = group.every((row) => row.done);
      const index = this.groups.push(group) - 1;
      const name = cluster ? groupLabel(group) : entry.title;
      const label = name + (selected ? ", selected" : "") + (finished ? ", completed" : "");
      const classes = [
        "pin",
        cluster ? "cluster" : "",
        kind === "landmark" ? "place" : "",
        selected ? "selected" : "",
        finished ? "finished" : "",
        y < 74 ? "label-below" : "",
        x < 100 ? "label-right" : "",
        x > b.w0 - 100 ? "label-left" : "",
      ].filter(Boolean).join(" ");
      markers.push(
        '<button type="button" tabindex="-1" data-group="' + index +
        '" data-entry="' + esc(entry.id) + '" data-kind="' + kind + '" class="' + classes +
        '" style="left:' + x.toFixed(1) + "px;top:" + y.toFixed(1) +
        "px;--cat:" + categories[kind][2] + '" aria-label="' + esc(label) + '"' +
        (cluster ? ' aria-expanded="false" aria-controls="map-group-preview"' : "") +
        (selected ? ' aria-current="true"' : "") +
        '><span class="pin-glyph">' + (cluster ? fmt(group.length) : icon(kind)) + "</span>" +
        (finished ? '<span class="pin-done">' + icon("check") + "</span>" : "") +
        '<span class="pin-label" aria-hidden="true">' + esc(name) + "</span></button>",
      );
    }
    const markup = markers.join("");
    if (this.markerMarkup !== markup) {
      const focused = this.pins.contains(document.activeElement);
      const focusId = this.pins.querySelector('[tabindex="0"]')?.dataset.entry;
      this.closeGroup();
      this.pins.innerHTML = markup;
      this.markerMarkup = markup;
      const next = (focusId && [...this.pins.children].find((node) => node.dataset.entry === focusId))
        || this.pins.querySelector(".selected") || this.pins.firstElementChild;
      if (next) {
        next.tabIndex = 0;
        if (focused) next.focus({ preventScroll: true });
      } else if (focused) {
        this.el.focus({ preventScroll: true });
      }
    }
    const route = $("route-overlay");
    let lines = "";
    const line = (a, cls) =>
      '<polyline class="' +
      cls +
      '" points="' +
      a
        .map((p) =>
          pos(p)
            .map((n) => n.toFixed(1))
            .join(","),
        )
        .join(" ") +
      '"/>';
    for (const segment of this.track) {
      if (segment.points.length > 1)
        lines += line(
          segment.points,
          segment.road ? "road-line" : "waypoint-line",
        );
    }
    if (located(this.origin)) {
      const [x, y] = pos(this.origin);
      lines +=
        '<circle class="origin-ring" cx="' +
        x +
        '" cy="' +
        y +
        '" r="10"/><circle class="origin-dot" cx="' +
        x +
        '" cy="' +
        y +
        '" r="5"/><text class="hero-map-label" x="' + (x + 14) + '" y="' + (y - 9) + '">YOU</text>';
    }
    (this.stops || []).forEach((s, i) => {
      const [x, y] = pos(s);
      lines +=
        '<g class="stop-dot"><circle cx="' +
        x +
        '" cy="' +
        y +
        '" r="9"/><text x="' +
        x +
        '" y="' +
        (y + 4) +
        '">' +
        (i + 1) +
        "</text></g>";
    });
    route.innerHTML = lines;
  }
}
