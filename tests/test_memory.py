"""Unit tests for MemoryStore - add/search and scope isolation."""
import pytest
from toolbench_synthgen.memory import MemoryStore, InMemoryStore


class TestInMemoryStoreInterface:
    """Test that InMemoryStore implements required interface."""

    @pytest.fixture
    def memory_store(self):
        """Provide InMemoryStore for testing (no API key required)."""
        return InMemoryStore()

    def test_add_and_search_returns_stored_entry(self, memory_store):
        """Verify that add followed by search returns the stored entry."""
        # Add an entry
        memory_store.add(
            content="Tool output: result_id=abc123, data={temperature: 72}",
            scope="session",
            metadata={"conversation_id": "conv_1", "step": 0, "endpoint": "weather.get"}
        )

        # Search should return the entry
        results = memory_store.search(
            query="weather temperature",
            scope="session",
            top_k=5
        )

        assert len(results) >= 1
        # Verify the content is retrievable
        assert any("abc123" in str(r.get("content", "")) for r in results)

    def test_scope_isolation_session_not_in_corpus(self, memory_store):
        """Entries in session scope should NOT be returned when querying corpus scope."""
        # Add entry to session scope
        memory_store.add(
            content="Session data: user asked about weather",
            scope="session",
            metadata={"conversation_id": "conv_1", "step": 0}
        )

        # Search in corpus scope should NOT find session entries
        results = memory_store.search(
            query="weather",
            scope="corpus",
            top_k=5
        )

        # Should be empty or not contain session data
        for r in results:
            assert "Session data" not in str(r.get("content", ""))

    def test_scope_isolation_corpus_not_in_session(self, memory_store):
        """Entries in corpus scope should NOT be returned when querying session scope."""
        # Add entry to corpus scope
        memory_store.add(
            content="Corpus summary: Tools used - weather_api, maps_api",
            scope="corpus",
            metadata={"conversation_id": "conv_1", "tools": ["weather_api", "maps_api"]}
        )

        # Search in session scope should NOT find corpus entries
        results = memory_store.search(
            query="weather_api",
            scope="session",
            top_k=5
        )

        # Should be empty or not contain corpus data
        for r in results:
            assert "Corpus summary" not in str(r.get("content", ""))

    def test_search_empty_store_returns_empty_list(self, memory_store):
        """Search on empty store should return empty list, not error."""
        results = memory_store.search(
            query="anything",
            scope="session",
            top_k=5
        )

        assert results == [] or isinstance(results, list)

    def test_add_with_metadata(self, memory_store):
        """Metadata should be preserved when adding entries."""
        metadata = {
            "conversation_id": "conv_123",
            "step": 2,
            "endpoint": "api.endpoint",
            "custom_field": "custom_value"
        }

        memory_store.add(
            content="Test content with metadata",
            scope="session",
            metadata=metadata
        )

        results = memory_store.search(query="Test content", scope="session", top_k=1)

        assert len(results) >= 1
        # Check metadata is preserved
        assert results[0]["metadata"].get("conversation_id") == "conv_123"

    def test_top_k_limits_results(self, memory_store):
        """Search should respect top_k limit."""
        # Add multiple entries
        for i in range(10):
            memory_store.add(
                content=f"Entry number {i}",
                scope="session",
                metadata={"index": i}
            )

        results = memory_store.search(query="Entry", scope="session", top_k=3)

        assert len(results) <= 3

    def test_multiple_scopes_independent(self, memory_store):
        """Different scopes should maintain independent entries."""
        # Add to session
        memory_store.add(
            content="Session entry 1",
            scope="session",
            metadata={"type": "session"}
        )
        memory_store.add(
            content="Session entry 2",
            scope="session",
            metadata={"type": "session"}
        )

        # Add to corpus
        memory_store.add(
            content="Corpus entry 1",
            scope="corpus",
            metadata={"type": "corpus"}
        )

        # Check counts
        session_results = memory_store.search("entry", scope="session", top_k=10)
        corpus_results = memory_store.search("entry", scope="corpus", top_k=10)

        assert len(session_results) == 2
        assert len(corpus_results) == 1


