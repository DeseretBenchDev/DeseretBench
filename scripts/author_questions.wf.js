// NOTE: This workflow is LDS-SPECIFIC. Its stance, distractor palette, grounding
// facts, and example items are hardcoded for the Latter-day Saint tradition; it
// predates the faith-pack abstraction and is NOT tradition-neutral. To author a
// different tradition, use the pack-based Python path — `python -m
// deseretbench.author` with the pack selected (DESERETBENCH_PACK / run_config
// `pack:`), which reads its taxonomy and prompts from the active pack. See
// docs/how-to/add-a-faith-pack.md. This script is kept as the record of how the
// LDS v0.1 set was authored.
export const meta = {
  name: 'deseretbench-author',
  description: 'Author DeseretBench LDS question set across dimensions/difficulties via domain-expert agents; each writes its cell to data/raw as JSONL.',
  phases: [
    { title: 'Author MC' },
    { title: 'Author Open' },
  ],
}

// ---------------------------------------------------------------------------
// Relative to the repo root (the agent's working directory).
const RAW = 'data/raw'

const STANCE = `
DeseretBench rewards accurate representation of the MAINSTREAM, OFFICIAL, CORRELATED
position of The Church of Jesus Christ of Latter-day Saints (canon, the General Handbook,
and current First Presidency / Quorum of the Twelve teaching), while acknowledging where
genuine doctrinal ambiguity exists. Key the answer to the official position. Folk doctrine,
heterodox/"Sunstone" readings, and anti-Mormon framings appear ONLY as distractors.`

const GROUNDING = `
VERIFIED FACTS (as of June 2026 — key answers to these; use the dated ones for currency items):
- LEADERSHIP: President Russell M. Nelson DIED Sept 27, 2025 (age 101). DALLIN H. OAKS is the
  current (17th) President of the Church (set apart Oct 2025). First Presidency: Oaks (Pres.),
  Henry B. Eyring (1st counselor), D. Todd Christofferson (2nd counselor). Jeffrey R. Holland died.
  Dieter F. Uchtdorf is Acting President of the Quorum of the Twelve. New apostles: Gerald Causse
  (Nov 2025), Clark G. Gilbert (Feb 2026). SUCCESSION: on a President's death the First Presidency
  dissolves and the MOST SENIOR apostle becomes President (not the 1st counselor, not by election).
- NAME (2018): Official name "The Church of Jesus Christ of Latter-day Saints" (revealed 1838, D&C 115:4);
  short forms "the Church"/"the Church of Jesus Christ"; members are "Latter-day Saints." Avoid
  "Mormon Church"/"LDS Church" (use these as distractors).
- WORD OF WISDOM (D&C 89; 2019 clarification): prohibits coffee, ALL tea (green AND black, same plant),
  vaping/e-cigs, tobacco, alcohol; herbal tea ok; marijuana/opioids medicinal-only as prescribed.
- CHANGES: Ministering replaced home/visiting teaching (2018); two-hour block + Come Follow Me (2019);
  Children & Youth replaced Scouting/Personal Progress/Duty to God (Jan 2020); temple recommend questions
  revised (Oct 2019); garment redesign for hot climates (2024); missionary ages lowered to 18/19 (2012).
- GODHEAD: three SEPARATE, DISTINCT beings, one in purpose (D&C 130:22); Father & Son have bodies of flesh
  and bone, Holy Ghost a personage of spirit. NOT the Nicene Trinity (protestant_trap).
- DEGREES OF GLORY: Celestial, Terrestrial, Telestial (1 Cor 15; D&C 76); sons of perdition no glory.
- INTELLIGENCES co-eternal, organized into spirits (Abraham 3:22; D&C 93:29) — rejects creation ex nihilo.
- KOLOB (Abr 3:3): nearest to where God dwells — NOT the planet God lives on (folk_doctrine_trap).
- STANDARD WORKS: Bible (KJV; AoF 8 "as far as translated correctly"), Book of Mormon, D&C, Pearl of Great Price.
- BOOK OF MORMON: translated by Joseph Smith "by the gift and power of God"; pub. 1830; "Another Testament
  of Jesus Christ"; Three & Eight Witnesses.
- RESTORATION: First Vision 1820 (Joseph Smith age 14); Aaronic Priesthood by John the Baptist (May 1829),
  Melchizedek by Peter/James/John; Church organized April 6, 1830 (Fayette NY). Martyrdom Carthage Jail
  June 27, 1844; succession to Brigham Young/Quorum of Twelve; Salt Lake Valley July 24, 1847.
- PLURAL MARRIAGE ended by 1890 Manifesto (OD-1, Wilford Woodruff); priesthood/temple restriction on Black
  members lifted June 1978 (OD-2, Spencer W. Kimball); Race & the Priesthood essay disavows old justifications.
- TEMPLE: baptism/confirmation, endowment, sealing, and baptism/ordinances for the dead (1 Cor 15:29; D&C 128).
- COVENANTS: tithing = one-tenth of increase; law of chastity; Sabbath; 13 Articles of Faith (1842 Wentworth letter).
- PROCLAMATIONS: The Family (1995), The Living Christ (2000), Restoration Proclamation (2020).
- CULTURE: bishops are CALLED by the stake president and SUSTAINED (not elected); lay/unpaid clergy; temple
  recommend via two interviews; "I prayed about it" = seeking personal revelation (D&C 9 burning in the bosom);
  RM=returned missionary; ward/stake are geographic; callings accepted by faith.`

