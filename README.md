# ToolBench SynthGen

An offline multi-agent conversation generator that produces multi-turn, multi-step, multi-tool tool-use traces grounded in tool schemas from ToolBench.

## Features

- **Tool Registry**: Loads and normalizes ToolBench tool definitions with robust error handling
- **Tool Graph**: Constructs a graph capturing tools, endpoints, parameters, and semantic groupings
- **Multi-Agent System**: Five specialized agents (Sampler, Planner, UserProxy, Assistant, Validator) collaborate to generate conversations
- **Agentic Memory**: Session and corpus memory backed by mem0 for context-aware generation
- **Deterministic Generation**: Seed-based reproducibility for all outputs
- **Comprehensive Validation**: Schema, linkage, multi-step, and multi-tool validation
- **Diversity Metrics**: Jaccard dissimilarity, memory grounding rate, and pattern entropy

## Installation

1. Create and activate a Python virtual environment (Python 3.10+).
2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

This installs the `toolbench-synthgen` package and exposes the `toolbench-synthgen` CLI.

## Quick Start

```bash
# 1. Build registry and graph from ToolBench tools
toolbench-synthgen build \
  --toolbench-path /path/to/ToolBench/data/toolenv/tools \
  --artifacts-dir artifacts

# 2. Generate conversations
toolbench-synthgen generate \
  --output-path data/conversations.jsonl \
  --num-conversations 50 \
  --seed 42

# 3. Validate the dataset
toolbench-synthgen validate --input-path data/conversations.jsonl

# 4. Compute metrics
toolbench-synthgen metrics --input-path-a data/conversations.jsonl
```

## CLI Commands

### `build` - Build Registry and Graph

```bash
toolbench-synthgen build \
  --toolbench-path /path/to/ToolBench/data/toolenv/tools \
  --artifacts-dir artifacts
```

Loads ToolBench tool definitions and creates:
- `tool_registry.json`: Normalized tool definitions with endpoints, parameters, and metadata
- `tool_graph.json`: Graph with tool, endpoint, parameter, response_field, and concept nodes

The loader handles missing/inconsistent fields gracefully and logs skipped files.

### `generate` - Generate Conversations

```bash
toolbench-synthgen generate \
  --output-path data/conversations.jsonl \
  --num-conversations 100 \
  --seed 42 \
  [--no-corpus-memory]
```

**Options:**
- `--output-path`: Path to output JSONL file (default: `data/conversations.jsonl`)
- `--num-conversations`: Number of conversations to generate (default: 10)
- `--seed`: Random seed for deterministic generation (default: 42)
- `--no-corpus-memory`: Disable corpus-level memory (session memory remains active)

**Output Format (JSONL):**
Each line is a JSON object with:
- `conversation_id`: Unique identifier
- `messages`: List of role-tagged messages (user, assistant, tool)
- `tool_calls`: List of tool calls with endpoint_id, arguments, step_index
- `tool_outputs`: Mocked responses with payload and derived_ids
- `metadata`: seed, tool_ids_used, num_turns, num_clarification_questions, memory_grounding_rate, corpus_memory_enabled, pattern_type

### `validate` - Validate Dataset

```bash
toolbench-synthgen validate \
  --input-path data/conversations.jsonl \
  [--strict]
```

Checks:
- **Schema validity**: Each line parses as valid ConversationRecord
- **Linkage**: Every ToolOutput.tool_call_id references a valid ToolCall.id
- **Multi-step**: Each conversation has ≥3 tool calls
- **Multi-tool**: Each conversation uses ≥2 distinct tools
- **Clarifications**: Assistant clarification messages match metadata count
- **Memory grounding rate**: Recomputes and verifies stored value

Use `--strict` to stop on first error. Exits with non-zero status on schema/linkage errors.

### `metrics` - Compute Metrics

```bash
# Single dataset
toolbench-synthgen metrics --input-path-a data/run_a.jsonl

# Compare two datasets (A/B test)
toolbench-synthgen metrics \
  --input-path-a data/run_a.jsonl \
  --input-path-b data/run_b.jsonl
```

Reports:
- **Diversity (Jaccard)**: Average pairwise Jaccard distance between tool sets
- **Memory Grounding Rate**: Mean/min/max and histogram
- **Pattern Entropy**: Diversity of conversation patterns

## Diversity Experiment

To compare corpus memory impact on diversity:

```bash
# Run A: corpus memory disabled
toolbench-synthgen generate \
  --output-path data/run_a.jsonl \
  --num-conversations 100 \
  --seed 42 \
  --no-corpus-memory

# Run B: corpus memory enabled
toolbench-synthgen generate \
  --output-path data/run_b.jsonl \
  --num-conversations 100 \
  --seed 42

# Compare metrics
toolbench-synthgen metrics \
  --input-path-a data/run_a.jsonl \
  --input-path-b data/run_b.jsonl
```

## Demo & Results

