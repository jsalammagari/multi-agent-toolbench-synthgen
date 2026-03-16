from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str
    tool_call_id: Optional[str] = None


class ToolCall(BaseModel):
    id: str
    endpoint_id: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    step_index: int


class ToolOutput(BaseModel):
    id: str
    tool_call_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    derived_ids: Dict[str, str] = Field(default_factory=dict)


class ConversationMetadata(BaseModel):
    seed: int
    tool_ids_used: List[str] = Field(default_factory=list)
    num_turns: int = 0
    num_clarification_questions: int = 0
    memory_grounding_rate: Optional[float] = None
    corpus_memory_enabled: Optional[bool] = None
    pattern_type: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class ConversationRecord(BaseModel):
    conversation_id: str
    messages: List[Message]
    tool_calls: List[ToolCall]
    tool_outputs: List[ToolOutput]
    metadata: ConversationMetadata