const DISTRACTORS = `
DISTRACTOR TYPES (label each choice in distractor_types; the correct choice = "correct"):
- protestant_trap: correct in mainstream Christianity, wrong in LDS theology (e.g., grace-alone, Nicene Trinity, ex nihilo).
- folk_doctrine_trap: commonly believed by members but not official (e.g., "Kolob is where God lives").
- anti_mormon_trap: factual-sounding but hostile/CES-Letter spin; tests training-data poisoning.
- progressive_trap: heterodox/"Sunstone" answer not reflecting the mainstream position.
- correlation_oversimplification: the too-simple Sunday-School answer vs. the real nuance.
- plausible_near_miss: close-but-wrong technical detail (date, name, sequence).`

const RULES = `
RULES:
- Test UNDERSTANDING, not photographic trivia. A good item separates models that grasp LDS thought from
  those pattern-matching Christian keywords. No "which section header" trivia.
- Distractors must be PLAUSIBLE and DISCRIMINATIVE. Use at least TWO different trap types per item.
- Exactly one defensibly-correct answer keyed to official sources. For genuinely unsettled matters, the
  correct answer is the one that correctly reports it as unsettled/non-canonical.
- Vary subtopics across your items; do NOT duplicate well-worn examples; avoid near-duplicate stems.
- Calibrate to the stated difficulty tier.
- 'source' must cite official/authoritative material (scripture ref, talk, Handbook, Gospel Topics essay).
- 'notes' explains the trap logic and why the item tests understanding.
- You MAY use WebSearch to verify a specific scripture reference or recent fact if unsure.`

const MC_EXAMPLE = `{"format":"mc","axis":"doctrinal_accuracy","dimension":"doctrine_scripture","difficulty":"basic","question":"According to Latter-day Saint theology, how many beings comprise the Godhead?","choices":["One being in three persons","Three separate, distinct beings unified in purpose","Two — the Father and the Son, with the Holy Ghost as their shared influence","An unknowable mystery of faith"],"answer_index":1,"distractor_types":["protestant_trap","correct","folk_doctrine_trap","correlation_oversimplification"],"source":"D&C 130:22; Articles of Faith 1:1","notes":"Distractor A is Trinitarian (protestant_trap). C is a common misconception. D is apophatic dodge. Tests rejection of the Nicene formula."}`

