from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set

from toolbench_synthgen.models import ConversationRecord


@dataclass
class ValidationResult:
    valid: bool
    reasons: List[str]


class ConversationValidatorAgent:
    """Validate structural and basic semantic properties of a ConversationRecord."""

    def validate(self, convo: ConversationRecord) -> ValidationResult:
        reasons: List[str] = []

        # Multi-step: at least 3 tool calls.
        if len(convo.tool_calls) < 3:
            reasons.append("Conversation must contain at least 3 tool calls.")

        # Multi-tool: at least 2 distinct tools when possible.
        tool_ids: Set[str] = set()
        for call in convo.tool_calls:
            tool_id = call.endpoint_id.split(".")[0]
            tool_ids.add(tool_id)
        if len(tool_ids) < 2:
            reasons.append("Conversation should use at least 2 distinct tools when available.")

        # Message-role sanity: only allowed roles.
        allowed_roles = {"user", "assistant", "tool"}
        for msg in convo.messages:
            if msg.role not in allowed_roles:
                reasons.append(f"Invalid role in messages: {msg.role}")
                break

        # Basic memory-grounding behavior: for non-first tool calls, expect arguments
        # to indicate when they were grounded from memory (as set by AssistantAgent).
        for call in convo.tool_calls:
            if call.step_index > 0:
                if not call.arguments.get("from_memory"):
                    reasons.append(
                        f"Tool call at step_index={call.step_index} is not marked as grounded from session memory."
                    )
                    break

        valid = not reasons
        return ValidationResult(valid=valid, reasons=reasons)

