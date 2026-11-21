# Choosing a model

The atlas ships with enrichment off. Community refreshes, map positions, navigation and player checklists work in this mode. The general scan can run every 6, 12 or 24 hours while the server is running.

| Choice | When to use it | Provider cost |
| --- | --- | --- |
| No model | Read the atlas and refresh community sources | No inference |
| OpenRouter · free router | Extract occasional text using hosted free models | The `openrouter/free` router lists zero input and output token prices. Its available models and service limits vary. [Free router](https://openrouter.ai/openrouter/free) |
| Ollama on this computer | Use an already installed text model | Inference uses your own hardware. [Ollama pricing](https://ollama.com/pricing) |
| Ollama Cloud | Use an Ollama key and accept metered inference for optional enrichment | Pay-as-you-go requests consume usage credits. [Ollama pricing](https://ollama.com/pricing) |

## The Ollama Cloud suggestion

On **November 21, 2026**, Ollama’s canonical pricing page listed per-token rates for every cloud model, including accounts with a $0 subscription price. We could not verify an unconditionally free Ollama Cloud model. For a hosted free option in the atlas, choose **OpenRouter · free router** and keep the free router selected. [Ollama pricing](https://ollama.com/pricing) · [OpenRouter pricing for the free router](https://openrouter.ai/openrouter/free)

For short text extraction on Ollama Cloud, the picker suggests **`gpt-oss:20b`** when the live inventory includes it. Ollama lists a 20.9B model with configurable reasoning and a published price of **$0.07 per million input tokens and $0.30 per million output tokens** at review time. Its larger 120B sibling was listed at $0.15 and $0.60 respectively. This is a cost-based choice for a short quote-extraction task. We have no cross-model accuracy or latency benchmark for GTA VI reports. [Ollama pricing table](https://ollama.com/pricing) · [Model card](https://ollama.com/library/gpt-oss:20b) · [Reasoning controls](https://docs.ollama.com/capabilities/thinking)

The atlas requests low reasoning effort for this model and sets a 220-token generation limit. It sends at most one extraction request per general refresh. A new report must supply a matching source quotation for the app to retain a generated instruction. Bounty Watch runs independently of model inference.

## Using the dropdown

1. Open **Settings** and choose a provider. Opening the Ollama Cloud picker retrieves its public model IDs without a key. Reopening Settings within 15 minutes reuses the catalogue on that page. **Refresh model list** requests an update.
2. Select a model in the dropdown. A suggested model is labeled and requires you to select it. If your existing selection disappears, the picker preserves the ID and labels it outside the current list. You can also choose **Enter a custom model ID**.
3. For Ollama Cloud, enter the key in the local app, enable enrichment and explicitly permit possible charges. Saving an inactive provider allows you to keep exploring without running inference. Disconnecting returns the app to no-model mode.
4. If the catalogue cannot load, the picker identifies a previous list when available and offers custom entry. A listed model can still be unavailable to an account or temporarily rate-limited. The atlas makes no paid fallback selection.

The public Ollama inventory returned **24 IDs** on the review date. Its metadata flagged one as unavailable in the API. The implemented filter consequently offered **23 text-model IDs**. Inventory requests and chat requests are separate. Only the anonymous inventory was tested against live Ollama infrastructure. Configuration, extraction and provider errors were exercised with synthetic fixtures. [Public inventory](https://ollama.com/v1/models) · [Ollama Cloud API](https://docs.ollama.com/cloud)
