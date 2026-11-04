"""The Route Finding problem: a directed, weighted graph with an origin and goals."""

import math


class RouteProblem:
    """A route finding problem on a 2D directed graph.

    Attributes:
        nodes: dict mapping node id -> (x, y) coordinates.
        origin: the start node id.
        destinations: frozenset of goal node ids (reaching any one is a solution).
    """

    def __init__(self, nodes, edges, origin, destinations):
        self.nodes = dict(nodes)
        self.origin = origin
        self.destinations = frozenset(destinations)

        # Adjacency list: node id -> [(neighbour id, cost), ...] sorted by
        # neighbour id, so successors come out in ascending order (NOTE 2).
        self._adjacency = {node_id: [] for node_id in self.nodes}
        for src, dst, cost in edges:
            self._adjacency[src].append((dst, cost))
        for neighbours in self._adjacency.values():
            neighbours.sort()

    def successors(self, state):
        """Return [(next_state, step_cost), ...] in ascending node order."""
        return self._adjacency[state]

    def is_goal(self, state):
        return state in self.destinations

    def distance(self, a, b):
        """Straight-line (Euclidean) distance between nodes a and b."""
        (x1, y1), (x2, y2) = self.nodes[a], self.nodes[b]
        return math.hypot(x2 - x1, y2 - y1)

    def heuristic(self, state):
        """Straight-line distance from `state` to the nearest destination.

        GBFS uses this value directly. It is not always a lower bound on the
        remaining cost, because the file format allows an edge to cost less
        than its straight-line length. AS therefore multiplies it by a safe
        scale factor (see astar.heuristic_scale), and CUS2 divides it by the
        longest edge to estimate remaining moves.
        """
        return min(self.distance(state, goal) for goal in self.destinations)
