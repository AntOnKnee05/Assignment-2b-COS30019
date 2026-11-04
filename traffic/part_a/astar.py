"""A* search (AS): minimize total edge cost with a safe distance estimate."""

from .node import Node, SearchResult, expand
from .frontier import PriorityFrontier


def heuristic_scale(problem):
    """Bound cost per unit distance using the cheapest edge ratio.

    For every edge u->v, scale * distance(u, v) <= cost(u, v).
    The triangle inequality then makes scaled distance to the nearest goal
    a lower bound on remaining path cost. Zero-cost edges may make it zero.
    """
    scale = 1.0
    for source in problem.nodes:
        for target, cost in problem.successors(source):
            length = problem.distance(source, target)
            if length > 0:
                scale = min(scale, cost / length)
    return scale


def astar(problem):
    """A* with best-cost pruning and goal testing on removal.

    Rank nodes by f = path_cost + scaled straight-line distance. Count all
    created nodes, including the root and children rejected by best-cost pruning.
    Assumes finite coordinates and nonnegative finite edge costs.
    """
    scale = heuristic_scale(problem)
    root = Node(problem.origin)
    nodes_created = 1
    frontier = PriorityFrontier()
    frontier.push(root, scale * problem.heuristic(root.state))
    best_cost = {root.state: 0}

    while frontier:
        node = frontier.pop()
        if node.path_cost > best_cost[node.state]:
            continue
        # A generated goal may be more expensive than a route still waiting.
        if problem.is_goal(node.state):
            return SearchResult(node, nodes_created)

        for child in expand(problem, node):
            nodes_created += 1
            if child.path_cost < best_cost.get(child.state, float('inf')):
                best_cost[child.state] = child.path_cost
                estimate = scale * problem.heuristic(child.state)
                frontier.push(child, child.path_cost + estimate)

    return SearchResult(None, nodes_created)