- Video demo: [Multi-Agent ToolBench SynthGen (YouTube)](https://www.youtube.com/watch?v=7Rk2B012Too)
- `run_a.jsonl` results (corpus memory disabled): [Download](https://drive.google.com/file/d/1vYXV5hqRiaYfrBXueUpW4uG-SyoqUIIX/view?usp=sharing)
- `run_b.jsonl` results (corpus memory enabled): [Download](https://drive.google.com/file/d/13KE8vdDkVhoTbezU1rfN8SMdr1itNo8K/view?usp=sharing)

## Project Structure

```
toolbench_synthgen/
├── __init__.py
├── cli.py                 # CLI entrypoint (build, generate, validate, metrics)
├── models.py              # Pydantic models (Message, ToolCall, ToolOutput, etc.)
├── registry/              # Tool registry and ToolBench loader
│   ├── __init__.py
│   ├── loader.py          # load_toolbench_tools() with error handling
│   ├── models.py          # Tool, Endpoint, Parameter, ResponseField
│   └── registry.py        # ToolRegistry class
├── graph/                 # Tool graph construction
│   ├── __init__.py
│   └── tool_graph.py      # ToolGraph, build_tool_graph()
├── executor/              # Offline tool execution
│   ├── __init__.py
│   └── offline.py         # OfflineExecutor with validation
├── agents/                # Multi-agent system
│   ├── __init__.py
│   ├── sampler.py         # SamplerAgent - proposes tool chains
│   ├── planner.py         # PlannerAgent - creates conversation plans
│   ├── user_proxy.py      # UserProxyAgent - simulates user
│   ├── assistant.py       # AssistantAgent - tool calls & clarifications
│   ├── validator.py       # ConversationValidatorAgent
│   └── generator.py       # ConversationGeneratorCore orchestrator
├── memory/                # Agentic memory layer
│   ├── __init__.py
│   └── store.py           # MemoryStore (mem0) and InMemoryStore
└── pipeline/              # Pipeline orchestration
    ├── __init__.py
    ├── generate.py        # generate_dataset()
    ├── validate.py        # DatasetValidator
    └── metrics.py         # MetricsComputer

tests/                     # Test suite
├── __init__.py
├── conftest.py            # Shared pytest fixtures
├── test_registry.py       # Unit tests for parsing/validation
├── test_memory.py         # Unit tests for MemoryStore
└── test_e2e.py            # End-to-end tests (≥50 samples)

artifacts/                 # Pre-built artifacts (generated by build command)
├── tool_registry.json     # Normalized tool definitions
└── tool_graph.json        # Tool relationship graph
```

## Testing

Run the full test suite:

```bash
pytest tests/ -v
```

Run specific test categories:

```bash
# Unit tests for registry parsing/validation
pytest tests/test_registry.py -v

# Unit tests for MemoryStore (add→search, scope isolation)
pytest tests/test_memory.py -v

# End-to-end tests (generates ≥50 samples)
pytest tests/test_e2e.py -v
```

### Test Coverage

- **Registry Tests**: Parsing valid/invalid JSON, missing fields, parameter extraction, enum constraints
- **Memory Tests**: Add/search functionality, scope isolation (session vs corpus), helper functions
- **E2E Tests**: Full pipeline from build to validate, determinism verification, output format compliance

## Architecture

### Multi-Agent System

1. **SamplerAgent**: Samples tool chains from the Tool Graph (min 3 endpoints)
2. **PlannerAgent**: Creates conversation plans with goals, domains, and step sequences
3. **UserProxyAgent**: Generates user messages and answers clarification questions
4. **AssistantAgent**: Executes tool calls, queries memory, emits responses
5. **ConversationValidatorAgent**: Validates structural properties

### Memory System

- **Session Memory** (`scope="session"`): Per-conversation tool outputs for argument grounding
- **Corpus Memory** (`scope="corpus"`): Cross-conversation summaries for diversity

### Data Flow

```
ToolBench JSON → Registry → Graph → Sampler → Planner → Generator → JSONL
                                      ↑                      ↓
                                 Corpus Memory ←────── Corpus Summary
```

## Configuration

**No external API keys are required for basic functionality.** The MemoryStore automatically
falls back to an InMemoryStore (recency-based retrieval) when mem0's semantic search
cannot be initialized.

For full semantic search capabilities with mem0:
- Set `OPENAI_API_KEY` environment variable, OR
- Configure Ollama for local LLM inference

The assessment specifies: "mem0 defaults to an in-process vector store (Qdrant embedded).
No external service is required for the exercise." The fallback ensures the pipeline works
without any external services while still meeting the MemoryStore interface requirements.

## Requirements

- Python 3.10+
- typer >= 0.12.0
- mem0ai >= 0.0.8
- pydantic >= 2.7.0
- networkx >= 3.2.0
- sentence-transformers >= 2.2.0 (for local embeddings when mem0 is available)
- pytest >= 8.0.0 (dev)

## License

See LICENSE file for details.