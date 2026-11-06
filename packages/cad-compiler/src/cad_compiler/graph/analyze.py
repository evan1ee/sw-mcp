"""Graph analysis and topological sorting (spec 5.7.1, 6.7.2)."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from cad_ir.part_feature_graph.model import PartGraph, SolidNode


class GraphCycleError(ValueError):
    """Raised when a dependency cycle is detected in the graph."""


@dataclass(frozen=True, slots=True)
class GraphAnalysis:
    """Analyzed graph structure with topological build order and dependency maps."""

    order: tuple[str, ...]
    dependencies: Mapping[str, frozenset[str]]
    dependents: Mapping[str, frozenset[str]]
    cycle: tuple[str, ...] | None = None


def resolve_dependencies(graph: PartGraph) -> dict[str, set[str]]:
    """Collect all dependencies per node, including implied profile dependencies."""
    deps: dict[str, set[str]] = {node_id: set() for node_id in graph.nodes}
    for node_id, node in graph.nodes.items():
        for d in node.dependencies:
            deps[node_id].add(d)
        if isinstance(node, SolidNode) and node.profile in graph.nodes:
            deps[node_id].add(node.profile)
    return deps


def analyze_graph(graph: PartGraph) -> GraphAnalysis:
    """Perform topological sort and dependency analysis on the feature graph.

    Ties are broken by node ID in ascending order (spec 5.7.1).
    """
    deps = resolve_dependencies(graph)
    dependents: dict[str, set[str]] = defaultdict(set)
    in_degree: dict[str, int] = {}

    for node_id, d_set in deps.items():
        # Only count in-degree for dependencies that exist in graph
        valid_deps = {d for d in d_set if d in graph.nodes}
        in_degree[node_id] = len(valid_deps)
        for d in valid_deps:
            dependents[d].add(node_id)

    # Ready queue with tie-breaking by node ID
    ready = sorted([nid for nid, deg in in_degree.items() if deg == 0])
    order: list[str] = []

    while ready:
        curr = ready.pop(0)
        order.append(curr)
        newly_ready: list[str] = []
        for dep in sorted(dependents[curr]):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                newly_ready.append(dep)
        # Re-sort ready list to maintain tie-breaking by ID
        ready = sorted(ready + newly_ready)

    if len(order) < len(graph.nodes):
        # Cycle detected among unvisited nodes
        unvisited = tuple(sorted(set(graph.nodes) - set(order)))
        return GraphAnalysis(
            order=tuple(order),
            dependencies={k: frozenset(v) for k, v in deps.items()},
            dependents={k: frozenset(v) for k, v in dependents.items()},
            cycle=unvisited,
        )

    return GraphAnalysis(
        order=tuple(order),
        dependencies={k: frozenset(v) for k, v in deps.items()},
        dependents={k: frozenset(v) for k, v in dependents.items()},
        cycle=None,
    )


def build_order(graph: PartGraph) -> tuple[str, ...]:
    """Return the deterministic topological build order of nodes in graph (spec 5.7.1).

    Raises GraphCycleError if dependencies contain a cycle.
    """
    analysis = analyze_graph(graph)
    if analysis.cycle is not None:
        raise GraphCycleError(f"Dependency cycle detected involving nodes: {analysis.cycle}")
    return analysis.order
