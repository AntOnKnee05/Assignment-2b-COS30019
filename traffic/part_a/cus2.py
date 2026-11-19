"""CUS2: iterative deepening A* (IDA*) for fewest moves."""

from math import inf

from .node import Node, SearchResult, expand


def longest_edge_length(problem):
    """One move can cover at most this much geometric distance."""
    return max((problem.distance(source, target)
                for source in problem.nodes
                for target, _ in problem.successors(source)), default=0.0)


def cus2(problem):
    """Repeat DFS under increasing f = depth + estimated-moves thresholds.

    Distance to the nearest goal divided by the longest edge is a lower
    bound on moves remaining. Use zero when no positive-length edge exists.
    Costs are recorded but do not affect priorities. Assume finite geometry.
    Thresholds advance to the smallest exceeded f, not by a fixed increment.
    Exhaustion without a cutoff means no solution. Every created Node counts,
    including repeated roots, cycle rejections and threshold rejections.
    """
    longest = longest_edge_length(problem)

    def remaining_moves(state):
        return problem.heuristic(state) / longest if longest > 0 else 0.0

    threshold = remaining_moves(problem.origin)
    nodes_created = 0
    while True:
        root = Node(problem.origin)
        nodes_created += 1
        if problem.is_goal(root.state):
            return SearchResult(root, nodes_created)
        next_threshold = inf
        # Only active DFS frames are retained; no best-first priority queue.
        stack = [(root, expand(problem, root))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                stack.pop()
                continue
            nodes_created += 1
            if node.on_path(child.state):
                continue
            score = child.depth + remaining_moves(child.state)
            if score > threshold:
                next_threshold = min(next_threshold, score)
                continue
            if problem.is_goal(child.state):
                return SearchResult(child, nodes_created)
            stack.append((child, expand(problem, child)))
        if next_threshold == inf:
            return SearchResult(None, nodes_created)
        threshold = next_threshold