class TestInMemoryStore:
    """Specific tests for InMemoryStore implementation."""

    def test_recency_based_retrieval(self):
        """InMemoryStore should return most recent entries."""
        store = InMemoryStore()

        store.add("First entry", scope="session", metadata={"order": 1})
        store.add("Second entry", scope="session", metadata={"order": 2})
        store.add("Third entry", scope="session", metadata={"order": 3})

        results = store.search("entry", scope="session", top_k=2)

        # Should return most recent (Third, Second)
        assert len(results) == 2
        # Most recent should be first
        assert "Third" in results[0]["content"]
        assert "Second" in results[1]["content"]

    def test_empty_top_k_returns_empty(self):
        """top_k=0 should return empty list."""
        store = InMemoryStore()
        store.add("Entry", scope="session", metadata={})

        results = store.search("Entry", scope="session", top_k=0)

        assert results == []

    def test_query_ignored_for_inmemory(self):
        """InMemoryStore ignores query text (no semantic search)."""
        store = InMemoryStore()

        store.add("Weather data for New York", scope="session", metadata={})

        # Query doesn't match content but should still return (recency-based)
        results = store.search("completely unrelated query", scope="session", top_k=1)

        assert len(results) == 1
        assert "Weather" in results[0]["content"]


class TestMemoryStoreHelpers:
    """Tests for helper functions."""

    def test_add_session_tool_output(self):
        """Test add_session_tool_output helper."""
        from toolbench_synthgen.memory import add_session_tool_output, InMemoryStore

        store = InMemoryStore()

        add_session_tool_output(
            store=store,
            conversation_id="conv_1",
            step=0,
            endpoint="weather.get_forecast",
            tool_output_json='{"result_id": "abc", "data": {"temp": 72}}'
        )

        results = store.search("weather", scope="session", top_k=1)
        assert len(results) >= 1
        assert results[0]["metadata"]["conversation_id"] == "conv_1"
        assert results[0]["metadata"]["step"] == 0
        assert results[0]["metadata"]["endpoint"] == "weather.get_forecast"

    def test_add_corpus_summary(self):
        """Test add_corpus_summary helper."""
        from toolbench_synthgen.memory import add_corpus_summary, InMemoryStore

        store = InMemoryStore()

        add_corpus_summary(
            store=store,
            conversation_id="conv_1",
            tools=["weather_api", "maps_api"],
            pattern_type="sequential",
            summary_text="Tools: weather_api, maps_api. Pattern: sequential."
        )

        results = store.search("weather", scope="corpus", top_k=1)
        assert len(results) >= 1
        assert results[0]["metadata"]["conversation_id"] == "conv_1"
        assert results[0]["metadata"]["tools"] == ["weather_api", "maps_api"]
        assert results[0]["metadata"]["pattern_type"] == "sequential"

    def test_session_tool_output_content_format(self):
        """Tool output should be stored as JSON string."""
        from toolbench_synthgen.memory import add_session_tool_output, InMemoryStore

        store = InMemoryStore()
        tool_output = '{"result_id": "xyz", "value": 42}'

        add_session_tool_output(
            store=store,
            conversation_id="conv_1",
            step=1,
            endpoint="api.endpoint",
            tool_output_json=tool_output
        )

        results = store.search("", scope="session", top_k=1)
        assert tool_output in results[0]["content"]


class TestMemoryStoreWithMem0:
    """Tests for MemoryStore (with mem0 or InMemoryStore fallback)."""

    @pytest.fixture
    def mem0_store(self):
        """Provide MemoryStore (falls back to InMemoryStore if mem0 unavailable)."""
        store = MemoryStore()
        return store

    def test_mem0_add_and_search(self, mem0_store):
        """Basic add/search with MemoryStore."""
        mem0_store.add(
            content="Test content for mem0",
            scope="session",
            metadata={"test": True}
        )

        results = mem0_store.search("Test content", scope="session", top_k=1)

        # Should return results (mem0 semantic or InMemoryStore recency-based)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_mem0_scope_isolation(self, mem0_store):
        """MemoryStore should isolate scopes via namespace."""
        mem0_store.add(
            content="Session only content",
            scope="session",
            metadata={"scope": "session"}
        )

        # Search in different scope
        results = mem0_store.search("Session only", scope="corpus", top_k=5)

        # Should not find session content in corpus scope
        for r in results:
            content = str(r.get("content", "") or r.get("memory", ""))
            assert "Session only content" not in content
