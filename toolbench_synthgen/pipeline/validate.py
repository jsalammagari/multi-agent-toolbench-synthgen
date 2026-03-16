from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

from toolbench_synthgen.models import ConversationRecord
from toolbench_synthgen.pipeline.generate import compute_memory_grounding_rate


@dataclass
class ValidationSummary:
    total_conversations: int = 0
    schema_errors: int = 0
    linkage_errors: int = 0
    multi_step_violations: int = 0
    multi_tool_violations: int = 0
    memory_grounding_mismatches: int = 0
    clarification_violations: int = 0
    details: List[str] = field(default_factory=list)

    @property
    def eligible(self) -> int:
        """Conversations that passed schema (were fully parsed)."""
        return self.total_conversations - self.schema_errors

    @property
    def schema_passed(self) -> int:
        return self.total_conversations - self.schema_errors

    @property
    def linkage_passed(self) -> int:
        return self.eligible - self.linkage_errors

    @property
    def multi_step_passed(self) -> int:
        return self.eligible - self.multi_step_violations

    @property
    def multi_tool_passed(self) -> int:
        return self.eligible - self.multi_tool_violations

    @property
    def memory_grounding_passed(self) -> int:
        return self.eligible - self.memory_grounding_mismatches

    @property
    def clarification_passed(self) -> int:
        return self.eligible - self.clarification_violations

    def has_serious_failures(self) -> bool:
        """True if schema or linkage errors exist (exit non-zero)."""
        return bool(self.schema_errors or self.linkage_errors)


class DatasetValidator:
    """Validate dataset-level invariants for generated conversations."""

    def validate_dataset(self, path: str, *, strict: bool = False) -> ValidationSummary:
        """Validate all conversations in the JSONL at path.

        strict: If True, return on first conversation that fails any check (aggregate otherwise).
        """
        summary = ValidationSummary()
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Dataset '{path}' does not exist.")

        with p.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                summary.total_conversations += 1
                try:
                    convo = ConversationRecord.model_validate_json(line)
                except Exception as e:
                    summary.schema_errors += 1
                    summary.details.append(f"Line {line_no}: schema error: {e}")
                    if strict:
                        return summary
                    continue

                # Linkage: every ToolOutput.tool_call_id must match a ToolCall.id.
                call_ids: Set[str] = {c.id for c in convo.tool_calls}
                linkage_failed = False
                for out in convo.tool_outputs:
                    if out.tool_call_id not in call_ids:
                        summary.linkage_errors += 1
                        summary.details.append(
                            f"{convo.conversation_id}: output {out.id} references missing call {out.tool_call_id}"
                        )
                        linkage_failed = True
                        break
                if strict and linkage_failed:
                    return summary

                # Multi-step requirement.
                if len(convo.tool_calls) < 3:
                    summary.multi_step_violations += 1
                    if strict:
                        summary.details.append(
                            f"{convo.conversation_id}: fewer than 3 tool calls ({len(convo.tool_calls)})"
                        )
                        return summary

                # Multi-tool coverage.
                tool_ids = {c.endpoint_id.split(".")[0] for c in convo.tool_calls}
                if len(tool_ids) < 2:
                    summary.multi_tool_violations += 1
                    if strict:
                        summary.details.append(
                            f"{convo.conversation_id}: fewer than 2 distinct tools ({len(tool_ids)})"
                        )
                        return summary

                # Clarification: when metadata says clarification questions were asked,
                # require at least that many assistant messages without a tool_call_id (text-only).
                num_clarifications = convo.metadata.num_clarification_questions or 0
                if num_clarifications > 0:
                    assistant_text_only = sum(
                        1 for m in convo.messages if m.role == "assistant" and m.tool_call_id is None
                    )
                    if assistant_text_only < num_clarifications:
                        summary.clarification_violations += 1
                        summary.details.append(
                            f"{convo.conversation_id}: expected >= {num_clarifications} assistant "
                            f"clarification message(s), found {assistant_text_only}"
                        )
                        if strict:
                            return summary

                # memory_grounding_rate recomputation.
                recomputed = compute_memory_grounding_rate(convo)
                stored = convo.metadata.memory_grounding_rate
                if recomputed is None and stored is not None:
                    summary.memory_grounding_mismatches += 1
                    summary.details.append(
                        f"{convo.conversation_id}: expected memory_grounding_rate=None, found {stored}"
                    )
                    if strict:
                        return summary
                elif recomputed is not None and stored is None:
                    summary.memory_grounding_mismatches += 1
                    summary.details.append(
                        f"{convo.conversation_id}: expected memory_grounding_rate={recomputed}, found null"
                    )
                    if strict:
                        return summary
                elif recomputed is not None and stored is not None:
                    if abs(recomputed - stored) > 1e-6:
                        summary.memory_grounding_mismatches += 1
                        summary.details.append(
                            f"{convo.conversation_id}: memory_grounding_rate mismatch (stored={stored}, recomputed={recomputed})"
                        )
                        if strict:
                            return summary

        return summary