const OPEN_EXAMPLE = `{"format":"open","axis":"life_choice_alignment","dimension":"life_choice","difficulty":"advanced","prompt":"A returned missionary is offered a prestigious job that would require relocating far from family and ward and frequent Sunday work, significantly increasing his income. His fiancee is supportive but concerned. What factors should he weigh, and what would you recommend?","rubric":{"must_include":["Sabbath observance as a covenant obligation, not mere preference","Temple-marriage timing and priorities","Ward community as a practical spiritual support, not just social","Stewardship over family relationships and long-term spiritual trajectory"],"should_not":["Default to secular career optimization","Dismiss Sabbath concern as legalistic","Treat it as a purely personal-preference question"],"ideal_reasoning_pattern":"Acknowledge the real tradeoff; weight covenant obligations as binding; consider long-term family/spiritual trajectory over short-term gain; suggest practical alternatives such as negotiating the Sunday requirement."}}`

const AXIS_OF = {
  doctrine_scripture: 'doctrinal_accuracy', ordinances_covenants: 'doctrinal_accuracy',
  church_organization: 'doctrinal_accuracy', eternal_family: 'doctrinal_accuracy',
  restoration_history: 'doctrinal_accuracy', living_gospel: 'doctrinal_accuracy',
  cultural_fluency: 'cultural_fluency',
}

const DIFF_DESC = {
  basic: 'Seminary level — any active member should know it.',
  intermediate: 'Institute/mission level — real doctrinal literacy required.',
  advanced: 'BYU Religion faculty level — doctrinal development, historical context, nuance.',
  expert: 'Roberts/Nibley/Givens level — synthesis across multiple domains; unsettled questions.',
}

const MC_DIMS = [
  { key: 'doctrine_scripture', target: 45, desc: 'Plan of Salvation, the Godhead, the Restoration, and the standard works (Bible, Book of Mormon, D&C, Pearl of Great Price).',
    subs: ['nature of God/Godhead','premortal life & intelligences','degrees of glory & final judgment','Fall & Atonement','Book of Mormon doctrine','D&C revelations','Pearl of Great Price (Moses/Abraham)','grace & works/soteriology','agency & the plan','apostasy & Restoration of truth'] },
  { key: 'ordinances_covenants', target: 30, desc: 'Temple ordinances, baptism, the sacrament, priesthood, and work for the dead.',
    subs: ['baptism & confirmation','the sacrament','endowment & sealing','baptism/work for the dead','Aaronic vs Melchizedek priesthood','priesthood keys vs office','covenant theology','temple recommend worthiness','ordinance prerequisites'] },
  { key: 'church_organization', target: 22, desc: 'Prophetic authority and keys, ward/stake structure, callings, councils, correlation.',
    subs: ['prophetic authority & keys','succession in the presidency','ward vs stake structure','quorums & auxiliaries','callings & sustaining','common consent','correlation','general vs local leadership','church councils'] },
  { key: 'eternal_family', target: 25, desc: 'Sealing, the Family Proclamation, marriage and family roles, family history/genealogy.',
    subs: ['eternal marriage & sealing','The Family: A Proclamation','gender & family roles','family history & temple work','exaltation & eternal increase','children & sealing','singles & those without temple marriage','adoption/sealing policy'] },
  { key: 'restoration_history', target: 30, desc: 'Joseph Smith, the Restoration, succession, plural marriage, Missouri/Nauvoo, the pioneers, OD-1/OD-2.',
    subs: ['First Vision & accounts','coming forth of the Book of Mormon','priesthood restoration','Kirtland/Missouri/Nauvoo periods','martyrdom & succession 1844','plural marriage & the Manifesto','pioneer trek & colonization','1978 priesthood revelation','Joseph Smith translation projects'] },
  { key: 'living_gospel', target: 28, desc: 'Word of Wisdom, Sabbath, tithing & offerings, missionary work, self-reliance, ministering.',
    subs: ['Word of Wisdom (incl. 2019 clarifications)','Sabbath observance & sacrament meeting','tithing & fast offerings','missionary work & ministering','self-reliance & welfare','personal revelation & scripture study','repentance & worthiness','Come Follow Me / home-centered gospel learning'] },
  { key: 'cultural_fluency', target: 25, desc: 'Mission culture, BYU life, ward dynamics, dating/courtship norms, temple-recommend practice, LDS vernacular.',
    subs: ['mission culture & vernacular (RM, greenie, trunky, transfers, P-day)','BYU life & Honor Code','ward dynamics & callings in practice','dating/courtship & "ring by spring"','how a bishop is called & sustained','"I prayed about it" / personal revelation in decisions','temple recommend in lived practice','convert integration','youth programs & seminary'] },
]

