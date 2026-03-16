from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from toolbench_synthgen.agents.assistant import AssistantAgent, AssistantConfig
from toolbench_synthgen.agents.planner import PlannerAgent
from toolbench_synthgen.agents.sampler import SamplerAgent
from toolbench_synthgen.agents.user_proxy import UserProxyAgent
from toolbench_synthgen.agents.validator import ConversationValidatorAgent
from toolbench_synthgen.executor import OfflineExecutor
from toolbench_synthgen.graph import ToolGraph
from toolbench_synthgen.memory import MemoryStoreProtocol
from toolbench_synthgen.models import (
    ConversationMetadata,
    ConversationRecord,
    Message,
    ToolCall,
    ToolOutput,
)
from toolbench_synthgen.registry import ToolRegistry


@dataclass
class ConversationGeneratorConfig:
    conversation_id: str
    seed: int
    corpus_memory_enabled: bool = True


class ConversationGeneratorCore:
    """Core orchestration for generating a single conversation."""

    def __init__(
        self,
        registry: ToolRegistry,
        graph: ToolGraph,
        executor: OfflineExecutor,
        memory_store: MemoryStoreProtocol,
        config: ConversationGeneratorConfig,
    ) -> None:
        self.registry = registry
        self.graph = graph
        self.executor = executor
        self.memory_store = memory_store
        self.config = config

        self.sampler = SamplerAgent(graph=self.graph, seed=config.seed)
        self.planner = PlannerAgent(seed=config.seed)
        self.user_proxy = UserProxyAgent()
        self.validator = ConversationValidatorAgent()

    def generate(self) -> ConversationRecord:
        # Corpus context (if enabled) is provided to the planner.
        corpus_context = (
            self.memory_store.search(
                query="diversity", scope="corpus", top_k=5
            )
            if self.config.corpus_memory_enabled
            else []
        )

        chain = self.sampler.sample_chain(min_length=3)
        plan = self.planner.plan(chain, corpus_summaries=corpus_context)

        messages: List[Message] = []
        tool_calls: List[ToolCall] = []
        tool_outputs: List[ToolOutput] = []
        session_state: Dict[str, Any] = {}

        # Initial user request.
        initial_user = self.user_proxy.initial_message(plan)
        messages.append(initial_user)

        assistant = AssistantAgent(
            executor=self.executor,
            memory_store=self.memory_store,
            config=AssistantConfig(conversation_id=self.config.conversation_id),
        )

        # Iterate over plan steps, alternating user and assistant turns.
        for step in plan.steps:
            # Assistant turn.
            assistant_messages, calls, outputs, session_state = assistant.handle_step(
                step,  # plan step
                ConversationRecord(
                    conversation_id=self.config.conversation_id,
                    messages=messages,
                    tool_calls=tool_calls,
                    tool_outputs=tool_outputs,
                    metadata=ConversationMetadata(
                        seed=self.config.seed,
                        corpus_memory_enabled=self.config.corpus_memory_enabled,
                    ),
                ),
                session_state,
            )
            messages.extend(assistant_messages)
            tool_calls.extend(calls)
            tool_outputs.extend(outputs)

            # If this step was a clarification, simulate a user answer immediately.
            if step.kind == "clarification":
                user_reply = self.user_proxy.answer_clarification(step)
                messages.append(user_reply)

        metadata = ConversationMetadata(
            seed=self.config.seed,
            tool_ids_used=list({c.endpoint_id.split('.')[0] for c in tool_calls}),
            num_turns=len(messages),
            num_clarification_questions=sum(
                1 for m in messages if m.role == "assistant" and "specify" in m.content
            ),
            corpus_memory_enabled=self.config.corpus_memory_enabled,
            pattern_type=chain.pattern_type,
        )

        convo = ConversationRecord(
            conversation_id=self.config.conversation_id,
            messages=messages,
            tool_calls=tool_calls,
            tool_outputs=tool_outputs,
            metadata=metadata,
        )

        # Validate conversation structure.
        result = self.validator.validate(convo)
        if not result.valid:
            # For now, we keep the conversation but annotate reasons in metadata.extra.
            convo.metadata.extra["validation_reasons"] = result.reasons

        return convo

