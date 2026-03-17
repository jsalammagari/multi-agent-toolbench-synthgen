from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List

from .models import Endpoint, Parameter, ResponseField, Tool, ToolRegistryData

logger = logging.getLogger(__name__)


def _iter_tool_files(root: Path) -> List[Path]:
    """Recursively find candidate ToolBench tool JSON files under root."""
    files: List[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".json"):
                files.append(Path(dirpath) / name)
    return files


def load_toolbench_tools(root: str) -> ToolRegistryData:
    """Load ToolBench-style tool definitions from a directory into a ToolRegistryData.

    This loader is designed to be tolerant of missing or slightly inconsistent fields.
    It expects each JSON file to roughly follow the ToolBench `toolenv` convention:

    {
        "tool_description": "...",
        "tool_name": "...",
        "standardized_name": "...",
        "api_list": [
            {
                "name": "get_foo",
                "description": "...",
                "required_parameters": [...],
                "optional_parameters": [...],
                ...
            }
        ],
        "category": "Sports",
        ...
    }
    """
    root_path = Path(root)
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"ToolBench path '{root}' does not exist or is not a directory.")

    tools: List[Tool] = []
    skipped_files: List[str] = []
    for path in _iter_tool_files(root_path):
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"Skipping {path}: Invalid JSON - {e}")
            skipped_files.append(str(path))
            continue
        except PermissionError:
            logger.warning(f"Skipping {path}: Permission denied")
            skipped_files.append(str(path))
            continue
        except Exception as e:
            logger.warning(f"Skipping {path}: {type(e).__name__} - {e}")
            skipped_files.append(str(path))
            continue

        tool_name = raw.get("standardized_name") or raw.get("tool_name") or path.stem
        tool_id = tool_name
        tool_desc = raw.get("tool_description") or raw.get("title")

        tags: List[str] = []
        category = raw.get("category_name") or raw.get("category")
        if isinstance(category, str):
            tags.append(category)

        endpoints: List[Endpoint] = []
        for api in raw.get("api_list", []):
            endpoint_name = api.get("name") or "endpoint"
            endpoint_id = f"{tool_id}.{endpoint_name}"
            ep_desc = api.get("description")

            params: List[Parameter] = []

            for p in api.get("required_parameters", []) or []:
                if isinstance(p, dict):
                    pname = p.get("name") or p.get("key") or "param"
                    ptype = p.get("type") or "string"
                    pdesc = p.get("description")
                else:
                    pname = str(p)
                    ptype = "string"
                    pdesc = None
                params.append(
                    Parameter(
                        name=pname,
                        type=ptype,
                        required=True,
                        description=pdesc,
                    )
                )

            for p in api.get("optional_parameters", []) or []:
                if isinstance(p, dict):
                    pname = p.get("name") or p.get("key") or "param"
                    ptype = p.get("type") or "string"
                    pdesc = p.get("description")
                    default = p.get("default")
                    enum = p.get("enum")
                else:
                    pname = str(p)
                    ptype = "string"
                    pdesc = None
                    default = None
                    enum = None
                params.append(
                    Parameter(
                        name=pname,
                        type=ptype,
                        required=False,
                        description=pdesc,
                        default=default,
                        enum=enum,
                    )
                )

            # ToolBench toolenv files often do not include a structured response schema;
            # we keep response_fields empty and retain the raw api json in metadata.
            response_fields: List[ResponseField] = []

            endpoints.append(
                Endpoint(
                    id=endpoint_id,
                    tool_id=tool_id,
                    name=endpoint_name,
                    description=ep_desc,
                    parameters=params,
                    response_fields=response_fields,
                    metadata={"source_file": str(path), "raw": api},
                )
            )

        tools.append(
            Tool(
                id=tool_id,
                name=tool_name,
                description=tool_desc,
                metadata={"source_file": str(path), "raw": raw},
                tags=tags,
                endpoints=endpoints,
            )
        )

    if skipped_files:
        logger.info(f"Skipped {len(skipped_files)} files due to errors")

    return ToolRegistryData(tools=tools)
