from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


from toolbench_synthgen.graph import ToolGraph
from toolbench_synthgen.graph.tool_graph import NodeType


class PatternType(str, Enum):
    """Types of tool-calling patterns supported by the sampler."""
    SEQUENTIAL = "sequential"  # Tools called one after another: A -> B -> C
    PARALLEL = "parallel"      # Multiple tools called independently: A, B, C (no dependencies)
    BRANCHING = "branching"    # One tool followed by parallel tools: A -> (B, C)


@dataclass
class SampledToolChain:
    endpoint_ids: List[str]
    pattern_type: str
    tools_used: List[str]
    tags: List[str]
    # For parallel/branching patterns, indicates which endpoints can run in parallel
    parallel_groups: List[List[int]] = field(default_factory=list)


class SamplerAgent:
    """Propose candidate tool chains from the Tool Graph.

    Supports multiple sampling patterns:
    - sequential: Tools called one after another (A -> B -> C)
    - parallel: Multiple tools called independently (A, B, C)
    - branching: One tool followed by parallel tools (A -> (B, C))
    """

    # Weights for random pattern selection
    PATTERN_WEIGHTS = {
        PatternType.SEQUENTIAL: 0.5,  # 50% sequential
        PatternType.PARALLEL: 0.3,    # 30% parallel
        PatternType.BRANCHING: 0.2,   # 20% branching
    }

    def __init__(self, graph: ToolGraph, seed: int = 42) -> None:
        self._graph = graph
        self._rng = random.Random(seed)

    def _select_pattern(self) -> PatternType:
        """Randomly select a pattern type based on weights."""
        patterns = list(self.PATTERN_WEIGHTS.keys())
        weights = list(self.PATTERN_WEIGHTS.values())
        return self._rng.choices(patterns, weights=weights, k=1)[0]

    def _get_endpoint_nodes(self):
        """Get all endpoint nodes from the graph."""
        return [n for n in self._graph.nodes if n.type == NodeType.ENDPOINT]

    def _collect_tags(self, tools_used: List[str]) -> List[str]:
        """Collect tags from tool nodes."""
        tags: List[str] = []
        for tool_id in tools_used:
            tool_node_id = f"tool:{tool_id}"
            for node in self._graph.nodes:
                if node.id == tool_node_id:
                    tags.extend(node.metadata.get("tags", []))
        return list(set(tags))

    def _sample_sequential(self, endpoint_nodes, min_length: int) -> SampledToolChain:
        """Sample a sequential tool chain: A -> B -> C."""
        chain_nodes = self._rng.sample(endpoint_nodes, k=min_length)
        endpoint_ids = [n.metadata["tool_id"] + "." + n.label for n in chain_nodes]
        tools_used = list({n.metadata["tool_id"] for n in chain_nodes})
        tags = self._collect_tags(tools_used)

        return SampledToolChain(
            endpoint_ids=endpoint_ids,
            pattern_type=PatternType.SEQUENTIAL.value,
            tools_used=tools_used,
            tags=tags,
            parallel_groups=[],  # No parallel execution in sequential
        )

    def _sample_parallel(self, endpoint_nodes, min_length: int) -> SampledToolChain:
        """Sample a parallel tool chain: (A, B, C) - all independent."""
        chain_nodes = self._rng.sample(endpoint_nodes, k=min_length)
        endpoint_ids = [n.metadata["tool_id"] + "." + n.label for n in chain_nodes]
        tools_used = list({n.metadata["tool_id"] for n in chain_nodes})
        tags = self._collect_tags(tools_used)

        # All endpoints are in a single parallel group
        parallel_groups = [list(range(len(endpoint_ids)))]

        return SampledToolChain(
            endpoint_ids=endpoint_ids,
            pattern_type=PatternType.PARALLEL.value,
            tools_used=tools_used,
            tags=tags,
            parallel_groups=parallel_groups,
        )

    def _sample_branching(self, endpoint_nodes, min_length: int) -> SampledToolChain:
        """Sample a branching tool chain: A -> (B, C) - one lead, rest parallel."""
        chain_nodes = self._rng.sample(endpoint_nodes, k=min_length)
        endpoint_ids = [n.metadata["tool_id"] + "." + n.label for n in chain_nodes]
        tools_used = list({n.metadata["tool_id"] for n in chain_nodes})
        tags = self._collect_tags(tools_used)

        # First endpoint is sequential, rest are parallel
        # parallel_groups: [[1, 2, ...]] means indices 1, 2, ... can run in parallel after index 0
        if len(endpoint_ids) > 1:
            parallel_groups = [list(range(1, len(endpoint_ids)))]
        else:
            parallel_groups = []

        return SampledToolChain(
            endpoint_ids=endpoint_ids,
            pattern_type=PatternType.BRANCHING.value,
            tools_used=tools_used,
            tags=tags,
            parallel_groups=parallel_groups,
        )

    def sample_chain(
        self,
        min_length: int = 3,
        seed: Optional[int] = None,
        pattern: Optional[PatternType] = None,
    ) -> SampledToolChain:
        """Sample a tool chain from the graph.

        Args:
            min_length: Minimum number of endpoints in the chain.
            seed: Optional seed to reset RNG for deterministic sampling.
            pattern: Optional specific pattern to use. If None, randomly selected.

        Returns:
            SampledToolChain with endpoints and pattern metadata.
        """
        if seed is not None:
            self._rng = random.Random(seed)

        endpoint_nodes = self._get_endpoint_nodes()
        if len(endpoint_nodes) < min_length:
            raise ValueError("Not enough endpoints in graph to sample a chain.")

        # Select pattern (random or specified)
        selected_pattern = pattern if pattern is not None else self._select_pattern()

        # Sample based on pattern type
        if selected_pattern == PatternType.SEQUENTIAL:
            return self._sample_sequential(endpoint_nodes, min_length)
        elif selected_pattern == PatternType.PARALLEL:
            return self._sample_parallel(endpoint_nodes, min_length)
        elif selected_pattern == PatternType.BRANCHING:
            return self._sample_branching(endpoint_nodes, min_length)
        else:
            # Fallback to sequential
            return self._sample_sequential(endpoint_nodes, min_length)