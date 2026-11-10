"""Run 15 real-data end-to-end scenarios and verify routes against Dijkstra.

Five trips are each run with the three models (TREE, LSTM, GRU). Every scenario
predicts traffic, converts it to edge travel times, finds up to five routes and
then checks the result independently. Used by the command line (which writes
results/route_scenarios.csv) and by the GUI's Test scenarios tab.
"""
import csv
import heapq
from .predict import Predictor
from .route import plan
from .settings import ROOT, load_config

MODELS = ('TREE', 'LSTM', 'GRU')

# (origin, destination, departure, what the trip exercises)
TRIPS = [
    ('2000', '3002', '2006-10-30T08:00', 'Brief example, Monday morning peak'),
    ('0970', '2827', '2006-10-30T17:00', 'Long trip, Monday evening peak'),
    ('4821', '2200', '2006-10-28T12:00', 'Saturday midday'),
    ('2846', '3180', '2006-10-29T00:00', 'Sunday midnight, light traffic'),
    ('4266', '4266', '2006-11-02T09:00', 'Same origin and destination, date after the data'),
]

CHECKS = (
    'Best route equals independent Dijkstra',
    'Every route starts at origin and ends at destination',
    'No route revisits a site (loopless)',
    'No duplicate routes',
    'Routes sorted by travel time',
    'Route time equals sum of its edge times',
)


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


def verify(result, origin, destination):
    """Return {check name: bool} for one planned result."""
    routes = result['routes']
    paths = [tuple(r['path']) for r in routes]
    costs = {(e['source'], e['target']): e['minutes'] for e in result['edges']}
    minutes = [r['minutes'] for r in routes]
    return dict(zip(CHECKS, (
        bool(routes) and abs(minutes[0] - dijkstra(result['edges'], origin, destination)) < 1e-7,
        bool(routes) and all(p[0] == origin and p[-1] == destination for p in paths),
        all(len(p) == len(set(p)) for p in paths),
        len(paths) == len(set(paths)),
        all(b >= a - 1e-9 for a, b in zip(minutes, minutes[1:])),
        all(abs(sum(costs[a, b] for a, b in zip(p, p[1:])) - m) < 1e-7 for p, m in zip(paths, minutes)),
    )))


def run_all(config=None, progress=None):
    """Run all 15 scenarios. Yields (row, result, checks) as each finishes.

    `progress`, if given, is called with a short text before each scenario.
    """
    config = config or load_config()
    number = 0
    for model in MODELS:
        predictor = Predictor(config, model)
        for origin, destination, departure, description in TRIPS:
            number += 1
            if progress:
                progress(f'Scenario {number}/15: {model} {origin} -> {destination} at {departure}')
            cfg = {**config, 'origin': origin, 'destination': destination, 'departure': departure, 'model': model}
            result = plan(cfg, predictor)
            checks = verify(result, origin, destination)
            routes = result['routes']
            row = {'scenario': number, 'description': description, 'model': model, 'origin': origin,
                   'destination': destination, 'departure': departure, 'routes': len(routes),
                   'best_minutes': routes[0]['minutes'] if routes else '',
                   'path': ' -> '.join(routes[0]['path']) if routes else '',
                   'nodes_created': result['nodes_created'], 'fallback_inputs': result['fallback_history_values'],
                   'capacity_clipped_edges': result['capacity_clipped_edges'],
                   'checks_passed': f'{sum(checks.values())}/{len(checks)}',
                   'result': 'PASS' if all(checks.values()) else 'FAIL'}
            yield row, result, checks


def main():
    rows = []
    for row, _, checks in run_all(progress=print):
        rows.append(row)
        for name, ok in checks.items():
            if not ok:
                print(f'  FAILED: {name}')
    output = ROOT / 'results/route_scenarios.csv'; output.parent.mkdir(exist_ok=True)
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    failed = [r['scenario'] for r in rows if r['result'] != 'PASS']
    if failed:
        raise SystemExit(f'Scenarios failed: {failed}. Saved {output}')
    print(f'All 15 real-data scenarios passed. Saved {output}')


if __name__ == '__main__':
    main()
