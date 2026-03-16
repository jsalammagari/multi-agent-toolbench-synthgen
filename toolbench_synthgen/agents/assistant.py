from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from toolbench_synthgen.executor import OfflineExecutor, ValidationError
from toolbench_synthgen.memory import MemoryStore, add_session_tool_output
from toolbench_synthgen.models import ConversationRecord, Message, ToolCall, ToolOutput
from toolbench_synthgen.agents.planner import ConversationPlan, PlanStep


@dataclass
class AssistantConfig:
    conversation_id: str


class AssistantAgent:
    """Assistant that decides between clarifications and tool calls."""

    def __init__(
        self,
        executor: OfflineExecutor,
        memory_store: MemoryStore,
        config: AssistantConfig,
    ) -> None:
        self.executor = executor
        self.memory_store = memory_store
        self.config = config

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

        if plan_step.kind == "clarification":
            # Ask a simple clarification question about language parameter.
            content = f"To proceed with {plan_step.endpoint_id}, could you specify the language (e.g., 'en')?"
            messages.append(Message(role="assistant", content=content))
            return messages, tool_calls, tool_outputs, session_state

        # For tool_call steps, build arguments from latest user message and (optionally) session memory.
        endpoint_id = plan_step.endpoint_id or ""

        # Simple argument filling: start with lang='en'.
        args: Dict[str, Any] = {"lang": "en"}

        # For non-first tool calls, consult session memory and mark arguments as grounded
        # when any previous tool outputs are found.
        grounded_from_memory = False
        if step_index > 0:
            results = self.memory_store.search(
                query=endpoint_id,
                scope="session",
                top_k=1,
            )
            if results:
                grounded_from_memory = True
                # Record in arguments that they were informed by retrieved memory.
                args["from_memory"] = True

        try:
            call, output, new_state = self.executor.execute(
                endpoint_id=endpoint_id,
                arguments=args,
                session_state=session_state,
                step_index=step_index,
            )
        except ValidationError as e:
            # Turn validation error into a clarifying question.
            content = (
                f"I need more information for {endpoint_id}: {e.errors}. "
                "Could you provide the missing details?"
            )
            messages.append(Message(role="assistant", content=content))
            return messages, tool_calls, tool_outputs, session_state

        tool_calls.append(call)
        tool_outputs.append(output)

        # Write to session memory.
        add_session_tool_output(
            self.memory_store,
            conversation_id=self.config.conversation_id,
            step=step_index,
            endpoint=endpoint_id,
            tool_output_json=output.model_dump_json(),
        )

        # Assistant summarises the tool result back to the user.
        messages.append(
            Message(
                role="assistant",
                content=f"Called {endpoint_id} and obtained result_id={output.derived_ids.get('result_id')}.",
                tool_call_id=call.id,
            )
        )

        return messages, tool_calls, tool_outputs, new_state

