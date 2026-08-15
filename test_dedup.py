"""Tests for arcaeon-dedup. The product claim is "removes repeats, never
facts", so the load-bearing tests are the NEGATIVE ones: the pairs that must
SURVIVE. The 0.1.0 suite had none, which is why it passed on a library that
deleted 99.7% of distinct 20-word inputs.

Run: python test_dedup.py
"""
import sys
sys.path.insert(0, r"C:/Users/USER/arcaeon-dedup")
from arcaeon_dedup import dedupe, simhash, hamming


def test_quickstart_removes_the_refetched_doc():
    doc = ("Docs: the API returns 200 on success. See the reference for details.")
    kept, report = dedupe([
        doc,
        doc.replace(". ", ".  "),          # same doc, refetched, whitespace noise
        "The database connection timed out after 30 seconds.",
    ])
    assert len(kept) == 2, kept
    assert report.removed == 1 and report.removed_indices == [1]
    print("PASS the quickstart: a refetched doc collapses, the distinct one stays")


# --- audit 2026-08-14: it was deleting content that was not duplicated ------
#
# SimHash is a CANDIDATE filter. Used as the verdict, it collapses anything
# whose words mostly overlap, and "mostly the same words" is not "the same
# meaning" — it is where the meaning usually lives. These are the pairs that
# must survive, and every one of them was being deleted at stock defaults.

MUST_SURVIVE = [
    ("permutation", "Alice owes Bob $100.", "Bob owes Alice $100."),
    ("direction", "Transfer 500 from savings to checking",
     "Transfer 500 from checking to savings"),
    ("failover", "Server A failed over to server B",
     "Server B failed over to server A"),
    ("negation", "Deploy to production.", "Do not deploy to production."),
    ("negation-long", "The patient is allergic to penicillin",
     "The patient is not allergic to penicillin"),
    ("antonym", "Charge the customer $19", "Refund the customer $19"),
    ("dosage", "Patient 4471, dosage 25 mg once daily, no known allergies.",
     "Patient 4472, dosage 50 mg twice daily, no known allergies."),
    ("log-line",
     "2026-08-14 order 88214 payment declined for customer bob@corp.com amount 12.50",
     "2026-08-14 order 88216 payment declined for customer dave@corp.com amount 18400.00"),
    ("json-row", '{"user_id": 2, "name": "Bob", "role": "viewer", "active": true}',
     '{"user_id": 3, "name": "Carol", "role": "editor", "active": true}'),
]


def test_distinct_content_is_never_silently_dropped():
    for name, a, b in MUST_SURVIVE:
        kept, report = dedupe([a, b])
        assert len(kept) == 2, (
            "SILENT DATA LOSS (%s): %r and %r are different facts, and one was "
            "deleted. hamming=%d" % (name, a, b, hamming(simhash(a, 1), simhash(b, 1))))
        assert report.removed == 0, name
    print("PASS %d distinct-but-similar pairs all survive (permutation, "
          "negation, antonym, ids, amounts)" % len(MUST_SURVIVE))


def test_real_duplicates_still_collapse():
    """The gate must not turn the library into a no-op: verbatim repeats,
    whitespace/case/punctuation noise, and repeated boilerplate still go."""
    doc = ("The database connection timed out after 30 seconds. Retrying with "
           "exponential backoff, three attempts, then failing the request.")
    cases = [
        ("verbatim", doc, doc),
        ("whitespace", doc, doc.replace(" ", "  ")),
        ("case", doc, doc.upper()),
        ("trailing punctuation", doc, doc + "!!"),
        ("wrapper noise", doc, "\n\n" + doc + "\n"),
    ]
    for name, a, b in cases:
        kept, report = dedupe([a, b])
        assert len(kept) == 1, "%s: a real duplicate survived" % name
        assert report.removed == 1, name
    print("PASS verbatim/whitespace/case/punctuation duplicates still collapse")


def test_unrelated_documents_never_collide():
    """At max_hamming=12 over 64 bits the ball is big enough that O(n^2) pairs
    finds a collision between documents sharing ZERO words."""
    import random
    rnd = random.Random(7)
    vocab = ["w%d" % i for i in range(4000)]
    docs = [" ".join(rnd.sample(vocab, 40)) for _ in range(1200)]
    kept, report = dedupe(docs)
    assert report.removed == 0, (
        "collided %d independent documents: indices %s"
        % (report.removed, report.removed_indices[:5]))
    print("PASS 1200 independent random documents: zero collisions")


