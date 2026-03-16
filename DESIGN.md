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

## Current Implementation (Stories 1–3)

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

### Offline Execution Model

- **Data models**
  - `Message`:
    - `role`, `content`, optional `tool_call_id`.
  - `ToolCall`:
    - `id`, `endpoint_id`, `arguments`, `step_index`.
  - `ToolOutput`:
    - `id`, `tool_call_id`, structured `payload`, and any `derived_ids` (e.g., generated object IDs).
  - `ConversationMetadata`:
    - `seed`, `tool_ids_used`, `num_turns`, `num_clarification_questions`, `memory_grounding_rate`, `corpus_memory_enabled`, `pattern_type`, plus an extensible `extra` dict.
  - `ConversationRecord`:
    - `conversation_id`, `messages`, `tool_calls`, `tool_outputs`, `metadata`.
  - All of the above are Pydantic models defined in `toolbench_synthgen/models.py` and serialize cleanly to/from JSON for the eventual JSONL dataset.

- **Argument validation**
  - `OfflineExecutor.validate_args(endpoint_id, arguments)`:
    - Looks up the endpoint in `ToolRegistry`.
    - Ensures all required parameters defined on the endpoint are present in `arguments`.
    - Collects missing-parameter errors in a structured `errors` dict.
    - Raises a `ValidationError` with `endpoint_id` and `errors` when validation fails.

- **Deterministic mock responses**
  - `OfflineExecutor.execute(endpoint_id, arguments, session_state, step_index)`:
    - Runs `validate_args`; on validation failure:
      - Returns a `ToolCall` and `ToolOutput` whose payload includes an `"error"` field containing the validation error details, without mutating `session_state`.
    - On success:
      - Uses a seeded RNG derived from the global `seed`, `endpoint_id`, and `arguments` to generate deterministic mock outputs.
      - Produces a `ToolCall` and `ToolOutput` with a synthetic `result_id` and an `echo` of the input arguments.
      - Same seed + same endpoint + same arguments → same `result_id` and payload, regardless of `step_index`.

- **Session state and chaining**
  - `session_state` is a simple dictionary maintained by the executor:
    - `"objects"`: maps generated IDs (e.g., `result_id`) to their payloads.
    - `"last_result"`: holds the most recent payload.
  - After successful execution, the executor:
    - Stores the payload under its `result_id` key in `session_state["objects"]`.
    - Updates `session_state["last_result"]`.
  - This enables later tool calls to reference earlier outputs by ID or via the last-result cache, without coupling the executor to any particular agent implementation.

Future stories will build on this foundation:

## Agentic Memory

- **MemoryStore abstraction**
  - Implemented in `toolbench_synthgen/memory/store.py` and exposed via `toolbench_synthgen.memory`.
  - Exact interface:
    - `add(self, content: str, scope: str, metadata: dict) -> None`
    - `search(self, query: str, scope: str, top_k: int = 5) -> list[dict]`
  - Internally wraps `mem0.Memory`, passing `scope` as the `namespace` so that:
    - `scope="session"` and `scope="corpus"` are stored in separate namespaces.
    - Searching one scope never returns entries from the other (scope isolation).

- **Session memory (`scope="session"`)**
  - Typical entries:
    - `content`: JSON-serialized `ToolOutput` from Story 3.
    - `metadata`: at least `{"conversation_id": ..., "step": ..., "endpoint": ...}`.
  - Write path:
    - After **every tool call completes**, the generator will serialize the tool output and call:
      - `MemoryStore.add(content=tool_output_json, scope="session", metadata={...})`.
    - Helper: `add_session_tool_output` encapsulates this convention.
  - Read path:
    - Before constructing arguments for any non-first tool call, the Assistant will:
      - Call `MemoryStore.search(query, scope="session")` (e.g., using endpoint or conversation context).
      - Inject any retrieved entries into the argument-filling prompt/context.

- **Corpus memory (`scope="corpus"`)**
  - Typical entries:
    - `content`: a compact summary string, e.g.  
      `"Tools: weather_api, maps_api. Domain: travel. Pattern: sequential multi-step."`
    - `metadata`: at least `{"conversation_id": ..., "tools": [...], "pattern_type": ...}`.
  - Write path:
    - After a conversation is fully generated and validated, the generator will:
      - Build a summary string and call `MemoryStore.add(..., scope="corpus", metadata={...})` (or use `add_corpus_summary`).
  - Read path:
    - Before the Planner generates a new conversation plan, it will:
      - Call `MemoryStore.search(query, scope="corpus")` to retrieve prior summaries.
      - Use these to diversify or specialise new tool chains and conversation patterns.

- **Metrics and determinism**
  - For the `memory_grounding_rate` metric and related analyses, a retrieval is considered **present** whenever `search()` for a given scope returns **at least one** result, regardless of internal similarity scores from mem0.
  - Since mem0 search is approximate, determinism at the pipeline level focuses on:
    - Using consistent scopes (`"session"`/`"corpus"`) and queries.
    - Treating non-empty vs empty search results as the key signal, rather than relying on exact ordering or scores.

Future stories will integrate this memory layer with the multi-agent generator and metrics:

- Use session memory for grounding tool arguments within a conversation.
- Use corpus memory for cross-conversation diversity and planning.
- Compute `memory_grounding_rate` based on whether non-first tool calls included at least one retrieved memory entry in their argument prompts.

