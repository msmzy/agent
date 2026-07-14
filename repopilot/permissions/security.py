"""Security review: prompt injection detection and tool input scanning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SecurityResult:
    is_suspicious: bool
    severity: str = "low"
    reason: str = ""


INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    (r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions", "high",
     "Prompt injection: instruction override attempt"),
    (r"you\s+are\s+now\s+(a|an)\s+", "medium",
     "Prompt injection: role reassignment attempt"),
    (r"system\s*:\s*", "medium",
     "Prompt injection: system message injection"),
    (r"<\s*system\s*>", "high",
     "Prompt injection: system tag injection"),
    (r"act\s+as\s+(if|though)?\s*(you|a|an)\s+", "medium",
     "Prompt injection: persona hijacking"),
    (r"forget\s+(everything|all|your)\s+", "high",
     "Prompt injection: memory wipe attempt"),
    (r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", "high",
     "Prompt injection: chat template markers"),
    (r"IMPORTANT:\s*new\s+instructions", "high",
     "Prompt injection: priority override"),
    (r"tool_result|tool_use|assistant\s*:", "medium",
     "Prompt injection: API message format spoofing"),
]

PATH_TRAVERSAL_PATTERNS: list[str] = [
    r"\.\./\.\./",
    r"/etc/passwd",
    r"/etc/shadow",
    r"~/.ssh/",
    r"~/.aws/",
    r"/proc/self/",
]


class SecurityReviewer:
    """Multi-layer security review for tool inputs."""

    def __init__(self, extra_patterns: list[tuple[str, str, str]] | None = None) -> None:
        self.patterns = list(INJECTION_PATTERNS)
        if extra_patterns:
            self.patterns.extend(extra_patterns)

    def check_tool_input(self, tool_name: str, tool_input: dict[str, Any]) -> SecurityResult:
        input_text = _flatten_input(tool_input)

        injection_result = self._check_prompt_injection(input_text)
        if injection_result.is_suspicious:
            return injection_result

        if tool_name in ("read_file", "write_file", "edit_file"):
            path_result = self._check_path_traversal(tool_input.get("file_path", ""))
            if path_result.is_suspicious:
                return path_result

        if tool_name == "bash":
            return self._check_bash_security(tool_input.get("command", ""))

        return SecurityResult(is_suspicious=False)

    def _check_prompt_injection(self, text: str) -> SecurityResult:
        for pattern, severity, reason in self.patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return SecurityResult(is_suspicious=True, severity=severity, reason=reason)
        return SecurityResult(is_suspicious=False)

    def _check_path_traversal(self, path: str) -> SecurityResult:
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, path):
                return SecurityResult(
                    is_suspicious=True,
                    severity="high",
                    reason=f"Path traversal detected: {path}",
                )
        return SecurityResult(is_suspicious=False)

    def _check_bash_security(self, command: str) -> SecurityResult:
        sensitive_env_vars = ["API_KEY", "SECRET", "PASSWORD", "TOKEN", "CREDENTIALS"]
        for var in sensitive_env_vars:
            if re.search(rf"\becho\s+\${var}\b", command, re.IGNORECASE):
                return SecurityResult(
                    is_suspicious=True,
                    severity="medium",
                    reason=f"Attempting to read sensitive env var: {var}",
                )

        if "|" in command:
            parts = command.split("|")
            if any(re.search(r"\bcurl\b|\bwget\b|\bnc\b", p) for p in parts):
                return SecurityResult(
                    is_suspicious=True,
                    severity="high",
                    reason="Piping output to network command",
                )

        return SecurityResult(is_suspicious=False)

    def check_tool_output(self, tool_name: str, output: str) -> SecurityResult:
        return self._check_prompt_injection(output)


def _flatten_input(tool_input: dict[str, Any]) -> str:
    parts = []
    for v in tool_input.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, dict)):
            parts.append(str(v))
    return " ".join(parts)
