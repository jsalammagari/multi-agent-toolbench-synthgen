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

## Current Implementation (Stories 1–6)

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

## Multi-Agent System

### SamplerAgent

- **Responsibility**: Propose candidate tool chains from the Tool Graph.
- **Inputs**: `ToolGraph`, random seed.
- **Behavior**:
  - Selects endpoint nodes from the graph and samples a chain (currently sequential, length ≥ 3).
  - Derives:
    - `endpoint_ids`: ordered list of endpoint identifiers.
    - `tools_used`: distinct tool IDs used in the chain.
    - `pattern_type`: currently `"sequential"`, extensible to parallel/mixed.
    - `tags`: any associated concept/tag metadata from tool nodes (used as a domain hint).

### PlannerAgent

- **Responsibility**: Turn a sampled tool chain into a conversation plan.
- **Inputs**: `SampledToolChain`, optional corpus memory summaries, configuration/seed.
- **Behavior**:
  - Determines a domain (e.g., from chain tags) and constructs a user goal string.
  - Uses corpus summaries to slightly diversify plans when similar pattern/domain combinations have been seen before.
  - Produces a `ConversationPlan`:
    - `goal` and `domain`.
    - Ordered `PlanStep`s that alternate between:
      - `kind="clarification"` steps (where the assistant should ask questions).
      - `kind="tool_call"` steps referencing specific endpoint IDs.

### UserProxyAgent

- **Responsibility**: Simulate the user side of the interaction.
- **Behavior**:
  - Generates the initial user `Message` expressing the plan’s goal.
  - Answers clarification questions with follow-up user messages, providing simple but usable parameter values (e.g., `lang="en"`), while tracking what has already been provided per endpoint.

### AssistantAgent

- **Responsibility**: Decide between asking clarifications and issuing tool calls, and execute tools via the OfflineExecutor.
- **Inputs**: `OfflineExecutor`, `MemoryStore`, `AssistantConfig` (including `conversation_id`), current `ConversationRecord`, `PlanStep`, and session state.
- **Behavior**:
  - For `kind="clarification"` steps:
    - Emits an assistant `Message` asking for missing details (e.g., language).
  - For `kind="tool_call"` steps:
    - Builds tool-call arguments based on conversation context (currently defaulting to `lang="en"`).
    - For non-first tool calls, queries `MemoryStore.search(..., scope="session")`; when any prior tool outputs are retrieved, marks the arguments as `from_memory=True` to indicate that they are grounded in session memory.
    - Calls `executor.execute(...)`:
      - On `ValidationError`, turns errors into a clarifying `Message` instead of executing.
      - On success:
        - Appends resulting `ToolCall` and `ToolOutput` to the conversation.
        - Writes the `ToolOutput` into session memory using `add_session_tool_output(...)`.
        - Sends an assistant `Message` summarizing the tool result for the user.

### ConversationValidatorAgent

- **Responsibility**: Check structural and basic semantic properties of conversations.
- **Behavior**:
  - Ensures at least 3 tool calls (multi-step).
  - Encourages use of ≥ 2 distinct tools where possible (multi-tool).
  - Verifies that message roles are within an allowed set (`user`, `assistant`, `tool`).
  - Performs a basic memory-grounding check:
    - For non-first tool calls, expects arguments to include `from_memory=True`, indicating that the Assistant consulted session memory before forming the call.
  - Returns a `ValidationResult` (`valid`, `reasons`), which is currently attached to `ConversationMetadata.extra` if invalid.

### ConversationGeneratorCore

