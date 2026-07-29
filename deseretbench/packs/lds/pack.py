"""The Latter-day Saint pack.

This is the reference tradition and the model for every other pack. The values
below were extracted verbatim from the original ``schema``, ``judge``, and
``report`` module constants, so with this pack active the benchmark reproduces
v0.1 exactly. Authoring and reviewer content (the generation taxonomy and the
review prompts) are extracted in the authoring phase.

The framing throughout is the mainstream, official, correlated position of the
Church of Jesus Christ of Latter-day Saints — see ``data/grounding_brief.md``.
"""

from __future__ import annotations

from pathlib import Path

from deseretbench.packs import Pack

_ROOT = Path(__file__).resolve().parents[3]   # repo root
LETTERS = "ABCDEFGH"

# --------------------------------------------------------------------------- #
# Taxonomy
# --------------------------------------------------------------------------- #

AXES = frozenset({"doctrinal_accuracy", "cultural_fluency", "life_choice_alignment"})

MC_DIMENSIONS = frozenset({
    "doctrine_scripture", "ordinances_covenants", "church_organization",
    "eternal_family", "restoration_history", "living_gospel", "cultural_fluency",
})

OPEN_DIMENSIONS = frozenset({"life_choice", "cultural_open"})

DISTRACTOR_TYPES = frozenset({
    "correct",                       # the keyed answer
    "protestant_trap",
    "folk_doctrine_trap",
    "anti_mormon_trap",
    "progressive_trap",
    "correlation_oversimplification",
    "plausible_near_miss",
})

# Every dimension belongs to exactly one axis; a mismatch would silently pollute
# per-axis scoring downstream.
AXIS_FOR_DIMENSION = {
    "doctrine_scripture": "doctrinal_accuracy",
    "ordinances_covenants": "doctrinal_accuracy",
    "church_organization": "doctrinal_accuracy",
    "eternal_family": "doctrinal_accuracy",
    "restoration_history": "doctrinal_accuracy",
    "living_gospel": "doctrinal_accuracy",
    "cultural_fluency": "cultural_fluency",
    "life_choice": "life_choice_alignment",
    "cultural_open": "cultural_fluency",
}

# --------------------------------------------------------------------------- #
# Report labels (radar dimension order + short display names)
# --------------------------------------------------------------------------- #

DIM_ORDER = ("doctrine_scripture", "ordinances_covenants", "church_organization",
             "eternal_family", "restoration_history", "living_gospel",
             "cultural_fluency")

DIM_SHORT = {"doctrine_scripture": "Doctrine", "ordinances_covenants": "Ordinances",
             "church_organization": "Church Org", "eternal_family": "Eternal Family",
             "restoration_history": "Rest. History", "living_gospel": "Living Gospel",
             "cultural_fluency": "Cultural"}

# --------------------------------------------------------------------------- #
# Judge panel
# --------------------------------------------------------------------------- #

JUDGE_PERSONAS = {
    "seminary_teacher": (
        "an experienced Latter-day Saint seminary teacher who knows the standard works "
        "and how to explain doctrine plainly to youth"),
    "byu_religion_professor": (
        "a BYU religion professor with deep knowledge of doctrinal development, Church "
        "history, the Gospel Topics Essays, and where genuine ambiguity exists"),
    "bishop": (
        "a serving bishop who counsels members through real life decisions with both "
        "doctrinal fidelity and pastoral compassion"),
}

JUDGE_SYSTEM = (
    "You are an expert evaluator scoring another AI's written response to a question "
    "about Latter-day Saint life and doctrine. Be rigorous, fair, and concrete. "
    "Output only the requested JSON.")

JUDGE_DIMENSIONS = ("doctrinal_accuracy", "cultural_authenticity",
                    "practical_wisdom", "distinctiveness")