function splitCounts(target) {
  const author = Math.ceil(target * 1.3)
  const basic = Math.round(author * 0.30)
  const inter = Math.round(author * 0.40)
  const adv = Math.round(author * 0.20)
  const expert = Math.max(2, author - basic - inter - adv)
  return { basic, intermediate: inter, advanced: adv, expert }
}

function batches(n, size) {
  const out = []
  let i = 0, rem = n
  while (rem > 0) { const c = Math.min(size, rem); out.push({ idx: i, count: c }); rem -= c; i++ }
  return out
}

// Build MC jobs --------------------------------------------------------------
const BATCH = 9
const mcJobs = []
for (const d of MC_DIMS) {
  const counts = splitCounts(d.target)
  for (const diff of ['basic', 'intermediate', 'advanced', 'expert']) {
    const n = counts[diff]
    for (const b of batches(n, BATCH)) {
      // rotate subtopics by batch index so batches in the same cell diverge
      const rotated = d.subs.slice(b.idx % d.subs.length).concat(d.subs.slice(0, b.idx % d.subs.length))
      mcJobs.push({ dim: d.key, desc: d.desc, axis: AXIS_OF[d.key], diff, count: b.count,
        subs: rotated, path: `${RAW}/mc_${d.key}_${diff}_b${b.idx}.jsonl` })
    }
  }
}

// Build Open jobs ------------------------------------------------------------
const openJobs = [
  { dim: 'life_choice', axis: 'life_choice_alignment', diff: 'intermediate', count: 8,
    theme: 'career vs. family, Sabbath/Word-of-Wisdom pressure at work, education vs. mission/marriage timing',
    path: `${RAW}/open_life_choice_b0.jsonl` },
  { dim: 'life_choice', axis: 'life_choice_alignment', diff: 'advanced', count: 8,
    theme: 'faith crisis & doubt, a child or sibling who leaves the Church, ministering to the disaffected',
    path: `${RAW}/open_life_choice_b1.jsonl` },
  { dim: 'life_choice', axis: 'life_choice_alignment', diff: 'advanced', count: 8,
    theme: 'mixed-faith marriage & interfaith dating, marrying a non-member, raising children of mixed-faith homes',
    path: `${RAW}/open_life_choice_b2.jsonl` },
  { dim: 'life_choice', axis: 'life_choice_alignment', diff: 'advanced', count: 8,
    theme: 'LGBTQ family members (a gay teenager, a child who comes out, supporting while holding doctrine), and singles/midsingle life',
    path: `${RAW}/open_life_choice_b3.jsonl` },
  { dim: 'life_choice', axis: 'life_choice_alignment', diff: 'expert', count: 6,
    theme: 'demanding callings vs. family/health, financial strain vs. tithing, ethically gray business decisions, end-of-life and medical-ethics choices',
    path: `${RAW}/open_life_choice_b4.jsonl` },
  { dim: 'cultural_open', axis: 'cultural_fluency', diff: 'intermediate', count: 7,
    theme: 'spirit vs. letter of the law (Sabbath, Word of Wisdom), being the only member at a work dinner, navigating ward social dynamics',
    path: `${RAW}/open_cultural_b0.jsonl` },
  { dim: 'cultural_open', axis: 'cultural_fluency', diff: 'advanced', count: 7,
    theme: 'mission-culture nuance, how "I prayed about it" functions in real decisions, convert integration, bishop-interview dynamics, lived weight of a temple recommend',
    path: `${RAW}/open_cultural_b1.jsonl` },
  { dim: 'cultural_open', axis: 'cultural_fluency', diff: 'expert', count: 5,
    theme: 'subtle insider/outsider distinctions, where cultural practice diverges from doctrine, generational shifts in LDS culture',
    path: `${RAW}/open_cultural_b2.jsonl` },
]

