from __future__ import annotations

import logging
from typing import Any, Dict, List, Protocol

logger = logging.getLogger(__name__)


class MemoryStoreProtocol(Protocol):
    """Protocol for add/search memory stores (mem0 or in-memory)."""

    def add(self, content: str, scope: str, metadata: Dict[str, Any]) -> None: ...
    def search(self, query: str, scope: str, top_k: int = 5) -> List[Dict[str, Any]]: ...


class InMemoryStore:
    """In-memory store with the same add/search interface. No embedder or API key.

    Used when corpus_memory_enabled=False so the pipeline can run without external APIs.
    Search returns the most recently added items for the scope (no semantic search).
    """

    def __init__(self) -> None:
        # List of (content, scope, metadata); search returns last top_k for scope.
        self._entries: List[tuple[str, str, Dict[str, Any]]] = []

    def add(self, content: str, scope: str, metadata: Dict[str, Any]) -> None:
        self._entries.append((content, scope, metadata))

    def search(self, query: str, scope: str, top_k: int = 5) -> List[Dict[str, Any]]:
        matches = [e for e in self._entries if e[1] == scope]
        # Return last top_k as dicts for API compatibility.
        recent = matches[-top_k:] if top_k else []
        return [{"content": c, "metadata": m} for c, _, m in reversed(recent)]


def _get_mem0_config(use_local_embeddings: bool = True) -> Dict[str, Any]:
    """Get mem0 configuration.

    Args:
        use_local_embeddings: If True, uses local Hugging Face embeddings.
                              If False, uses OpenAI embeddings (requires API key).

    Returns:
        mem0 configuration dictionary.

    Note:
        mem0 requires an LLM for memory extraction. Options:
        - OpenAI: Set OPENAI_API_KEY environment variable
        - Ollama: Install and run Ollama locally
        - Other providers: Configure accordingly

        The embedder can be local (Hugging Face) but LLM is still required.
    """
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "toolbench_synthgen",
                "embedding_model_dims": 384 if use_local_embeddings else 1536,
            },
        },
    }

    if use_local_embeddings:
        config["embedder"] = {
            "provider": "huggingface",
            "config": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
            },
        }

    return config


class MemoryStore:
    """mem0-backed memory abstraction with session and corpus scopes.

    This class wraps mem0 for semantic search capabilities. Note that mem0 requires
    an LLM provider for memory extraction:
    - For OpenAI: Set the OPENAI_API_KEY environment variable
    - For local: Configure Ollama with a local model

    If mem0 initialization fails, falls back to InMemoryStore (recency-based, no semantic search).

    Interface (must be exact):
        add(self, content: str, scope: str, metadata: dict) -> None
        search(self, query: str, scope: str, top_k: int = 5) -> list[dict]
    """

    def __init__(self, config: Dict[str, Any] | None = None, use_local_embeddings: bool = True) -> None:
        """Initialize mem0 Memory.

        Args:
            config: Optional custom mem0 configuration. If None, uses default configuration.
            use_local_embeddings: If True and config is None, uses local Hugging Face embeddings.
                                  mem0 still requires an LLM provider (e.g., OpenAI or Ollama).
        """
        self._fallback_store: InMemoryStore | None = None

        effective_config = config if config is not None else _get_mem0_config(use_local_embeddings)
        try:
            from mem0 import Memory
            self._memory = Memory.from_config(effective_config)
            logger.info("MemoryStore initialized with mem0")
        except ImportError:
            logger.warning("mem0 not installed. Using InMemoryStore fallback.")
            self._fallback_store = InMemoryStore()
        except Exception as e:
            logger.warning(
                f"Failed to initialize mem0: {e}. "
                "Using InMemoryStore fallback (recency-based, no semantic search). "
                "To enable semantic search, set OPENAI_API_KEY or configure another LLM provider."
            )
            self._fallback_store = InMemoryStore()

    def add(self, content: str, scope: str, metadata: Dict[str, Any]) -> None:
        """Add a new memory entry under the given scope."""
        if self._fallback_store is not None:
            self._fallback_store.add(content, scope, metadata)
            return
        # `scope` is free-form, but this project uses "session" and "corpus".
        self._memory.add(content, metadata=metadata, namespace=scope)

    def search(self, query: str, scope: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for memories under the given scope.

        For later metrics, a retrieval is considered "present" whenever this
        method returns at least one result for the requested scope.
        """
        if self._fallback_store is not None:
            return self._fallback_store.search(query, scope, top_k)

        results = self._memory.search(query, namespace=scope, limit=top_k)
        # Ensure we always return a list[dict] even if mem0 returns other shapes.
        if isinstance(results, dict):
            return [results]
        return list(results or [])


def add_session_tool_output(
    store: MemoryStoreProtocol,
    conversation_id: str,
    step: int,
    endpoint: str,
    tool_output_json: str,
) -> None:
    """Helper to write a tool output into session memory.

    Convention:
        content  = JSON-serialized ToolOutput
        scope    = "session"
        metadata = {"conversation_id": ..., "step": ..., "endpoint": ...}
    """
    metadata = {
        "conversation_id": conversation_id,
        "step": step,
        "endpoint": endpoint,
    }
    store.add(content=tool_output_json, scope="session", metadata=metadata)


def add_corpus_summary(
    store: MemoryStoreProtocol,
    conversation_id: str,
    tools: List[str],
    pattern_type: str,
    summary_text: str,
) -> None:
    """Helper to write a conversation summary into corpus memory.

    Convention:
        content  = compact summary text, e.g.
                   "Tools: weather_api, maps_api. Domain: travel. Pattern: sequential."
        scope    = "corpus"
        metadata = {"conversation_id": ..., "tools": [...], "pattern_type": ...}
    """
    metadata = {
        "conversation_id": conversation_id,
        "tools": tools,
        "pattern_type": pattern_type,
    }
    store.add(content=summary_text, scope="corpus", metadata=metadata)

