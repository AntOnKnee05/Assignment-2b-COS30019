"""Greedy best-first search (GBFS) - informed."""

from .node import Node, SearchResult, expand
from .frontier import PriorityFrontier


def gbfs(problem):
    """Run GBFS on `problem` and return a SearchResult.

    Evaluate nodes using only h(n): problem.heuristic(state).

    Reject cycles on the current path, as in DFS. Count every created Node,
    including rejected cycle nodes. Equal priorities follow insertion order;
    siblings are inserted in ascending id order. Cost optimality is not
    guaranteed because the priority ignores cost already paid.
    """
    root = Node(problem.origin)
    nodes_created = 1

    frontier = PriorityFrontier()
    frontier.push(root, problem.heuristic(root.state))

    while frontier:
        node = frontier.pop()
        if problem.is_goal(node.state):
            return SearchResult(node, nodes_created)

        for child in expand(problem, node):
            nodes_created += 1
            if not node.on_path(child.state):
                frontier.push(child, problem.heuristic(child.state))

    return SearchResult(None, nodes_created)
