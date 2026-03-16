import json
from pathlib import Path

import typer

from toolbench_synthgen.graph import build_tool_graph
from toolbench_synthgen.pipeline import generate_dataset
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
) -> None:
    """
    Validate a generated dataset.

    Placeholder implementation; full validation logic will be added later.
    """
    typer.echo(f"[validate] Not yet implemented. Would validate dataset at '{input_path}'.")


@app.command()
def metrics(
    input_path_a: str = typer.Option(
        "data/run_a.jsonl",
        "--input-path-a",
        help="Path to dataset for Run A (e.g., corpus memory disabled).",
    ),
    input_path_b: str = typer.Option(
        "data/run_b.jsonl",
        "--input-path-b",
        help="Path to dataset for Run B (e.g., corpus memory enabled).",
    ),
) -> None:
    """
    Compute evaluation metrics (including diversity) over one or two datasets.

    Placeholder implementation; metric computation will be added later.
    """
    typer.echo(
        "[metrics] Not yet implemented. "
        f"Would compute metrics for '{input_path_a}' and '{input_path_b}'."
    )


if __name__ == "__main__":
    app()

