"""Robust multiple-choice answer extraction.

Models may emit a reasoning preamble before the answer. We extract the final
chosen letter, tolerating many phrasings. Unparseable responses return None and
are scored incorrect (and the parse-failure rate is reported separately).
"""

from __future__ import annotations

import re
from typing import Optional

from .schema import LETTERS


# A candidate letter must be standalone: not the first letter of a word like
# "depends"/"Actually", and not immediately preceded by a word character.
_STANDALONE = r"(?<![A-Za-z0-9])\(?\*{0,2}([A-H])\*{0,2}\)?(?![A-Za-z0-9])"
# "A or B" / "A/B" after the letter = a hedge, not a decision. The trailing
# letter is matched WITHOUT IGNORECASE and excludes lowercase 'a', so the
# English article doesn't hedge a decided answer ("ANSWER: B, or a variant").
_HEDGE_AFTER = re.compile(r"\s*(?:[oO][rR]|/)\s*\(?\*{0,2}(?:[A-H]|[b-h])(?![A-Za-z0-9])")


def _last_unhedged(matches, valid, text) -> Optional[str]:
    for m in reversed(matches):
        letter = m.group(1).upper()
        if letter not in valid:
            continue
        if _HEDGE_AFTER.match(text[m.end():]):
            return None  # explicitly ambiguous — report a parse failure
        return letter
    return None


def parse_answer(text: str, n_choices: int, choices: list[str] | None = None
                 ) -> Optional[str]:
    if not text:
        return None
    valid = set(LETTERS[:n_choices])
    t = text.strip()

    # 1) Explicit "ANSWER: X" — prefer the LAST one (final decision).
    pat = re.compile(r"answer\s*[:\-]?\s*" + _STANDALONE, re.IGNORECASE)
    letter = _last_unhedged(list(pat.finditer(t)), valid, t)
    if letter:
        return letter

    # 2a) A positive answer statement — beats mere option/choice mentions,
    #     which rule 2b only consults when no statement exists (eliminative
    #     prose like "option D is wrong" must not flip the parse).
    pat2a = re.compile(
        r"(?:(?:correct|best|final)\s+answer\s+is|the\s+answer\s+(?:is|appears\s+to\s+be|"
        r"would\s+be|should\s+be)|my\s+answer\s+is|i\s+(?:would\s+)?choose|i\s+select|"
        r"i\s+(?:would\s+)?pick|i'd\s+(?:choose|pick|go\s+with)|going\s+with)\s*" + _STANDALONE,
        re.IGNORECASE)
    letter = _last_unhedged(list(pat2a.finditer(t)), valid, t)
    if letter:
        return letter

    pat2b = re.compile(r"(?:option|choice)\s*" + _STANDALONE, re.IGNORECASE)
    letter = _last_unhedged(list(pat2b.finditer(t)), valid, t)
    if letter:
        return letter

    # 3) A bare letter on its own line (scan from the end).
    for line in reversed(t.splitlines()):
        s = line.strip().strip(".:)*( ")
        if len(s) == 1 and s.upper() in valid:
            return s.upper()
        m = re.fullmatch(r"\(?\*{0,2}([A-H])\*{0,2}\)?[.):]?", s)
        if m and m.group(1).upper() in valid:
            return m.group(1).upper()

    # 4) Last resort: restated option text uniquely matching one choice.
    if choices:
        tail = t[-400:].lower()
        hits = []
        for i, c in enumerate(choices):
            cc = c.strip().lower()
            if len(cc) >= 8 and cc in tail:
                hits.append(i)
        if len(hits) == 1:
            return LETTERS[hits[0]]

    return None


def is_correct(text: str, answer_index: int, choices: list[str]) -> tuple[bool, Optional[str]]:
    letter = parse_answer(text, len(choices), choices)
    if letter is None:
        return False, None
    return (LETTERS.index(letter) == answer_index), letter
