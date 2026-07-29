"""TEMPLATE faith pack — fill in a new tradition here.

You reached this file because you ran:

    python -m deseretbench.newpack <key> --name "<your tradition>"

which copied this template to deseretbench/packs/<key>/ and substituted the
identity fields. Now work through every ``TODO`` below, top to bottom. The
sections are: identity, taxonomy, judge, authoring, and reviewer validation.
The parts that are genuinely reusable across traditions (the three evaluation
axes, the open-ended dimensions, the difficulty tiers, the shape of the judge
JSON) are already filled in — you are supplying the *content* of your tradition,
not rebuilding the scaffold.

Nothing here runs a model. When the taxonomy and prompts are filled, select this
pack (``DESERETBENCH_PACK=<key>`` or ``pack: <key>`` in configs/run_config.yaml)
and follow docs/how-to/add-a-faith-pack.md to author, validate, and score.
"""

from __future__ import annotations

from pathlib import Path

from deseretbench.packs import Pack

_HERE = Path(__file__).resolve().parent
LETTERS = "ABCDEFGH"

# --------------------------------------------------------------------------- #
# Identity  (the newpack command filled KEY / NAME / TITLE for you)
# --------------------------------------------------------------------------- #
KEY = "__KEY__"
NAME = "__NAME__"          # the tradition, phrased to drop into a sentence
TITLE = "__TITLE__"        # the report wordmark, e.g. "CatholicBench"
BLURB = "TODO: one line — what this benchmark measures and for whom"

# --------------------------------------------------------------------------- #
# Taxonomy  — what every item is validated against
# --------------------------------------------------------------------------- #
# The three top-level AXES are tradition-neutral (accuracy of doctrine, fluency
# in the culture, alignment of life counsel). Keep them unless your tradition
# genuinely needs different axes.
AXES = frozenset({"doctrinal_accuracy", "cultural_fluency", "life_choice_alignment"})

# TODO: your multiple-choice dimensions. Each MUST appear in AXIS_FOR_DIMENSION.
# Give a "cultural_fluency" dimension (lived practice / vernacular) its own entry
# on the cultural axis, as below.
MC_DIMENSIONS = frozenset({"core_doctrine", "practice_and_worship", "cultural_fluency"})

# Reusable as-is: open-ended items split into life-choice scenarios and
# open cultural-fluency prompts.
OPEN_DIMENSIONS = frozenset({"life_choice", "cultural_open"})

# TODO: the distractor traps that separate real understanding from surface
# pattern-matching in YOUR tradition. Keep "correct" (the keyed answer) and
# "plausible_near_miss"; replace/extend the tradition-specific traps. (For LDS
# these were protestant_trap, folk_doctrine_trap, etc. — see packs/lds/pack.py.)
DISTRACTOR_TYPES = frozenset({
    "correct",
    "plausible_near_miss",
    "other_tradition_trap",       # TODO: right elsewhere, wrong in this tradition
    "folk_belief_trap",           # TODO: commonly believed but not official
    "oversimplification",         # TODO: catechism-simple vs. the real nuance
})

# Every dimension belongs to exactly one axis.
AXIS_FOR_DIMENSION = {
    "core_doctrine": "doctrinal_accuracy",
    "practice_and_worship": "doctrinal_accuracy",
    "cultural_fluency": "cultural_fluency",
    "life_choice": "life_choice_alignment",
    "cultural_open": "cultural_fluency",
}

# Report labels: the radar's dimension order and short display names.
DIM_ORDER = ("core_doctrine", "practice_and_worship", "cultural_fluency")
DIM_SHORT = {"core_doctrine": "Doctrine", "practice_and_worship": "Practice",
             "cultural_fluency": "Cultural"}

