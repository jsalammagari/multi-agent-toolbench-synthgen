from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from toolbench_synthgen.models import ToolCall, ToolOutput
from toolbench_synthgen.registry import ToolRegistry


class ValidationError(Exception):
    def __init__(self, endpoint_id: str, errors: Dict[str, str]) -> None:
        super().__init__(f"Validation failed for {endpoint_id}: {errors}")
        self.endpoint_id = endpoint_id
        self.errors = errors


@dataclass
class OfflineExecutor:
    registry: ToolRegistry
    seed: int = 42

    def _rng_for_call(self, endpoint_id: str, arguments: Dict[str, Any]) -> random.Random:
        key = f"{self.seed}:{endpoint_id}:{sorted(arguments.items())}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        seed_int = int(digest[:16], 16)
        return random.Random(seed_int)

    def validate_args(self, endpoint_id: str, arguments: Dict[str, Any]) -> None:
        endpoint = self.registry.get_endpoint(endpoint_id)
        if not endpoint:
            raise ValidationError(endpoint_id, {"endpoint": "Unknown endpoint"})

        errors: Dict[str, str] = {}
        for param in endpoint.parameters:
            if param.required and param.name not in arguments:
                errors[param.name] = "Missing required parameter"

        if errors:
            raise ValidationError(endpoint_id, errors)

    def execute(
        self,
        endpoint_id: str,
        arguments: Dict[str, Any],
        session_state: Dict[str, Any],
        step_index: int,
    ) -> Tuple[ToolCall, ToolOutput, Dict[str, Any]]:
        try:
            self.validate_args(endpoint_id, arguments)
        except ValidationError as e:
            call = ToolCall(
                id=f"call_{step_index}",
                endpoint_id=endpoint_id,
                arguments=arguments,
                step_index=step_index,
            )
            output = ToolOutput(
                id=f"out_{step_index}",
                tool_call_id=call.id,
                payload={"error": e.errors},
                derived_ids={},
            )
            return call, output, session_state

        rng = self._rng_for_call(endpoint_id, arguments)

        call = ToolCall(
            id=f"call_{step_index}",
            endpoint_id=endpoint_id,
            arguments=arguments,
            step_index=step_index,
        )

        object_id = f"obj_{rng.randint(1, 10_000)}"
        payload = {
            "result_id": object_id,
            "endpoint": endpoint_id,
            "echo": arguments,
        }

        output = ToolOutput(
            id=f"out_{step_index}",
            tool_call_id=call.id,
            payload=payload,
            derived_ids={"result_id": object_id},
        )

        session_objects = session_state.get("objects", {})
        session_objects[object_id] = payload
        session_state["objects"] = session_objects
        session_state["last_result"] = payload

        return call, output, session_state

