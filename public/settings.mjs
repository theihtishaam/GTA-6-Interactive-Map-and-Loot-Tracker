import { $, json, link, post, toast } from "./ui.mjs";
const presets = {
  "ollama-cloud": "Ollama Cloud",
  "ollama-local": "Ollama on this computer",
  openrouter: "OpenRouter",
  custom: "Custom OpenAI-compatible endpoint",
  opencode: "OpenCode Console",
  none: "No model · zero inference",
};
const MANUAL = "__custom__";
let publicCatalogue = null;
export function showSettings(state, open, update) {
  const current = state.provider || {},
    first =
      current.kind && current.kind !== "none" ? current.kind : "ollama-cloud";
  open(
    "Settings",
    '<div><h3>Connect an optional model</h3><p class="hint">The atlas runs free without AI. An enabled model can enrich one new public report per scan.</p>' +
      '<label class="form-field" id="key-field"><span>API key · kept in server memory until restart</span><input id="key" type="password" autocomplete="off" spellcheck="false" placeholder="Enter a key on this computer" aria-describedby="key-route"></label>' +
      '<p class="hint" id="key-route" role="status"></p>' +
      '<label class="form-field"><span>Service for this key or local model</span><select id="provider"><option value="">Choose the service that issued this key…</option>' +
      Object.entries(presets)
        .map(
          ([id, label]) =>
            '<option value="' + id + '">' + label + "</option>",
        )
        .join("") +
      "</select></label>" +
      '<div id="provider-fields"><label class="form-field" id="base-field"><span>API base URL</span><input id="base" type="url" placeholder="https://provider.example/v1" autocomplete="off"></label>' +
      '<label class="form-field"><span id="model-choice-label">Model</span><select id="model-choice" aria-labelledby="model-choice-label" aria-describedby="model-hint"></select></label>' +
      '<label class="form-field" id="custom-model-field" hidden><span>Custom model ID</span><input id="model" autocomplete="off" placeholder="Enter the provider’s exact model ID"></label>' +
      '<p class="hint" id="model-hint" aria-live="polite"></p>' +
      '<button class="action" id="list-models">Refresh model list</button><p class="hint" id="provider-advice"></p>' +
      '<label class="checkline"><input id="enable" type="checkbox">Use this model to enrich new reports</label>' +
      '<label class="checkline" id="paid-field"><input id="allow-paid" type="checkbox">Allow a provider or model that may charge my account</label></div>' +
      '<p class="hint" id="provider-status" aria-live="polite"></p><div class="actions"><button class="primary" id="save-provider">Save provider</button><button class="action" id="clear-provider">Disconnect</button></div></div>' +
      '<div class="dialog-section"><h3>Community updates</h3><p class="hint">Checks continue while the local server is running, even with the map closed.</p><label class="form-field"><span>Check for new reports</span><select id="interval"><option value="24">Every 24 hours</option><option value="12">Every 12 hours</option><option value="6">Every 6 hours</option></select></label><button class="action" id="save-interval">Save schedule</button></div>' +
      '<div class="dialog-section"><h3>Local server</h3><p class="hint">Closing this tab keeps scheduled checks running. With npm, use <code>npx gta6-loot-map stop</code>. With the Windows ZIP, double-click <strong>Stop Atlas.cmd</strong>.</p><button class="action" id="stop-server">Stop server</button><p class="hint" id="server-status" role="status"></p></div>',
  );
  $("stop-server").onclick = async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await post("/api/launcher/stop", {instance: state.instance});
      open("Map server stopped", '<p>Scheduled checks are paused. You can close this tab.</p><p>Restart with <code>npx gta6-loot-map</code>, or double-click <strong>Start Atlas.cmd</strong> in the extracted Windows ZIP. From source, use <code>py app.py</code> on Windows or <code>python3 app.py</code> on macOS or Linux.</p>');
    } catch (err) {
      $("server-status").textContent = err.message;
      button.disabled = false;
    }
  };
  $("interval").value = state.interval || 24;
  $("provider").value = first;
  const providerInput = $("provider");
  const keyInput = $("key"), baseInput = $("base");
  let inventory = null, requestNumber = 0, timer, controller;
  let explicitModel = false;
  let explicitService = false, boundService = "", boundBase = "";
  function cancelProbe() {
    requestNumber++;
    clearTimeout(timer);
    controller?.abort();
    $("list-models").disabled = false;
  }
  function canProbe() {
    const kind = providerInput.value;
    return kind && kind !== "none" && (!["custom", "ollama-local"].includes(kind) || baseInput.value.trim());
  }
  function showRoute() {
    const kind = providerInput.value;
    const notes = {
      "": "Select the service that issued this key to check the connection.",
      "none": "Discovery and navigation run without a model.",
      "ollama-local": "The atlas checks installed models on your computer.",
    };
    let note = notes[kind] || "Enter a key or browse the model list. Choose its issuing service before connecting.";
    if (keyInput.value && kind) {
      note = kind === "custom" && !baseInput.value.trim()
        ? "Enter the API base URL to check this key with your chosen endpoint."
        : "Selected service: " + presets[kind] + ". Checking uses no inference.";
    }
    $("key-route").textContent = note;
  }
  function scheduleProbe(delay = 0) {
    cancelProbe();
    if (canProbe()) timer = setTimeout(refreshModels, delay);
  }
  function modelId() {
    const choice = $("model-choice").value;
    return choice === MANUAL ? $("model").value.trim() : choice;
  }
  function syncCustom() {
    $("custom-model-field").hidden = $("model-choice").value !== MANUAL;
  }
  function fillChoices(selected = "", keepCustom = false) {
    const kind = providerInput.value;
    const choice = $("model-choice");
    let models = inventory?.models || [];
    if (kind === "openrouter" && !$("allow-paid").checked)
      models = models.filter(id => id === "openrouter/free" || id.endsWith(":free"));
    choice.replaceChildren(new Option("Choose a model", ""));
    const recommended = inventory?.recommended;
    if (models.includes(recommended))
      choice.add(new Option(recommended + " · default", recommended));
    for (const id of models) {
      if (id !== recommended) choice.add(new Option(id, id));
    }
    if (selected && !models.includes(selected) && !keepCustom) {
      const label = inventory ? selected + " · outside current list" : selected;
      choice.add(new Option(label, selected));
    }
    choice.add(new Option("Enter a custom model ID…", MANUAL));
    choice.value = keepCustom ? MANUAL : selected || (!explicitModel && models.includes(recommended) ? recommended : "");
    syncCustom();
  }
  async function refreshModels() {
    const kind = providerInput.value;
    cancelProbe();
    if (!canProbe()) return;
    const version = requestNumber;
    const params = payload();
    if (params.key) {
      boundService = kind;
      if (kind === "custom") boundBase = params.base;
    }
    params.checkAccess = Boolean(params.key || (current.hasKey && current.kind === kind && (!params.base || params.base === current.base)));
    controller = new AbortController();
    const button = $("list-models");
    button.disabled = true;
    $("model-hint").textContent = params.checkAccess ? "Checking the selected service and loading models…" : "Checking the provider’s model list…";
    try {
      const result = await json("/api/provider/models", {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(params), signal: controller.signal,
      });
      if (version !== requestNumber || !providerInput.isConnected) return;
      const value = modelId(), custom = $("model-choice").value === MANUAL;
      inventory = result;
      if (kind === "ollama-cloud") {
        const {keyStatus, ...catalogue} = result;
        publicCatalogue = {time: Date.now(), result: catalogue};
      }
      fillChoices(explicitModel ? value : "", custom);
      describeInventory();
      if (result.keyStatus === "verified") $("key-route").textContent = presets[kind] + " confirmed this key. No inference was requested.";
      if (result.keyStatus === "catalogue-only" && params.checkAccess)
        $("key-route").textContent = "The catalogue responded. This service checks model access on the first enrichment.";
    } catch (err) {
      if (version !== requestNumber || !providerInput.isConnected) return;
      const fallback = inventory ? "Showing the last list loaded in this session." : "You can enter a custom ID.";
      $("model-hint").textContent = "Model list unavailable. " + fallback + " " + err.message;
      if (params.checkAccess) $("key-route").textContent = err.message;
    } finally {
      if (version === requestNumber && providerInput.isConnected) button.disabled = false;
    }
  }
  function describeInventory() {
    const selected = modelId();
    let text = inventory
      ? inventory.models.length + " text model IDs returned by the provider."
      : "Refresh to see this provider’s models, or enter a custom ID.";
    if (inventory && !inventory.models.length) text = "The provider returned no eligible models.";
    if (inventory?.recommended === "openrouter/free")
      text += " The free 120B model is absent from this list. The free router can use other available models.";
    else if (inventory?.recommended)
      text += " The default is " + inventory.recommended + ". You can choose another model.";
    if (inventory && selected && !inventory.models.includes(selected))
      text += " Your selected ID is outside this list. Check it with the provider.";
    $("model-hint").textContent = text;
  }
  function redraw() {
    const k = $("provider").value,
      same = k === current.kind;
    $("provider-fields").hidden = !k || k === "none";
    $("save-provider").disabled = !k;
    $("base-field").hidden = !["custom", "ollama-local"].includes(k);
    $("key-field").hidden = ["none", "ollama-local"].includes(k);
    $("base").value = same
      ? current.base || ""
      : k === "ollama-local"
        ? "http://127.0.0.1:11434"
        : "";
    cancelProbe();
    inventory = k === "ollama-cloud" ? publicCatalogue?.result : null;
    $("list-models").disabled = false;
    $("model").value = "";
    $("key").placeholder =
      same && current.hasKey
        ? "A key is set · leave blank to keep it"
        : "Enter a key on this computer";
    $("enable").checked = same && current.enabled;
    $("allow-paid").checked = same && current.allowPaid;
    $("paid-field").hidden = !["ollama-cloud", "openrouter", "opencode", "custom"].includes(k);
    explicitModel = Boolean(same && current.model);
    fillChoices(explicitModel ? current.model : "");
    describeInventory();
    $("provider-status").textContent = same ? current.lastStatus || "" : "";
    $("provider-advice").innerHTML =
      {
        "ollama-cloud":
          "Browsing models is free. Ollama Cloud meters inference. OpenRouter also offers free models. " + link("https://ollama.com/pricing", "Ollama pricing"),
        "ollama-local":
          "Use an installed model. Local inference uses your computer.",
        openrouter:
          "Free models are shown first. Availability and rate limits vary.",
        opencode:
          "OpenCode restricts its free chat models to its own client. Console API models can incur charges.",
        custom:
          "Supply a compatible chat-completions API root. Remote model pricing is set by that provider.",
      }[k] || "";
    showRoute();
    updateSaveLabel();
    const cached = k === "ollama-cloud" && publicCatalogue && Date.now() - publicCatalogue.time < 15 * 60_000;
    if (!cached || keyInput.value || (same && current.hasKey)) scheduleProbe();
  }
  function payload() {
    const k = $("provider").value,
      p = {
        kind: k,
        model: modelId(),
        enabled: $("enable").checked,
        allowPaid: $("allow-paid").checked,
      };
    if (["custom", "ollama-local"].includes(k)) p.base = $("base").value.trim();
    if (keyInput.value && !["", "none", "ollama-local"].includes(k)) p.key = keyInput.value;
    return p;
  }
  function status(s) {
    $("provider-status").textContent = s;
  }
  async function submit(button, fn) {
    button.disabled = true;
    try {
      await fn();
    } catch (e) {
      status(e.message);
      toast(e.message);
    } finally {
      button.disabled = false;
    }
  }
  function updateSaveLabel() {
    $("save-provider").textContent = $("enable").checked ? "Connect and scan" : "Save provider";
  }
  providerInput.onchange = () => {
    const kind = providerInput.value;
    if ((boundService && kind !== boundService) || ["none", "ollama-local"].includes(kind)) {
      keyInput.value = "";
      boundService = boundBase = "";
    }
    explicitService = Boolean(kind);
    if (keyInput.value && kind) boundService = kind;
    redraw();
  };
  keyInput.oninput = () => {
    cancelProbe();
    boundService = boundBase = "";
    const key = keyInput.value;
    const recognized = /^sk-or-v1-[0-9a-f]{64}$/i.test(key);
    if (recognized && providerInput.value !== "openrouter") {
      providerInput.value = "openrouter";
      explicitService = false;
      redraw();
    } else if (key && !recognized && (!explicitService || (key.startsWith("sk-or-v1-") && providerInput.value !== "openrouter"))) {
      providerInput.value = "";
      explicitService = false;
      redraw();
    } else {
      showRoute();
    }
    if (key && providerInput.value) boundService = providerInput.value;
    if (key && providerInput.value === "custom" && baseInput.value.trim()) boundBase = baseInput.value.trim();
    if (key.startsWith("sk-or-v1-") && !recognized) {
      cancelProbe();
      $("key-route").textContent = "Finish entering the OpenRouter key to check it.";
    } else scheduleProbe(450);
  };
  $("enable").onchange = updateSaveLabel;
  $("model-choice").onchange = () => { explicitModel = true; syncCustom(); describeInventory(); };
  $("allow-paid").onchange = () => {
    fillChoices(modelId(), $("model-choice").value === MANUAL);
    describeInventory();
  };
  $("base").oninput = () => {
    cancelProbe();
    if (boundBase && boundBase !== baseInput.value.trim()) {
      keyInput.value = "";
      boundService = boundBase = "";
    }
    inventory = null;
    $("list-models").disabled = false;
    fillChoices(modelId(), $("model-choice").value === MANUAL);
    describeInventory();
    showRoute();
  };
  baseInput.onchange = () => scheduleProbe();
  $("dialog").addEventListener("close", () => {
    requestNumber++;
    clearTimeout(timer);
    controller?.abort();
    keyInput.value = "";
  }, {once:true});
  redraw();
  $("save-interval").onclick = (e) =>
    submit(e.currentTarget, async () => {
      update(
        await post("/api/settings", { interval: Number($("interval").value) }),
      );
      toast("Refresh schedule saved.");
    });
  $("list-models").onclick = refreshModels;
  $("save-provider").onclick = (e) =>
    submit(e.currentTarget, async () => {
      cancelProbe();
      const params = payload();
      const res = await post("/api/provider", {...params, startDiscovery:params.enabled, manualModel:$("model-choice").value === MANUAL});
      update(res);
      $("key").value = "";
      $("dialog").close();
      const deferred = res.provider?.lastStatus?.startsWith("Model catalogue unsupported.");
      toast(res.initialDiscovery ? "Provider saved. Initial discovery requested." :
        deferred ? res.provider.lastStatus : "Provider settings saved.");
    });
  $("clear-provider").onclick = (e) =>
    submit(e.currentTarget, async () => {
      update(
        await post("/api/provider", { kind: "none", enabled: false, key: "" }),
      );
      $("key").value = "";
      $("dialog").close();
      toast("Provider disconnected.");
    });
}
