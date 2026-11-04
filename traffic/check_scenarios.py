"""Run 15 real-data end-to-end scenarios and verify routes against Dijkstra."""
import csv
import heapq
from pathlib import Path
from .predict import Predictor
from .route import plan
from .settings import ROOT, load_config


def dijkstra(edges, start, goal):
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge['source'], []).append((edge['target'], edge['minutes']))
    frontier, best = [(0, start)], {start: 0}
    while frontier:
        cost, node = heapq.heappop(frontier)
        if cost > best[node]: continue
        if node == goal: return cost
        for target, weight in adjacency.get(node, []):
            if cost + weight < best.get(target, float('inf')):
                best[target] = cost + weight; heapq.heappush(frontier, (cost+weight, target))
    return float('inf')


def main():
    config = load_config()
    pairs = [('2000', '3002', '2006-10-30T08:00'), ('0970', '2827', '2006-10-30T17:00'),
             ('4821', '2200', '2006-10-28T12:00'), ('2846', '3180', '2006-10-29T00:00'),
             ('4266', '4266', '2006-11-02T09:00')]
    rows = []
    for model in ('TREE', 'LSTM', 'GRU'):
        predictor = Predictor(config, model)
        for origin, destination, departure in pairs:
            cfg = {**config, 'origin': origin, 'destination': destination, 'departure': departure, 'model': model}
            result = plan(cfg, predictor)
            routes = result['routes']
            if not routes or abs(routes[0]['minutes'] - dijkstra(result['edges'], origin, destination)) > 1e-7:
                raise AssertionError('Shortest route differs from independent Dijkstra')
            costs = {(e['source'], e['target']): e['minutes'] for e in result['edges']}
            previous, seen = -1, set()
            for route in routes:
                path = tuple(route['path'])
                assert path[0] == origin and path[-1] == destination and len(path) == len(set(path))
                assert path not in seen and route['minutes'] >= previous - 1e-9
                assert abs(sum(costs[a,b] for a,b in zip(path,path[1:])) - route['minutes']) < 1e-7
                seen.add(path); previous = route['minutes']
            rows.append({'scenario': len(rows)+1, 'model': model, 'origin': origin, 'destination': destination,
                         'departure': departure, 'routes': len(routes), 'best_minutes': routes[0]['minutes'],
                         'path': ' -> '.join(routes[0]['path']), 'nodes_created': result['nodes_created'],
                         'fallback_inputs': result['fallback_history_values'], 'capacity_clipped_edges': result['capacity_clipped_edges'],
                         'result': 'PASS'})
    output = ROOT / 'results/route_scenarios.csv'; output.parent.mkdir(exist_ok=True)
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(f'All 15 real-data scenarios passed. Saved {output}')


if __name__ == '__main__':
    main()
