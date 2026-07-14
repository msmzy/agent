"""Self-evolving memory engine: reflect → extract → classify → store → update index.

Implements the closed-loop: execution → reflection → extraction → categorized storage
→ index update → on-demand reuse.
"""

from __future__ import annotations

from typing import Any

import anthropic

from repopilot.memory.store import MemoryStore
from repopilot.memory.types import MemoryRecord, MemoryType

REFLECTION_PROMPT = """\
Analyze the following conversation and extract reusable knowledge.
For each piece of knowledge, classify it into one of these types:
- user: Information about the user's role, preferences, expertise
- feedback: Guidance on how to approach work (corrections or confirmed approaches)
- project: Ongoing work, goals, decisions within the project
- reference: Pointers to external resources
- procedural: Reusable step-by-step procedures learned from execution

For each memory, provide:
1. name: A short descriptive name
2. type: One of the types above
3. description: One-line description for indexing
4. content: The actual knowledge to remember

Rules:
- Do NOT save code patterns, file paths, or project structure (derivable from code)
- Do NOT save git history or debugging solutions (in code/commits)
- Do NOT save ephemeral task details
- DO save surprising insights, user preferences, non-obvious decisions
- DO save procedural knowledge that would speed up similar future tasks

Respond in JSON format:
{
  "memories": [
    {
      "name": "...",
      "type": "...",
      "description": "...",
      "content": "..."
    }
  ]
}

If nothing worth remembering, respond: {"memories": []}
"""


class MemoryEvolution:
    """Extracts and persists reusable knowledge from conversations."""

    def __init__(
        self,
        store: MemoryStore,
        model: str = "claude-haiku-4-5",
    ) -> None:
        self.store = store
        self.model = model
        self.client = anthropic.Anthropic()

    def reflect_and_extract(self, conversation_text: str) -> list[MemoryRecord]:
        """Analyze a conversation and extract memories."""
        if len(conversation_text) < 200:
            return []

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.0,
                system=REFLECTION_PROMPT,
                messages=[{"role": "user", "content": conversation_text}],
            )
        except Exception:
            return []

        return self._parse_and_store(response)

    def _parse_and_store(self, response: Any) -> list[MemoryRecord]:
        import json

        text = response.content[0].text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []

        memories = data.get("memories", [])
        saved = []

        for mem in memories:
            try:
                memory_type = MemoryType(mem["type"])
            except (KeyError, ValueError):
                continue

            record = MemoryRecord(
                name=mem.get("name", "unnamed"),
                description=mem.get("description", ""),
                type=memory_type,
                content=mem.get("content", ""),
            )

            existing = self.store.get_by_name(record.name)
            if existing:
                record.content = self._merge_content(existing.content, record.content)

            self.store.save(record)
            saved.append(record)

        return saved

    def _merge_content(self, existing: str, new: str) -> str:
        """Merge new content into existing memory, avoiding duplication."""
        if new in existing:
            return existing
        return f"{existing}\n\n---\n\n{new}"

    def should_reflect(self, turn_count: int, has_tool_calls: bool) -> bool:
        """Determine if reflection should be triggered."""
        if turn_count >= 10:
            return True
        if turn_count >= 5 and has_tool_calls:
            return True
        return False

    def prune_stale(self, max_age_days: int = 90, min_access: int = 0) -> list[str]:
        """Remove memories that haven't been accessed and are old."""
        from datetime import datetime, timedelta

        cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
        pruned = []

        for record in self.store.list_all():
            if record.access_count <= min_access and record.updated_at < cutoff:
                self.store.delete(record.name)
                pruned.append(record.name)

        return pruned
