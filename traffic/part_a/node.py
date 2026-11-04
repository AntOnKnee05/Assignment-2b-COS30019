"""Search tree nodes and the result type shared by every search method."""

from dataclasses import dataclass
from typing import Optional


class Node:
    """A node in the search tree.

    Several tree nodes can hold the same graph state (node id) when it is
    reachable along different paths.
    """

    __slots__ = ("state", "parent", "path_cost", "depth")

    def __init__(self, state, parent=None, path_cost=0):
        self.state = state
        self.parent = parent
        self.path_cost = path_cost
        self.depth = 0 if parent is None else parent.depth + 1

    def path(self):
        """Return the list of states from the root to this node."""
        states = []
        node = self
        while node is not None:
            states.append(node.state)
            node = node.parent
        return states[::-1]

    def on_path(self, state):
        """True if `state` already appears on the path to this node (cycle check)."""
        node = self
        while node is not None:
            if node.state == state:
                return True
            node = node.parent
        return False

    def __repr__(self):
        return f"Node({self.state}, g={self.path_cost}, depth={self.depth})"


def expand(problem, node):
    """Yield child nodes of `node` in ascending order of state.

    Every yielded child is a newly *created* node, so callers should count
    them towards number_of_nodes.
    """
    for state, cost in problem.successors(node.state):
        yield Node(state, node, node.path_cost + cost)


@dataclass
class SearchResult:
    """What every search method returns.

    goal: the goal Node that was reached, or None if no solution was found.
    nodes_created: number of search tree nodes created (including the root).
    """

    goal: Optional[Node]
    nodes_created: int
