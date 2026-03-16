import json
from pathlib import Path
from typing import Any, Dict, Optional

import typer

from toolbench_synthgen.graph import build_tool_graph
from toolbench_synthgen.pipeline import (
    DatasetValidator,
    MetricsComputer,
    generate_dataset,
)
from toolbench_synthgen.registry import ToolRegistry, load_toolbench_tools


app = typer.Typer(help="ToolBench-based offline synthetic conversation generator.")


@app.command()
def build(
    toolbench_path: str = typer.Option(
        ...,
        "--toolbench-path",
        help="Path to ToolBench tool definitions (e.g., toolenv JSONs).",
    ),
    artifacts_dir: str = typer.Option(
        "artifacts",
        "--artifacts-dir",
        help="Directory where registry/graph artifacts will be written.",
    ),
) -> None:
    """
    Build registry / graph / index from ToolBench tool definitions and write artifacts.
    """
    try:
        data = load_toolbench_tools(toolbench_path)
        registry = ToolRegistry(data)
    except FileNotFoundError as e:
        typer.echo(f"[build] Error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"[build] Failed to load ToolBench tools: {e}")
        raise typer.Exit(code=1)

    artifacts_root = Path(artifacts_dir)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    registry_path = artifacts_root / "tool_registry.json"
    graph_path = artifacts_root / "tool_graph.json"

    registry.save(str(registry_path))

    graph = build_tool_graph(registry)
    graph.save(str(graph_path))

    num_tools = len(list(registry.tools))
    num_endpoints = len(list(registry.endpoints))

    summary = {
        "tools": num_tools,
        "endpoints": num_endpoints,
        "registry_path": str(registry_path),
        "graph_path": str(graph_path),
    }
    typer.echo("[build] Completed registry and graph construction:")
    typer.echo(json.dumps(summary, indent=2))


@app.command()
def generate(
    output_path: str = typer.Option(
        "data/conversations.jsonl",
        "--output-path",
        help="Path to the JSONL file where generated conversations will be written.",
    ),
    num_conversations: int = typer.Option(
        10,
        "--num-conversations",
        help="Number of conversations to generate.",
    ),
    seed: int = typer.Option(
        42,
        "--seed",
        help="Random seed for deterministic generation.",
    ),
    no_corpus_memory: bool = typer.Option(
        False,
        "--no-corpus-memory",
        help="Disable corpus-level memory when set.",
    ),
) -> None:
    """
    Generate conversations and write them to a JSONL dataset.
    """
    artifacts_root = Path("artifacts")
    registry_path = artifacts_root / "tool_registry.json"
    graph_path = artifacts_root / "tool_graph.json"

    if not registry_path.exists() or not graph_path.exists():
        typer.echo(
            "[generate] Missing artifacts. Please run 'toolbench-synthgen build' first."
        )
        raise typer.Exit(code=1)

    corpus_enabled = not no_corpus_memory

    typer.echo(
        f"[generate] Generating {num_conversations} conversations to '{output_path}' "
        f"with seed={seed}, corpus_memory_enabled={corpus_enabled}."
    )

    conversations = generate_dataset(
        registry_path=str(registry_path),
        graph_path=str(graph_path),
        output_path=output_path,
        num_conversations=num_conversations,
        seed=seed,
        corpus_memory_enabled=corpus_enabled,
    )

    typer.echo(
        json.dumps(
            {
                "output_path": output_path,
                "num_conversations": len(conversations),
            },
            indent=2,
        )
    )


@app.command()
def validate(
    input_path: str = typer.Option(
        "data/conversations.jsonl",
        "--input-path",
        help="Path to the JSONL dataset to validate.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Fail on first validation error (default: aggregate all).",
    ),
) -> None:
    """
    Validate a generated dataset.
    """
    validator = DatasetValidator()
    summary = validator.validate_dataset(input_path, strict=strict)

    report: Dict[str, Any] = {
        "total_conversations": summary.total_conversations,
        "schema": {"passed": summary.schema_passed, "errors": summary.schema_errors},
        "linkage": {"passed": summary.linkage_passed, "errors": summary.linkage_errors},
        "multi_step": {"passed": summary.multi_step_passed, "violations": summary.multi_step_violations},
        "multi_tool": {"passed": summary.multi_tool_passed, "violations": summary.multi_tool_violations},
        "clarification": {"passed": summary.clarification_passed, "violations": summary.clarification_violations},
        "memory_grounding": {"passed": summary.memory_grounding_passed, "mismatches": summary.memory_grounding_mismatches},
    }
    if summary.details:
        report["details"] = summary.details

    typer.echo(json.dumps(report, indent=2))

    if summary.has_serious_failures():
        raise typer.Exit(code=1)


@app.command()
def metrics(
    input_path_a: str = typer.Option(
        "data/run_a.jsonl",
        "--input-path-a",
        help="Path to first dataset (e.g., Run A, corpus memory disabled).",
    ),
    input_path_b: Optional[str] = typer.Option(
        None,
        "--input-path-b",
        help="Optional second dataset (e.g., Run B, corpus memory enabled).",
    ),
) -> None:
    """
    Compute evaluation metrics (including diversity) over one or two datasets.
    """
    computer = MetricsComputer()
    result_a = computer.compute_for_dataset(input_path_a)

    output: Dict[str, Any] = {
        "run_a": {
            "path": input_path_a,
            "diversity_jaccard": result_a.diversity_jaccard,
            "memory_grounding": {
                "mean": result_a.mgr_mean,
                "min": result_a.mgr_min,
                "max": result_a.mgr_max,
                "histogram": result_a.mgr_histogram,
            },
            "pattern_entropy": result_a.pattern_entropy,
        }
    }

    # Human-readable summary for Run A
    typer.echo("[metrics] Run A:")
    typer.echo(f"  path: {input_path_a}")
    typer.echo(f"  diversity_jaccard: {result_a.diversity_jaccard:.4f}")
    typer.echo(f"  memory_grounding: mean={result_a.mgr_mean:.4f} min={result_a.mgr_min:.4f} max={result_a.mgr_max:.4f}")
    typer.echo(f"  pattern_entropy: {result_a.pattern_entropy:.4f}")

    if input_path_b:
        result_b = computer.compute_for_dataset(input_path_b)
        output["run_b"] = {
            "path": input_path_b,
            "diversity_jaccard": result_b.diversity_jaccard,
            "memory_grounding": {
                "mean": result_b.mgr_mean,
                "min": result_b.mgr_min,
                "max": result_b.mgr_max,
                "histogram": result_b.mgr_histogram,
            },
            "pattern_entropy": result_b.pattern_entropy,
        }
        typer.echo("[metrics] Run B:")
        typer.echo(f"  path: {input_path_b}")
        typer.echo(f"  diversity_jaccard: {result_b.diversity_jaccard:.4f}")
        typer.echo(f"  memory_grounding: mean={result_b.mgr_mean:.4f} min={result_b.mgr_min:.4f} max={result_b.mgr_max:.4f}")
        typer.echo(f"  pattern_entropy: {result_b.pattern_entropy:.4f}")

    typer.echo("")
    typer.echo("[metrics] JSON output:")
    typer.echo(json.dumps(output, indent=2))


if __name__ == "__main__":
    app()