- **Responsibility**: Orchestrate all agents to produce a single `ConversationRecord`.
- **Inputs**: `ToolRegistry`, `ToolGraph`, `OfflineExecutor`, `MemoryStore`, and `ConversationGeneratorConfig` (`conversation_id`, `seed`, `corpus_memory_enabled`).
- **Flow**:
  1. **Corpus context** (if enabled): queries `MemoryStore.search(..., scope="corpus")` for prior summaries.
  2. **Sampling**: `SamplerAgent` samples a tool chain from the graph.
  3. **Planning**: `PlannerAgent` creates a `ConversationPlan` using the chain and any corpus context.
  4. **Initial user**: `UserProxyAgent` emits the initial user request message.
  5. **User–Assistant loop**:
     - For each `PlanStep`:
       - `AssistantAgent.handle_step(...)` produces assistant messages and, for tool-call steps, executes tools via the executor and writes outputs into **session memory**.
       - For clarification steps, `UserProxyAgent` immediately responds with a follow-up user message.
  6. **Metadata**: assembles `ConversationMetadata` (seed, tools used, num turns, num clarifications, pattern type, corpus_memory_enabled).
  7. **Validation**: `ConversationValidatorAgent` validates the conversation; reasons are stored in `metadata.extra` when not fully valid.
- **Memory usage**:
  - Session memory (`scope="session"`) is updated after each successful tool call and is intended to be read by future steps for argument grounding.
  - Corpus memory (`scope="corpus"`) is read before planning when enabled and will be written after conversations in the generation pipeline (next stories).

## Generation Pipeline

- **ConversationGeneratorCore vs dataset generation**
  - `ConversationGeneratorCore` is responsible for generating a **single** `ConversationRecord` given the registry, graph, executor, and memory.
  - The `generate_dataset` function in `toolbench_synthgen/pipeline/generate.py` builds on this core to:
    - Load the `ToolRegistry` and `ToolGraph` artifacts produced by the `build` command.
    - Create a shared `MemoryStore` and `OfflineExecutor`.
    - Loop over `num_conversations`, instantiating a new `ConversationGeneratorCore` per conversation with a deterministic seed offset (`seed + i`).

- **Session and corpus memory usage during generation**
  - **Session memory**:
    - Within each conversation, the executor and assistant:
      - Write every successful tool output to `scope="session"` with metadata `{"conversation_id", "step", "endpoint"}`.
      - Query `scope="session"` for non-first tool calls, marking arguments as `from_memory=True` when any entries are retrieved (used later for metrics).
  - **Corpus memory**:
    - If `corpus_memory_enabled` is `True` in `ConversationGeneratorConfig`:
      - Before planning each conversation, the planner receives corpus context from `MemoryStore.search(..., scope="corpus")`.
      - After a conversation is generated, `generate_dataset` constructs a compact summary string and writes it to `scope="corpus"` via `add_corpus_summary`, with metadata including `conversation_id`, `tools`, and `pattern_type`.
    - When the CLI flag `--no-corpus-memory` is set, the generator:
      - Sets `corpus_memory_enabled=False` in configuration.
      - Skips all corpus-memory reads and writes.

- **memory_grounding_rate computation**
  - Implemented in `compute_memory_grounding_rate`:
    - Let `C` be the set of tool calls with `step_index > 0` (non-first calls).
    - If `C` is empty, `memory_grounding_rate` is set to `null`.
    - Otherwise:
      - Numerator: number of calls in `C` whose `arguments` include `from_memory=True`.
      - Denominator: `len(C)`.
      - `memory_grounding_rate = numerator / denominator`.
  - This aligns with the requirement that a retrieval is considered present whenever `search()` returns at least one result and that information has been incorporated into the argument-filling context (signaled here by `from_memory=True`).

- **Dataset output format**
  - `generate_dataset` writes each `ConversationRecord` as a single JSON line to the configured output path.
  - Each record contains:
    - `conversation_id`
    - `messages`: list of `Message` objects with `role`, `content`, and optional `tool_call_id`.
    - `tool_calls`: list of `ToolCall` objects with `id`, `endpoint_id`, `arguments`, and `step_index`.
    - `tool_outputs`: list of `ToolOutput` objects with `id`, `tool_call_id`, `payload`, and `derived_ids`.
    - `metadata`: `ConversationMetadata` populated with at least:
      - `seed`
      - `tool_ids_used`
      - `num_turns`
      - `num_clarification_questions`
      - `memory_grounding_rate`
      - `corpus_memory_enabled`
      - `pattern_type`
      - optional `extra` (e.g., validation reasons).

## Validation (Dataset Validator)

The `validate` CLI command runs a **DatasetValidator** over a JSONL dataset of `ConversationRecord`s. The following invariants are checked; violations are aggregated (or, with `--strict`, the run stops on the first failure).

