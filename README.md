# ToolBench SynthGen

An offline multi-agent conversation generator that produces multi-turn, multi-step, multi-tool tool-use traces grounded in tool schemas from ToolBench.

## Installation

1. Create and activate a Python virtual environment (Python 3.10+).
2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

This installs the `toolbench-synthgen` package and exposes the `toolbench-synthgen` CLI.

## CLI Commands

- Build registry and graph artifacts from ToolBench tools:

```bash
toolbench-synthgen build --toolbench-path /path/to/ToolBench/data/toolenv/tools --artifacts-dir artifacts
```

- Generate conversations into a JSONL dataset:

```bash
toolbench-synthgen generate --output-path data/conversations.jsonl --num-conversations 10 --seed 42
```

- Validate a generated dataset:

```bash
toolbench-synthgen validate --input-path data/conversations.jsonl
```

- Compute metrics over one or two datasets:

```bash
toolbench-synthgen metrics --input-path-a data/run_a.jsonl --input-path-b data/run_b.jsonl
```

## Build Inputs and Artifacts

The `build` command expects a directory containing ToolBench-style tool JSON files (for example, files under `ToolBench/data/toolenv/tools`). It:

- Loads and normalizes tool definitions into a **Tool Registry** capturing tools, endpoints, parameters, and basic metadata.
- Constructs a **Tool Graph** whose nodes include tools, endpoints, parameters, response fields, and concept/tag nodes; edges capture relationships such as `Tool → Endpoint`, `Endpoint → Parameter`, `Endpoint → ResponseField`, and `Concept/Tag ↔ Tool`.
- Writes both artifacts into the configured `--artifacts-dir` (by default, an `artifacts/` directory).

These artifacts will later be used by the sampler and multi-agent generator to propose realistic multi-step, multi-tool chains during dataset generation.

## Project Structure

- `toolbench_synthgen/`
  - `registry/` – Tool registry models, loader, and query API for ToolBench definitions.
  - `graph/` – Tool graph representation and constructors built from the registry.
  - `executor/` – Offline tool execution model (to be implemented).
  - `agents/` – Multi-agent conversation system (to be implemented).
  - `memory/` – `MemoryStore` abstraction backed by `mem0` (to be implemented).
  - `pipeline/` – Orchestration for build / generate / validate / metrics (to be implemented).
  - `cli.py` – CLI entrypoint providing `build`, `generate`, `validate`, and `metrics` commands.
- `tests/` – Test package, to be populated in later stories.

Each subsequent story will extend this scaffolding and update the documentation to describe newly implemented functionality.

