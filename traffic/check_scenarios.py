"""Run 15 distinct real-data test scenarios with each of the three models.

Each scenario is one problem the system must handle: normal journeys at
different times, edge cases (identical endpoints, adjacent sites, only one
possible route, midnight crossover, a date after the data), alternative
settings (summed flow, source-site flow) and invalid requests that must be
rejected. Every scenario runs with TREE, LSTM and GRU (45 results).

Route results are checked independently (Dijkstra, exhaustive enumeration of
loopless paths, endpoints, loops, duplicates, ordering, edge sums). Where real
counts exist for the forecast hour, the model's predicted site flows are
compared with the actual flows, and its chosen route is re-costed under actual
traffic to measure how many minutes it loses against the best route in hindsight.

Used by the command line (writes results/route_scenarios.csv) and by the GUI's
Test scenarios tab.
"""
import csv
import heapq
import math
from datetime import datetime
import numpy as np
from .dataset import STEP
from .network import weighted_edges
from .predict import Predictor
from .route import plan
from .settings import ROOT, load_config

MODELS = ('TREE', 'LSTM', 'GRU')

# Each scenario: what it tests, its inputs, optional setting overrides and the
# expected outcome. 'routes' = exact number of routes expected; 'error' = the
# request must be rejected with a message containing this text.
SCENARIOS = [
    dict(description='Brief example, Monday morning peak', origin='2000', destination='3002',
         departure='2006-10-30T08:00', routes=5),
    dict(description='Long trip across the network, Monday evening peak', origin='0970', destination='2827',
         departure='2006-10-30T17:00', routes=5),
    dict(description='Weekend traffic, Saturday midday', origin='4821', destination='2200',
         departure='2006-10-28T12:00', routes=5),
    dict(description='Light traffic, Sunday midnight', origin='2846', destination='3180',
         departure='2006-10-29T00:00', routes=5),
    dict(description='Same origin and destination', origin='4266', destination='4266',
         departure='2006-10-31T09:00', routes=1),
    dict(description='Adjacent sites at the earliest permitted time (training cutoff)', origin='2000',
         destination='4043', departure='2006-10-22T00:00', routes=5),
    dict(description='Reverse direction of the long evening trip', origin='2827', destination='0970',
         departure='2006-10-30T17:00', routes=5),
    dict(description='Only one possible route (dead-end site to its neighbour)', origin='2820',
         destination='3662', departure='2006-10-31T12:00', routes=1),
    dict(description='Forecast hour crosses midnight into the next day', origin='3120', destination='4063',
         departure='2006-10-30T23:45', routes=5),
    dict(description='Date after the data ends (seasonal fallback only)', origin='2000', destination='3002',
         departure='2006-11-06T08:00', routes=5),
    dict(description='Summed approach flow at peak (capacity limit)', origin='2000', destination='3002',
         departure='2006-10-30T08:00', routes=5, settings={'flow_aggregation': 'sum'}),
    dict(description='Source-site traffic instead of destination', origin='2000', destination='3002',
         departure='2006-10-30T08:00', routes=5, settings={'flow_site': 'source'}),
    dict(description='Invalid time, not on a 15-minute boundary', origin='2000', destination='3002',
         departure='2006-10-30T08:10', error='15-minute boundary'),
    dict(description='Date inside the training period', origin='2000', destination='3002',
         departure='2006-10-15T08:00', error='outside training'),
    dict(description='Unknown SCATS site', origin='9999', destination='3002',
         departure='2006-10-30T08:00', error='known SCATS sites'),
]

ROUTE_CHECKS = (
    'Best route equals independent Dijkstra',
    'Routes equal the cheapest loopless paths found by exhaustive search',
    'Expected number of routes returned',
    'Every route starts at origin and ends at destination',
    'No route revisits a site (loopless)',
    'No duplicate routes',
    'Routes sorted by travel time',
    'Route time equals sum of its edge times',
)
ERROR_CHECKS = (
    'Request rejected instead of returning routes',
    'Error message explains the problem',
)


def adjacency(edges):
    graph = {}
    for edge in edges:
        graph.setdefault(edge['source'], []).append((edge['target'], edge['minutes']))
    return graph