# --------------------------------------------------------------------------- #
# Judge  — the open-ended scoring panel
# --------------------------------------------------------------------------- #
# TODO: three distinct expert-evaluator personas for your tradition.
JUDGE_PERSONAS = {
    "teacher": "TODO: an expert teacher who explains doctrine plainly",
    "scholar": "TODO: a scholar who knows doctrinal development and where ambiguity lives",
    "pastor": "TODO: a pastoral counselor who weighs doctrine and compassion",
}

JUDGE_SYSTEM = (
    f"You are an expert evaluator scoring another AI's written response to a question "
    f"about {NAME}. Be rigorous, fair, and concrete. Output only the requested JSON.")

# The four scoring dimensions are reusable; the JSON below is generated from this
# tuple, so if you change it the prompt stays consistent. "distinctiveness"
# rewards a recognizably in-tradition answer (not generic/secular).
JUDGE_DIMENSIONS = ("doctrinal_accuracy", "cultural_authenticity",
                    "practical_wisdom", "distinctiveness")


def build_judge_prompt(item: dict, response: str, persona_key: str) -> str:
    persona = JUDGE_PERSONAS[persona_key]
    r = item["rubric"]
    must = "\n".join(f"  - {x}" for x in r["must_include"])
    snot = "\n".join(f"  - {x}" for x in r["should_not"])
    score_lines = "\n".join(
        f"- {d}: TODO one line on what a 5/5 looks like for {d} in {NAME}"
        for d in JUDGE_DIMENSIONS)
    json_fields = ", ".join(f'"{d}": <1-5>' for d in JUDGE_DIMENSIONS)
    return f"""You are {persona}.

You are scoring an AI model's response to this scenario.

SCENARIO:
{item['prompt']}

SCORING RUBRIC
The response SHOULD engage these points (must_include):
{must}
The response should NOT do these (should_not):
{snot}
Ideal reasoning pattern:
  {r['ideal_reasoning_pattern']}

MODEL RESPONSE TO SCORE:
\"\"\"
{response}
\"\"\"

Score the response on each dimension from 1 (poor) to 5 (excellent):
{score_lines}

Also report:
- must_include_hits: integer count of the must_include points genuinely engaged
- must_include_total: total number of must_include points
- should_not_violations: integer count of should_not items the response committed

Respond with ONLY this JSON (no other text):
{{{json_fields}, "must_include_hits": <int>, "must_include_total": <int>, "should_not_violations": <int>, "justification": "<one sentence>"}}"""


# --------------------------------------------------------------------------- #
# Authoring  — the taxonomy and prompts that generate a fresh question set
# --------------------------------------------------------------------------- #
# The grounding brief is the factual anchor embedded in every authoring prompt —
# canon, official handbooks, the source-priority order. Write it in
# grounding_brief.md next to this file.
GROUNDING = (_HERE / "grounding_brief.md").read_text(encoding="utf-8")

STANCE = f"""TODO: state the STANCE this benchmark rewards — the mainstream, official position
of {NAME}, and which sources are authoritative. Say plainly that folk belief, heterodox
readings, and hostile framings appear ONLY as distractors, never as keyed answers."""

DISTRACTORS = """DISTRACTOR TYPES (label each choice in distractor_types; the correct choice = "correct"):
- other_tradition_trap: TODO — correct in a neighbouring tradition, wrong here
- folk_belief_trap: TODO — commonly believed by members but not official
- oversimplification: TODO — catechism-simple answer vs. the real nuance
- plausible_near_miss: close-but-wrong technical detail (date, name, sequence)"""

RULES = """RULES:
- Test UNDERSTANDING, not trivia. Separate models that grasp this tradition's thought from
  those pattern-matching neighbouring-tradition keywords.
- Distractors must be plausible and discriminative; use at least TWO distinct trap types per item.
- Exactly one defensibly-correct answer keyed to official sources; for genuinely unsettled
  matters, the correct answer reports it as unsettled.
- Vary subtopics; avoid near-duplicate stems.
- 'source' cites official/authoritative material; 'notes' explains the trap logic."""

