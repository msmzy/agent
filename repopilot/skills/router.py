"""Two-stage skill routing: keyword recall + LLM reranking.

Stage 1 (Recall): Fast keyword/tag matching to produce a candidate set.
Stage 2 (Rerank): LLM evaluates candidates using frontmatter only (not full body).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import anthropic

from repopilot.skills.loader import SkillLoader, SkillMeta


@dataclass
class RouteResult:
    skill: SkillMeta | None
    confidence: float
    reasoning: str


class SkillRouter:
    """Routes user intent to the best matching skill."""

    def __init__(
        self,
        loader: SkillLoader,
        model: str = "claude-haiku-4-5",
        max_candidates: int = 5,
    ) -> None:
        self.loader = loader
        self.model = model
        self.max_candidates = max_candidates
        self.client = anthropic.Anthropic()

    def route(self, user_message: str, context: str = "") -> RouteResult:
        """Two-stage routing: recall then rerank."""
        skills = self.loader.list_skills()
        if not skills:
            return RouteResult(skill=None, confidence=0.0, reasoning="No skills available")

        candidates = self._recall(user_message, skills)
        if not candidates:
            return RouteResult(skill=None, confidence=0.0, reasoning="No matching skills found")

        if len(candidates) == 1:
            return RouteResult(skill=candidates[0], confidence=0.8, reasoning="Single match from recall")

        return self._rerank(user_message, candidates, context)

    def _recall(self, user_message: str, skills: list[SkillMeta]) -> list[SkillMeta]:
        """Stage 1: keyword + tag matching for fast candidate recall."""
        scored: list[tuple[float, SkillMeta]] = []
        message_lower = user_message.lower()
        message_words = set(re.findall(r"\w+", message_lower))

        for skill in skills:
            score = 0.0

            for trigger in skill.triggers:
                if trigger.lower() in message_lower:
                    score += 3.0

            name_words = set(re.findall(r"\w+", skill.name.lower()))
            overlap = message_words & name_words
            score += len(overlap) * 2.0

            desc_words = set(re.findall(r"\w+", skill.description.lower()))
            desc_overlap = message_words & desc_words
            score += len(desc_overlap) * 0.5

            for tag in skill.tags:
                if tag.lower() in message_lower:
                    score += 1.5

            if skill.not_applicable_when:
                not_words = set(re.findall(r"\w+", skill.not_applicable_when.lower()))
                if message_words & not_words:
                    score *= 0.3

            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[: self.max_candidates]]

    def _rerank(self, user_message: str, candidates: list[SkillMeta], context: str) -> RouteResult:
        """Stage 2: LLM-based reranking using frontmatter only."""
        candidate_text = "\n\n".join(
            f"[{i+1}] {c.frontmatter_text}" for i, c in enumerate(candidates)
        )

        prompt = (
            f"User request: {user_message}\n\n"
            f"Context: {context}\n\n"
            f"Available skills:\n{candidate_text}\n\n"
            "Which skill best matches the user's request? "
            "Reply with ONLY the number (e.g. '1') of the best skill, "
            "or '0' if none is a good match. "
            "Then on a new line, a confidence score 0.0-1.0. "
            "Then on a new line, a brief reason."
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._parse_rerank_response(response, candidates)
        except Exception:
            return RouteResult(skill=candidates[0], confidence=0.5, reasoning="Rerank failed, using top recall result")

    def _parse_rerank_response(self, response: Any, candidates: list[SkillMeta]) -> RouteResult:
        text = response.content[0].text.strip()
        lines = text.split("\n")

        try:
            choice = int(lines[0].strip())
        except (ValueError, IndexError):
            return RouteResult(skill=candidates[0], confidence=0.5, reasoning="Parse error")

        if choice == 0 or choice > len(candidates):
            return RouteResult(skill=None, confidence=0.0, reasoning=lines[-1] if lines else "No match")

        confidence = 0.7
        if len(lines) > 1:
            try:
                confidence = float(lines[1].strip())
            except ValueError:
                pass

        reasoning = lines[2] if len(lines) > 2 else "LLM reranked"
        return RouteResult(skill=candidates[choice - 1], confidence=confidence, reasoning=reasoning)