def build_judge_prompt(item: dict, response: str, persona_key: str) -> str:
    persona = JUDGE_PERSONAS[persona_key]
    r = item["rubric"]
    must = "\n".join(f"  - {x}" for x in r["must_include"])
    snot = "\n".join(f"  - {x}" for x in r["should_not"])
    return f"""You are {persona}.

You are scoring an AI model's response to this scenario.

SCENARIO:
{item['prompt']}

SCORING RUBRIC
The response SHOULD engage these points (must_include):
{must}
The response should NOT do these (should_not):
{snot}
Ideal Latter-day Saint reasoning pattern:
  {r['ideal_reasoning_pattern']}

MODEL RESPONSE TO SCORE:
\"\"\"
{response}
\"\"\"

Score the response on each dimension from 1 (poor) to 5 (excellent):
- doctrinal_accuracy: reflects actual mainstream LDS teaching
- cultural_authenticity: sounds like someone who understands lived LDS life
- practical_wisdom: genuinely useful counsel, not just doctrinally correct
- distinctiveness: gives a recognizably Latter-day Saint answer (not generic Christian/secular)

Also report:
- must_include_hits: integer count of the must_include points genuinely engaged
- must_include_total: total number of must_include points
- should_not_violations: integer count of should_not items the response committed

Respond with ONLY this JSON (no other text):
{{"doctrinal_accuracy": <1-5>, "cultural_authenticity": <1-5>, "practical_wisdom": <1-5>, "distinctiveness": <1-5>, "must_include_hits": <int>, "must_include_total": <int>, "should_not_violations": <int>, "justification": "<one sentence>"}}"""


# --------------------------------------------------------------------------- #
# Authoring — the taxonomy and prompts that generate a fresh question set
# --------------------------------------------------------------------------- #

# The grounding brief is the factual anchor embedded in every authoring prompt.
# It stays at data/grounding_brief.md (README, DATASET_CARD, and the docs all
# point there); other packs keep their brief inside the pack directory. Read
# defensively: scoring and reporting don't need it, and every module now imports
# the pack, so a missing brief must not make the whole package unimportable —
# only authoring requires it (author.py guards on grounding being present).
try:
    GROUNDING = (_ROOT / "data" / "grounding_brief.md").read_text(encoding="utf-8")
except OSError:
    GROUNDING = None

STANCE = """DeseretBench rewards accurate representation of the MAINSTREAM, OFFICIAL, CORRELATED
position of The Church of Jesus Christ of Latter-day Saints (canon, the General Handbook, and
current First Presidency / Quorum of the Twelve teaching), while acknowledging where genuine
doctrinal ambiguity exists. Key answers to the official position. Folk doctrine, heterodox
("Sunstone") readings, and anti-Mormon framings appear ONLY as distractors."""

DISTRACTORS = """DISTRACTOR TYPES (label each choice in distractor_types; the correct choice = "correct"):
- protestant_trap: correct in mainstream Christianity, wrong in LDS theology (grace-alone, Nicene Trinity, ex nihilo)
- folk_doctrine_trap: commonly believed by members but not official (e.g. "Kolob is where God lives")
- anti_mormon_trap: factual-sounding but hostile/CES-Letter spin
- progressive_trap: heterodox/"Sunstone" answer not reflecting the mainstream position
- correlation_oversimplification: too-simple Sunday-School answer vs. the real nuance
- plausible_near_miss: close-but-wrong technical detail (date, name, sequence)"""

RULES = """RULES:
- Test UNDERSTANDING, not photographic trivia. Separate models that grasp LDS thought from
  those pattern-matching Christian keywords. No "which section header" trivia.
- Distractors must be plausible and discriminative; use at least TWO distinct trap types per item.
- Exactly one defensibly-correct answer keyed to official sources. For genuinely unsettled matters,
  the correct answer correctly reports it as unsettled/non-canonical.
- Vary subtopics; do NOT duplicate well-worn examples; avoid near-duplicate stems.
- 'source' cites official/authoritative material; 'notes' explains the trap logic + why it tests understanding."""

MC_EXAMPLE = '{"format":"mc","axis":"doctrinal_accuracy","dimension":"doctrine_scripture","difficulty":"basic","question":"...","choices":["...","...","...","..."],"answer_index":1,"distractor_types":["protestant_trap","correct","folk_doctrine_trap","plausible_near_miss"],"source":"D&C 130:22","notes":"..."}'
OPEN_EXAMPLE = '{"format":"open","axis":"life_choice_alignment","dimension":"life_choice","difficulty":"advanced","prompt":"...","rubric":{"must_include":["...","..."],"should_not":["...","..."],"ideal_reasoning_pattern":"..."}}'

DIFF_DESC = {
    "basic": "Seminary level — any active member should know it.",
    "intermediate": "Institute/mission level — real doctrinal literacy required.",
    "advanced": "BYU Religion faculty level — doctrinal development, historical context, nuance.",
    "expert": "Roberts/Nibley/Givens level — synthesis across domains; unsettled questions.",
}

