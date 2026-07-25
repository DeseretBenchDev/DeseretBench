# ADR-0013: The 2026 cohort expansion and GPU-served local inference

Status: Accepted

Date: 2026-07-23

## Context

Two things changed at once: the local cohort went stale, and the machine grew a
working GPU.

**The cohort was stale, verifiably.** Every local family in v0.1 predates 2026,
by the ollama library's own index timestamps: `qwen3` 2025-10-10, `gemma3`
2025-08-15, `deepseek-r1` 2025-07-02, `phi4-mini` 2025-02-28, `smollm2` 2024.
No `qwen3` tag was added or updated in the January–July 2026 window at all. A
benchmark whose open-weights cohort is a year behind measures history.

**The GPU works now.** v0.1's local cohort ran CPU-only because the card was on
nouveau; the proprietary driver (580.173.02 / CUDA 13.0) now serves inference,
which is what makes re-running a larger local cohort affordable at all. The
operator-side runbook for GPU-served local models is kept outside this repo,
alongside the watchdog, because it hardcodes machine-specific paths.

Candidates were selected by inverting the usual order: enumerate the **ollama
library** first — it is simultaneously the authoritative dated index and the
exact set this harness can serve — then verify each survivor's provenance
against its first-party Hugging Face org. Anything failing *any* of four filters
was rejected outright rather than scored lower: exact tag exists · a usable
non-thinking path · known quantization · first-party provenance and license.

## Decision

**Add five models, one per vendor family** — Granite, Qwen3.5, Ministral,
Nemotron, Gemma 4 — with every tag pinned exactly:

| Tag | Size | Vendor / license | Note |
|---|---|---|---|
| `granite4.1:3b` | 2.1 GB | IBM · Apache-2.0 | no `latest` tag exists; size must be explicit |
| `qwen3.5:4b` | 3.4 GB | Alibaba | no `-instruct` tag published anywhere |
| `ministral-3:3b` | 3.0 GB | Mistral · Apache-2.0 | reasoning is a *separate* repo |
| `nemotron-3-nano:4b` | 2.8 GB | NVIDIA · NVIDIA Open Model License | the one non-permissive entry |
| `gemma4:e2b-it-qat` | 4.3 GB | Google | QAT build — see asymmetry below |

Pinning is not pedantry here: three of these families ship a `latest` that is
unusable on a 6 GB card. `nemotron-3-nano:latest` is a 24 GB 30B;
`qwen3.5:latest` is the 6.6 GB 9B. A bare `ollama pull` would fetch the wrong
artifact silently.

**Send the `think` key to the families that need it.** `_OLLAMA_THINK_FAMILIES`
gained `nemotron` and `gemma4`. Matching is substring-on-the-tag, so the Gemma
entry must be exactly `gemma4` — a bare `gemma` would also match the
non-thinking `gemma3` builds, where sending the key 400s. `qwen3` already
covers `qwen3.5` by substring.

This is load-bearing rather than cosmetic. Both new families reason by default
and publish no instruct variant. Without the key they consume the entire
`num_predict` budget on reasoning and return an empty answer — the failure is
silent and total, not merely slow, so an MC track would record blanks rather
than errors.

**Qwen3.5 is included despite having no `-instruct` tag** because this harness
already uses the one control surface that works: `/api/chat` with a **top-level**
`think` field. The widely-reported failures come from placing `think` inside
`options` (silently ignored) or using `/api/generate` (ignores it). Verified
live: a correct answer in 197 tokens at `effort=low`, fully GPU-resident.

## Consequences

- **Gemma 4 carries a documented quantization asymmetry.** The only gemma4 tag
  that fits 6 GB is the QAT build at 4.3 GB; every q4_K_M variant is 7.2 GB or
  larger. So this one entry is quantization-aware-trained while the rest of the
  local cohort is Q4_K_M. That is a real confound for any Gemma-4-vs-others
  comparison and is recorded here rather than buried — the alternative was
  excluding Gemma 4 entirely.
- **Statistical power drops for everyone.** The Holm family is all pairs, so the
  cohort going 17 → 22 takes it from C(17,2)=136 to **C(22,2)=231**. Every
  existing comparison becomes more conservative, including the frontier
  Claude-vs-Claude ones that are the most interesting. This is the same tax
  documented when the cohort went 9 → 17, and it is the reason the expansion is
  one model per family rather than every size of each.
- **Provenance breadth improves markedly**, which is the offsetting gain: the
  cohort adds IBM, Mistral, and NVIDIA as vendors. A cross-vendor result is
  harder to dismiss than another size of a family already present.
- **One entry is not permissively licensed.** Nemotron ships under the NVIDIA
  Open Model License rather than Apache/MIT. It is measured, not redistributed,
  so this is a note rather than a blocker — but it is the only cohort entry whose
  terms would need review before anything is redistributed.
- **The cache is not busted.** The key is
  `{backend, model, system, prompt, effort, run_index}` and does not include the
  `think` flag or the hardware, so the existing 17 models replay for free and
  only genuinely-new calls run. It also means v0.1's local numbers are
  CPU-provenance while new ones are GPU-served; identical greedy decoding should
  agree, but the two are not bit-guaranteed identical and should not be silently
  mixed within one comparison.

## Links

- [ADR-0011](0011-local-open-weights-backend.md) — the ollama backend and the
  original local cohort this extends
- [ADR-0010](0010-cohort-selection-by-cli-probe.md) — cohort-selection precedent
- [ADR-0006](0006-statistical-testing-protocol.md) — the Holm family the
  expansion taxes
- `configs/models.yaml`, `deseretbench/runner.py` (`_OLLAMA_THINK_FAMILIES`),
  `tests/test_ollama.py`
