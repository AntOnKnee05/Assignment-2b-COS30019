"""Search methods ported from the team Assignment 2A repository.

Ported from Part A commit e3d8399 with relative imports adapted. A* adds
best-cost pruning; the other five are unchanged. Only A* minimises total
cost, so it is the default for travel-time routing. The rest are available
so their routes and search effort can be compared on the real network.
"""

from .astar import astar
from .bfs import bfs
from .cus1 import cus1
from .cus2 import cus2
from .dfs import dfs
from .gbfs import gbfs

# Keys match the Part A command-line method names.
METHODS = {
    'AS': astar,
    'BFS': bfs,
    'DFS': dfs,
    'GBFS': gbfs,
    'CUS1': cus1,
    'CUS2': cus2,
}

# What each method minimises; only AS is guaranteed the fastest route.
OPTIMISES = {
    'AS': 'travel time (optimal)',
    'BFS': 'fewest intersections',
    'DFS': 'nothing (first route found)',
    'GBFS': 'straight-line closeness (greedy)',
    'CUS1': 'fewest intersections (iterative deepening)',
    'CUS2': 'fewest intersections (IDA*)',
}
