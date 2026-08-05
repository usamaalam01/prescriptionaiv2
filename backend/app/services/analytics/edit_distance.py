"""Levenshtein-based CER and WER for prescription analytics."""

from __future__ import annotations


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def character_error_rate(hypothesis: str | None, reference: str | None) -> float | None:
    """CER = edit distance / len(reference). None if reference empty."""
    if reference is None:
        return None
    ref = reference
    hyp = hypothesis or ""
    if len(ref) == 0:
        return None if hyp else 0.0
    return levenshtein(hyp, ref) / len(ref)


def word_error_rate(hypothesis: str | None, reference: str | None) -> float | None:
    """WER = word-level Levenshtein / word count in reference."""
    if reference is None:
        return None
    ref_words = reference.split()
    hyp_words = (hypothesis or "").split()
    if not ref_words:
        return None if hyp_words else 0.0
    # Sequence Levenshtein on word tokens
    n, m = len(ref_words), len(hyp_words)
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i]
        for j in range(1, m + 1):
            cost = 0 if ref_words[i - 1] == hyp_words[j - 1] else 1
            cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1] / n


def as_percent(rate: float | None) -> float | None:
    if rate is None:
        return None
    return round(rate * 100, 2)