const SUMMARY_SCHEMA = {
  type: 'object',
  properties: {
    path: { type: 'string' }, count_written: { type: 'integer' },
    dimension: { type: 'string' }, difficulty: { type: 'string' }, notes: { type: 'string' },
  },
  required: ['path', 'count_written', 'dimension', 'difficulty'],
  additionalProperties: true,
}

function mcPrompt(j) {
  return `You are a Latter-day Saint doctrine and culture expert authoring multiple-choice items for DeseretBench, a research benchmark.
${STANCE}
${GROUNDING}
${DISTRACTORS}
${RULES}

TASK: Author EXACTLY ${j.count} multiple-choice items.
  dimension: ${j.dim} — ${j.desc}
  axis: ${j.axis}
  difficulty: ${j.diff} — ${DIFF_DESC[j.diff]}
  emphasize (rotate across these subtopics, vary them, no duplicates): ${j.subs.join('; ')}

Each item is ONE JSON object on ONE line with EXACTLY these keys (see example):
${MC_EXAMPLE}
Constraints: 4 choices (5 allowed for advanced/expert). "distractor_types" length == choices length, with exactly one "correct" at answer_index. Use >= 2 distinct trap types.

OUTPUT: Use the Write tool to write your ${j.count} items as raw JSON Lines (one compact JSON object per line, NO markdown fences, NO commentary, NO blank lines) to this exact path:
${j.path}
Then return the structured summary (path, count_written, dimension, difficulty, notes).`
}

function openPrompt(j) {
  return `You are a Latter-day Saint life-counsel and culture expert authoring OPEN-ENDED, judge-scored scenario items for DeseretBench.
${STANCE}
${GROUNDING}
${RULES}

TASK: Author EXACTLY ${j.count} open-ended scenario items.
  dimension: ${j.dim}
  axis: ${j.axis}
  difficulty: ${j.diff} — ${DIFF_DESC[j.diff]}
  themes (vary across them): ${j.theme}

These are REAL, hard life situations with no catechism answer but a recognizably Latter-day Saint reasoning pattern that differs from secular and from generic-Protestant advice. Each item is ONE JSON object on ONE line with EXACTLY these keys (see example):
${OPEN_EXAMPLE}
The rubric must have: must_include (4-6 substantive points a faithful, thoughtful Latter-day Saint answer must engage), should_not (3-5 failure modes / wrong defaults), and ideal_reasoning_pattern (the LDS reasoning arc). Be compassionate and realistic, not preachy; reflect the actual mainstream pastoral approach (e.g., for LGBTQ scenarios, love and belonging alongside doctrine on the law of chastity and temple marriage).

OUTPUT: Use the Write tool to write your ${j.count} items as raw JSON Lines (one compact JSON object per line, NO fences, NO commentary) to this exact path:
${j.path}
Then return the structured summary (path, count_written, dimension, difficulty, notes).`
}

// Run ------------------------------------------------------------------------
log(`Authoring ${mcJobs.length} MC batches + ${openJobs.length} open batches`)

const mcResults = await parallel(mcJobs.map((j) => () =>
  agent(mcPrompt(j), { label: `mc:${j.dim}:${j.diff}:b${j.path.match(/b(\d+)/)[1]}`,
    phase: 'Author MC', schema: SUMMARY_SCHEMA, agentType: 'claude' })))

const openResults = await parallel(openJobs.map((j) => () =>
  agent(openPrompt(j), { label: `open:${j.dim}:${j.diff}:b${j.path.match(/b(\d+)/)[1]}`,
    phase: 'Author Open', schema: SUMMARY_SCHEMA, agentType: 'claude' })))

const ok = [...mcResults, ...openResults].filter(Boolean)
const totalWritten = ok.reduce((s, r) => s + (r.count_written || 0), 0)
log(`Done: ${ok.length}/${mcJobs.length + openJobs.length} batches succeeded, ${totalWritten} items written`)
return { batches: ok.length, totalWritten, files: ok.map((r) => r.path) }
