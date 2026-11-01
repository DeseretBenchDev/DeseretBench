# Score stored answers with a second judge family

Every open-ended score comes from one judge model family, prompted as three personas. The
personas agree closely, but that is one family agreeing with itself. A second judge from
another lab re-scores the answers already stored, with the same personas, prompt and rubric,
and the comparison shows whether the standings depend on the judge.

It is a separate measurement. The standings keep the primary judge's scores.

## Before you start

- Pick the second judge. It must come from another family than `judges.primary_model`; the
  tool refuses a judge from the same family before any call.
- Name it in `configs/models.yaml` under `judges.second` (`model`, `backend`, and
  `backend_opts` if the backend needs them), or pass `--judge-model` and `--backend`.
- It makes three judge calls per stored answer. The merged run holds about 3,800 scored
  answers, so a full pass is about 11,400 calls. `--fraction 0.25` judges a seeded quarter.

## Steps

```bash
# 1. Judge stored answers (model calls; nothing is regenerated)
.venv/bin/python -m deseretbench.second_judge run \
    --run runs/v0_1_plus --out runs/second_judge --fraction 0.25

# 2. Compare (no model calls)
.venv/bin/python -m deseretbench.second_judge compare \
    --run runs/v0_1_plus --second runs/second_judge
```

Step 1 writes `second_judge_raw.jsonl`, `second_scores.jsonl` and a snapshot into its own
directory and refuses to write into the run it reads. Step 2 writes
`results/judge_agreement.json` and `reports/JUDGE_AGREEMENT.md`.

## Reading the result

- **Answer by answer:** Spearman ρ (do the judges order answers the same way?), Krippendorff's
  α (do they give the same score?), and the mean difference in composite points.
- **The ranking:** Spearman ρ over model means, and the pairs of models whose order the second
  judge reverses. This is the question the standings depend on.
- **Per model:** the paired difference between judges over the same answers, with a bootstrap
  interval and Holm correction across models. A model that one judge favours shows here.

A judge that is harsher on everything moves every score and changes no rank. A judge that
reorders models is the finding that matters.
