from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from toolbench_synthgen.agents.sampler import SampledToolChain


@dataclass
class PlanStep:
    kind: str  # "tool_call" or "clarification"
    endpoint_id: Optional[str] = None
    missing_params: Optional[List[str]] = None


@dataclass
class ConversationPlan:
    goal: str
    domain: Optional[str]
    steps: List[PlanStep]


class PlannerAgent:
    """Plan a conversation around a sampled tool chain."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def plan(
        self,
        chain: SampledToolChain,
        corpus_summaries: List[Dict[str, Any]],
    ) -> ConversationPlan:
        domain = chain.tags[0] if chain.tags else None

        # Very simple diversification: if corpus already contains this pattern_type + domain,
        # prefer mentioning that we explore a slightly different variant in the goal text.
        seen_patterns = {
            (s.get("pattern_type"), s.get("domain"))
            for s in (summary.get("metadata", {}) for summary in corpus_summaries)
        }
        pattern_key = (chain.pattern_type, domain)
        diversified = pattern_key in seen_patterns

        goal_domain = domain or "a realistic user scenario"
        if diversified:
            goal = f"Explore a new variation of {goal_domain} using tools {', '.join(chain.tools_used)}."
        else:
            goal = f"Use tools {', '.join(chain.tools_used)} to accomplish a {goal_domain} task."

        steps: List[PlanStep] = []
        for endpoint_id in chain.endpoint_ids:
            # For now, always allow one clarification step before each tool call.
            steps.append(PlanStep(kind="clarification", endpoint_id=endpoint_id))
            steps.append(PlanStep(kind="tool_call", endpoint_id=endpoint_id))

        return ConversationPlan(goal=goal, domain=domain, steps=steps)

