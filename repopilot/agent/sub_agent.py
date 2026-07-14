"""Sub-agent manager: spawns, controls, and collects results from child agents.

Architecture: centralized orchestration where the main agent is the sole planner
and quality controller. Sub-agents are tool-call-dispatched workers with:
- Independent context windows
- Restricted tool sets (read-only by default)
- Path boundary restrictions
- No control transfer (results return to main agent)
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from typing import Any

import anthropic
from rich.console import Console

from repopilot.config.settings import Settings
from repopilot.tools.registry import ToolRegistry

console = Console()

AGENT_TYPE_CONFIGS: dict[str, dict[str, Any]] = {
    "explore": {
        "system_suffix": "You are an exploration agent. Search the codebase to answer questions. Report findings concisely.",
        "default_tools": ["read_file", "glob", "grep"],
        "max_iterations": 20,
    },
    "plan": {
        "system_suffix": "You are a planning agent. Analyze the codebase and design implementation strategies. Do not make changes.",
        "default_tools": ["read_file", "glob", "grep"],
        "max_iterations": 15,
    },
    "general": {
        "system_suffix": "You are a task agent. Complete the assigned task using available tools.",
        "default_tools": ["read_file", "write_file", "edit_file", "glob", "grep", "bash"],
        "max_iterations": 30,
    },
}


@dataclass
class SubAgentResult:
    agent_id: str
    description: str
    output: str
    token_usage: dict[str, int] = field(default_factory=dict)
    success: bool = True


class SubAgentManager:
    """Manages lifecycle of sub-agents: creation, execution, result collection."""

    def __init__(
        self,
        settings: Settings,
        tool_registry: ToolRegistry,
        base_system_prompt: str,
        working_dir: str = ".",
    ) -> None:
        self.settings = settings
        self.registry = tool_registry
        self.base_system_prompt = base_system_prompt
        self.working_dir = working_dir
        self.client = anthropic.Anthropic()
        self._agent_counter = 0
        self._results: list[SubAgentResult] = []

    def spawn_and_run(
        self,
        description: str,
        prompt: str,
        agent_type: str = "general",
        allowed_tools: list[str] | None = None,
    ) -> str:
        """Spawn a sub-agent and run it synchronously."""
        self._agent_counter += 1
        agent_id = f"agent-{self._agent_counter}"

        config = AGENT_TYPE_CONFIGS.get(agent_type, AGENT_TYPE_CONFIGS["general"])
        tools = self._build_tool_set(allowed_tools or config["default_tools"])
        system = f"{self.base_system_prompt}\n\n{config['system_suffix']}"
        max_iter = config["max_iterations"]

        console.print(f"[cyan]Spawning sub-agent:[/cyan] {description} ({agent_type})")

        result = self._run_agent_loop(
            agent_id=agent_id,
            system=system,
            tools=tools,
            prompt=prompt,
            max_iterations=max_iter,
        )

        self._results.append(SubAgentResult(
            agent_id=agent_id,
            description=description,
            output=result,
        ))

        return result

    def spawn_parallel(
        self, tasks: list[dict[str, Any]], max_workers: int = 3
    ) -> list[SubAgentResult]:
        """Spawn multiple sub-agents in parallel."""
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.spawn_and_run,
                    description=task["description"],
                    prompt=task["prompt"],
                    agent_type=task.get("agent_type", "general"),
                    allowed_tools=task.get("allowed_tools"),
                ): task
                for task in tasks
            }
            for future in concurrent.futures.as_completed(futures):
                task = futures[future]
                try:
                    output = future.result()
                    results.append(SubAgentResult(
                        agent_id=f"parallel-{len(results)}",
                        description=task["description"],
                        output=output,
                    ))
                except Exception as e:
                    results.append(SubAgentResult(
                        agent_id=f"parallel-{len(results)}",
                        description=task["description"],
                        output=f"Error: {e}",
                        success=False,
                    ))
        return results

    def _run_agent_loop(
        self,
        agent_id: str,
        system: str,
        tools: list[dict[str, Any]],
        prompt: str,
        max_iterations: int,
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            try:
                response = self.client.messages.create(
                    model=self.settings.model,
                    max_tokens=self.settings.max_tokens,
                    temperature=0.0,
                    system=system,
                    tools=tools,
                    messages=messages,
                )
            except Exception as e:
                return f"API error: {e}"

            assistant_content = []
            final_text = ""

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    final_text = block.text
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason == "end_turn":
                return final_text

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in assistant_content:
                    if block.get("type") == "tool_use":
                        result = self.registry.execute(block["name"], **block.get("input", {}))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": result.error if result.is_error else result.output,
                            **({"is_error": True} if result.is_error else {}),
                        })
                messages.append({"role": "user", "content": tool_results})

        return f"[{agent_id}] Max iterations reached"

    def _build_tool_set(self, allowed_names: list[str]) -> list[dict[str, Any]]:
        tools = []
        for name in allowed_names:
            tool = self.registry.get(name)
            if tool:
                tools.append(tool.to_api_format())
        return tools

    def get_results(self) -> list[SubAgentResult]:
        return list(self._results)