MC_DIMS = (
    ("doctrine_scripture", 45, "Plan of Salvation, the Godhead, the Restoration, and the standard works.",
     ["nature of God/Godhead", "premortal life & intelligences", "degrees of glory & judgment", "Fall & Atonement",
      "Book of Mormon doctrine", "D&C revelations", "Moses/Abraham (PoGP)", "grace & works/soteriology",
      "agency & the plan", "apostasy & Restoration"]),
    ("ordinances_covenants", 30, "Temple ordinances, baptism, the sacrament, priesthood, and work for the dead.",
     ["baptism & confirmation", "the sacrament", "endowment & sealing", "work for the dead",
      "Aaronic vs Melchizedek priesthood", "keys vs office", "covenant theology", "temple recommend worthiness"]),
    ("church_organization", 22, "Prophetic authority and keys, ward/stake structure, callings, councils, correlation.",
     ["prophetic authority & keys", "succession in the presidency", "ward vs stake", "quorums & auxiliaries",
      "callings & sustaining", "common consent", "correlation", "church councils"]),
    ("eternal_family", 25, "Sealing, the Family Proclamation, marriage and family roles, family history.",
     ["eternal marriage & sealing", "The Family: A Proclamation", "gender & family roles", "family history & temple work",
      "exaltation & eternal increase", "children & sealing", "singles without temple marriage"]),
    ("restoration_history", 30, "Joseph Smith, the Restoration, succession, plural marriage, Missouri/Nauvoo, pioneers, OD-1/OD-2.",
     ["First Vision & accounts", "coming forth of the Book of Mormon", "priesthood restoration",
      "Kirtland/Missouri/Nauvoo", "martyrdom & succession 1844", "plural marriage & the Manifesto",
      "pioneer trek & colonization", "1978 priesthood revelation"]),
    ("living_gospel", 28, "Word of Wisdom, Sabbath, tithing & offerings, missionary work, self-reliance, ministering.",
     ["Word of Wisdom (incl. 2019 clarifications)", "Sabbath & sacrament meeting", "tithing & fast offerings",
      "missionary work & ministering", "self-reliance & welfare", "personal revelation & study",
      "repentance & worthiness", "Come Follow Me / home-centered learning"]),
    ("cultural_fluency", 25, "Mission culture, BYU life, ward dynamics, dating norms, temple-recommend practice, vernacular.",
     ["mission culture & vernacular (RM, greenie, trunky, transfers, P-day)", "BYU life & Honor Code",
      "ward dynamics & callings in practice", "dating/courtship & 'ring by spring'",
      "how a bishop is called & sustained", "'I prayed about it' in decisions", "temple recommend in practice",
      "convert integration", "youth programs & seminary"]),
)

OPEN_CELLS = (
    ("life_choice", "intermediate", 8, "career vs. family, Sabbath/Word-of-Wisdom pressure at work, education vs. mission/marriage timing"),
    ("life_choice", "advanced", 8, "faith crisis & doubt, a child/sibling who leaves the Church, ministering to the disaffected"),
    ("life_choice", "advanced", 8, "mixed-faith marriage & interfaith dating, marrying a non-member, raising children in mixed-faith homes"),
    ("life_choice", "advanced", 8, "LGBTQ family members (a gay teenager, a child who comes out, love+belonging alongside doctrine), singles/midsingle life"),
    ("life_choice", "expert", 6, "demanding callings vs. family/health, financial strain vs. tithing, ethically gray business, end-of-life/medical ethics"),
    ("cultural_open", "intermediate", 7, "spirit vs. letter of the law (Sabbath, Word of Wisdom), being the only member at a work dinner, ward social dynamics"),
    ("cultural_open", "advanced", 7, "mission-culture nuance, how 'I prayed about it' functions, convert integration, bishop-interview dynamics, weight of a temple recommend"),
    ("cultural_open", "expert", 5, "subtle insider/outsider distinctions, where cultural practice diverges from doctrine, generational shifts in LDS culture"),
)


def mc_authoring_prompt(c):
    return f"""You are a Latter-day Saint doctrine and culture expert authoring multiple-choice items for DeseretBench, a research benchmark.
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
    return f"""You are a Latter-day Saint life-counsel and culture expert authoring OPEN-ENDED, judge-scored scenario items for DeseretBench.
{STANCE}

{GROUNDING}

{RULES}

TASK: Author EXACTLY {c['count']} open-ended scenario items.
  dimension: {c['dim']}
  axis: {c['axis']}
  difficulty: {c['diff']} — {DIFF_DESC[c['diff']]}
  themes (vary across them): {c['theme']}

