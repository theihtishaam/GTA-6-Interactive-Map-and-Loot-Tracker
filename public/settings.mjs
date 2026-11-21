import { $, link, post, toast } from "./ui.mjs";
const presets = {
  "ollama-cloud": ["Ollama Cloud", ""],
  "ollama-local": ["Ollama on this computer", ""],
  openrouter: ["OpenRouter · free router", "openrouter/free"],
  custom: ["Custom OpenAI-compatible endpoint", ""],
  opencode: ["OpenCode Console", ""],
  none: ["No model · zero inference", ""],
};
const MANUAL = "__custom__";
let publicCatalogue = null;
export function showSettings(state, open, update) {
  const current = state.provider || {},
    first =
      current.kind && current.kind !== "none" ? current.kind : "ollama-cloud";
  open(
    "Settings",
    '<h3>Community updates</h3><p class="hint">Checks continue while the local server is running, even with the map closed.</p><label class="form-field"><span>Check for new reports</span><select id="interval"><option value="24">Every 24 hours</option><option value="12">Every 12 hours</option><option value="6">Every 6 hours</option></select></label><button class="action" id="save-interval">Save schedule</button>' +
      '<div class="dialog-section"><h3>Optional model</h3><p class="hint">The atlas runs free without AI. Enable enrichment to process at most one new public report per refresh.</p>' +
      '<label class="form-field"><span>Provider</span><select id="provider">' +
      Object.entries(presets)
        .map(
          ([id, [label]]) =>
            '<option value="' + id + '">' + label + "</option>",
        )
        .join("") +
      "</select></label>" +
      '<div id="provider-fields"><label class="form-field" id="base-field"><span>API base URL</span><input id="base" type="url" placeholder="https://provider.example/v1" autocomplete="off"></label>' +
      '<label class="form-field"><span id="model-choice-label">Model</span><select id="model-choice" aria-labelledby="model-choice-label" aria-describedby="model-hint"></select></label>' +
      '<label class="form-field" id="custom-model-field" hidden><span>Custom model ID</span><input id="model" autocomplete="off" placeholder="Enter the provider’s exact model ID"></label>' +
      '<p class="hint" id="model-hint" aria-live="polite"></p>' +
      '<label class="form-field" id="key-field"><span>API key · kept in server memory until restart</span><input id="key" type="password" autocomplete="off" spellcheck="false" placeholder="Enter a key on this computer"></label>' +
      '<button class="action" id="list-models">Refresh model list</button><p class="hint" id="provider-advice"></p>' +
      '<label class="checkline"><input id="enable" type="checkbox">Use this model to enrich new reports</label>' +
      '<label class="checkline" id="paid-field"><input id="allow-paid" type="checkbox">Allow a provider or model that may charge my account</label></div>' +
      '<p class="hint" id="provider-status" aria-live="polite"></p><div class="actions"><button class="primary" id="save-provider">Save provider</button><button class="action" id="clear-provider">Disconnect</button></div></div>',
  );
  $("interval").value = state.interval || 24;
  $("provider").value = first;
  const providerInput = $("provider");
  let inventory = null, requestNumber = 0;
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
      choice.add(new Option(recommended + " · suggested for short extracts", recommended));
    for (const id of models) {
      if (id !== recommended) choice.add(new Option(id, id));
    }
    if (selected && !models.includes(selected) && !keepCustom) {
      const label = inventory ? selected + " · outside current list" : selected;
      choice.add(new Option(label, selected));
    }
    choice.add(new Option("Enter a custom model ID…", MANUAL));
    choice.value = keepCustom ? MANUAL : selected;
    syncCustom();
  }
  async function refreshModels() {
    const kind = providerInput.value;
    const version = ++requestNumber;
    const button = $("list-models");
    button.disabled = true;
    $("model-hint").textContent = "Checking the provider’s model list…";
    try {
      const params = kind === "ollama-cloud" ? {kind} : payload();
      const result = await post("/api/provider/models", params);
      if (version !== requestNumber || !providerInput.isConnected) return;
      const value = modelId(), custom = $("model-choice").value === MANUAL;
      inventory = result;
      if (kind === "ollama-cloud")
        publicCatalogue = {time: Date.now(), result};
      fillChoices(value, custom);
      describeInventory();
    } catch (err) {
      if (version !== requestNumber || !providerInput.isConnected) return;
      const fallback = inventory ? "Showing the last list loaded in this session." : "You can enter a custom ID.";
      $("model-hint").textContent = "Model list unavailable. " + fallback + " " + err.message;
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
    if (inventory?.recommended)
      text += " The suggested model, " + inventory.recommended + ", supports low reasoning effort and has a low published token price.";
    if (inventory && selected && !inventory.models.includes(selected))
      text += " Your selected ID is outside this list. Check it with the provider.";
    $("model-hint").textContent = text;
  }
  function redraw() {
    const k = $("provider").value,
      same = k === current.kind;
    $("provider-fields").hidden = k === "none";
    $("base-field").hidden = !["custom", "ollama-local"].includes(k);
    $("key-field").hidden = k === "ollama-local";
    $("base").value = same
      ? current.base || ""
      : k === "ollama-local"
        ? "http://127.0.0.1:11434"
        : "";
    requestNumber++;
    inventory = k === "ollama-cloud" ? publicCatalogue?.result : null;
    $("list-models").disabled = false;
    $("model").value = "";
    $("key").value = "";
    $("key").placeholder =
      same && current.hasKey
        ? "A key is set · leave blank to keep it"
        : "Enter a key on this computer";
    $("enable").checked = same && current.enabled;
    $("allow-paid").checked = same && current.allowPaid;
    $("paid-field").hidden = !["ollama-cloud", "openrouter", "opencode", "custom"].includes(k);
    fillChoices(same ? current.model || presets[k][1] : presets[k][1]);
    describeInventory();
    $("provider-status").textContent = same ? current.lastStatus || "" : "";
    $("provider-advice").innerHTML =
      {
        "ollama-cloud":
          "Browsing this list is free. Ollama Cloud meters every inference request against usage credits. For free cloud inference, choose the OpenRouter free router. " + link("https://ollama.com/pricing", "Ollama pricing"),
        "ollama-local":
          "Use an installed model. Local inference uses your computer.",
        openrouter:
          "openrouter/free uses the free router. Availability and rate limits vary.",
        opencode:
          "OpenCode restricts its free chat models to its own client. Console API models can incur charges.",
        custom:
          "Supply a compatible chat-completions API root. Remote model pricing is set by that provider.",
      }[k] || "";
    if (k === "ollama-cloud" && (!publicCatalogue || Date.now() - publicCatalogue.time > 15 * 60_000))
      refreshModels();
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
    if ($("key").value) p.key = $("key").value;
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
  $("provider").onchange = redraw;
  $("model-choice").onchange = () => { syncCustom(); describeInventory(); };
  $("allow-paid").onchange = () => {
    fillChoices(modelId(), $("model-choice").value === MANUAL);
    describeInventory();
  };
  $("base").oninput = () => {
    requestNumber++;
    inventory = null;
    $("list-models").disabled = false;
    fillChoices(modelId(), $("model-choice").value === MANUAL);
    describeInventory();
  };
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
      const res = await post("/api/provider", payload());
      update(res);
      $("key").value = "";
      $("dialog").close();
      toast("Provider settings saved.");
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
