# How to run any model against a question set

Goal: point the benchmark at a model behind an OpenAI-compatible API — OpenAI,
xAI Grok, DeepSeek, Zhipu GLM, Moonshot Kimi, OpenRouter, Together, or a local
proxy — and score it on the existing LDS set (or on a set of your own).

This is the `openai_compat` backend. It complements the three in
[add-a-model.md](add-a-model.md) (`claude_cli`, `anthropic_api`, `ollama`);
read that page for the cohort-entry mechanics and effort handling. Everything
here is the delta for a hosted, OpenAI-shaped provider.

Honest status: this path is **implemented and unit-tested** (`tests/test_openai_compat.py`)
but has not been run against a live provider in a published cohort. The wire
shape is pinned by tests; treat the numbers you get as your own run, not part of
v0.1.

## What the backend does

Every backend in `deseretbench/runner.py` shares one contract —
`(model, system, prompt, effort, timeout, opts) -> CallResult`. `openai_compat`
POSTs `{model, messages, stream:false}` to `{base_url}/chat/completions` with a
`Authorization: Bearer <key>` header, and reads `choices[0].message.content`.
No SDK, no new dependency (it uses `urllib`, like the ollama backend).

Two deliberate choices worth knowing:

- **`model_served` is reported as `None`.** Providers echo dated snapshots
  (`gpt-5` → `gpt-5-2026-01-15`) that don't fit the Anthropic alias shape the
  served-model guard understands, so reporting the echoed id would throw away a
  perfectly good answer as a false "fallback". The echoed id is kept in
  `served_all` for provenance instead.
- **`reasoning_effort` is off unless you opt in.** Many providers reject an
  unrecognised field with a 400, so the abstract `effort` knob is *not* sent as
  `reasoning_effort` unless `openai_map_effort: true`.

## 1. Get a key and set the provider

The backend authenticates with an **API key** read from an environment variable
you name. Set two things in `configs/run_config.yaml` under `runner:` (a
commented stanza is already there):

```yaml
runner:
  # ...
  openai_base_url: https://api.x.ai/v1     # the provider's base URL
  openai_api_key_env: XAI_API_KEY          # env var that holds the key
  # openai_map_effort: true                # only for models that accept reasoning_effort
  # openai_extra_body: {temperature: 0}    # extra params merged into the request body
```

Then export the key in the shell that runs the benchmark:

```bash
export XAI_API_KEY=...        # never commit this
```

Common providers (all OpenAI-compatible):

| Provider   | `openai_base_url`                       | key env (your choice) |
|------------|-----------------------------------------|-----------------------|
| OpenAI     | `https://api.openai.com/v1`             | `OPENAI_API_KEY`      |
| xAI Grok   | `https://api.x.ai/v1`                   | `XAI_API_KEY`         |
| DeepSeek   | `https://api.deepseek.com`              | `DEEPSEEK_API_KEY`    |
| Zhipu GLM  | `https://open.bigmodel.cn/api/paas/v4`  | `ZHIPU_API_KEY`       |
| Moonshot   | `https://api.moonshot.cn/v1`            | `MOONSHOT_API_KEY`    |
| OpenRouter | `https://openrouter.ai/api/v1`          | `OPENROUTER_API_KEY`  |

> **Subscription vs API key.** This backend needs a **key**. A consumer chat
> subscription (ChatGPT Plus, X Premium) is not a key. To drive a subscription
> you need a proxy that exchanges the session for an OpenAI-shaped endpoint;
> point `openai_base_url` at that proxy and `openai_api_key_env` at whatever
> token it wants. Standing up that proxy is a separate task from this one.

Because the base URL and key are configured once per run, **test one provider at
a time**: set the provider, run, then switch. (Grok and OpenAI can't be in the
same cohort run today — a small future ergonomic improvement, not a limitation
of the scoring.)

## 2. Add the models to the cohort

Append entries to `configs/models.yaml` with `backend: openai_compat`:

```yaml
cohort:
  # ...
  - id: grok-5                    # the provider's model id, verbatim
    tier: grok
    label: "Grok 5"
    generation: 5.0
    backend: openai_compat
```

Probe one cheaply before a full run:

```bash
XAI_API_KEY=... .venv/bin/python - <<'PY'
from deseretbench.runner import Runner
cfg = {"runner": {"backend": "claude_cli",
                  "openai_base_url": "https://api.x.ai/v1",
                  "openai_api_key_env": "XAI_API_KEY"}}
r = Runner(cfg).call("grok-5", "You are answering a knowledge assessment.",
                     "What is 7+5? Reply with only the number.", "low",
                     backend="openai_compat")
print(r.ok, repr(r.text), r.served_all, r.error)
PY
```

A bad key or unknown model fails fast (no retries): `openai http 401/404` are in
`_PERMANENT_ERROR_MARKERS`; `429` and `5xx` retry.

## 3. Run — against the LDS set, or your own

Against the existing LDS questions (cache means only the new model costs
anything):

```bash
.venv/bin/python -m deseretbench.run_benchmark mc \
  --questions data/questions_mc.jsonl --out runs/my_run --models grok-5
.venv/bin/python -m deseretbench.run_benchmark open \
  --questions data/questions_open.jsonl --out runs/my_run --models grok-5
```

Against a set of your own, point `--questions` at any JSONL that validates
against the schema (see [../reference/data-formats.md](../reference/data-formats.md));
for a different tradition, generate one as a faith pack (see
[add-a-faith-pack.md](add-a-faith-pack.md)).

Then analyze and report as usual:

```bash
.venv/bin/python -m deseretbench.analyze --run runs/my_run --out results/summary.json
.venv/bin/python -m deseretbench.report --summary results/summary.json
```
