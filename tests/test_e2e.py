"""End-to-end test that builds artifacts and generates a dataset of at least 50 samples."""
import pytest
import json
from pathlib import Path
from toolbench_synthgen.registry import load_toolbench_tools, ToolRegistry
from toolbench_synthgen.graph import build_tool_graph
from toolbench_synthgen.pipeline import generate_dataset, DatasetValidator


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture
    def toolbench_sample_dir(self, tmp_path):
        """Create a sample ToolBench directory with multiple tools."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # Create multiple tool definitions for variety
        tools = [
            {
                "tool_name": f"tool_{i}",
                "standardized_name": f"tool_{i}",
                "tool_description": f"Test tool {i}",
                "category": f"Category_{i % 5}",
                "api_list": [
                    {
                        "name": f"endpoint_{j}",
                        "description": f"Endpoint {j} of tool {i}",
                        "required_parameters": [
                            {"name": "param1", "type": "string", "description": "Required param"}
                        ],
                        "optional_parameters": [
                            {"name": "lang", "type": "string", "default": "en"}
                        ]
                    }
                    for j in range(3)  # 3 endpoints per tool
                ]
            }
            for i in range(20)  # 20 tools total = 60 endpoints
        ]

        for i, tool in enumerate(tools):
            tool_file = tools_dir / f"tool_{i}.json"
            tool_file.write_text(json.dumps(tool))

        return tools_dir

    @pytest.fixture
    def built_artifacts(self, toolbench_sample_dir, tmp_path):
        """Build registry and graph artifacts."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Load tools and create registry
        data = load_toolbench_tools(str(toolbench_sample_dir))
        registry = ToolRegistry(data)

        # Save registry
        registry_path = artifacts_dir / "tool_registry.json"
        registry.save(str(registry_path))

        # Build and save graph
        graph = build_tool_graph(registry)
        graph_path = artifacts_dir / "tool_graph.json"
        graph.save(str(graph_path))

        return {
            "registry_path": str(registry_path),
            "graph_path": str(graph_path),
            "artifacts_dir": artifacts_dir
        }

    def test_build_creates_registry_artifact(self, built_artifacts):
        """Build command should create tool_registry.json."""
        registry_path = Path(built_artifacts["registry_path"])
        assert registry_path.exists()

        with registry_path.open() as f:
            data = json.load(f)
        assert "tools" in data
        assert len(data["tools"]) == 20

    def test_build_creates_graph_artifact(self, built_artifacts):
        """Build command should create tool_graph.json."""
        graph_path = Path(built_artifacts["graph_path"])
        assert graph_path.exists()

        with graph_path.open() as f:
            data = json.load(f)
        assert "nodes" in data
        assert "edges" in data
        # Should have tool, endpoint, parameter, concept nodes
        node_types = {n["type"] for n in data["nodes"]}
        assert "tool" in node_types
        assert "endpoint" in node_types

    def test_graph_has_correct_node_counts(self, built_artifacts):
        """Graph should have expected number of nodes."""
        graph_path = Path(built_artifacts["graph_path"])

        with graph_path.open() as f:
            data = json.load(f)

        tool_nodes = [n for n in data["nodes"] if n["type"] == "tool"]
        endpoint_nodes = [n for n in data["nodes"] if n["type"] == "endpoint"]

        assert len(tool_nodes) == 20  # 20 tools
        assert len(endpoint_nodes) == 60  # 20 tools * 3 endpoints each

    def test_generate_at_least_50_samples(self, built_artifacts, tmp_path):
        """Generate command should produce at least 50 valid conversation samples."""
        output_path = tmp_path / "conversations.jsonl"

        # Generate 50+ conversations
        conversations = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=50,
            seed=42,
            corpus_memory_enabled=False,  # Use InMemoryStore for testing
        )

        # Verify count
        assert len(conversations) >= 50

        # Verify file was written
        assert output_path.exists()

        # Count lines in file
        with output_path.open() as f:
            lines = [line for line in f if line.strip()]
        assert len(lines) >= 50

    def test_generated_conversations_have_required_fields(self, built_artifacts, tmp_path):
        """Each generated conversation should have all required metadata fields."""
        output_path = tmp_path / "conversations.jsonl"

        conversations = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=10,
            seed=42,
            corpus_memory_enabled=False,
        )

        required_metadata_fields = [
            "seed",
            "tool_ids_used",
            "num_turns",
            "num_clarification_questions",
            "memory_grounding_rate",
            "corpus_memory_enabled",
        ]

        for convo in conversations:
            # Check conversation structure
            assert convo.conversation_id is not None
            assert len(convo.messages) > 0
            assert convo.metadata is not None

            # Check all required metadata fields
            for field in required_metadata_fields:
                assert hasattr(convo.metadata, field), f"Missing field: {field}"

    def test_generated_conversations_have_multi_step_traces(self, built_artifacts, tmp_path):
        """Substantial portion should have ≥3 tool calls (multi-step)."""
        output_path = tmp_path / "conversations.jsonl"

        conversations = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=50,
            seed=42,
            corpus_memory_enabled=False,
        )

        multi_step_count = sum(1 for c in conversations if len(c.tool_calls) >= 3)

        # At least 80% should be multi-step (sampler enforces min_length=3)
        assert multi_step_count >= 40, f"Only {multi_step_count}/50 have ≥3 tool calls"

    def test_generated_conversations_have_multi_tool_traces(self, built_artifacts, tmp_path):
        """Substantial portion should use ≥2 distinct tools (multi-tool)."""
        output_path = tmp_path / "conversations.jsonl"

        conversations = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=50,
            seed=42,
            corpus_memory_enabled=False,
        )

        multi_tool_count = sum(
            1 for c in conversations
            if len(set(call.endpoint_id.split('.')[0] for call in c.tool_calls)) >= 2
        )

        # At least 50% should be multi-tool (graph sampling is random)
        assert multi_tool_count >= 25, f"Only {multi_tool_count}/50 use ≥2 distinct tools"

    def test_validate_command_passes_on_generated_data(self, built_artifacts, tmp_path):
        """Validate command should pass on properly generated data."""
        output_path = tmp_path / "conversations.jsonl"

        generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=50,
            seed=42,
            corpus_memory_enabled=False,
        )

        validator = DatasetValidator()
        summary = validator.validate_dataset(str(output_path))

        # Should have no schema errors
        assert summary.schema_errors == 0, f"Schema errors: {summary.details}"

        # Should have no linkage errors
        assert summary.linkage_errors == 0, f"Linkage errors: {summary.details}"

    def test_determinism_same_seed_same_output(self, built_artifacts, tmp_path):
        """Same seed should produce identical output."""
        output_path_1 = tmp_path / "run1.jsonl"
        output_path_2 = tmp_path / "run2.jsonl"

        # Generate twice with same seed
        convos_1 = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path_1),
            num_conversations=10,
            seed=12345,
            corpus_memory_enabled=False,
        )

        convos_2 = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path_2),
            num_conversations=10,
            seed=12345,
            corpus_memory_enabled=False,
        )

        # Should produce identical conversations
        assert len(convos_1) == len(convos_2)
        for c1, c2 in zip(convos_1, convos_2):
            assert c1.conversation_id == c2.conversation_id
            assert len(c1.tool_calls) == len(c2.tool_calls)
            for tc1, tc2 in zip(c1.tool_calls, c2.tool_calls):
                assert tc1.endpoint_id == tc2.endpoint_id

    def test_different_seeds_produce_different_output(self, built_artifacts, tmp_path):
        """Different seeds should produce different output."""
        output_path_1 = tmp_path / "seed1.jsonl"
        output_path_2 = tmp_path / "seed2.jsonl"

        convos_1 = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path_1),
            num_conversations=10,
            seed=111,
            corpus_memory_enabled=False,
        )

        convos_2 = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path_2),
            num_conversations=10,
            seed=222,
            corpus_memory_enabled=False,
        )

        # At least some conversations should differ
        differences = 0
        for c1, c2 in zip(convos_1, convos_2):
            if c1.tool_calls and c2.tool_calls:
                if c1.tool_calls[0].endpoint_id != c2.tool_calls[0].endpoint_id:
                    differences += 1

        assert differences > 0, "Different seeds should produce different outputs"

    def test_corpus_memory_flag_affects_output(self, built_artifacts, tmp_path):
        """--no-corpus-memory flag should be reflected in metadata."""
        output_disabled = tmp_path / "disabled.jsonl"

        convos_disabled = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_disabled),
            num_conversations=5,
            seed=42,
            corpus_memory_enabled=False,
        )

        # Check metadata reflects the flag for disabled corpus memory
        for c in convos_disabled:
            assert c.metadata.corpus_memory_enabled == False

        # Test with corpus memory enabled
        # Now uses local Hugging Face embeddings - no API key required
        output_enabled = tmp_path / "enabled.jsonl"
        convos_enabled = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_enabled),
            num_conversations=5,
            seed=42,
            corpus_memory_enabled=True,
        )

        for c in convos_enabled:
            assert c.metadata.corpus_memory_enabled == True

    def test_output_format_is_valid_jsonl(self, built_artifacts, tmp_path):
        """Output should be valid JSONL (one JSON object per line)."""
        output_path = tmp_path / "output.jsonl"

        generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=10,
            seed=42,
            corpus_memory_enabled=False,
        )

        with output_path.open() as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    assert isinstance(obj, dict)
                    assert "conversation_id" in obj
                    assert "messages" in obj
                    assert "tool_calls" in obj
                    assert "tool_outputs" in obj
                    assert "metadata" in obj
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON on line {line_num}: {e}")

    def test_tool_calls_have_valid_endpoint_ids(self, built_artifacts, tmp_path):
        """All tool calls should reference valid endpoint IDs."""
        output_path = tmp_path / "output.jsonl"

        conversations = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=20,
            seed=42,
            corpus_memory_enabled=False,
        )

        # Load registry to check endpoint IDs
        registry = ToolRegistry.load(built_artifacts["registry_path"])
        valid_endpoints = {e.id for e in registry.endpoints}

        for convo in conversations:
            for call in convo.tool_calls:
                assert call.endpoint_id in valid_endpoints, \
                    f"Invalid endpoint_id: {call.endpoint_id}"

    def test_tool_outputs_link_to_tool_calls(self, built_artifacts, tmp_path):
        """Each tool output should reference a valid tool call ID."""
        output_path = tmp_path / "output.jsonl"

        conversations = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=20,
            seed=42,
            corpus_memory_enabled=False,
        )

        for convo in conversations:
            call_ids = {call.id for call in convo.tool_calls}
            for output in convo.tool_outputs:
                assert output.tool_call_id in call_ids, \
                    f"Output {output.id} references missing call {output.tool_call_id}"

    def test_memory_grounding_rate_computed(self, built_artifacts, tmp_path):
        """memory_grounding_rate should be computed for conversations with multiple tool calls."""
        output_path = tmp_path / "output.jsonl"

        conversations = generate_dataset(
            registry_path=built_artifacts["registry_path"],
            graph_path=built_artifacts["graph_path"],
            output_path=str(output_path),
            num_conversations=20,
            seed=42,
            corpus_memory_enabled=False,
        )

        for convo in conversations:
            non_first_calls = [c for c in convo.tool_calls if c.step_index > 0]
            if non_first_calls:
                # Should have a computed rate
                assert convo.metadata.memory_grounding_rate is not None
                assert 0.0 <= convo.metadata.memory_grounding_rate <= 1.0
            else:
                # No non-first calls, rate should be None
                assert convo.metadata.memory_grounding_rate is None


