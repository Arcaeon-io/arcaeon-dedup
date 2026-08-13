"""arcaeon-dedup — strip near-duplicate text from an agent's context before it costs tokens.

Retrieved chunks, tool outputs, conversation history, and memory stores fill up
with near-duplicates — the same passage phrased three ways, the same doc pulled
twice, boilerplate repeated across results. Every redundant copy is pure token
waste you pay for on every call.

`dedupe()` finds near-duplicates with **SimHash** — a locality-sensitive hash, so
"almost the same" collapses, not just byte-identical — and drops the redundant
ones, keeping the first of each cluster. **No LLM call, no embeddings, no network:
pure stdlib.** That's the point — it costs essentially nothing to run, so it's
cheap enough to put in front of every context assembly.

    from arcaeon_dedup import dedupe
    kept, report = dedupe([
        "The API returned status 200 and the user was created.",
        "Status 200 returned by the API; the user was created.",   # near-dup
        "The database connection timed out after 30 seconds.",
    ])
    # kept -> 2 items (the near-dup dropped)
    # report -> DedupeReport(kept=2, removed=1, chars_saved=..., est_tokens_saved=...)

Zero dependencies. MIT. Built by Arcaeon — the evidence layer for AI.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

__version__ = "0.1.0"
__all__ = ["dedupe", "simhash", "hamming", "DedupeReport"]

_WORD = re.compile(r"\w+")
_BITS = 64
_MASK = (1 << _BITS) - 1


def _shingles(text: str, k: int = 3) -> list[str]:
    """Word k-grams — the features SimHash weighs. Falls back to single words for short text."""
    words = _WORD.findall(text.lower())
    if len(words) < k:
        return words or [text.lower()]
    return [" ".join(words[i:i + k]) for i in range(len(words) - k + 1)]


def _feature_hash(feature: str) -> int:
    return int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")


def simhash(text: str, k: int = 3) -> int:
    """64-bit SimHash of text — near-identical text yields near-identical hashes."""
    v = [0] * _BITS
    shingles = _shingles(text, k)
    if not shingles:
        return 0
    for sh in shingles:
        h = _feature_hash(sh)
        for i in range(_BITS):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(_BITS):
        if v[i] > 0:
            out |= (1 << i)
    return out & _MASK


def hamming(a: int, b: int) -> int:
    """Number of differing bits — the near-duplicate distance. 0 = identical fingerprint."""
    return bin(a ^ b).count("1")


@dataclass
class DedupeReport:
    kept: int
    removed: int
    chars_saved: int
    est_tokens_saved: int
    removed_indices: list[int]

    def __str__(self) -> str:
        return (f"deduped: kept {self.kept}, removed {self.removed} near-duplicate(s); "
                f"~{self.chars_saved:,} chars / ~{self.est_tokens_saved:,} tokens saved")


def dedupe(items: list[str], *, max_hamming: int = 12, k: int = 1,
           keep: str = "first") -> tuple[list[str], DedupeReport]:
    """Remove near-duplicate strings from a list, preserving order.

    Two items are near-duplicates if their SimHashes differ by <= max_hamming bits
    (out of 64). Defaults (k=1 word-level shingles, max_hamming=12) are calibrated so
    reordered/lightly-reworded paraphrases (typically ~10-12 bits apart) collapse
    while genuinely different text (~30+ bits apart) is left alone — a wide safe
    margin. Lower max_hamming = stricter; raise it to catch heavier paraphrase at
    the risk of false-positives. k=1 is order-insensitive (a bag-of-words fingerprint);
    raise k to 2-3 to weight word order (catches only closer-to-verbatim dupes).

    keep="first" (default) keeps the earliest of each duplicate cluster (best for
    chronological context — the original stays). keep="longest" keeps the most
    complete phrasing.

    Returns (kept_items, DedupeReport). Order of kept items is preserved. Pure
    stdlib: no LLM, no embeddings, no network.
    """
    if keep not in ("first", "longest"):
        raise ValueError("keep must be 'first' or 'longest'")
    fps = [(i, s, simhash(s, k)) for i, s in enumerate(items)]
    kept: list[tuple[int, str, int]] = []
    removed_idx: list[int] = []
    chars_saved = 0
    for i, s, fp in fps:
        dup_of = None
        for ki, (_, _, kfp) in enumerate(kept):
            if hamming(fp, kfp) <= max_hamming:
                dup_of = ki
                break
        if dup_of is None:
            kept.append((i, s, fp))
        else:
            if keep == "longest" and len(s) > len(kept[dup_of][1]):
                # swap: the longer phrasing wins its cluster; the shorter is dropped
                chars_saved += len(kept[dup_of][1])
                removed_idx.append(kept[dup_of][0])
                kept[dup_of] = (i, s, fp)
            else:
                chars_saved += len(s)
                removed_idx.append(i)
    kept_sorted = [s for (_, s, _) in sorted(kept, key=lambda t: t[0])]
    report = DedupeReport(
        kept=len(kept_sorted), removed=len(removed_idx),
        chars_saved=chars_saved, est_tokens_saved=chars_saved // 4,  # ~4 chars/token rule of thumb
        removed_indices=sorted(removed_idx))
    return kept_sorted, report
