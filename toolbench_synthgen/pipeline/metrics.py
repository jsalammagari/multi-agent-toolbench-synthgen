from __future__ import annotations

import json
from dataclasses import dataclass
from math import log2
from pathlib import Path
from typing import Dict, List, Set, Tuple

from toolbench_synthgen.models import ConversationRecord


def _load_conversations(path: str) -> List[ConversationRecord]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset '{path}' does not exist.")
    records: List[ConversationRecord] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(ConversationRecord.model_validate_json(line))
    return records


def _jaccard_distance(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return 1.0 - inter / union


@dataclass
class MetricsResult:
    diversity_jaccard: float
    mgr_mean: float
    mgr_min: float
    mgr_max: float
    mgr_histogram: Dict[str, int]
    pattern_entropy: float


class MetricsComputer:
    """Compute diversity and memory-grounding metrics for one or two datasets."""

    def compute_for_dataset(self, path: str) -> MetricsResult:
        convos = _load_conversations(path)
        if not convos:
            raise ValueError("Dataset is empty.")

        # Diversity: pairwise Jaccard over tool_ids_used sets.
        tool_sets: List[Set[str]] = [
            set(c.metadata.tool_ids_used) for c in convos
        ]
        distances: List[float] = []
        for i in range(len(tool_sets)):
            for j in range(i + 1, len(tool_sets)):
                distances.append(_jaccard_distance(tool_sets[i], tool_sets[j]))
        diversity = sum(distances) / len(distances) if distances else 0.0

        # memory_grounding_rate stats.
        mgr_values = [
            c.metadata.memory_grounding_rate
            for c in convos
            if c.metadata.memory_grounding_rate is not None
        ]
        if mgr_values:
            mgr_mean = sum(mgr_values) / len(mgr_values)
            mgr_min = min(mgr_values)
            mgr_max = max(mgr_values)
            buckets = {"0.0": 0, "(0.0,0.5]": 0, "(0.5,1.0)": 0, "1.0": 0}
            for v in mgr_values:
                if v == 0.0:
                    buckets["0.0"] += 1
                elif 0.0 < v <= 0.5:
                    buckets["(0.0,0.5]"] += 1
                elif 0.5 < v < 1.0:
                    buckets["(0.5,1.0)"] += 1
                elif v == 1.0:
                    buckets["1.0"] += 1
        else:
            mgr_mean = mgr_min = mgr_max = 0.0
            buckets = {"0.0": 0, "(0.0,0.5]": 0, "(0.5,1.0)": 0, "1.0": 0}

        # Entropy over pattern_type.
        counts: Dict[str, int] = {}
        for c in convos:
            pt = c.metadata.pattern_type or "unknown"
            counts[pt] = counts.get(pt, 0) + 1
        total = sum(counts.values())
        entropy = 0.0
        for n in counts.values():
            p = n / total
            entropy -= p * log2(p)

        return MetricsResult(
            diversity_jaccard=diversity,
            mgr_mean=mgr_mean,
            mgr_min=mgr_min,
            mgr_max=mgr_max,
            mgr_histogram=buckets,
            pattern_entropy=entropy,
        )

