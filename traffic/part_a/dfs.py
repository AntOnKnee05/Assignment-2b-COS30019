"""Depth-first search (DFS) - uninformed."""

from .node import Node, SearchResult, expand


def dfs(problem):
    """Run DFS on `problem` and return a SearchResult.

    Use a stack and test goals when popped. Reject cycles on the current
    path, while allowing the same state on different search-tree branches.
    Count every created Node, including the root and rejected cycle nodes.
    DFS finds a route, but does not guarantee minimum cost or fewest moves.
    """
    root = Node(problem.origin)
    nodes_created = 1

    frontier = [root]

    while frontier:
        node = frontier.pop()  # Last in, first out: follow the deepest branch.
        if problem.is_goal(node.state):
            return SearchResult(node, nodes_created)

        children = []
        for child in expand(problem, node):
            nodes_created += 1
            if not node.on_path(child.state):
                children.append(child)

        # expand() yields ascending ids. Push backwards so the smallest
        # sibling is on top and will be explored first.
        frontier.extend(reversed(children))

    return SearchResult(None, nodes_created)
