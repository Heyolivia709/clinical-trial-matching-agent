"""Trial Retrieval deep module. Gate 3, additive.

    retrieve(timeline, snapshot, k) -> CandidateSet

Owns ingestion, corpus membership, candidate filters, BM25, embeddings, and
reciprocal-rank fusion. Index internals stay behind the adapter interface.
"""
