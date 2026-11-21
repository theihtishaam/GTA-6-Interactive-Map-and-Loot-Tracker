import { $, json, post, located, toast } from "./ui.mjs";

// Image bytes stay in this dialog and the loopback locator. They never enter the journal.
export function screenshotLocator(open, accept) {
  open(
    "Locate from the in-game map",
    '<p class="hint">Choose a GTA VI pause-map screenshot with visible roads. Then mark your player arrow. The image is matched on this computer.</p>' +
      '<label class="form-field"><span>Map screenshot</span><input id="gps-file" type="file" accept="image/png,image/jpeg,image/webp"></label>' +
      '<canvas id="gps-preview" tabindex="0" aria-label="Click your player arrow. Arrow keys move the crosshair and Enter confirms." hidden></canvas>' +
      '<p class="hint" role="status" id="gps-message"></p><div class="actions"><button class="primary" id="gps-confirm" disabled>Locate this point</button></div>',
  );
  const fileInput = $("gps-file"),
    canvas = $("gps-preview"),
    message = $("gps-message"),
    confirm = $("gps-confirm");
  let source = null,
    target = null,
    busy = false,
    generation = 0;
  const draw = () => {
    canvas.width = source.width;
    canvas.height = source.height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(source, 0, 0);
    if (target) {
      const size = Math.max(8, canvas.width / 80);
      ctx.strokeStyle = "#ffc246";
      ctx.lineWidth = Math.max(2, canvas.width / 350);
      ctx.shadowColor = "#000";
      ctx.shadowBlur = 3;
      ctx.beginPath();
      ctx.arc(target.x, target.y, size, 0, Math.PI * 2);
      ctx.moveTo(target.x - size * 1.5, target.y);
      ctx.lineTo(target.x + size * 1.5, target.y);
      ctx.moveTo(target.x, target.y - size * 1.5);
      ctx.lineTo(target.x, target.y + size * 1.5);
      ctx.stroke();
    }
    canvas.hidden = false;
    confirm.disabled = !target || busy;
  };
  fileInput.onchange = async () => {
    const version = ++generation,
      f = fileInput.files[0];
    source = null;
    target = null;
    confirm.disabled = true;
    canvas.hidden = true;
    if (!f) return;
    if (f.size > 24 * 1024 * 1024) {
      message.textContent = "Choose a screenshot smaller than 24 MB.";
      return;
    }
    try {
      const bitmap = await createImageBitmap(f);
      try {
        if (version !== generation) return;
        const scale = Math.min(1, 1200 / Math.max(bitmap.width, bitmap.height));
        source = document.createElement("canvas");
        source.width = Math.max(1, Math.round(bitmap.width * scale));
        source.height = Math.max(1, Math.round(bitmap.height * scale));
        source
          .getContext("2d")
          .drawImage(bitmap, 0, 0, source.width, source.height);
      } finally {
        bitmap.close();
      }
      message.textContent =
        "Click the player arrow, or use the arrow keys to place the crosshair.";
      draw();
      canvas.focus();
    } catch {
      message.textContent =
        "This image could not be opened. Try a PNG or JPEG screenshot.";
    }
  };
  canvas.onclick = (e) => {
    if (!source || busy) return;
    const b = canvas.getBoundingClientRect();
    target = {
      x: Math.min(
        source.width - 1,
        Math.max(
          0,
          Math.round(((e.clientX - b.left) * source.width) / b.width),
        ),
      ),
      y: Math.min(
        source.height - 1,
        Math.max(
          0,
          Math.round(((e.clientY - b.top) * source.height) / b.height),
        ),
      ),
    };
    draw();
  };
  canvas.onkeydown = (e) => {
    if (!source || busy) return;
    if (e.key === "Enter" && target) {
      e.preventDefault();
      confirm.click();
      return;
    }
    const d = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    }[e.key];
    if (!d) return;
    e.preventDefault();
    target ??= {
      x: Math.floor(source.width / 2),
      y: Math.floor(source.height / 2),
    };
    const step = e.shiftKey ? 12 : 1;
    target.x = Math.max(0, Math.min(source.width - 1, target.x + d[0] * step));
    target.y = Math.max(0, Math.min(source.height - 1, target.y + d[1] * step));
    draw();
  };
  confirm.onclick = async () => {
    if (!source || !target || busy) return;
    busy = true;
    fileInput.disabled = true;
    confirm.disabled = true;
    message.textContent = "Matching roads and coastline to Leonida…";
    try {
      const data = source.toDataURL("image/jpeg", 0.86).split(",")[1];
      const result = await post("/api/locate", {
        image: data,
        pixelX: target.x,
        pixelY: target.y,
      });
      if (!located(result))
        throw Error(
          "Could not establish a reliable position. Choose a wider area with distinctive streets.",
        );
      if (!canvas.isConnected || !$("dialog").open) return;
      $("dialog").close();
      accept({ ...result, label: "Screenshot position" });
      toast("Position set from the screenshot.");
    } catch (e) {
      message.textContent = e.message;
    } finally {
      busy = false;
      fileInput.disabled = false;
      confirm.disabled = !target;
    }
  };
}
let timer = null,
  seen = null,
  busy = false;
export function following() {
  return timer !== null;
}
export function followPosition(enable, update, status) {
  if (timer !== null) clearInterval(timer);
  timer = null;
  seen = null;
  if (!enable) return;
  async function poll() {
    if (document.hidden || busy) return;
    busy = true;
    try {
      const p = await json("/api/position");
      if (!following()) return;
      if (located(p) && p.updatedAt !== seen) {
        seen = p.updatedAt;
        update({ ...p, label: "Live position" });
        status(
          "Position received " + new Date(p.updatedAt).toLocaleTimeString(),
        );
      } else if (!p || !located(p))
        status("Waiting for a local coordinate source.");
    } catch {
      if (following()) status("Local position feed unavailable.");
    } finally {
      busy = false;
    }
  }
  timer = setInterval(poll, 2000);
  poll();
}
