"""Memory retrieval with keyword matching and TF-IDF scoring."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from repopilot.memory.store import MemoryStore
from repopilot.memory.types import MemoryRecord, MemoryType


@dataclass
class SearchResult:
    record: MemoryRecord
    score: float
    match_reason: str


class MemoryIndexer:
    """Retrieves relevant memories using keyword matching and TF-IDF."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        records = self.store.list_all()
        if memory_type:
            records = [r for r in records if r.type == memory_type]
        if not records:
            return []

        idf = self._compute_idf(records)
        query_terms = _tokenize(query)
        results = []

        for record in records:
            score, reason = self._score(query_terms, record, idf)
            if score > 0:
                results.append(SearchResult(record=record, score=score, match_reason=reason))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def get_relevant_context(self, query: str, max_tokens: int = 2000) -> str:
        """Get relevant memories formatted for injection into context."""
        results = self.search(query, top_k=5)
        if not results:
            return ""

        parts = ["## Relevant Memories\n"]
        estimated_tokens = 10
        for r in results:
            entry = f"### [{r.record.type.value}] {r.record.name}\n{r.record.content}\n"
            entry_tokens = len(entry.split()) * 1.3
            if estimated_tokens + entry_tokens > max_tokens:
                break
            parts.append(entry)
            estimated_tokens += entry_tokens

        return "\n".join(parts)

    def _compute_idf(self, records: list[MemoryRecord]) -> dict[str, float]:
        n = len(records)
        df: Counter[str] = Counter()
        for record in records:
            terms = set(_tokenize(f"{record.name} {record.description} {record.content}"))
            for term in terms:
                df[term] += 1
        return {term: math.log(1 + n / (1 + count)) for term, count in df.items()}

    def _score(
        self,
        query_terms: list[str],
        record: MemoryRecord,
        idf: dict[str, float],
    ) -> tuple[float, str]:
        doc_text = f"{record.name} {record.description} {record.content}"
        doc_terms = _tokenize(doc_text)
        doc_tf = Counter(doc_terms)
        doc_len = len(doc_terms) or 1

        score = 0.0
        matched_terms = []

        for term in query_terms:
            if term in doc_tf:
                tf = doc_tf[term] / doc_len
                term_idf = idf.get(term, 0)
                score += tf * term_idf
                matched_terms.append(term)

        name_terms = set(_tokenize(record.name))
        name_overlap = set(query_terms) & name_terms
        score += len(name_overlap) * 2.0

        recency_bonus = min(record.access_count * 0.1, 1.0)
        score += recency_bonus

        reason = f"matched: {', '.join(matched_terms[:5])}" if matched_terms else "no direct match"
        return score, reason


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\w+", text) if len(w) > 1]
