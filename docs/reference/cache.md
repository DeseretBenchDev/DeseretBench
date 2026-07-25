# Response cache reference

DeseretBench caches every successful model call on disk, content-addressed by
what was asked. This is what makes runs resume-safe: a re-run skips completed
work and only fills gaps. This page describes the cache exactly as implemented
in `deseretbench/runner.py`. For recovering an interrupted run, see
[recover-interrupted-run](../how-to/recover-interrupted-run.md); for the design
reasoning, see [measurement integrity](../explanation/measurement-integrity.md).

## Location and layout

The cache is a single **flat directory of `<sha256-hex>.json` files** at the
repo root: `./cache/`. One file per cached call; no subdirectories, no index.
Each file's content is the JSON of a `CallResult` (`CallResult.to_json()`,
`runner.py:61-65`), with the bulky `raw` CLI blob dropped — the raw backend
response is never persisted.

Which code uses which directory:

| Caller | Cache directory |
|---|---|
| `run_benchmark.py` | `ROOT / run_config.yaml runner.cache_dir` (currently `cache`) — the only caller that honors the config key (`run_benchmark.py:131,223`) |
| `author.py` | hardcoded `ROOT/'cache'` (`author.py:258`) |
| `validate_questions.py` | hardcoded `ROOT/'cache'` (`validate_questions.py:101`) |
| `python -m deseretbench.runner` (smoke test) | `cache` **relative to the current working directory** (`runner.py:420`) — run it from the repo root or it creates a stray `cache/` |

Today all config and hardcoded values agree on repo-root `./cache`, so
everything shares one cache. Changing `runner.cache_dir` in
`configs/run_config.yaml` would move only `run_benchmark.py`'s cache and
silently split it from authoring/validation.

The directory is gitignored (`cache/` in `.gitignore`).

## Cache key

The key is the SHA-256 of a canonical JSON encoding of exactly six fields
(`_cache_key`, `runner.py:73-82`):

```python
json.dumps(
    {"b": backend, "m": model, "s": system, "p": prompt,
     "e": effort, "r": run_index},
    sort_keys=True, ensure_ascii=False,
)
```

encoded as UTF-8 and hashed. `sort_keys=True` makes the encoding
order-independent; `ensure_ascii=False` keeps non-ASCII characters literal
(so the hash is over the actual text, not `\uXXXX` escapes).

| Field | Meaning |
|---|---|
| `b` | backend name (`claude_cli` or `anthropic_api`) |
| `m` | requested model id |
| `s` | system prompt text |
| `p` | full rendered user prompt |
| `e` | effort level (`low`/`medium`/`high`/…) |
| `r` | run index (which repeat, 0-based) |

### Deliberately excluded fields

These are execution parameters, not the question being asked — changing them
should reuse existing answers, not re-buy them:

| Excluded | Rationale |
|---|---|
| `timeout_seconds` | How long we wait doesn't change what was asked; the config file annotates it "not part of the cache key". |
| `tools` | Always `""` in practice; a transport option, not prompt content. |
| `max_retries` / `retry_backoff_seconds` | Retry policy affects how a result was obtained, not what it is. |
| `max_parallel` | Scheduling width; irrelevant to any single call. |

### What invalidates the cache

Any change to a keyed field yields a new hash, i.e. a fresh (billed) call:

- the system prompt (`run_config.yaml system_prompt`)
- the rendered prompt text — item wording **or** the Jinja2 templates
  (`mc_prompt_template` / `open_prompt_template`), including whitespace
- the effort level for that item class (`run_config.yaml effort.*`)
- the model id — including alias vs. dated snapshot: `claude-opus-4-8` and
  `claude-opus-4-8-20260115` are different cache keys even though the served
  model may be identical
- the backend (`claude_cli` ↔ `anthropic_api` never share entries)
- the run index (each repeat run is its own entry)

## Read path (guards)

On `Runner.call` with `use_cache=True` (the default), a cached entry is served
only if **both** hold (`runner.py:343-356`):

1. `ok` is truthy — failed calls are never served from cache (they are also
   never written; see below), so failures retry on every resume.
2. `_served_matches(model_requested, model_served)` — the entry's recorded
   serving model matches the request, tolerating only alias↔dated-snapshot
   resolution (a `-YYYYMMDD` suffix in either direction, `runner.py:292-311`).
   This rejects silent-fallback artifacts cached before the served-model guard
   existed, so resumes re-run them instead of laundering the contamination.

Any exception while reading or parsing an entry (corrupt JSON, truncated file)
is silently swallowed and the call is recomputed (`runner.py:355-356`). A
served cache hit is reconstructed field-filtered against the `CallResult`
dataclass and gets `cache_hit=True` forced.

`use_cache=False` skips both the read and the write.

## Write path

Only **successful** results are written (`runner.py:379-380`):

```python
if last.ok and use_cache:
    cpath.write_text(json.dumps(last.to_json(), ensure_ascii=False))
```

Failures, timeouts, and served-mismatch results never enter the cache.
Consequence: interrupted or partially failed runs are cheap to resume (hits are
free and instant), but persistently failing items cost a live attempt on every
resume.

## Legacy-entry compatibility

The `CallResult` schema has grown over the project's life. Older entries on
disk lack `served_all`, `called_at`, `cache_creation_input_tokens`, and
`cache_read_input_tokens`. The read path handles this by construction: unknown
fields are dropped and missing fields take dataclass defaults
(`runner.py:351-353`), so old entries load fine — but cache hits from them
report `0` for the cache-token fields and `None` for `called_at`. Any tooling
that aggregates cache files must treat these fields as optional.

## Operational notes

- **Size:** roughly 21–22k entries (~90 MB) as of July 2026; the directory
  grows monotonically since entries are never evicted or overwritten with
  failures.
- **Safe to delete, but expensive:** removing `cache/` loses no benchmark
  results (those live in `runs/`), but the next run re-executes — and
  re-bills — every call from scratch. There is no partial-invalidation tool;
  to force a re-run of a specific slice, change a keyed field or use
  `use_cache=False` in code.
- **Cache hits and accounting:** hits do not increment `Runner.n_live_calls`
  and add nothing to `Runner.total_spend_usd`; they keep the original
  `called_at` timestamp from disk.

## See also

- [configuration.md](configuration.md) — `runner.cache_dir` and the other runner keys
- [data-formats.md](data-formats.md) — the `CallResult` fields that appear in cached entries
- [recover-interrupted-run](../how-to/recover-interrupted-run.md) — resuming a run on top of the cache
