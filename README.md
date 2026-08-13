# arcaeon-dedup

**Strip near-duplicate text from an agent's context before it costs you tokens.**
*Pure stdlib. No LLM, no embeddings, no network. Cheap enough to run on every call.*

```bash
pip install arcaeon-dedup
```

## Why

Retrieved chunks, tool outputs, conversation history, and memory stores fill up with
near-duplicates — the same passage phrased three ways, the same doc pulled twice,
boilerplate repeated across results. Every redundant copy is pure token waste, and
you pay for it on **every** call that carries it.

Most "dedup" tooling is built for training corpora, or needs embeddings + a vector DB
to run. For agent context you want something that costs essentially nothing, so you
can put it in front of every context assembly without thinking about it.

`arcaeon-dedup` uses **SimHash** — a locality-sensitive hash, so *almost the same*
collapses, not just byte-identical — over pure Python. No model call, no API, no
dependencies.

## Use

```python
from arcaeon_dedup import dedupe

chunks = [
    "The API returned status 200 and the user was created successfully.",
    "Status 200 was returned by the API; the user was created successfully.",  # near-dup
    "The database connection timed out after 30 seconds.",
]

kept, report = dedupe(chunks)
# kept   -> 2 items (the near-duplicate dropped, order preserved)
# report -> deduped: kept 2, removed 1 near-duplicate(s); ~62 chars / ~15 tokens saved
```

Tuning:

```python
dedupe(chunks, max_hamming=12, k=1, keep="first")
```

- `max_hamming` (default **12**, of 64 bits): how close counts as "duplicate."
  Defaults are calibrated so reordered/lightly-reworded paraphrases (~10-12 bits
  apart) collapse while genuinely different text (~30+ bits apart) is left alone —
  a wide, safe margin. Lower = stricter.
- `k` (default **1**): shingle size. `k=1` is order-insensitive (a bag-of-words
  fingerprint — good for paraphrase); `k=2-3` weights word order (only closer-to-
  verbatim dupes).
- `keep`: `"first"` keeps the earliest of each cluster (best for chronological
  context — the original stays); `"longest"` keeps the fullest phrasing.

Also exported: `simhash(text)`, `hamming(a, b)` if you want the primitives directly.

## What it is / isn't

**Is:** a fast, dependency-free near-duplicate filter for the text you're about to
put in a context window — retrieval results, tool outputs, message history, memories.

**Isn't:** a semantic clusterer or a summarizer. It removes *redundant copies*, not
*related-but-distinct* content, and it won't rewrite anything. For paraphrase far from
the original, raise `max_hamming` (accepting more false-positives) or reach for an
embedding-based tool — this one is deliberately the cheap, safe, zero-dep first pass.

MIT. Built by [Arcaeon](https://arcaeon.io) — the evidence layer for AI.
