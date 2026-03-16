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

## CLI Commands (scaffolding only)

All commands are currently placeholders that print a message indicating they were invoked. Later stories will add full functionality.

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

## Project Structure (current scaffolding)

- `toolbench_synthgen/`
  - `registry/` – Tool registry and loaders for ToolBench definitions (to be implemented).
  - `graph/` – Tool graph representation and samplers (to be implemented).
  - `executor/` – Offline tool execution model (to be implemented).
  - `agents/` – Multi-agent conversation system (to be implemented).
  - `memory/` – `MemoryStore` abstraction backed by `mem0` (to be implemented).
  - `pipeline/` – Orchestration for build / generate / validate / metrics (to be implemented).
  - `cli.py` – CLI entrypoint providing `build`, `generate`, `validate`, and `metrics` commands.
- `tests/` – Test package, to be populated in later stories.

Each subsequent story will extend this scaffolding and update the documentation to describe newly implemented functionality.