Real, hard life situations with no catechism answer but a recognizably Latter-day Saint reasoning
pattern distinct from secular and from generic-Protestant advice. Each item is a JSON object with
EXACTLY these keys (example):
{OPEN_EXAMPLE}
rubric.must_include: 4-6 substantive points a faithful, thoughtful Latter-day Saint answer must engage.
rubric.should_not: 3-5 failure modes/wrong defaults. rubric.ideal_reasoning_pattern: the LDS reasoning arc.
Be compassionate and realistic, reflecting actual mainstream pastoral practice (e.g. for LGBTQ scenarios,
love and belonging alongside doctrine on the law of chastity and temple marriage).

OUTPUT: Respond with ONLY a JSON array of the {c['count']} item objects. No prose, no markdown fences."""


# --------------------------------------------------------------------------- #
# Reviewer validation — the automated expert panel that vets candidates
# --------------------------------------------------------------------------- #

REVIEWERS = {
    "orthodox_member":
        "You are a devout, doctrinally orthodox Latter-day Saint who has served as a bishop "
        "and stake president. You know the standard works and the General Handbook well.",
    "byu_religion_instructor":
        "You are a BYU religion/institute instructor with deep knowledge of doctrine, Church "
        "history, the Gospel Topics Essays, and where genuine doctrinal ambiguity exists.",
    "church_historian":
        "You are a Latter-day Saint church historian (Rough Stone Rolling / Saints level) who "
        "is precise about dates, sources, and the development of doctrine and practice.",
    "adult_convert":
        "You are an adult convert to the Church of Jesus Christ of Latter-day Saints. You catch "
        "assumptions that only lifelong members would know, and you value clarity for outsiders.",
    "international_returned_missionary":
        "You are a returned missionary who served outside the United States. You catch "
        "Anglo-centric or US-cultural assumptions that don't generalize to the global Church.",
}


def mc_review_prompt(item: dict) -> str:
    opts = "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(item["choices"]))
    return f"""Review this multiple-choice item for a Latter-day Saint knowledge benchmark.
Do NOT assume any option is the intended key; judge it yourself.

ITEM ({item['dimension']} / {item['difficulty']}):
{item['question']}
{opts}

Decide, as an expert, the single BEST answer per the MAINSTREAM, OFFICIAL position of
The Church of Jesus Christ of Latter-day Saints. Then evaluate the item.

Respond with ONLY this JSON:
{{"best_answer": "<letter>", "n_defensible_options": <int how many options could be defended as correct>, "clarity": <1-5>, "tests_understanding": <true|false, false if it is mere trivia>, "flags": [<any of: "ambiguous","multiple_correct","unfair","trivia","anglocentric","factually_wrong","none">], "comment": "<one sentence>"}}"""


def open_review_prompt(item: dict) -> str:
    r = item["rubric"]
    must = "; ".join(r["must_include"])
    snot = "; ".join(r["should_not"])
    return f"""Review this OPEN-ENDED scenario item and its scoring rubric for a Latter-day Saint
life-counsel benchmark.

SCENARIO ({item['dimension']} / {item['difficulty']}):
{item['prompt']}

RUBRIC must_include: {must}
RUBRIC should_not: {snot}
RUBRIC ideal_reasoning: {r['ideal_reasoning_pattern']}

Evaluate whether the scenario is realistic and whether the rubric fairly and accurately
captures how a faithful, thoughtful Latter-day Saint (bishop-level pastoral wisdom) would
actually reason — neither too rigid/legalistic nor heterodox.

Respond with ONLY this JSON:
{{"realistic": <1-5>, "rubric_fair": <1-5>, "clarity": <1-5>, "flags": [<any of: "rubric_too_rigid","rubric_heterodox","unrealistic","anglocentric","factually_wrong","none">], "comment": "<one sentence>"}}"""


PACK = Pack(
    key="lds",
    name="the Latter-day Saint tradition",
    report_title="DeseretBench",
    report_blurb=("a reproducible benchmark for LDS doctrinal accuracy, cultural "
                  "fluency, and life-choice alignment in large language models"),
    results_dir="results",
    reports_dir="reports",
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
    # authoring
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
    # reviewer validation
    reviewers=REVIEWERS,
    mc_review_prompt=mc_review_prompt,
    open_review_prompt=open_review_prompt,
)
