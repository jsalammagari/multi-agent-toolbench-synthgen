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

## Current Implementation (Story 1)

- Project is packaged via `pyproject.toml` with an installable `toolbench-synthgen` distribution.
- Dependencies and development tools are listed in `requirements.txt`.
- Package layout and empty subpackages (`registry`, `graph`, `executor`, `agents`, `memory`, `pipeline`) are created.
- CLI skeleton implemented in `toolbench_synthgen/cli.py` exposes four commands:
  - `build`
  - `generate`
  - `validate`
  - `metrics`
- Each command accepts the core flags required by later stories and currently prints a placeholder “not yet implemented” message.

Future stories will fill in the remaining sections of this document:

- Architecture & major modules
- Tool registry & graph design
- Multi-agent system design
- Agentic memory implementation and `memory_grounding_rate`
- Offline executor design and chain consistency
- Validation, metrics, and diversity analysis

At this point, only scaffolding & CLI are implemented; no tool ingestion, generation, or evaluation logic exists yet.

