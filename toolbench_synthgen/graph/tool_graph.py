from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List

from toolbench_synthgen.registry.models import Endpoint, Tool
from toolbench_synthgen.registry.registry import ToolRegistry


class NodeType(str, Enum):
    TOOL = "tool"
    ENDPOINT = "endpoint"
    PARAMETER = "parameter"
    RESPONSE_FIELD = "response_field"
    CONCEPT = "concept"


@dataclass
class Node:
    id: str
    type: NodeType
    label: str
    metadata: Dict


@dataclass
class Edge:
    source: str
    target: str
    type: str


@dataclass
class ToolGraph:
    nodes: List[Node]
    edges: List[Edge]

    def to_json_dict(self) -> Dict:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }

    def save(self, path: str) -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(self.to_json_dict(), f, indent=2)


def build_tool_graph(registry: ToolRegistry) -> ToolGraph:
    """Construct a ToolGraph from a ToolRegistry."""
    nodes: List[Node] = []
    edges: List[Edge] = []

    # Concept/tag nodes (one per unique tag)
    concept_nodes: Dict[str, Node] = {}

    def add_node(node: Node) -> None:
        nodes.append(node)

    def add_edge(source: str, target: str, edge_type: str) -> None:
        edges.append(Edge(source=source, target=target, type=edge_type))

    for tool in registry.tools:
        tool_node = Node(
            id=f"tool:{tool.id}",
            type=NodeType.TOOL,
            label=tool.name,
            metadata={"tags": tool.tags},
        )
        add_node(tool_node)

        # Concept/tag associations
        for tag in tool.tags:
            concept_id = f"concept:{tag}"
            if concept_id not in concept_nodes:
                concept_node = Node(
                    id=concept_id,
                    type=NodeType.CONCEPT,
                    label=tag,
                    metadata={},
                )
                concept_nodes[concept_id] = concept_node
                add_node(concept_node)
            add_edge(concept_id, tool_node.id, "concept_to_tool")
            add_edge(tool_node.id, concept_id, "tool_to_concept")

        for endpoint in tool.endpoints:
            _add_endpoint_subgraph(tool_node, endpoint, add_node, add_edge)

    return ToolGraph(nodes=nodes, edges=edges)


def _add_endpoint_subgraph(
    tool_node: Node,
    endpoint: Endpoint,
    add_node,
    add_edge,
) -> None:
    ep_node_id = f"endpoint:{endpoint.id}"
    ep_node = Node(
        id=ep_node_id,
        type=NodeType.ENDPOINT,
        label=endpoint.name,
        metadata={"tool_id": endpoint.tool_id},
    )
    add_node(ep_node)
    add_edge(tool_node.id, ep_node_id, "tool_to_endpoint")

    for param in endpoint.parameters:
        param_node_id = f"parameter:{endpoint.id}:{param.name}"
        param_node = Node(
            id=param_node_id,
            type=NodeType.PARAMETER,
            label=param.name,
            metadata={
                "endpoint_id": endpoint.id,
                "required": param.required,
                "type": param.type,
            },
        )
        add_node(param_node)
        add_edge(ep_node_id, param_node_id, "endpoint_to_parameter")

    for resp in endpoint.response_fields:
        resp_node_id = f"response_field:{endpoint.id}:{resp.name}"
        resp_node = Node(
            id=resp_node_id,
            type=NodeType.RESPONSE_FIELD,
            label=resp.name,
            metadata={"endpoint_id": endpoint.id, "type": resp.type},
        )
        add_node(resp_node)
        add_edge(ep_node_id, resp_node_id, "endpoint_to_response_field")