class TestDatasetValidator:
    """Tests for the DatasetValidator class."""

    @pytest.fixture
    def valid_dataset(self, tmp_path):
        """Create a valid dataset file."""
        output_path = tmp_path / "valid.jsonl"

        conversations = [
            {
                "conversation_id": f"conv_{i}",
                "messages": [
                    {"role": "user", "content": "Request"},
                    {"role": "assistant", "content": "Response 1", "tool_call_id": "call_0"},
                    {"role": "assistant", "content": "Response 2", "tool_call_id": "call_1"},
                    {"role": "assistant", "content": "Response 3", "tool_call_id": "call_2"},
                ],
                "tool_calls": [
                    {"id": "call_0", "endpoint_id": f"tool_{i}.endpoint_0", "arguments": {}, "step_index": 0},
                    {"id": "call_1", "endpoint_id": f"tool_{i+1}.endpoint_0", "arguments": {"from_memory": True}, "step_index": 1},
                    {"id": "call_2", "endpoint_id": f"tool_{i+2}.endpoint_0", "arguments": {"from_memory": True}, "step_index": 2},
                ],
                "tool_outputs": [
                    {"id": "out_0", "tool_call_id": "call_0", "payload": {}, "derived_ids": {}},
                    {"id": "out_1", "tool_call_id": "call_1", "payload": {}, "derived_ids": {}},
                    {"id": "out_2", "tool_call_id": "call_2", "payload": {}, "derived_ids": {}},
                ],
                "metadata": {
                    "seed": 42,
                    "tool_ids_used": [f"tool_{i}", f"tool_{i+1}", f"tool_{i+2}"],
                    "num_turns": 4,
                    "num_clarification_questions": 0,
                    "memory_grounding_rate": 1.0,
                    "corpus_memory_enabled": True,
                    "pattern_type": "sequential"
                }
            }
            for i in range(10)
        ]

        with output_path.open("w") as f:
            for c in conversations:
                f.write(json.dumps(c) + "\n")

        return output_path

    def test_validator_passes_valid_dataset(self, valid_dataset):
        """Validator should pass on valid dataset."""
        validator = DatasetValidator()
        summary = validator.validate_dataset(str(valid_dataset))

        assert summary.schema_errors == 0
        assert summary.linkage_errors == 0

    def test_validator_detects_schema_errors(self, tmp_path):
        """Validator should detect schema errors."""
        output_path = tmp_path / "invalid_schema.jsonl"

        with output_path.open("w") as f:
            f.write('{"invalid": "missing required fields"}\n')

        validator = DatasetValidator()
        summary = validator.validate_dataset(str(output_path))

        assert summary.schema_errors > 0

    def test_validator_detects_linkage_errors(self, tmp_path):
        """Validator should detect when tool_output references invalid tool_call."""
        output_path = tmp_path / "invalid_linkage.jsonl"

        conversation = {
            "conversation_id": "test",
            "messages": [{"role": "user", "content": "Hi"}],
            "tool_calls": [
                {"id": "call_0", "endpoint_id": "api.endpoint", "arguments": {}, "step_index": 0}
            ],
            "tool_outputs": [
                {"id": "out_0", "tool_call_id": "nonexistent_call", "payload": {}, "derived_ids": {}}
            ],
            "metadata": {
                "seed": 42,
                "tool_ids_used": [],
                "num_turns": 1,
                "num_clarification_questions": 0,
                "memory_grounding_rate": None,
                "corpus_memory_enabled": True
            }
        }

        with output_path.open("w") as f:
            f.write(json.dumps(conversation) + "\n")

        validator = DatasetValidator()
        summary = validator.validate_dataset(str(output_path))

        assert summary.linkage_errors > 0

    def test_validator_detects_multi_step_violations(self, tmp_path):
        """Validator should flag conversations with < 3 tool calls."""
        output_path = tmp_path / "few_tools.jsonl"

        conversation = {
            "conversation_id": "test",
            "messages": [{"role": "user", "content": "Hi"}],
            "tool_calls": [
                {"id": "call_0", "endpoint_id": "api.endpoint", "arguments": {}, "step_index": 0}
            ],
            "tool_outputs": [
                {"id": "out_0", "tool_call_id": "call_0", "payload": {}, "derived_ids": {}}
            ],
            "metadata": {
                "seed": 42,
                "tool_ids_used": ["api"],
                "num_turns": 1,
                "num_clarification_questions": 0,
                "memory_grounding_rate": None,
                "corpus_memory_enabled": True
            }
        }

        with output_path.open("w") as f:
            f.write(json.dumps(conversation) + "\n")

        validator = DatasetValidator()
        summary = validator.validate_dataset(str(output_path))

        assert summary.multi_step_violations > 0
