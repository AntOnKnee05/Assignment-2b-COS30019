"""CUS1: iterative deepening depth-first search for fewest moves."""

from .node import Node, SearchResult, expand


def cus1(problem):
    """Run depth limits 0, 1, ... with path cycle checking.

    Iterator frames implement DFS without Python recursion. A boundary node
    is a cutoff only when it has a non-ancestor successor. If a whole pass
    has no cutoff, all reachable simple routes are exhausted. At most V-1
    moves are needed for a simple path on a finite V-node graph.
    Count every Node actually created, including each iteration's root.
    """
    nodes_created = 0
    for limit in range(len(problem.nodes)):
        root = Node(problem.origin)
        nodes_created += 1
        cutoff = False
        # A frame stores a node and its lazily generated ascending children.
        stack = [(root, None)]
        while stack:
            node, children = stack[-1]
            if children is None:
                if problem.is_goal(node.state):
                    return SearchResult(node, nodes_created)
                if node.depth == limit:
                    cutoff |= any(not node.on_path(state)
                                  for state, _ in problem.successors(node.state))
                    stack.pop()
                    continue
                children = expand(problem, node)
                stack[-1] = (node, children)
            child = next(children, None)
            if child is None:
                stack.pop()
                continue
            nodes_created += 1
            if not node.on_path(child.state):
                stack.append((child, None))
        if not cutoff:
            break
    return SearchResult(None, nodes_created)
