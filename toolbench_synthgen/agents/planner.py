from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from toolbench_synthgen.agents.sampler import SampledToolChain


@dataclass
class PlanStep:
    kind: str  # "tool_call", "clarification", or "parallel_tool_calls"
    endpoint_id: Optional[str] = None
    missing_params: Optional[List[str]] = None
    # For parallel_tool_calls, list of endpoint_ids to call in parallel
    parallel_endpoints: List[str] = field(default_factory=list)


@dataclass
class ConversationPlan:
    goal: str
    domain: Optional[str]
    steps: List[PlanStep]
    pattern_type: str = "sequential"


class PlannerAgent:
    """Plan a conversation around a sampled tool chain.

    Handles different tool-calling patterns:
    - sequential: Each tool call happens one after another
    - parallel: Multiple tools are called at once (shown as a group)
    - branching: One initial tool, then multiple parallel follow-ups
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def _build_sequential_steps(self, chain: SampledToolChain) -> List[PlanStep]:
        """Build steps for sequential pattern: clarification -> tool_call for each."""
        steps: List[PlanStep] = []
        for endpoint_id in chain.endpoint_ids:
            steps.append(PlanStep(kind="clarification", endpoint_id=endpoint_id))
            steps.append(PlanStep(kind="tool_call", endpoint_id=endpoint_id))
        return steps

    def _build_parallel_steps(self, chain: SampledToolChain) -> List[PlanStep]:
        """Build steps for parallel pattern: one clarification, then parallel tool calls."""
        steps: List[PlanStep] = []
        # Single clarification for all parallel tools
        steps.append(PlanStep(
            kind="clarification",
            endpoint_id=chain.endpoint_ids[0],
            parallel_endpoints=chain.endpoint_ids,
        ))
        # All tools called in parallel
        steps.append(PlanStep(
            kind="parallel_tool_calls",
            parallel_endpoints=chain.endpoint_ids,
        ))
        return steps

    def _build_branching_steps(self, chain: SampledToolChain) -> List[PlanStep]:
        """Build steps for branching pattern: lead tool, then parallel follow-ups."""
        steps: List[PlanStep] = []

        if not chain.endpoint_ids:
            return steps

        # First tool is sequential (the "branch root")
        lead_endpoint = chain.endpoint_ids[0]
        steps.append(PlanStep(kind="clarification", endpoint_id=lead_endpoint))
        steps.append(PlanStep(kind="tool_call", endpoint_id=lead_endpoint))

        # Remaining tools are called in parallel (the "branches")
        if len(chain.endpoint_ids) > 1:
            branch_endpoints = chain.endpoint_ids[1:]
            steps.append(PlanStep(
                kind="clarification",
                endpoint_id=branch_endpoints[0],
                parallel_endpoints=branch_endpoints,
            ))
            steps.append(PlanStep(
                kind="parallel_tool_calls",
                parallel_endpoints=branch_endpoints,
            ))

        return steps

    def plan(
        self,
        chain: SampledToolChain,
        corpus_summaries: List[Dict[str, Any]],
    ) -> ConversationPlan:
        domain = chain.tags[0] if chain.tags else None

        # Diversification: if corpus already contains this pattern_type + domain,
        # prefer mentioning that we explore a slightly different variant in the goal text.
        seen_patterns = {
            (s.get("metadata", {}).get("pattern_type"), s.get("metadata", {}).get("domain"))
            for s in corpus_summaries
        }
        pattern_key = (chain.pattern_type, domain)
        diversified = pattern_key in seen_patterns

        goal_domain = domain or "a realistic user scenario"
        pattern_desc = self._pattern_description(chain.pattern_type)

        if diversified:
            goal = (
                f"Explore a new variation of {goal_domain} using tools "
                f"{', '.join(chain.tools_used)} in a {pattern_desc} pattern."
            )
        else:
            goal = (
                f"Use tools {', '.join(chain.tools_used)} to accomplish a {goal_domain} task "
                f"with a {pattern_desc} approach."
            )

        # Build steps based on pattern type
        if chain.pattern_type == "parallel":
            steps = self._build_parallel_steps(chain)
        elif chain.pattern_type == "branching":
            steps = self._build_branching_steps(chain)
        else:  # sequential (default)
            steps = self._build_sequential_steps(chain)

        return ConversationPlan(
            goal=goal,
            domain=domain,
            steps=steps,
            pattern_type=chain.pattern_type,
        )

    def _pattern_description(self, pattern_type: str) -> str:
        """Return a human-readable description of the pattern."""
        descriptions = {
            "sequential": "step-by-step sequential",
            "parallel": "parallel multi-tool",
            "branching": "branching workflow",
        }
        return descriptions.get(pattern_type, "sequential")