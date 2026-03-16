from __future__ import annotations

from typing import Any, Dict, List

from mem0 import Memory


class MemoryStore:
    """mem0-backed memory abstraction with session and corpus scopes.

    Interface (must be exact):
        add(self, content: str, scope: str, metadata: dict) -> None
        search(self, query: str, scope: str, top_k: int = 5) -> list[dict]
    """

    def __init__(self) -> None:
        # Single mem0 Memory instance; scope is passed via namespace.
        self._memory = Memory()

    def add(self, content: str, scope: str, metadata: Dict[str, Any]) -> None:
        """Add a new memory entry under the given scope."""
        # `scope` is free-form, but this project uses "session" and "corpus".
        self._memory.add(content, metadata=metadata, namespace=scope)

    def search(self, query: str, scope: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for memories under the given scope.

        For later metrics, a retrieval is considered "present" whenever this
        method returns at least one result for the requested scope.
        """
        results = self._memory.search(query, namespace=scope, limit=top_k)
        # Ensure we always return a list[dict] even if mem0 returns other shapes.
        if isinstance(results, dict):
            return [results]
        return list(results or [])


def add_session_tool_output(
    store: MemoryStore,
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
    store: MemoryStore,
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

