from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from toolbench_synthgen.executor import OfflineExecutor, ValidationError
from toolbench_synthgen.memory import MemoryStoreProtocol, add_session_tool_output
from toolbench_synthgen.models import ConversationRecord, Message, ToolCall, ToolOutput
from toolbench_synthgen.agents.planner import ConversationPlan, PlanStep


@dataclass
class AssistantConfig:
    conversation_id: str


class AssistantAgent:
    """Assistant that decides between clarifications and tool calls.

    Handles different plan step kinds:
    - clarification: Ask user for more information
    - tool_call: Execute a single tool
    - parallel_tool_calls: Execute multiple tools in parallel
    """

    def __init__(
        self,
        executor: OfflineExecutor,
        memory_store: MemoryStoreProtocol,
        config: AssistantConfig,
    ) -> None:
        self.executor = executor
        self.memory_store = memory_store
        self.config = config

    def _execute_single_tool(
        self,
        endpoint_id: str,
        step_index: int,
        session_state: Dict[str, Any],
    ) -> Tuple[ToolCall, ToolOutput, Dict[str, Any], bool]:
        """Execute a single tool call and return results."""
        args: Dict[str, Any] = {"lang": "en"}

        # For non-first tool calls, consult session memory
        grounded_from_memory = False
        if step_index > 0:
            results = self.memory_store.search(
                query=endpoint_id,
                scope="session",
                top_k=1,
            )
            if results:
                grounded_from_memory = True
                args["from_memory"] = True

        call, output, new_state = self.executor.execute(
            endpoint_id=endpoint_id,
            arguments=args,
            session_state=session_state,
            step_index=step_index,
        )

        # Write to session memory
        add_session_tool_output(
            self.memory_store,
            conversation_id=self.config.conversation_id,
            step=step_index,
            endpoint=endpoint_id,
            tool_output_json=output.model_dump_json(),
        )

        return call, output, new_state, grounded_from_memory

    def handle_step(
        self,
        plan_step: PlanStep,
        conversation: ConversationRecord,
        session_state: Dict[str, Any],
    ) -> Tuple[List[Message], List[ToolCall], List[ToolOutput], Dict[str, Any]]:
        messages: List[Message] = []
        tool_calls: List[ToolCall] = []
        tool_outputs: List[ToolOutput] = []

        step_index = len(conversation.tool_calls)

        # Handle clarification steps
        if plan_step.kind == "clarification":
            if plan_step.parallel_endpoints:
                # Clarification for parallel tools
                endpoints_str = ", ".join(plan_step.parallel_endpoints)
                content = (
                    f"To proceed with these tools in parallel ({endpoints_str}), "
                    "could you specify the language (e.g., 'en')?"
                )
            else:
                content = f"To proceed with {plan_step.endpoint_id}, could you specify the language (e.g., 'en')?"
            messages.append(Message(role="assistant", content=content))
            return messages, tool_calls, tool_outputs, session_state

        # Handle parallel tool calls
        if plan_step.kind == "parallel_tool_calls":
            result_ids = []
            current_state = session_state

            for i, endpoint_id in enumerate(plan_step.parallel_endpoints):
                current_step_index = step_index + i
                try:
                    call, output, current_state, _ = self._execute_single_tool(
                        endpoint_id=endpoint_id,
                        step_index=current_step_index,
                        session_state=current_state,
                    )
                    tool_calls.append(call)
                    tool_outputs.append(output)
                    result_ids.append(f"{endpoint_id}={output.derived_ids.get('result_id')}")
                except ValidationError as e:
                    # Log error but continue with other parallel calls
                    result_ids.append(f"{endpoint_id}=ERROR")

            # Summarize all parallel results
            messages.append(
                Message(
                    role="assistant",
                    content=f"Executed {len(plan_step.parallel_endpoints)} tools in parallel: {', '.join(result_ids)}.",
                    tool_call_id=tool_calls[-1].id if tool_calls else None,
                )
            )
            return messages, tool_calls, tool_outputs, current_state

        # Handle single tool_call steps
        endpoint_id = plan_step.endpoint_id or ""

        try:
            call, output, new_state, _ = self._execute_single_tool(
                endpoint_id=endpoint_id,
                step_index=step_index,
                session_state=session_state,
            )
        except ValidationError as e:
            content = (
                f"I need more information for {endpoint_id}: {e.errors}. "
                "Could you provide the missing details?"
            )
            messages.append(Message(role="assistant", content=content))
            return messages, tool_calls, tool_outputs, session_state

        tool_calls.append(call)
        tool_outputs.append(output)

        messages.append(
            Message(
                role="assistant",
                content=f"Called {endpoint_id} and obtained result_id={output.derived_ids.get('result_id')}.",
                tool_call_id=call.id,
            )
        )

        return messages, tool_calls, tool_outputs, new_state

