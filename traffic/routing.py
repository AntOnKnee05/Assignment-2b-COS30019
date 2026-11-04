"""Yen's loopless top-k paths using the team's Part A A* as its shortest-path solver."""
import heapq
import math
from .part_a.astar import astar
from .part_a.problem import RouteProblem


def top_k_routes(nodes, edges, origin, destination, k=5):
    if origin not in nodes or destination not in nodes:
        raise ValueError('Origin and destination must be known SCATS sites')
    if not 1 <= k <= 5:
        raise ValueError('Choose between 1 and 5 routes')
    costs = {}
    for edge in edges:
        a, b, cost = edge['source'], edge['target'], edge['minutes']
        if a not in nodes or b not in nodes or not math.isfinite(cost) or cost <= 0:
            raise ValueError('Edges need valid nodes and positive finite travel times')
        costs[a, b] = min(costs.get((a, b), float('inf')), cost)
    # Coordinates are local planar kilometres. Part A scales its heuristic by
    # the minimum edge cost/distance, preserving an admissible lower bound.
    coordinates = {site: (node['lon'] * 111.32 * math.cos(math.radians(-37.82)), node['lat'] * 111.32)
                   for site, node in nodes.items()}
    total_created = 0

    def shortest(start, banned_nodes=frozenset(), banned_edges=frozenset()):
        nonlocal total_created
        remaining = {site: xy for site, xy in coordinates.items() if site not in banned_nodes}
        allowed = [(a, b, value) for (a, b), value in costs.items()
                   if a in remaining and b in remaining and (a, b) not in banned_edges]
        result = astar(RouteProblem(remaining, allowed, start, [destination]))
        total_created += result.nodes_created
        return tuple(result.goal.path()) if result.goal else None

    first = shortest(origin)
    if first is None:
        return [], total_created
    accepted, candidates, queued = [first], [], {first}

    def cost(path):
        return sum(costs[a, b] for a, b in zip(path, path[1:]))

    while len(accepted) < k:
        previous = accepted[-1]
        for index in range(len(previous) - 1):
            root = previous[:index + 1]
            banned_edges = {(p[index], p[index + 1]) for p in accepted
                            if len(p) > index + 1 and p[:index + 1] == root}
            spur = shortest(root[-1], frozenset(root[:-1]), banned_edges)
            if spur:
                path = root[:-1] + spur
                if path not in queued:
                    heapq.heappush(candidates, (cost(path), path)); queued.add(path)
        if not candidates:
            break
        accepted.append(heapq.heappop(candidates)[1])
    return [{'path': list(path), 'minutes': cost(path)} for path in accepted], total_created
