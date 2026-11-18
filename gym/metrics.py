"""Deterministic, transcript-only communication metrics.

What this CAN measure from text: word counts, answer length, filler/hedge
frequency, immediate word repetitions, sentence length.
What it CANNOT measure: pause duration, speaking rate, pronunciation,
intonation. It also depends on the speech-to-text engine: if the engine
drops "uh"/"um", filler counts will be under-reported (verify this in Stage 0).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from statistics import median

# Filled pauses: unambiguous disfluencies.
FILLED_PAUSES = ("uh", "uhh", "uhm", "um", "umm", "erm", "er", "ah", "eh", "hmm", "mm")
# Discourse-marker fillers: counted separately because they are often legitimate.
DISCOURSE_FILLERS = ("you know", "i mean", "basically", "actually", "kind of", "sort of",
                     "literally", "so yeah")
HEDGES = ("i think", "i guess", "maybe", "probably", "i'm not sure", "i am not sure",
          "i believe", "more or less")
LONG_ANSWER_WORDS = 150

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_SENT_SPLIT = re.compile(r"[.!?]+(?:\s|$)")
# "like" as a filler: preceded/followed by a comma, or sentence-initial "like,".
_LIKE_FILLER = re.compile(r"(?:^|[,.;]\s*)like\s*,|,\s*like\s+(?=\w)", re.IGNORECASE)


def _norm(text: str) -> str:
    return text.lower().replace("’", "'")


def words(text: str) -> list[str]:
    return _WORD.findall(_norm(text))


def _count_phrases(tokens: list[str], phrases: tuple[str, ...]) -> Counter:
    c: Counter = Counter()
    for phrase in phrases:
        parts = phrase.split()
        n = len(parts)
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == parts:
                c[phrase] += 1
    return c


def repetitions(tokens: list[str]) -> int:
    """Immediate repeats like 'the the' or 'I I' (restarts)."""
    return sum(1 for a, b in zip(tokens, tokens[1:]) if a == b and a not in {"very", "no"})


def sentences(text: str) -> list[str]:
    return [s for s in (x.strip() for x in _SENT_SPLIT.split(text)) if s]


@dataclass
class AnswerMetrics:
    index: int
    words: int
    sentences: int
    avg_sentence_words: float
    filled_pauses: dict[str, int]
    discourse_fillers: dict[str, int]
    like_fillers: int
    hedges: dict[str, int]
    repetitions: int
    filled_per_100w: float


@dataclass
class TranscriptMetrics:
    answers: int
    total_words: int
    median_answer_words: float
    max_answer_words: int
    long_answers: list[int]
    filled_pauses_total: int
    filled_per_100w: float
    discourse_fillers_total: int
    discourse_per_100w: float
    hedges_total: int
    hedges_per_100w: float
    repetitions_total: int
    top_fillers: list[tuple[str, int]]
    per_answer: list[AnswerMetrics] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _rate(n: int, total: int) -> float:
    return round(100.0 * n / total, 2) if total else 0.0


def analyze_answer(index: int, text: str) -> AnswerMetrics:
    toks = words(text)
    sents = sentences(text)
    fp = _count_phrases(toks, FILLED_PAUSES)
    df = _count_phrases(toks, DISCOURSE_FILLERS)
    hd = _count_phrases(toks, HEDGES)
    like = len(_LIKE_FILLER.findall(text))
    n = len(toks)
    return AnswerMetrics(
        index=index,
        words=n,
        sentences=len(sents),
        avg_sentence_words=round(n / len(sents), 1) if sents else float(n),
        filled_pauses=dict(fp),
        discourse_fillers=dict(df),
        like_fillers=like,
        hedges=dict(hd),
        repetitions=repetitions(toks),
        filled_per_100w=_rate(sum(fp.values()), n),
    )


def analyze_transcript(answers: list[str]) -> TranscriptMetrics:
    answers = [a for a in answers if a and a.strip()]
    per = [analyze_answer(i, a) for i, a in enumerate(answers)]
    total = sum(p.words for p in per)
    fp_total: Counter = Counter()
    df_total: Counter = Counter()
    hd_total = 0
    like_total = 0
    for p in per:
        fp_total.update(p.filled_pauses)
        df_total.update(p.discourse_fillers)
        hd_total += sum(p.hedges.values())
        like_total += p.like_fillers
    if like_total:
        df_total["like"] += like_total
    lengths = [p.words for p in per]
    caveats = [
        "Transcript-only: pauses, speaking rate and pronunciation are NOT measured.",
        "Filler counts depend on the speech-to-text engine; if it strips 'uh/um', counts are a lower bound.",
    ]
    if total and sum(fp_total.values()) == 0:
        caveats.append("Zero filled pauses detected: check whether the transcriber removes them.")
    return TranscriptMetrics(
        answers=len(per),
        total_words=total,
        median_answer_words=float(median(lengths)) if lengths else 0.0,
        max_answer_words=max(lengths, default=0),
        long_answers=[p.index for p in per if p.words > LONG_ANSWER_WORDS],
        filled_pauses_total=sum(fp_total.values()),
        filled_per_100w=_rate(sum(fp_total.values()), total),
        discourse_fillers_total=sum(df_total.values()),
        discourse_per_100w=_rate(sum(df_total.values()), total),
        hedges_total=hd_total,
        hedges_per_100w=_rate(hd_total, total),
        repetitions_total=sum(p.repetitions for p in per),
        top_fillers=(fp_total + df_total).most_common(8),
        per_answer=per,
        caveats=caveats,
    )
