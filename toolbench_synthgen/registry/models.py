from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Parameter(BaseModel):
    name: str
    type: str = "string"
    required: bool = False
    description: Optional[str] = None
    enum: Optional[List[Any]] = None
    default: Optional[Any] = None


class ResponseField(BaseModel):
    name: str
    type: str = "string"
    description: Optional[str] = None


class Endpoint(BaseModel):
    id: str
    tool_id: str
    name: str
    description: Optional[str] = None
    parameters: List[Parameter] = Field(default_factory=list)
    response_fields: List[ResponseField] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Tool(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    endpoints: List[Endpoint] = Field(default_factory=list)


class ToolRegistryData(BaseModel):
    tools: List[Tool]