def dijkstra(edges, start, goal):
    graph = adjacency(edges)
    frontier, best = [(0, start)], {start: 0}
    while frontier:
        cost, node = heapq.heappop(frontier)
        if cost > best[node]: continue
        if node == goal: return cost
        for target, weight in graph.get(node, []):
            if cost + weight < best.get(target, float('inf')):
                best[target] = cost + weight; heapq.heappush(frontier, (cost+weight, target))
    return float('inf')


def cheapest_paths(edges, origin, destination, k, bound):
    """Exhaustively list loopless paths no costlier than `bound` (all paths if bound is inf).

    Independent of the A*/Yen implementation: depth-first search over every
    simple path, pruned by the exact remaining distance to the goal. Stops once
    more than `k` paths are known when bound is infinite (only counting needed).
    """
    graph = adjacency(edges)
    reverse = {}
    for edge in edges:
        reverse.setdefault(edge['target'], []).append((edge['source'], edge['minutes']))
    remaining, frontier = {destination: 0}, [(0, destination)]
    while frontier:
        cost, node = heapq.heappop(frontier)
        if cost > remaining[node]: continue
        for source, weight in reverse.get(node, []):
            if cost + weight < remaining.get(source, float('inf')):
                remaining[source] = cost + weight; heapq.heappush(frontier, (cost + weight, source))
    found = []

    def search(node, path, cost):
        if math.isfinite(bound) and cost + remaining.get(node, float('inf')) > bound + 1e-7: return
        if not math.isfinite(bound) and len(found) > k: return
        if node == destination:
            found.append((cost, tuple(path))); return
        for target, weight in graph.get(node, []):
            if target not in path and target in remaining:
                path.append(target); search(target, path, cost + weight); path.pop()

    search(origin, [origin], 0.0)
    return sorted(found)


def verify_routes(result, origin, destination, expected):
    """Return {check name: bool} for one planned result."""
    routes = result['routes']
    paths = [tuple(r['path']) for r in routes]
    costs = {(e['source'], e['target']): e['minutes'] for e in result['edges']}
    minutes = [r['minutes'] for r in routes]
    k = 5
    bound = minutes[-1] if len(routes) == k else float('inf')
    reference = cheapest_paths(result['edges'], origin, destination, k, bound)[:k] if routes else []
    return dict(zip(ROUTE_CHECKS, (
        bool(routes) and abs(minutes[0] - dijkstra(result['edges'], origin, destination)) < 1e-7,
        len(reference) == len(routes) and all(abs(a[0] - b) < 1e-7 for a, b in zip(reference, minutes)),
        len(routes) == expected,
        bool(routes) and all(p[0] == origin and p[-1] == destination for p in paths),
        all(len(p) == len(set(p)) for p in paths),
        len(paths) == len(set(paths)),
        all(b >= a - 1e-9 for a, b in zip(minutes, minutes[1:])),
        all(abs(sum(costs[a, b] for a, b in zip(p, p[1:])) - m) < 1e-7 for p, m in zip(paths, minutes)),
    )))


def actual_comparison(predictor, cfg, result):
    """Compare predicted with recorded flows for the forecast hour, where recorded.

    For each site, only detectors with all four recorded counts are used, and
    the prediction is aggregated over the same detectors so both sides match.
    Returns flow MAE (veh/h) over sites with data, and - if every site has data -
    the best route's travel time under actual flows and the minutes it loses
    against the best route in hindsight.
    """
    stamp = datetime.fromisoformat(cfg['departure'])
    predictions, _ = predictor.forecast(stamp, 4)
    predicted, actual = {}, {}
    for meta, values in zip(predictor.meta, predictions):
        entries = predictor.series.get(tuple(meta['key']), {})
        counts = [entries.get(stamp + STEP * i, float('nan')) for i in range(4)]
        if all(np.isfinite(counts)):
            predicted.setdefault(meta['key'][0], []).append(float(values.sum()))
            actual.setdefault(meta['key'][0], []).append(float(sum(counts)))
    combine = np.sum if cfg['flow_aggregation'] == 'sum' else np.mean
    predicted = {s: float(combine(v)) for s, v in predicted.items()}
    actual = {s: float(combine(v)) for s, v in actual.items()}
    out = {'flow_mae': '', 'sites_with_actuals': len(actual), 'route_actual_minutes': '',
           'hindsight_best_minutes': '', 'minutes_lost': ''}
    if not actual:
        return out
    out['flow_mae'] = float(np.mean([abs(predicted[s] - actual[s]) for s in actual]))
    if len(actual) == len(result['nodes']) and result['routes']:
        real = weighted_edges([{k: e[k] for k in ('source', 'target', 'distance_km', 'road')} for e in result['edges']],
                              actual, cfg)
        costs = {(e['source'], e['target']): e['minutes'] for e in real}
        path = result['routes'][0]['path']
        out['route_actual_minutes'] = sum(costs[a, b] for a, b in zip(path, path[1:]))
        out['hindsight_best_minutes'] = dijkstra(real, cfg['origin'], cfg['destination'])
        # Rounded so floating-point noise never shows as a negative loss.
        out['minutes_lost'] = round(out['route_actual_minutes'] - out['hindsight_best_minutes'], 9) + 0.0
    return out


