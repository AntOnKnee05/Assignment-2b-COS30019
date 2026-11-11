"""Breadth-first search (BFS) - uninformed."""

from collections import deque

from .node import Node, SearchResult, expand


def bfs(problem):
    """Count every created Node, including the root and rejected repeats."""
    root = Node(problem.origin)
    nodes_created = 1

    # Goal test on generation: the first goal generated is at the shallowest
    # depth, so there is no need to wait until it is expanded.
    if problem.is_goal(root.state):
        return SearchResult(root, nodes_created)

    frontier = deque([root])      # FIFO queue
    reached = {root.state}        # graph search: never revisit a state

    while frontier:
        node = frontier.popleft()
        # Children come out in ascending order, so ties between nodes on the
        # same level are broken by smaller id, then insertion order (NOTE 2).
        for child in expand(problem, node):
            nodes_created += 1
            if child.state in reached:
                continue
            if problem.is_goal(child.state):
                return SearchResult(child, nodes_created)
            reached.add(child.state)
            frontier.append(child)

    return SearchResult(None, nodes_created)
