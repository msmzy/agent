"""Permission rules with deny-first semantics and tool risk classification."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    WRITE = "write"
    DANGEROUS = "dangerous"


TOOL_RISK_MAP: dict[str, RiskLevel] = {
    "read_file": RiskLevel.READ_ONLY,
    "glob": RiskLevel.READ_ONLY,
    "grep": RiskLevel.READ_ONLY,
    "write_file": RiskLevel.WRITE,
    "edit_file": RiskLevel.WRITE,
    "bash": RiskLevel.DANGEROUS,
    "agent": RiskLevel.WRITE,
    "skill": RiskLevel.READ_ONLY,
}

DANGEROUS_BASH_PATTERNS: list[str] = [
    r"\brm\s+-rf\b",
    r"\brm\s+-r\b",
    r"\bsudo\b",
    r"\bchmod\s+777\b",
    r"\bcurl\b.*\|\s*bash",
    r"\bwget\b.*\|\s*bash",
    r"\bgit\s+push\s+--force\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\b:(){ :\|:& };:\b",
    r"\b>\s*/dev/sd",
    r"\bkill\s+-9\b",
    r"\bpkill\b",
    r"\bdropdb\b",
    r"\bDROP\s+DATABASE\b",
    r"\bDROP\s+TABLE\b",
    r"\bTRUNCATE\b",
]


@dataclass
class Rule:
    tool: str
    pattern: str = "*"
    action: str = "allow"

    def matches(self, tool_name: str, tool_input: dict[str, Any]) -> bool:
        if not fnmatch.fnmatch(tool_name, self.tool):
            return False
        if self.pattern == "*":
            return True
        input_str = str(tool_input)
        return fnmatch.fnmatch(input_str, self.pattern)


@dataclass
class RuleEngine:
    """Deny-first rule engine: deny rules always win over allow rules."""

    allow_rules: list[Rule] = field(default_factory=list)
    deny_rules: list[Rule] = field(default_factory=list)

    def evaluate(self, tool_name: str, tool_input: dict[str, Any]) -> tuple[bool, str]:
        """Returns (allowed, reason)."""
        for rule in self.deny_rules:
            if rule.matches(tool_name, tool_input):
                return False, f"Denied by rule: {rule.tool}/{rule.pattern}"

        risk = TOOL_RISK_MAP.get(tool_name, RiskLevel.DANGEROUS)

        if risk == RiskLevel.READ_ONLY:
            return True, "Read-only tool, auto-allowed"

        for rule in self.allow_rules:
            if rule.matches(tool_name, tool_input):
                return True, f"Allowed by rule: {rule.tool}/{rule.pattern}"

        if risk == RiskLevel.DANGEROUS:
            return False, f"Dangerous tool '{tool_name}' requires explicit approval"

        if risk == RiskLevel.WRITE:
            return False, f"Write tool '{tool_name}' requires approval"

        return False, "No matching allow rule"

    def check_bash_command(self, command: str) -> tuple[bool, str]:
        """Check a bash command against dangerous patterns."""
        for pattern in DANGEROUS_BASH_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Dangerous command pattern detected: {pattern}"
        return True, "Command appears safe"

    @classmethod
    def from_settings(cls, settings: Any) -> RuleEngine:
        allow_rules = [
            Rule(tool=r.tool, pattern=r.pattern, action="allow")
            for r in settings.permissions
            if r.action == "allow"
        ]
        deny_rules = [
            Rule(tool=r.tool, pattern=r.pattern, action="deny")
            for r in settings.deny_rules
        ]
        return cls(allow_rules=allow_rules, deny_rules=deny_rules)