def test_input_validation_is_typed():
    for bad, exc in [("a bare string", TypeError), (b"bytes", TypeError),
                     (None, TypeError), (123, TypeError)]:
        try:
            dedupe(bad)
            assert False, "accepted %r as a list of documents" % (bad,)
        except exc:
            pass
    for bad in ([None], [123], [b"x"], ["ok", None]):
        try:
            dedupe(bad)
            assert False, "accepted %r as documents" % (bad,)
        except TypeError:
            pass
    for kw in ({"k": 0}, {"k": -1}, {"max_hamming": -1}, {"max_hamming": 65},
               {"min_overlap": 1.5}, {"min_overlap": -0.1}):
        try:
            dedupe(["a b c", "a b c"], **kw)
            assert False, "accepted %r" % (kw,)
        except ValueError:
            pass
    assert dedupe([]) == ([], dedupe([])[1])
    print("PASS bare strings, non-str entries, and out-of-range knobs are typed errors")


def test_k_zero_no_longer_collapses_everything():
    """`if len(words) < k` is False for k=0, so words[i:i+0] yielded '' for
    every position and every document fingerprinted identically."""
    try:
        dedupe(["the quick brown fox", "a totally different sentence"], k=0)
        assert False, "k=0 accepted"
    except ValueError:
        pass
    print("PASS k=0 is refused instead of collapsing the entire input to one item")


def test_keep_longest_respects_the_documented_contract():
    """keep='longest' swapped the cluster representative mid-scan, so
    membership chained transitively: an item 15 bits from the survivor got
    deleted against a representative it was never a duplicate of."""
    base = "the quick brown fox jumps over the lazy dog near the river bank today"
    a = base
    b = base + " and then it rained"
    c = base.replace("quick brown fox", "slow purple heron") + " and then it rained a lot more"
    kept, report = dedupe([a, b, c], keep="longest")
    for item in kept:
        for other in kept:
            if item is other:
                continue
    # whatever clusters, nothing may be dropped against an item it is not a
    # verified duplicate of
    for idx in report.removed_indices:
        dropped = [a, b, c][idx]
        assert any(_verified_dup(dropped, s) for s in kept), (
            "dropped %r with no verified duplicate among the survivors" % dropped)
    print("PASS keep='longest' never drops an item against a non-duplicate representative")


def test_unicode_and_pathological_input():
    from arcaeon_dedup import _shingles
    # CJK has no spaces: \w+ made the whole sentence ONE feature, so SimHash
    # degenerated to a plain hash and near-duplicate detection silently died.
    assert len(_shingles("你好世界这是一个测试句子", 3)) > 1, "CJK is one feature"
    kept, _ = dedupe(["你好世界这是一个测试句子", "你好世界这是一个测试句子"])
    assert len(kept) == 1, "identical CJK text did not collapse"
    kept, _ = dedupe(["ship it", "ship it???!!!"])
    assert len(kept) == 1, "punctuation-only difference survived"
    kept, _ = dedupe(["\U0001f600" * 3, "totally different words here entirely"])
    assert len(kept) == 2
    big = "word " * 50000
    kept, _ = dedupe([big, big])
    assert len(kept) == 1
    kept, _ = dedupe(["", "", "real content here"])
    assert len(kept) == 2, "empty strings should collapse together, content kept"
    print("PASS CJK/emoji/punctuation/huge/empty inputs behave, no crash")


def _verified_dup(a: str, b: str) -> bool:
    from arcaeon_dedup import _overlap
    return _overlap(a, b) >= 0.95


if __name__ == "__main__":
    test_quickstart_removes_the_refetched_doc()
    test_distinct_content_is_never_silently_dropped()
    test_real_duplicates_still_collapse()
    test_unrelated_documents_never_collide()
    test_input_validation_is_typed()
    test_k_zero_no_longer_collapses_everything()
    test_keep_longest_respects_the_documented_contract()
    test_unicode_and_pathological_input()
    print(chr(10) + "ALL 8 TESTS PASSED")
