# Choosing a model

The atlas ships with enrichment off. Community refreshes, map positions, navigation and player checklists work in this mode. The general scan can run every 6, 12 or 24 hours while the server is running.

| Choice | When to use it | Provider cost |
| --- | --- | --- |
| No model | Read the atlas and refresh community sources | No inference |
| OpenRouter | Use a hosted free model within the provider’s limits | The picker prefers the free 120B ID when listed and otherwise selects the free router if listed. [Free 120B](https://openrouter.ai/openai/gpt-oss-120b:free) · [Free router](https://openrouter.ai/openrouter/free) |
| Ollama on this computer | Use an already installed text model | Inference uses your own hardware. [Ollama pricing](https://ollama.com/pricing) |
| Ollama Cloud | Use an Ollama key and accept metered inference for optional enrichment | Pay-as-you-go requests consume usage credits. [Ollama pricing](https://ollama.com/pricing) |

## The default model

**GPT-OSS 120B** is preselected in a fresh Ollama Cloud connection when its catalogue includes `gpt-oss:120b`. Running it through the cloud uses the provider’s hardware and requires consent to possible charges. Ollama Local selects the same ID when you already have it installed. You can select a smaller model such as `gpt-oss:20b` or another available model. [Ollama Cloud model and API ID](https://ollama.com/library/gpt-oss:120b-cloud) · [Ollama pricing](https://ollama.com/pricing) · [Local model](https://ollama.com/library/gpt-oss:120b)

**For free hosted inference**, choose OpenRouter. On November 21, 2026 its catalogue advertised the paid 120B model and its free router. The free 120B model page existed, but the public endpoint list for that variant was empty. The picker will prefer `openai/gpt-oss-120b:free` if it appears in the model catalogue. Until then, `openrouter/free` can serve another free model. The app keeps a model you explicitly select when you refresh. [Model catalogue](https://openrouter.ai/api/v1/models) · [Free 120B endpoint inventory](https://openrouter.ai/api/v1/models/openai/gpt-oss-120b:free/endpoints)

The atlas requests low reasoning effort for the named 120B model on Ollama and OpenRouter and caps generation at 220 tokens for the short extraction task. It sends at most one extraction request per general refresh. A new report must supply a matching source quotation for the app to retain a generated instruction. Bounty Watch runs independently of model inference.

## Connecting from Settings

1. Open **Settings**. You can browse the public Ollama Cloud catalogue before entering a key. To connect, paste the key into the local app. The documented OpenRouter key format selects OpenRouter automatically. For an opaque key, choose the service that issued it. For a custom provider, also enter its exact API base URL. Changing the service or an already contacted custom endpoint clears the entered key. [OpenRouter key format](https://openrouter.ai/docs/api/api-reference/api-keys/create-a-new-api-key)
2. The model list loads automatically. Keep the selected default or choose another model. When no supported default is available, the picker asks you to choose. **Refresh model list** retries on demand. The public Ollama list stays available in the open page for 15 minutes. A retired manual selection remains visible with an availability note. **Enter a custom model ID** accepts exact identifiers.
3. Check **Use this model to enrich new reports** and choose **Connect and scan**. Providers or models that may charge require separate cost consent. Once the connection is set up, the server queues one general community scan. Repeated saves of the same active settings leave the queue alone. The scan sends at most one new or changed public excerpt to the model. If there is no eligible excerpt, it makes zero inference requests.
4. Change the general cadence under **Community updates**. The initial scan preserves the selected 6, 12 or 24 hours and the independent Bounty Watch schedule. Choose **Disconnect** for no-model mode. Local Ollama works with an installed text model and needs no API key.

## What the connection check establishes

| Selected service | How the check works |
| --- | --- |
| Ollama Cloud | The model list is public. With a key, the atlas separately sends a Bearer-authenticated `POST /api/me` to ollama.com and requires the account-name field in its successful response. It discards the account details. This is the account endpoint used by Ollama’s native client. Model-specific access, quota and billing are determined during inference. [Ollama client](https://github.com/ollama/ollama/blob/main/api/client.go) · [Ollama authentication](https://docs.ollama.com/api/authentication) |
| OpenRouter | A separate Bearer-authenticated `GET /api/v1/key` must return the expected current-key record. The atlas discards the record. It retrieves the model list anonymously. [OpenRouter current-key API](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key) |
| Local Ollama | The atlas asks the chosen loopback address for its installed model tags. Cloud-backed tags are excluded. [Ollama list API](https://docs.ollama.com/api/tags) |
| Custom compatible endpoint or OpenCode Console | The picker reports catalogue availability. A custom endpoint may require the key for its model list. A manually entered model can be saved for a service with an incomplete catalogue. If the server explicitly reports that model listing is unsupported, the manual model waits for the next scheduled or user-requested scan. A rejected key or another failed connection check stops the save. Enrichment checks model access when there is an eligible public excerpt. |

The server holds the key in memory for the current run. It stores the service, endpoint, model and cost preference in local settings. Restarting the server requires re-entering a remote key. The key goes only to the selected provider, and the client does not follow endpoint redirects. An unavailable catalogue or unsuccessful protected check displays its status in Settings. Browsing or checking a connection never sends a chat request.

The public Ollama inventory returned **24 IDs** on the review date. Its metadata flagged one as unavailable in the API. The implemented filter consequently offered **23 text-model IDs**. Inventory requests and chat requests are separate. Only the anonymous inventory was tested against live Ollama infrastructure. Configuration, extraction and provider errors were exercised with synthetic fixtures. [Public inventory](https://ollama.com/v1/models) · [Ollama Cloud API](https://docs.ollama.com/cloud)
