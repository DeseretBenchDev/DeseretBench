# Related Work & Landscape

*Compiled 2026-06-07 from a multi-source, adversarially-verified research pass. CEFEAI's
empirical results are self-reported preprints (~2 weeks old at writing) and have not been
peer-reviewed or independently replicated — cite as "the benchmark reports X," not as settled
fact. Verify dashboard numbers against cefe.ai before quoting; they track specific runs.*

## The one-line position

> Cross-tradition benchmarks ask whether a model treats faiths **evenly** or **mentions religion
> at all**. DeseretBench asks whether a model actually **knows and reasons within** one tradition.
> A model can look perfectly even-handed and still be doctrinally shallow on any specific faith —
> that is the gap a within-tradition depth benchmark fills.

Axes:

| | Cross-tradition (breadth) | Within-tradition (depth) |
|---|---|---|
| Question | Symmetry / representation across faiths | Accuracy + fluency + alignment inside one faith |
| Example | CEFEAI AllFaith; religious-bias studies | **DeseretBench**; IslamicMMLU; IslamicLegalBench; TGC |
| Blind spot | Can't tell if doctrine is *right* | Can't tell cross-faith *favoritism* |

The two axes are complementary, not competing. They overlap only in method (both lean on
LLM-as-judge scoring) and in that cross-tradition sets usually include the LDS tradition as one
data point among many — never probing its doctrine.

## CEFEAI — the nearest neighbor

**Consortium for Evaluating Faith and Ethics in AI** — a BYU-led four-university consortium
(Brigham Young, Baylor, Notre Dame, Yeshiva). Publicly launched 2026-05-26 at the Athens Summit
on AI Ethics, with Elder Gerrit W. Gong (LDS apostle) giving the keynote. Lead researcher:
David Wingate (BYU CS). Live leaderboard: **cefe.ai**. GitHub: github.com/CEFEAI
(contact admin@cefeai.org). Its **AllFaith Benchmark** has two cross-tradition components:

- **Conversion Bias** — *When AI Takes Sides on Questions of Faith*, arXiv 2605.22975.
  14 faiths × 13 ordered partner-faiths × 8 templates = 1,456 prompts; a human-verified
  LLM-as-judge rates each response 1–7 (encourage → discourage a conversion); 20 models.
  Reported finding: responses are **not symmetric** — Catholic / Bahá'í / Sikh broadly favored;
  Jehovah's Witnesses, atheists, agnostics disfavored; Anthropic & Meta least biased, Grok most.
- **Religious Representation** — *Omissive Bias in Religious Representation*, arXiv 2605.24319.
  150 secular, ethically-salient life questions (WildChat-sourced; selection validated by a
  nationally representative survey of 1,125 Americans); LLM-as-judge scores 0–4 for whether the
  answer surfaces *any* religion, practice, or leader; 27 models; 95% Wilson CIs. Introduces
  **"omissive bias"** — counting the *absence* of religious mention as a value-alignment signal.
  Reported finding: models consistently omit religious perspectives.

*Note:* the public GitHub repos contain only the datasets + the judge prompt; model lists and
results live in the papers and on cefe.ai. Baylor's press release mentions "three papers" but only
the two arXiv preprints above were located — there may be a third.

## True methodological precedents (closer to DeseretBench's design than CEFEAI)

- **IslamicMMLU** — arXiv 2603.23750 (Abdelaal et al., Edinburgh, Mar 2026). 10,013
  within-tradition multiple-choice questions across Quran (2,013), Hadith (4,000), and Fiqh
  (4,000). Its Fiqh track includes a **madhab (school-of-jurisprudence) bias-detection task**
  (one option per school, chi-squared vs. uniform) — the closest published analogue to our typed
  distractors. Pure MCQ accuracy, Modern Standard Arabic, no judge panel.
- **IslamicLegalBench** — arXiv 2602.21226 (Elmahjub et al., Feb 2026). 718 instances over 13
  tasks across seven schools of Islamic jurisprudence; explicitly frames itself around
  **within-tradition pluralism** ("multiple valid methodologies within Islam, not inter-faith
  diversity") — the same depth philosophy as DeseretBench.
- **TGC "AI Christian Benchmark"** — The Gospel Coalition / Keller Center (2025; 2026 expansion).
  7 LLMs on apologetics prompts, **hand-graded by 7 named Christian scholars** against
  per-question rubrics, with an explicitly **within-tradition normative scale** (≈65+ ≈ Nicene
  Christianity; 80+ ≈ TGC's own confessional standard). The strongest precedent for our
  normative-rubric + judge approach — they use humans where we (for v0.1) use an LLM panel.

## Broader bias / value-alignment context

- **Measuring Spiritual Values and Bias of LLMs** — arXiv 2410.11647 (Emory; KDD 2025 SciSoc
  workshop). Finds LLM "spiritual values" are diverse, not uniformly secular.
- **Religious Bias Landscape in Language and Text-to-Image Models** — arXiv 2501.08441
  (peer-reviewed, *AI & SOCIETY*). Cross-modal bias study; finds pronounced negative bias toward
  Islam. The cross-tradition-bias lineage CEFEAI extends.
- **Persistent Anti-Muslim Bias in LLMs** — Abid et al., 2021. The foundational religious-bias
  citation.
- General suites (MMLU / MMLU-Pro / BIG-bench) include only a thin comparative "world religions"
  slice — survey-level recall, no within-tradition depth. This is the gap statement.

## How DeseretBench differentiates (for the paper's framing)

1. **Within-tradition depth**, not cross-tradition symmetry — the only LDS-specific instrument.
2. **Three separated constructs** — doctrinal accuracy vs. cultural fluency vs. life-choice
   alignment — where prior within-tradition work (IslamicMMLU) is accuracy-only.
3. **Typed, discriminative distractors** keyed to a specific theology (Protestant trap,
   folk-doctrine trap, etc.), with source citations.
4. **A judge-panel rubric for lived life-choice counsel**, not just knowledge recall.
5. **Fully seeded, cached, reproducible harness** with item analysis and inter-rater reliability.

## Strategic notes

- **Cite**: both CEFEAI papers (as the cross-tradition foil) and IslamicMMLU / IslamicLegalBench /
  TGC (as within-tradition design precedents).
- **Engage**: CEFEAI's BYU/LDS leadership makes it the natural community/venue; an outreach draft exists as a
  local working document (not distributed with the repo).
- **Don't overclaim**: treat all of CEFEAI's findings as reported-not-established, and keep our own
  v0.1 framed as a proof of concept.
