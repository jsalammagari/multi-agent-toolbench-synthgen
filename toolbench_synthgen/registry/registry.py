from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Endpoint, Parameter, Tool, ToolRegistryData


class ToolRegistry:
    """In-memory registry of tools and endpoints loaded from ToolBench definitions."""

    def __init__(self, data: ToolRegistryData) -> None:
        self._data = data
        self._tools_by_id: Dict[str, Tool] = {t.id: t for t in data.tools}
        self._endpoints_by_id: Dict[str, Endpoint] = {}
        for tool in data.tools:
            for endpoint in tool.endpoints:
                self._endpoints_by_id[endpoint.id] = endpoint

    @property
    def tools(self) -> Iterable[Tool]:
        return self._tools_by_id.values()

    @property
    def endpoints(self) -> Iterable[Endpoint]:
        return self._endpoints_by_id.values()

    def list_tools(self) -> List[Tool]:
        return list(self.tools)

    def list_endpoints(self) -> List[Endpoint]:
        return list(self.endpoints)

    def get_tool(self, tool_id: str) -> Optional[Tool]:
        return self._tools_by_id.get(tool_id)

    def get_endpoint(self, endpoint_id: str) -> Optional[Endpoint]:
        return self._endpoints_by_id.get(endpoint_id)

    def get_parameters(self, endpoint_id: str) -> List[Parameter]:
        ep = self.get_endpoint(endpoint_id)
        return list(ep.parameters) if ep else []

    def to_json_dict(self) -> Dict:
        return self._data.model_dump()

    def save(self, path: str) -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(self.to_json_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "ToolRegistry":
        in_path = Path(path)
        with in_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        data = ToolRegistryData.model_validate(raw)
        return cls(data)

