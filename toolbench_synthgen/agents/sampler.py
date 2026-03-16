from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple

from toolbench_synthgen.graph import ToolGraph
from toolbench_synthgen.graph.tool_graph import NodeType


@dataclass
class SampledToolChain:
    endpoint_ids: List[str]
    pattern_type: str
    tools_used: List[str]
    tags: List[str]


class SamplerAgent:
    """Propose candidate tool chains from the Tool Graph."""

    def __init__(self, graph: ToolGraph, seed: int = 42) -> None:
        self._graph = graph
        self._rng = random.Random(seed)

    def sample_chain(self, min_length: int = 3) -> SampledToolChain:
        endpoint_nodes = [
            n for n in self._graph.nodes if n.type == NodeType.ENDPOINT
        ]
        if len(endpoint_nodes) < min_length:
            raise ValueError("Not enough endpoints in graph to sample a chain.")

        # Sample without replacement for basic diversity.
        chain_nodes = self._rng.sample(endpoint_nodes, k=min_length)
        endpoint_ids = [n.metadata["tool_id"] + "." + n.label for n in chain_nodes]

        tools_used = list({n.metadata["tool_id"] for n in chain_nodes})
        pattern_type = "sequential"

        # Collect any tag metadata from associated tool nodes when available.
        tags: List[str] = []
        for tool_id in tools_used:
            tool_node_id = f"tool:{tool_id}"
            for node in self._graph.nodes:
                if node.id == tool_node_id:
                    tags.extend(node.metadata.get("tags", []))
        tags = list({t for t in tags})

        return SampledToolChain(
            endpoint_ids=endpoint_ids,
            pattern_type=pattern_type,
            tools_used=tools_used,
            tags=tags,
        )

