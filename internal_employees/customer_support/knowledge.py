"""
Knowledge base retrieval against the new knowledge_base_articles
collection. Keyword/substring search via PocketBase's own filter syntax —
same pattern as search_and_health.pb.js's /api/search, not a separate
search service. Good enough for a first version; if this needs to become
semantic search later, that's a bigger, separate project, not something
to half-build here.
"""

import re

from .integrations.pocketbase import synkra_os


def build_kb_filter(query: str) -> str:
    """
    Pure function — no I/O. Builds a PocketBase filter string matching
    title, body, or tags against each significant word in the query,
    scoped to published articles only. Splitting into words (rather than
    one substring match on the whole query) means "billing invoice
    question" still matches an article titled just "Invoices", not only
    an exact-phrase match.
    """
    words = [w for w in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(w) > 2]
    if not words:
        return "is_published = true"

    clauses = []
    for word in words:
        escaped = word.replace("'", "''")
        clauses.append(f"(title ~ '{escaped}' || body ~ '{escaped}' || tags ~ '{escaped}')")
    return "is_published = true && (" + " || ".join(clauses) + ")"


async def search_knowledge_base(query: str, limit: int = 5) -> list[dict]:
    filter_expr = build_kb_filter(query)
    return await synkra_os.list_records(
        "knowledge_base_articles", filter_expr=filter_expr, per_page=limit
    )