def run_scenario(number, scenario, model, predictor, config):
    """Run one scenario with one model. Returns (row, result or None, checks)."""
    cfg = {**config, **scenario.get('settings', {}), 'origin': scenario['origin'],
           'destination': scenario['destination'], 'departure': scenario['departure'], 'model': model, 'routes': 5}
    row = {'scenario': number, 'description': scenario['description'], 'model': model,
           'origin': cfg['origin'], 'destination': cfg['destination'], 'departure': cfg['departure'],
           'flow_site': cfg['flow_site'], 'flow_aggregation': cfg['flow_aggregation'],
           'expected': f'reject ({scenario["error"]})' if 'error' in scenario else f'{scenario["routes"]} route(s)',
           'routes': '', 'best_minutes': '', 'path': '', 'nodes_created': '', 'fallback_inputs': '',
           'capacity_clipped_edges': '', 'flow_mae': '', 'sites_with_actuals': '', 'route_actual_minutes': '',
           'hindsight_best_minutes': '', 'minutes_lost': '', 'error': ''}
    result = None
    try:
        result = plan(cfg, predictor)
    except ValueError as error:
        row['error'] = str(error)
    if 'error' in scenario:
        checks = dict(zip(ERROR_CHECKS, (result is None, scenario['error'] in row['error'])))
        if result is not None:
            row['routes'] = len(result['routes'])
    elif result is None:
        checks = {name: False for name in ROUTE_CHECKS}
    else:
        routes = result['routes']
        checks = verify_routes(result, cfg['origin'], cfg['destination'], scenario['routes'])
        row.update({'routes': len(routes), 'best_minutes': routes[0]['minutes'] if routes else '',
                    'path': ' -> '.join(routes[0]['path']) if routes else '',
                    'nodes_created': result['nodes_created'], 'fallback_inputs': result['fallback_history_values'],
                    'capacity_clipped_edges': result['capacity_clipped_edges']})
        row.update(actual_comparison(predictor, cfg, result))
    row['checks_passed'] = f'{sum(checks.values())}/{len(checks)}'
    row['result'] = 'PASS' if all(checks.values()) else 'FAIL'
    return row, result, checks


def run_all(config=None, progress=None):
    """Run every scenario with every model. Yields (row, result, checks) as each finishes.

    `progress`, if given, is called with a short text before each run.
    """
    config = config or load_config()
    total = len(SCENARIOS) * len(MODELS)
    done = 0
    for model in MODELS:
        predictor = Predictor(config, model)
        for number, scenario in enumerate(SCENARIOS, 1):
            done += 1
            if progress:
                progress(f'Run {done}/{total}: scenario {number} with {model} '
                         f'({scenario["origin"]} -> {scenario["destination"]} at {scenario["departure"]})')
            yield run_scenario(number, scenario, model, predictor, config)


def main():
    rows = []
    for row, _, checks in run_all(progress=print):
        rows.append(row)
        for name, ok in checks.items():
            if not ok:
                print(f'  FAILED: {name}')
    rows.sort(key=lambda r: (r['scenario'], MODELS.index(r['model'])))
    output = ROOT / 'results/route_scenarios.csv'; output.parent.mkdir(exist_ok=True)
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    failed = [f'{r["scenario"]}/{r["model"]}' for r in rows if r['result'] != 'PASS']
    if failed:
        raise SystemExit(f'Scenario runs failed: {failed}. Saved {output}')
    print(f'All {len(SCENARIOS)} scenarios passed with all {len(MODELS)} models ({len(rows)} runs). Saved {output}')


if __name__ == '__main__':
    main()
