# Run a human review round

The shipped questions were written and reviewed by models. A human round checks them with
real reviewers and checks the judge panel against human scores. Plan and targets:
[DESIGN §6.1](../../DESIGN.md). No round has been run yet.

The tooling makes no model calls and changes no question file. It reports; what to do about
an item stays a decision.

## Who

At least three reviewers. An item needs three completed reviews to count as reviewed, the
same quorum the automated panel used. Start with one reviewer each for doctrine, scholarly
rigor and method, then widen to a bishop or stake president, a convert, and a returned
missionary who served outside the United States.

List reviewers by role in anything published. Give each an id such as `R1`.

## Time

The full packet is 213 multiple-choice items, 40 open-ended items and 40 answers to score,
which is several hours. A first round can stop at the open-ended sheet and the calibration
sheet, the parts multiple-choice agreement cannot replace.

## Steps

```bash
# 1. Build the packet from a neutral run. Use a new folder for each round.
.venv/bin/python -m deseretbench.human_review export --run runs/v0_1_plus --out review_round_1
```

2. Send each reviewer the contents of `review_round_1/packet/`. Keep
   `review_round_1/organiser/` to yourself: it says which model wrote each answer and how the
   judge scored it.
3. Put the filled sheets in `review_round_1/returned/`, named `review_mc.R1.csv`,
   `review_open.R1.csv` and `calibration.R1.csv`.

```bash
# 4. Read them back
.venv/bin/python -m deseretbench.human_review ingest review_round_1
```

Step 4 writes `results/human_review.json`.

## What reviewers see, and do not

| Sheet | Reviewers see | Reviewers do not see |
|---|---|---|
| `review_mc.csv` | question and options | which option is keyed; the type of each wrong answer |
| `review_open.csv` | situation, must-include and should-not points | the ideal reasoning pattern |
| `calibration.csv` | situation, the rubric, a stored answer | the model that wrote it; the judge's score |

The answers to score are spread evenly over the judge's score range, and shuffled. The choice
is seeded, so the same run gives the same packet.

## Reading the report

The report applies the keep rules of the automated panel unchanged:

- **Multiple choice:** kept if at least 60% of reviewers pick the keyed answer, mean clarity is
  4.0 or more, the mean count of defensible options is 1.5 or less, and at most one bad flag.
- **Open-ended:** kept if mean realism, rubric fairness and clarity are each 4.0 or more, with
  at most one bad flag.
- **Too few reviews:** listed as unreviewed, which is not a failure.
- **Reviewer agreement:** Fleiss' κ on multiple choice, target 0.7.
- **Judge against humans:** Spearman ρ between the judge's composite and the human mean,
  target 0.6, plus the mean difference in composite points. The human composite uses the same
  aggregation as the judge panel.

If the judge misses its target, its open-ended scores should not be read at scale until that
is understood. An item that fails is rewritten or dropped; a smaller clean set beats a larger
disputed one. Dropping an item changes the question set, so it starts a new edition of the
standings.
