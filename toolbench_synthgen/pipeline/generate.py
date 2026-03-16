from __future__ import annotations

import json
from pathlib import Path
from typing import List

from toolbench_synthgen.agents import (
    ConversationGeneratorCore,
    ConversationGeneratorConfig,
)
from toolbench_synthgen.executor import OfflineExecutor
from toolbench_synthgen.graph import ToolGraph
from toolbench_synthgen.graph.tool_graph import Edge, Node, NodeType
from toolbench_synthgen.memory import InMemoryStore, MemoryStore, add_corpus_summary
from toolbench_synthgen.models import ConversationRecord
from toolbench_synthgen.registry import ToolRegistry


def compute_memory_grounding_rate(convo: ConversationRecord) -> float | None:
    """Compute memory_grounding_rate based on ToolCall arguments."""
    non_first_calls = [c for c in convo.tool_calls if c.step_index > 0]
    if not non_first_calls:
        return None
    grounded = [c for c in non_first_calls if c.arguments.get("from_memory")]
    return len(grounded) / len(non_first_calls)


def generate_dataset(
    registry_path: str,
    graph_path: str,
    output_path: str,
    num_conversations: int,
    seed: int,
    corpus_memory_enabled: bool,
) -> List[ConversationRecord]:
    """Generate a dataset of ConversationRecords and write them as JSONL."""
    registry = ToolRegistry.load(registry_path)

    with Path(graph_path).open("r", encoding="utf-8") as f:
        graph_data = json.load(f)
    nodes = [
        Node(
            id=n["id"],
            type=NodeType(n["type"]) if isinstance(n["type"], str) else n["type"],
            label=n["label"],
            metadata=n.get("metadata", {}),
        )
        for n in graph_data["nodes"]
    ]
    edges = [Edge(source=e["source"], target=e["target"], type=e["type"]) for e in graph_data["edges"]]
    graph = ToolGraph(nodes=nodes, edges=edges)

    memory_store = InMemoryStore() if not corpus_memory_enabled else MemoryStore()
    executor = OfflineExecutor(registry=registry, seed=seed)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    conversations: List[ConversationRecord] = []

    with output_file.open("w", encoding="utf-8") as f:
        for i in range(num_conversations):
            conversation_id = f"conv_{i}"
            config = ConversationGeneratorConfig(
                conversation_id=conversation_id,
                seed=seed + i,
                corpus_memory_enabled=corpus_memory_enabled,
            )
            core = ConversationGeneratorCore(registry, graph, executor, memory_store, config)
            convo = core.generate()

            # Compute and fill memory_grounding_rate.
            mgr = compute_memory_grounding_rate(convo)
            convo.metadata.memory_grounding_rate = mgr

            # After successful generation, optionally write a corpus summary.
            if corpus_memory_enabled:
                summary_text = (
                    f"Tools: {', '.join(convo.metadata.tool_ids_used)}. "
                    f"Pattern: {convo.metadata.pattern_type}."
                )
                add_corpus_summary(
                    memory_store,
                    conversation_id=convo.conversation_id,
                    tools=convo.metadata.tool_ids_used,
                    pattern_type=convo.metadata.pattern_type or "unknown",
                    summary_text=summary_text,
                )

            f.write(convo.model_dump_json())
            f.write("\n")
            conversations.append(convo)

    return conversations