- **Schema validity**  
  Each line must parse as a valid `ConversationRecord` (Pydantic). Required fields and basic types for messages, tool calls, tool outputs, and metadata are enforced. Invalid lines are counted as schema errors and (in non-strict mode) skipped for downstream checks.

- **Linkage invariants**  
  Every `ToolOutput.tool_call_id` must equal some `ToolCall.id` in the same record. Step ordering and consistency of `step_index` are implied by the structure. Conversations with orphan outputs are counted as linkage errors.

- **Multi-step requirement**  
  Each conversation must have **≥ 3 tool calls**. Conversations with fewer are reported as multi-step violations.

- **Multi-tool coverage**  
  A substantial portion of conversations should use **≥ 2 distinct tools**. Distinct tool IDs are derived from `endpoint_id` (e.g. `tool_id` from `endpoint_id.split(".")[0]`). Conversations with only one tool are reported as multi-tool violations.

- **Clarification behavior**  
  When `metadata.num_clarification_questions` > 0, the validator requires at least that many **assistant messages without a tool call** (text-only messages) in the conversation. This ensures that where the generator recorded clarifications, the message sequence contains the expected number of clarification turns. Violations are reported as clarification violations.

- **memory_grounding_rate correctness**  
  For each conversation, the validator recomputes `memory_grounding_rate` from the definition (numerator = number of non-first tool calls whose `arguments` include `from_memory=True`; denominator = total non-first tool calls; value `null` when denominator is zero). The stored value in `metadata` is compared to the recomputed value; mismatches (including `null` vs non-null) are reported as memory_grounding_mismatches.

**Handling of violations**  
  The validator returns a **ValidationSummary** with total conversations, counts per category (schema_errors, linkage_errors, multi_step_violations, multi_tool_violations, clarification_violations, memory_grounding_mismatches), and optional detail strings. **Passed** counts per category are derived as (eligible − violations), where eligible is (total_conversations − schema_errors). The CLI prints a JSON report and exits with **non-zero status** when there are schema or linkage errors (serious failures); other violations are reported but do not change exit status.

## Metrics & Diversity Analysis

- **Diversity metric: pairwise tool-chain Jaccard dissimilarity**  
  For each conversation, the **tool-chain set** is the set of tool IDs used in that conversation (from `metadata.tool_ids_used`, or derived from `tool_calls` via `endpoint_id`).  
  For two conversations with tool sets \( A \) and \( B \), the **Jaccard distance** is:
  \[
  d_{\mathrm{Jaccard}}(A, B) = 1 - \frac{|A \cap B|}{|A \cup B|}.
  \]
  (If both sets are empty, distance is defined as 0.)  
  The **corpus diversity** metric is the **average pairwise Jaccard distance** over all pairs of conversations in the dataset. Higher values indicate more diverse tool usage across conversations.

- **memory_grounding_rate statistics**  
  For each dataset, the metrics pipeline computes:
  - **Mean, min, max** of `metadata.memory_grounding_rate` over conversations where it is non-null.
  - A **histogram** over buckets: `0.0`, `(0.0, 0.5]`, `(0.5, 1.0)`, `1.0`.

- **Pattern entropy**  
  Entropy over `metadata.pattern_type` (or `"unknown"` when null) is computed to capture diversity of conversation patterns (e.g. sequential vs other types).

- **Output**  
  The `metrics` CLI outputs both **human-readable** summary lines (path, diversity_jaccard, memory_grounding mean/min/max, pattern_entropy) and a **machine-readable** JSON object containing the same information plus the full histogram for each dataset (and, when two paths are given, for both Run A and Run B).

## Corpus Memory & Diversity Analysis

This subsection is the placeholder for **concrete numeric results and a short analysis** of the diversity experiment (Run A: corpus memory disabled vs Run B: corpus memory enabled, same seed and parameters). In a later story, the exact commands will be run, the metrics (diversity Jaccard, memory_grounding_rate stats, pattern entropy) for both runs will be pasted here, and a 3–5 sentence interpretation will be added (e.g. whether corpus memory leads to higher or lower tool-chain diversity and how memory_grounding_rate compares).

