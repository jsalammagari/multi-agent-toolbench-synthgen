from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from toolbench_synthgen.models import Message
from toolbench_synthgen.agents.planner import ConversationPlan, PlanStep


@dataclass
class UserState:
    provided_params: Dict[str, Dict[str, str]]


class UserProxyAgent:
    """Simulated user that follows a conversation plan."""

    def __init__(self) -> None:
        self.state = UserState(provided_params={})

    def initial_message(self, plan: ConversationPlan) -> Message:
        content = f"{plan.goal}"
        return Message(role="user", content=content)

    def answer_clarification(self, step: PlanStep) -> Message:
        endpoint_id = step.endpoint_id or "endpoint"
        # For now, answer all clarifications with generic but usable values.
        params = self.state.provided_params.setdefault(endpoint_id, {})
        params["lang"] = params.get("lang", "en")
        content = f"For {endpoint_id}, you can use lang='en'."
        return Message(role="user", content=content)

