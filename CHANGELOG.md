# Changelog — arcaeon-dedup

## 0.1.2 — unreleased (local, pending the 2 PM 2026-08-15 publish batch — NOT yet on PyPI)

Emoji/symbol-collapse fix, found while writing the order-dependence note below.

- **Symbol-only and emoji-only items no longer all collapse into one.** `_overlap()`
  builds its Jaccard score from character-4-grams and word-bigrams, both of which
  come from `\w+` word matching. Emoji, star-ratings, and other symbol-only strings
  normalize to an EMPTY feature set (`_normalize` finds no words), so every such
  pair read `_jaccard(empty, empty) == 1.0` — maximum overlap, guaranteed collapse,
  regardless of which symbols they actually were. A five-star rating and a
  one-star rating, a rocket emoji and a heart emoji, silently became "the same
  item" and one was deleted. Fix: when BOTH sides normalize to empty, overlap is
  now 1.0 only if the RAW strings are byte-identical, 0.0 otherwise — the only
  defensible "duplicate" with zero word content to compare is an exact repeat;
  anything else is content we cannot measure, so it is kept, not guessed.
- **New regression test** (`test_symbol_only_items_are_not_all_collapsed`): five
  distinct emoji/star/punctuation-only items must all survive `dedupe()`; two
  byte-identical emoji items must still collapse to one; empty-string items still
  collapse together while real content next to them is kept. 9/9 tests pass.
- **README addition: collapse is order-dependent by design.** Documented, not
  changed — clustering is greedy single-linkage against the first representative
  a candidate matches. If A matches B and B matches C but A does not match C,
  `[A, B, C]` keeps A and C while `[B, A, C]` collapses both into B: the same
  input set, different survivor count, depending on feed order. Every drop is
  still verified against the specific representative it was measured against, so
  nothing is removed against an item it was never compared with — but a pipeline
  that merges retrievers in arbitrary order and needs order-stable output should
  sort the input first, or run at `min_overlap=1.0` (exact-match only).
- **Version:** `__version__` and `pyproject.toml` bumped 0.1.1 → 0.1.2 locally.
  Held for the 2026-08-15 2 PM publish batch (rebuild dist from this source,
  clean-venv install, re-run discriminator, then `twine upload`) — not published
  to PyPI yet. products.yaml stays at 0.1.1 (PyPI's live version) until publish;
  do not advertise 0.1.2 on the site before it is live.

## 0.1.1 — 2026-08-14 (verify before deleting — 0.1.0 was dropping facts, not duplicates)

Hostile audit. At stock defaults the library silently deleted content that was
NOT duplicated, at these rates: 95.7% of 10-word items differing in one word,
99.7% at 20 words, 99.9% at 30 words; roughly 1 collision per 500–2000 documents
sharing zero words. Concretely, these all collapsed to one item and the report
called it a saving: "Alice owes Bob $100." / "Bob owes Alice $100." (hamming 0);
"Transfer 500 from savings to checking" / "...from checking to savings"; "The
patient is allergic to penicillin" / "...is NOT allergic..."; "Charge the
customer $19" / "Refund the customer $19"; three distinct patient records; four
distinct payment-decline log lines.

- **Cause:** SimHash was used as the VERDICT, not a filter. `k=1` makes the
  fingerprint a bag of words, and bit-summing is commutative, so any permutation
  of the same words lands at Hamming distance 0 — unreachable by any threshold.
  `max_hamming=12` over 64 bits is a ball wide enough that documents sharing no
  words at all can land inside it.
- **Fix:** SimHash still generates candidates; a candidate is now dropped only if
  MEASURED feature overlap clears `min_overlap` (default 0.95) — the minimum of
  character-4-gram and word-bigram Jaccard over normalized text. Two views,
  because bigrams carry the word order that catches Alice/Bob, and char-grams
  keep short strings and space-free scripts measurable. After the gate: 0/300
  dropped at 10/20/30/60 words with one word changed; 0 collisions across 1200
  independent documents; verbatim/whitespace/case/punctuation repeats still
  collapse.
- **Honest rescope:** this is a NEAR-VERBATIM deduper, stated in the README
  rather than left to be found. It does not collapse paraphrase and must not
  pretend to — no lexical distance separates "reworded, same meaning" from "one
  word changed, opposite meaning," and any setting that collapses the first
  deletes the second.
- **Also fixed:** `keep="longest"` mutated the cluster representative mid-scan,
  so membership chained transitively and items were deleted against a
  representative they were never compared with (now two passes, frozen
  representatives). `k=0` bypassed the length guard and collapsed the entire
  input to one item (now raises `ValueError`). A bare string was silently
  deduplicated character by character; `None`/int/bytes entries raised
  `AttributeError` from three different layers (now typed `TypeError`).
  CJK/Thai text was one `\w+` token, so SimHash degenerated to a plain hash and
  detection silently stopped (char-grams now cover it). NFKC normalization
  added.
- **Remaining limitation, stated rather than hidden:** one token changed inside
  a LONG document still reads as a repeat past some length — same theorem;
  `min_overlap=1.0` is the exact-only escape hatch.
- Test suite rewritten. The 0.1.0 suite asserted only that dedup FIRES — not one
  assertion that a distinct item survives — which is why it passed on all of the
  above. 9 must-survive pairs became the load-bearing tests (later 9→10 with the
  0.1.2 symbol-only regression).

## 0.1.0 — 2026-08-13 (initial build)

Token-saving primitive from the 2026-08-13 research: strip near-duplicate text
before it hits the context window. Pure stdlib SimHash, zero dependencies, no
LLM, calibrated defaults. The cheapest-to-run whitespace pick.
