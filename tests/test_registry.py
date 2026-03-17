"""Unit tests for registry parsing and validation."""
import pytest
import json
from pathlib import Path
from toolbench_synthgen.registry import load_toolbench_tools, ToolRegistry
from toolbench_synthgen.registry.models import Tool, Endpoint, Parameter


class TestRegistryLoader:
    """Tests for load_toolbench_tools function."""

    def test_load_valid_toolbench_json(self, tmp_path):
        """Should correctly parse a valid ToolBench JSON file."""
        # Create valid tool JSON
        tool_json = {
            "tool_name": "weather_api",
            "standardized_name": "weather_api",
            "tool_description": "Get weather data",
            "category": "Weather",
            "api_list": [
                {
                    "name": "get_forecast",
                    "description": "Get weather forecast",
                    "required_parameters": [
                        {"name": "city", "type": "string", "description": "City name"}
                    ],
                    "optional_parameters": [
                        {"name": "days", "type": "integer", "default": 7}
                    ]
                }
            ]
        }
        tool_file = tmp_path / "weather.json"
        tool_file.write_text(json.dumps(tool_json))

        result = load_toolbench_tools(str(tmp_path))

        assert len(result.tools) == 1
        assert result.tools[0].name == "weather_api"
        assert len(result.tools[0].endpoints) == 1
        assert result.tools[0].endpoints[0].name == "get_forecast"

    def test_load_handles_missing_fields(self, tmp_path):
        """Should use defaults when optional fields are missing."""
        minimal_json = {
            "api_list": [{"name": "endpoint1"}]
        }
        tool_file = tmp_path / "minimal.json"
        tool_file.write_text(json.dumps(minimal_json))

        result = load_toolbench_tools(str(tmp_path))

        assert len(result.tools) == 1
        # Tool name should fall back to filename stem
        assert result.tools[0].name == "minimal"

    def test_load_skips_invalid_json(self, tmp_path):
        """Should skip malformed JSON files without crashing."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json content")

        result = load_toolbench_tools(str(tmp_path))

        assert len(result.tools) == 0  # Skipped, not crashed

    def test_load_handles_empty_directory(self, tmp_path):
        """Should return empty registry for empty directory."""
        result = load_toolbench_tools(str(tmp_path))

        assert len(result.tools) == 0

    def test_load_nonexistent_directory_raises(self):
        """Should raise FileNotFoundError for non-existent path."""
        with pytest.raises(FileNotFoundError):
            load_toolbench_tools("/nonexistent/path")

    def test_load_parses_required_parameters(self, tmp_path):
        """Should correctly identify required vs optional parameters."""
        tool_json = {
            "tool_name": "test_api",
            "api_list": [{
                "name": "test_endpoint",
                "required_parameters": [
                    {"name": "required_param", "type": "string"}
                ],
                "optional_parameters": [
                    {"name": "optional_param", "type": "integer", "default": 10}
                ]
            }]
        }
        tool_file = tmp_path / "test.json"
        tool_file.write_text(json.dumps(tool_json))

        result = load_toolbench_tools(str(tmp_path))
        endpoint = result.tools[0].endpoints[0]

        required = [p for p in endpoint.parameters if p.required]
        optional = [p for p in endpoint.parameters if not p.required]

        assert len(required) == 1
        assert required[0].name == "required_param"
        assert len(optional) == 1
        assert optional[0].name == "optional_param"
        assert optional[0].default == 10

    def test_load_parses_enum_constraints(self, tmp_path):
        """Should preserve enum constraints on parameters."""
        tool_json = {
            "tool_name": "test_api",
            "api_list": [{
                "name": "test_endpoint",
                "optional_parameters": [
                    {"name": "format", "type": "string", "enum": ["json", "xml", "csv"]}
                ]
            }]
        }
        tool_file = tmp_path / "test.json"
        tool_file.write_text(json.dumps(tool_json))

        result = load_toolbench_tools(str(tmp_path))
        param = result.tools[0].endpoints[0].parameters[0]

        assert param.enum == ["json", "xml", "csv"]

    def test_load_handles_nested_directories(self, tmp_path):
        """Should recursively find JSON files in subdirectories."""
        # Create nested structure
        subdir = tmp_path / "category" / "subcategory"
        subdir.mkdir(parents=True)

        tool_json = {
            "tool_name": "nested_api",
            "api_list": [{"name": "endpoint1"}]
        }
        tool_file = subdir / "nested.json"
        tool_file.write_text(json.dumps(tool_json))

        result = load_toolbench_tools(str(tmp_path))

        assert len(result.tools) == 1
        assert result.tools[0].name == "nested_api"

    def test_load_extracts_category_as_tag(self, tmp_path):
        """Should extract category field as a tag."""
        tool_json = {
            "tool_name": "categorized_api",
            "category": "Weather",
            "api_list": [{"name": "endpoint1"}]
        }
        tool_file = tmp_path / "categorized.json"
        tool_file.write_text(json.dumps(tool_json))

        result = load_toolbench_tools(str(tmp_path))

        assert "Weather" in result.tools[0].tags


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    @pytest.fixture
    def sample_registry(self, tmp_path):
        """Create a sample registry for testing."""
        tool_json = {
            "tool_name": "weather_api",
            "standardized_name": "weather_api",
            "tool_description": "Weather API",
            "category": "Weather",
            "api_list": [
                {
                    "name": "get_forecast",
                    "description": "Get forecast",
                    "required_parameters": [{"name": "city", "type": "string"}]
                }
            ]
        }
        tool_file = tmp_path / "weather.json"
        tool_file.write_text(json.dumps(tool_json))

        data = load_toolbench_tools(str(tmp_path))
        return ToolRegistry(data)

    def test_registry_get_tool(self, sample_registry):
        """Should retrieve tool by ID."""
        tool = sample_registry.get_tool("weather_api")
        assert tool is not None
        assert tool.name == "weather_api"

    def test_registry_get_tool_not_found(self, sample_registry):
        """Should return None for non-existent tool."""
        tool = sample_registry.get_tool("nonexistent")
        assert tool is None

    def test_registry_get_endpoint(self, sample_registry):
        """Should retrieve endpoint by ID."""
        endpoint = sample_registry.get_endpoint("weather_api.get_forecast")
        assert endpoint is not None
        assert endpoint.name == "get_forecast"

    def test_registry_get_endpoint_not_found(self, sample_registry):
        """Should return None for non-existent endpoint."""
        endpoint = sample_registry.get_endpoint("nonexistent.endpoint")
        assert endpoint is None

    def test_registry_list_tools(self, sample_registry):
        """Should list all tools."""
        tools = list(sample_registry.tools)
        assert len(tools) == 1
        assert tools[0].name == "weather_api"

    def test_registry_list_endpoints(self, sample_registry):
        """Should list all endpoints."""
        endpoints = list(sample_registry.endpoints)
        assert len(endpoints) == 1
        assert endpoints[0].name == "get_forecast"

    def test_registry_save_and_load(self, sample_registry, tmp_path):
        """Should serialize and deserialize correctly."""
        save_path = tmp_path / "registry.json"
        sample_registry.save(str(save_path))

        loaded = ToolRegistry.load(str(save_path))

        assert len(list(loaded.tools)) == len(list(sample_registry.tools))
        assert len(list(loaded.endpoints)) == len(list(sample_registry.endpoints))

    def test_registry_get_parameters(self, sample_registry):
        """Should retrieve parameters for an endpoint."""
        params = sample_registry.get_parameters("weather_api.get_forecast")
        assert params is not None
        assert len(params) == 1
        assert params[0].name == "city"


class TestValidation:
    """Tests for conversation validation."""

    def test_validate_schema_valid_conversation(self, valid_conversation):
        """Should pass schema validation for valid conversation."""
        from toolbench_synthgen.models import ConversationRecord
        # Should not raise
        record = ConversationRecord.model_validate(valid_conversation)
        assert record.conversation_id == "test_conv_1"

    def test_validate_schema_missing_required_field(self):
        """Should fail validation when required field missing."""
        from toolbench_synthgen.models import ConversationRecord
        from pydantic import ValidationError

        invalid = {"conversation_id": "test"}  # Missing required fields

        with pytest.raises(ValidationError):
            ConversationRecord.model_validate(invalid)

    def test_validate_schema_invalid_message_role(self):
        """Should accept valid message roles."""
        from toolbench_synthgen.models import ConversationRecord

        conversation = {
            "conversation_id": "test",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
                {"role": "tool", "content": "Result"}
            ],
            "tool_calls": [],
            "tool_outputs": [],
            "metadata": {
                "seed": 42,
                "tool_ids_used": [],
                "num_turns": 3,
                "num_clarification_questions": 0,
                "memory_grounding_rate": None,
                "corpus_memory_enabled": True
            }
        }

        # Should not raise
        record = ConversationRecord.model_validate(conversation)
        assert len(record.messages) == 3

    def test_validate_tool_call_structure(self):
        """Should validate tool call structure."""
        from toolbench_synthgen.models import ToolCall

        tool_call = {
            "id": "call_0",
            "endpoint_id": "api.endpoint",
            "arguments": {"param": "value"},
            "step_index": 0
        }

        tc = ToolCall.model_validate(tool_call)
        assert tc.id == "call_0"
        assert tc.endpoint_id == "api.endpoint"

    def test_validate_tool_output_structure(self):
        """Should validate tool output structure."""
        from toolbench_synthgen.models import ToolOutput

        tool_output = {
            "id": "out_0",
            "tool_call_id": "call_0",
            "payload": {"result": "data"},
            "derived_ids": {"result_id": "123"}
        }

        to = ToolOutput.model_validate(tool_output)
        assert to.id == "out_0"
        assert to.tool_call_id == "call_0"

    def test_validate_metadata_fields(self):
        """Should validate all required metadata fields."""
        from toolbench_synthgen.models import ConversationMetadata

        metadata = {
            "seed": 42,
            "tool_ids_used": ["api1", "api2"],
            "num_turns": 5,
            "num_clarification_questions": 2,
            "memory_grounding_rate": 0.75,
            "corpus_memory_enabled": True,
            "pattern_type": "sequential"
        }

        m = ConversationMetadata.model_validate(metadata)
        assert m.seed == 42
        assert m.memory_grounding_rate == 0.75
