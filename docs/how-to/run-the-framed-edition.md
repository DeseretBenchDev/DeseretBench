# Run the framed edition

The framed edition asks the same questions with one added sentence in the system
prompt, telling the model which tradition to answer from. Comparing it with the neutral
run shows, for each model, what it knows against what it says by default. Background:
[ADR-0015](../adr/0015-framed-prompt-condition.md).

It is a separate measurement. Nothing here changes the standings.

## Before you start

- You need a finished neutral run to compare against (for the shipped standings,
  `runs/v0_1_plus`).
- A framed run makes every call again. Check for a live run first, as for any
  measurement.
- Use a new output directory. The run phases refuse to write framed records into a
  directory that holds a neutral run.

## Steps

```bash
# 1. Multiple choice, framed
.venv/bin/python -m deseretbench.run_benchmark mc --condition framed \
    --questions data/questions_mc.jsonl --out runs/framed --models MODEL_ID --runs 2

# 2. Open-ended, framed (generates, then judges with the usual panel)
.venv/bin/python -m deseretbench.run_benchmark open --condition framed \
    --questions data/questions_open.jsonl --out runs/framed --models MODEL_ID --runs 2

# 3. Compare with the neutral run
.venv/bin/python -m deseretbench.framing --neutral runs/v0_1_plus --framed runs/framed
```

Step 3 writes `results/framing.json` and `reports/FRAMING.md`. It uses the seed and the
resample count from `configs/run_config.yaml`, so rerunning it gives the same numbers.

## Reading the result

- **Gap** is framed minus neutral, over the items both runs scored.
- A clear positive gap: the model knows the teaching and does not reach for it unless
  told.
- No gap at a low score: the model does not know it.
- No gap at the ceiling says nothing; the neutral score left no room.

## What it will not do

- `analyze` stops if it finds a framed record in the run it is given.
- `merge_runs` refuses framed records.
- The sentence itself comes from the pack (`framed_instruction`). To change it, change
  the pack; that buys every framed call again.