MC_EXAMPLE = '{"format":"mc","axis":"doctrinal_accuracy","dimension":"core_doctrine","difficulty":"basic","question":"...","choices":["...","...","...","..."],"answer_index":1,"distractor_types":["other_tradition_trap","correct","folk_belief_trap","plausible_near_miss"],"source":"TODO","notes":"..."}'
OPEN_EXAMPLE = '{"format":"open","axis":"life_choice_alignment","dimension":"life_choice","difficulty":"advanced","prompt":"...","rubric":{"must_include":["...","..."],"should_not":["...","..."],"ideal_reasoning_pattern":"..."}}'

DIFF_DESC = {
    "basic": "TODO: entry level — any practicing adherent should know it.",
    "intermediate": "TODO: real doctrinal literacy required.",
    "advanced": "TODO: scholar level — doctrinal development, historical context, nuance.",
    "expert": "TODO: specialist level — synthesis across domains; unsettled questions.",
}

# TODO: your MC dimensions with target item counts and rotating subtopics.
# (dimension, target_count, one-line description, [subtopics ...])
MC_DIMS = (
    ("core_doctrine", 40, "TODO: what core_doctrine covers in this tradition.",
     ["TODO subtopic", "TODO subtopic", "TODO subtopic", "TODO subtopic"]),
    ("practice_and_worship", 30, "TODO: rites, worship, observance, obligations.",
     ["TODO subtopic", "TODO subtopic", "TODO subtopic"]),
    ("cultural_fluency", 25, "TODO: lived culture, vernacular, insider practice.",
     ["TODO subtopic", "TODO subtopic", "TODO subtopic"]),
)

# TODO: open-ended scenario cells. (dimension, difficulty, count, themes)
OPEN_CELLS = (
    ("life_choice", "advanced", 8, "TODO: hard real-life decisions this tradition faces"),
    ("cultural_open", "advanced", 7, "TODO: cultural-nuance scenarios, insider/outsider distinctions"),
)


def mc_authoring_prompt(c):
    return f"""You are an expert in {NAME} authoring multiple-choice items for a research benchmark.
{STANCE}

{GROUNDING}

{DISTRACTORS}

{RULES}

TASK: Author EXACTLY {c['count']} multiple-choice items.
  dimension: {c['dim']} — {c['desc']}
  axis: {c['axis']}
  difficulty: {c['diff']} — {DIFF_DESC[c['diff']]}
  emphasize (rotate across, vary, no duplicates): {'; '.join(c['subs'])}

Each item is a JSON object with EXACTLY these keys (example):
{MC_EXAMPLE}
4 choices (5 allowed for advanced/expert). distractor_types length == choices length, exactly one "correct" at answer_index, >= 2 distinct trap types.

OUTPUT: Respond with ONLY a JSON array of the {c['count']} item objects. No prose, no markdown fences."""


def open_authoring_prompt(c):
    return f"""You are an expert in {NAME} authoring OPEN-ENDED, judge-scored scenario items for a research benchmark.
{STANCE}

{GROUNDING}

{RULES}

TASK: Author EXACTLY {c['count']} open-ended scenario items.
  dimension: {c['dim']}
  axis: {c['axis']}
  difficulty: {c['diff']} — {DIFF_DESC[c['diff']]}
  themes (vary across them): {c['theme']}

Real, hard life situations with no catechism answer but a reasoning pattern recognizably rooted
in {NAME}, distinct from secular and neighbouring-tradition advice. Each item is a JSON object
with EXACTLY these keys (example):
{OPEN_EXAMPLE}
rubric.must_include: 4-6 substantive points a faithful, thoughtful adherent must engage.
rubric.should_not: 3-5 failure modes. rubric.ideal_reasoning_pattern: the in-tradition reasoning arc.

OUTPUT: Respond with ONLY a JSON array of the {c['count']} item objects. No prose, no markdown fences."""


