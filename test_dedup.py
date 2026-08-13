import sys
sys.path.insert(0, r"C:/Users/USER/arcaeon-dedup")
from arcaeon_dedup import dedupe, simhash, hamming

items = [
    "The API returned status 200 and the user was created successfully.",
    "Status 200 was returned by the API; the user was created successfully.",  # near-dup of #0
    "The database connection timed out after 30 seconds of waiting.",
    "The database connection timed out after thirty seconds of waiting.",       # near-dup of #2
    "Payment processing completed and a receipt was emailed to the customer.",  # distinct
]
kept, report = dedupe(items)
print(report)
print("kept count:", len(kept), "| removed indices:", report.removed_indices)
for k in kept:
    print("  KEPT:", k[:60])

# sanity: near-dups collapse, distinct survives
assert len(kept) == 3, f"expected 3 kept, got {len(kept)}"
assert report.removed == 2
# identical text -> hamming 0
assert hamming(simhash("hello world foo bar"), simhash("hello world foo bar")) == 0
# genuinely different -> large hamming
assert hamming(simhash("the cat sat on the mat"), simhash("quarterly revenue exceeded forecasts")) > 10
# keep='longest' keeps the fuller phrasing among near-dupes
kept2, r2 = dedupe([
    "The server returned an error and the request failed.",
    "The server returned an error, so the request failed to complete.",  # near-dup, longer
], keep="longest")
assert len(kept2) == 1 and "to complete" in kept2[0], kept2
print("PASS - collapses near-dupes, keeps distinct, longest-mode works, saved ~%d tokens" % report.est_tokens_saved)
