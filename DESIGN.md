# DESIGN (Scaffolding Stage)

This document outlines the planned architecture for the ToolBench-based offline synthetic conversation generator. At this stage, only project scaffolding and the CLI skeleton are implemented. All core functionality (registry, graph, executor, agents, memory, pipelines, metrics) will be added in subsequent stories and this document will be updated accordingly.

## Planned Architecture Overview

- Python package `toolbench_synthgen` with subpackages:
  - `registry` – Tool registry and loaders for ToolBench definitions.
  - `graph` – Tool graph representation and samplers.
  - `executor` – Offline tool execution model.
  - `agents` – Sampler, Planner, UserProxy, Assistant, and Validator agents.
  - `memory` – `MemoryStore` abstraction backed by `mem0` with `session` and `corpus` scopes.
  - `pipeline` – Orchestration for build / generate / validate / metrics commands.

## Current Implementation (Stories 1–2)

- Project is packaged via `pyproject.toml` with an installable `toolbench-synthgen` distribution.
- Dependencies and development tools are listed in `requirements.txt`.
- Package layout and subpackages (`registry`, `graph`, `executor`, `agents`, `memory`, `pipeline`) are created.
- CLI in `toolbench_synthgen/cli.py` exposes four commands:
  - `build` – now implemented to load ToolBench definitions, construct a Tool Registry and Tool Graph, and write artifacts.
  - `generate`
  - `validate`
  - `metrics`

### Tool Registry Design

- **Data model**
  - `Tool`:
    - `id`, `name`, `description`, `metadata`, `tags`, and `endpoints`.
  - `Endpoint`:
    - `id`, `tool_id`, `name`, `description`, `parameters`, `response_fields`, `metadata`.
  - `Parameter`:
    - `name`, `type`, `required`, `description`, `enum`, `default`.
  - `ResponseField`:
    - `name`, `type`, `description`.
- **Loader**
  - `load_toolbench_tools(root: str)` recursively scans a directory for `*.json` files and parses them as ToolBench-style `toolenv` specs (as used in [`OpenBMB/ToolBench`](https://github.com/OpenBMB/ToolBench)).
  - It is tolerant of missing or inconsistent fields:
    - Falls back to sensible defaults when fields like `tool_description`, `standardized_name`, or parameter metadata are absent.
    - Skips invalid JSON files instead of failing the entire build.
- **Registry API**
  - `ToolRegistry` wraps `ToolRegistryData` and exposes:
    - `list_tools()`, `list_endpoints()`
    - `get_tool(tool_id)`, `get_endpoint(endpoint_id)`
    - `get_parameters(endpoint_id)`
  - `ToolRegistry.save(path)` / `ToolRegistry.load(path)` serialize and reload the normalized registry as JSON.

### Tool Graph Design

- **Nodes**
  - `tool` nodes: one per `Tool` (`id="tool:{tool_id}"`), carrying tags as metadata.
  - `endpoint` nodes: one per `Endpoint` (`id="endpoint:{endpoint_id}"`).
  - `parameter` nodes: one per parameter on each endpoint (`id="parameter:{endpoint_id}:{param_name}"`).
  - `response_field` nodes: one per response field (currently empty for most ToolBench specs).
  - `concept` nodes: one per distinct tag/domain (`id="concept:{tag}"`).
- **Edges**
  - `tool_to_endpoint`: `Tool → Endpoint`.
  - `endpoint_to_parameter`: `Endpoint → Parameter`.
  - `endpoint_to_response_field`: `Endpoint → ResponseField`.
  - `concept_to_tool` and `tool_to_concept`: connect Concept/Tag nodes with Tools.
- **Construction and storage**
  - `build_tool_graph(registry: ToolRegistry)` traverses the registry and constructs a `ToolGraph` (nodes + edges).
  - `ToolGraph.save(path)` writes a JSON representation containing node and edge lists.
  - The graph is deterministic for a given registry: running `build` with the same ToolBench input and config re-produces the same artifacts (modulo file timestamps).

Future stories will fill in the remaining sections of this document:

- Architecture & major modules
- Tool registry & graph design
- Multi-agent system design
- Agentic memory implementation and `memory_grounding_rate`
- Offline executor design and chain consistency
- Validation, metrics, and diversity analysis

At this point, only scaffolding & CLI are implemented; no tool ingestion, generation, or evaluation logic exists yet.