# --------------------------------------------------------------------------- #
# Reviewer validation  — the automated expert panel that vets candidates
# --------------------------------------------------------------------------- #
# TODO: five reviewer personas that catch different failure modes (an orthodox
# insider, a scholar, a historian, a convert who spots insider assumptions, a
# reviewer from another region who catches cultural parochialism).
REVIEWERS = {
    "orthodox_adherent": "TODO: a devout, doctrinally orthodox insider who knows canon and handbook",
    "scholar": "TODO: a scholar of this tradition's doctrine, history, and ambiguities",
    "historian": "TODO: a historian precise about dates, sources, and doctrinal development",
    "convert": "TODO: an adult convert who catches assumptions only lifelong members would know",
    "global_member": "TODO: a member from another region who catches parochial/cultural assumptions",
}


def mc_review_prompt(item: dict) -> str:
    opts = "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(item["choices"]))
    return f"""Review this multiple-choice item for a {NAME} knowledge benchmark.
Do NOT assume any option is the intended key; judge it yourself.

ITEM ({item['dimension']} / {item['difficulty']}):
{item['question']}
{opts}

Decide, as an expert, the single BEST answer per the mainstream, official position of {NAME}.
Then evaluate the item.

Respond with ONLY this JSON:
{{"best_answer": "<letter>", "n_defensible_options": <int how many options could be defended as correct>, "clarity": <1-5>, "tests_understanding": <true|false, false if it is mere trivia>, "flags": [<any of: "ambiguous","multiple_correct","unfair","trivia","parochial","factually_wrong","none">], "comment": "<one sentence>"}}"""


def open_review_prompt(item: dict) -> str:
    r = item["rubric"]
    must = "; ".join(r["must_include"])
    snot = "; ".join(r["should_not"])
    return f"""Review this OPEN-ENDED scenario item and its scoring rubric for a {NAME} life-counsel benchmark.

SCENARIO ({item['dimension']} / {item['difficulty']}):
{item['prompt']}

RUBRIC must_include: {must}
RUBRIC should_not: {snot}
RUBRIC ideal_reasoning: {r['ideal_reasoning_pattern']}

Evaluate whether the scenario is realistic and whether the rubric fairly captures how a faithful,
thoughtful adherent of {NAME} would actually reason — neither too rigid nor heterodox.

Respond with ONLY this JSON:
{{"realistic": <1-5>, "rubric_fair": <1-5>, "clarity": <1-5>, "flags": [<any of: "rubric_too_rigid","rubric_heterodox","unrealistic","parochial","factually_wrong","none">], "comment": "<one sentence>"}}"""


PACK = Pack(
    key=KEY,
    name=NAME,
    report_title=TITLE,
    report_blurb=BLURB,
    data_dir=f"data/{KEY}",
    results_dir=f"results/{KEY}",
    reports_dir=f"reports/{KEY}",
    axes=AXES,
    mc_dimensions=MC_DIMENSIONS,
    open_dimensions=OPEN_DIMENSIONS,
    distractor_types=DISTRACTOR_TYPES,
    axis_for_dimension=AXIS_FOR_DIMENSION,
    dim_order=DIM_ORDER,
    dim_short=DIM_SHORT,
    judge_personas=JUDGE_PERSONAS,
    judge_system=JUDGE_SYSTEM,
    judge_dimensions=JUDGE_DIMENSIONS,
    build_judge_prompt=build_judge_prompt,
    grounding=GROUNDING,
    authoring_stance=STANCE,
    distractor_guide=DISTRACTORS,
    authoring_rules=RULES,
    mc_example=MC_EXAMPLE,
    open_example=OPEN_EXAMPLE,
    diff_desc=DIFF_DESC,
    mc_dims=MC_DIMS,
    open_cells=OPEN_CELLS,
    mc_authoring_prompt=mc_authoring_prompt,
    open_authoring_prompt=open_authoring_prompt,
    reviewers=REVIEWERS,
    mc_review_prompt=mc_review_prompt,
    open_review_prompt=open_review_prompt,
)
