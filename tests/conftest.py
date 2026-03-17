"""Pytest configuration and shared fixtures."""
import pytest
import json
from pathlib import Path


@pytest.fixture
def sample_tool_json():
    """Return a valid ToolBench tool JSON structure."""
    return {
        "tool_name": "sample_api",
        "standardized_name": "sample_api",
        "tool_description": "A sample API for testing",
        "category": "Testing",
        "api_list": [
            {
                "name": "get_data",
                "description": "Get some data",
                "required_parameters": [
                    {"name": "id", "type": "string", "description": "The ID"}
                ],
                "optional_parameters": [
                    {"name": "format", "type": "string", "default": "json", "enum": ["json", "xml"]}
                ]
            },
            {
                "name": "post_data",
                "description": "Post some data",
                "required_parameters": [
                    {"name": "data", "type": "object", "description": "The data to post"}
                ],
                "optional_parameters": []
            }
        ]
    }


@pytest.fixture
def temp_toolbench_dir(tmp_path, sample_tool_json):
    """Create a temporary ToolBench-like directory structure."""
    tools_dir = tmp_path / "toolenv" / "tools"
    tools_dir.mkdir(parents=True)

    # Create sample tool file
    tool_file = tools_dir / "sample_api.json"
    tool_file.write_text(json.dumps(sample_tool_json))

    return tmp_path


@pytest.fixture
def sample_conversation_record():
    """Return a valid ConversationRecord dict."""
    return {
        "conversation_id": "test_conv_001",
        "messages": [
            {"role": "user", "content": "I need weather data for New York"},
            {"role": "assistant", "content": "I'll get the weather forecast for New York."},
            {"role": "assistant", "content": "The forecast shows sunny weather.", "tool_call_id": "call_0"}
        ],
        "tool_calls": [
            {
                "id": "call_0",
                "endpoint_id": "weather_api.get_forecast",
                "arguments": {"city": "New York", "lang": "en"},
                "step_index": 0
            }
        ],
        "tool_outputs": [
            {
                "id": "out_0",
                "tool_call_id": "call_0",
                "payload": {"result_id": "res_123", "forecast": "sunny"},
                "derived_ids": {"result_id": "res_123"}
            }
        ],
        "metadata": {
            "seed": 42,
            "tool_ids_used": ["weather_api"],
            "num_turns": 3,
            "num_clarification_questions": 0,
            "memory_grounding_rate": None,
            "corpus_memory_enabled": True,
            "pattern_type": "sequential"
        }
    }


@pytest.fixture
def valid_conversation():
    """Create a valid conversation dict for testing."""
    return {
        "conversation_id": "test_conv_1",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ],
        "tool_calls": [],
        "tool_outputs": [],
        "metadata": {
            "seed": 42,
            "tool_ids_used": [],
            "num_turns": 2,
            "num_clarification_questions": 0,
            "memory_grounding_rate": None,
            "corpus_memory_enabled": True
        }
    }
