# November 2026: the eight-model box cohort (2026-11-08 to 2026-11-09)

Eight local open-weights models were added to the cohort. This note records what ran, what did
not and why. Scores are from `results/summary.json` (analysis seed 19470417, 100,000 bootstrap
resamples); model sampling is not seeded.

**Setup.** One consumer graphics card, Ollama 0.40.7, one model resident, serial requests, `num_ctx` 20480,
`num_predict` 16000. Shipped question set, unchanged. MC 2 repeats at low effort; open-ended 2
repeats at high effort, judged by `claude-sonnet-4-6` under three personas through the `claude` CLI.
The repeat counts follow the October additions: 2 MC throughout, and 2 open as the most recent
October runs used (their two Claude models ran 3).

**Every score in the table below rests on two repeats of each item, on both tracks.** For the
open-ended track that is 80 judged answers per model (40 items × 2), against 120 for the v0.1
cohort, which ran three. Two is the final count for these eight models. Scores are per-item
means, so the smaller count widens the intervals and does not change what is estimated.

| Model | Tag | Quantization | MC, 2 repeats (95% CI) | Open-ended, 2 repeats (95% CI) |
|---|---|---|---|---|
| Granite 4.2 8B | `granite4.2:8b` | Q4_K_M | 0.941 [0.913, 0.967] | 36.1 [31.8, 40.3] |
| Gemma 4 12B | `gemma4-12b:q4_0` | Q4_0 | 0.991 [0.981, 0.998] | 33.5 [30.0, 36.7] |
| Gemma 4 E4B | `gemma4:e4b-it-q4_K_M` | Q4_K_M | 0.951 [0.923, 0.974] | 29.2 [26.4, 32.0] |
| Falcon-H1R 7B | `hf.co/tiiuae/Falcon-H1R-7B-GGUF:Q4_K_M` | Q4_K_M | 0.887 [0.847, 0.923] | 28.0 [24.8, 30.9] |
| OLMo 3 7B Think | `olmo-3:7b-think` | Q4_K_M | 0.883 [0.843, 0.918] | 19.3 [16.8, 21.7] |
| LFM2.5 8B | `lfm2.5:8b` | Q4_K_M | 0.871 [0.831, 0.908] | 18.8 [16.1, 21.5] |
| Apertus 8B Instruct | `hf.co/unsloth/Apertus-8B-Instruct-2509-GGUF:Q4_K_M` | Q4_K_M | 0.915 [0.880, 0.946] | 17.3 [15.5, 19.0] |
| OLMo 3 7B Instruct | `olmo-3:7b-instruct` | Q4_K_M | 0.906 [0.871, 0.939] | 15.7 [12.8, 18.6] |

All 3,408 MC calls and 640 open generations succeeded, and all 1,920 judge verdicts parsed. Judge
α over the merged cohort is 0.992. Mean within-item standard deviation across the 2 MC repeats, in
the table's order: 0.036, 0.013, 0.030, 0.060, 0.073, 0.070, 0.053, 0.053. The
same statistic across the 2 open-ended repeats, in composite points (0–100) and in the same order:
6.9, 3.8, 4.5, 4.7, 4.2, 4.5, 3.9, 4.2. Each open-ended repeat is a fresh answer judged afresh, so
that figure includes the judges' spread. The thirteen earlier local models, which ran three
repeats, range from 0.5 to 6.7 on the same statistic.

## Not run

| Model | Reason |
|---|---|
| `phi4:14b` | not run at the shared window: VRAM (12.7 GB resident). Measured on 11 November on multiple choice only, under its own 2,048-token window: 0.986 [0.969, 0.998]. See PAPER §4.7. |
| `gpt-oss:20b` | not run: VRAM (13.8 GB on disk) |
| `gemma4:26b` | not run: VRAM (18.7 GB on disk) |
| `muse-glimmer:30b` | not run: VRAM (18.2 GB on disk) |
| `rnj-1:8b` | not run: load failure (`GGML_ASSERT(hparams.is_swa_any())`, twice) |

Fit was judged at `num_ctx` 20480 from the larger of the on-disk size and the resident size Ollama
reports. Ollama's reported sizes were unreliable for some models, which is why the on-disk size also counts.

## Caveats

- `think: false` clearly stops reasoning only on Granite 4.2 among the new thinking families.
  Falcon-H1R moves its reasoning inline, OLMo 3 Think keeps reasoning, and LFM2.5 still writes long
  answers, so their MC runs are not clean no-think measurements.
- OLMo 3 Instruct and Granite 4.2 ran with about 8–9% of layers on CPU. Speed differs; the model
  and the prompts do not.
- Gemma 4 12B is Q4_0 where the other new models are Q4_K_M.
- The judge is a Claude model scoring other labs' answers (see ADR-0005).
