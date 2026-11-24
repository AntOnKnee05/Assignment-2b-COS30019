"""Compare the six Part A search methods as Yen's path solver on the real network.

Every ordered pair of SCATS sites is routed with each method under the same
predicted travel times. A* is the reference because it returns the cheapest
paths. The summary reports search effort (nodes created, time) and route
quality (how often the best route is optimal, the minutes lost, and how much
slower the alternative routes are on average).

One condition (one model, one departure):

    python -m traffic.compare_search --departure 2006-10-30T08:00 --model GRU

Sweep (the four research journeys' departure times x all three models), which
writes one row per condition and method plus a pooled summary:

    python -m traffic.compare_search --sweep
"""
import argparse
import csv
from datetime import datetime
from itertools import permutations
from pathlib import Path
import time

from .network import load_network, weighted_edges
from .part_a import METHODS, OPTIMISES
from .predict import Predictor
from .routing import top_k_routes
from .settings import load_config

TOLERANCE = 1e-7
FIELDS = ['method', 'optimises', 'pairs', 'mean_nodes_created', 'mean_ms_per_query',
          'best_route_optimal_pct', 'mean_minutes_lost', 'max_minutes_lost',
          'same_top_k_as_astar_pct', 'mean_routes_returned', 'mean_top_k_gap_minutes',
          'mean_best_route_sites']
CONDITION_FIELDS = ['model', 'departure', 'label']

# Departure times of the four research journeys (report section 6.1).
SWEEP_DEPARTURES = {
    'Monday morning peak': '2006-10-30T08:00',
    'Monday evening peak': '2006-10-30T17:00',
    'Saturday midday': '2006-10-28T12:00',
    'Sunday midnight': '2006-10-29T00:00',
}
SWEEP_MODELS = ['TREE', 'LSTM', 'GRU']


def _mean(values):
    return sum(values) / len(values)


def compare(config, k=5):
    """Return one summary row per method for every ordered site pair."""
    stamp = datetime.fromisoformat(config['departure'])
    flows, _ = Predictor(config, config['model']).site_flows(stamp, config['flow_aggregation'])
    nodes, edges = load_network(config)
    weighted = weighted_edges(edges, flows, config)
    pairs = list(permutations(sorted(nodes), 2))
    runs = {}
    for method in METHODS:
        runs[method] = []
        for origin, destination in pairs:
            start = time.perf_counter()
            routes, created = top_k_routes(nodes, weighted, origin, destination, k, method)
            runs[method].append((routes, created, time.perf_counter() - start))
    reference = runs['AS']
    rows = []
    for method, results in runs.items():
        lost, gaps, optimal, same = [], [], 0, 0
        for (routes, _, _), (best, _, _) in zip(results, reference):
            gap = routes[0]['minutes'] - best[0]['minutes']
            lost.append(max(gap, 0.0))
            optimal += gap < TOLERANCE
            same += [r['path'] for r in routes] == [r['path'] for r in best]
            # Alternatives: compare the i-th route with A*'s i-th route where both exist.
            shared = min(len(routes), len(best))
            gaps.append(_mean([routes[i]['minutes'] - best[i]['minutes'] for i in range(shared)]))
        n = len(results)
        rows.append({'method': method, 'optimises': OPTIMISES[method], 'pairs': n,
                     'mean_nodes_created': round(_mean([r[1] for r in results]), 1),
                     'mean_ms_per_query': round(1000 * _mean([r[2] for r in results]), 3),
                     'best_route_optimal_pct': round(100 * optimal / n, 1),
                     'mean_minutes_lost': round(_mean(lost), 3),
                     'max_minutes_lost': round(max(lost), 3),
                     'same_top_k_as_astar_pct': round(100 * same / n, 1),
                     'mean_routes_returned': round(_mean([len(r[0]) for r in results]), 2),
                     'mean_top_k_gap_minutes': round(_mean(gaps), 3),
                     'mean_best_route_sites': round(_mean([len(r[0][0]['path']) for r in results]), 2)})
    return rows


def sweep(config, departures=SWEEP_DEPARTURES, models=SWEEP_MODELS, k=5, progress=print):
    """Run compare() for every model and departure; rows carry the condition."""
    rows = []
    for model in models:
        for label, departure in departures.items():
            progress(f'  {model} {label} ({departure}) ...')
            started = time.perf_counter()
            for row in compare({**config, 'model': model, 'departure': departure}, k):
                rows.append({'model': model, 'departure': departure, 'label': label, **row})
            progress(f'    done in {time.perf_counter() - started:.0f} s')
    return rows


def pool(rows):
    """Average per-condition rows into one row per method. Every condition
    routes the same site pairs, so averaging means gives the pooled mean."""
    pooled = []
    for method in METHODS:
        mine = [r for r in rows if r['method'] == method]
        out = {'method': method, 'optimises': OPTIMISES[method],
               'pairs': sum(r['pairs'] for r in mine)}
        for field in FIELDS[3:]:
            values = [r[field] for r in mine]
            out[field] = round(max(values) if field.startswith('max_') else _mean(values), 3)
        pooled.append(out)
    return pooled


def _write(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fields); writer.writeheader(); writer.writerows(rows)


def _print_table(rows):
    print(f'{"Method":6} {"Nodes":>10} {"ms":>8} {"Optimal %":>10} {"Mean lost":>10} {"Max lost":>9}'
          f' {"Same top5 %":>12} {"Top5 gap":>9}')
    for r in rows:
        print(f'{r["method"]:6} {r["mean_nodes_created"]:>10} {r["mean_ms_per_query"]:>8}'
              f' {r["best_route_optimal_pct"]:>10} {r["mean_minutes_lost"]:>10} {r["max_minutes_lost"]:>9}'
              f' {r["same_top_k_as_astar_pct"]:>12} {r["mean_top_k_gap_minutes"]:>9}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config')
    parser.add_argument('--departure')
    parser.add_argument('--model', choices=SWEEP_MODELS)
    parser.add_argument('--sweep', action='store_true',
                        help='all three models at the four research departure times')
    parser.add_argument('--output', help='CSV path (default depends on mode)')
    args = parser.parse_args()
    config = load_config(args.config)
    for key in ('departure', 'model'):
        if getattr(args, key):
            config[key] = getattr(args, key)
    try:
        if args.sweep:
            print(f'Sweeping {len(SWEEP_MODELS)} models x {len(SWEEP_DEPARTURES)} departures:')
            rows = sweep(config)
            pooled = pool(rows)
        else:
            rows = compare(config)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Comparison failed: {error}\n')
    if args.sweep:
        output = Path(args.output or 'results/search_comparison_sweep.csv')
        _write(output, CONDITION_FIELDS + FIELDS, rows)
        summary = output.with_name(output.stem + '_summary.csv')
        _write(summary, FIELDS, pooled)
        conditions = len(SWEEP_MODELS) * len(SWEEP_DEPARTURES)
        print(f'\n{rows[0]["pairs"]} site pairs x {conditions} conditions, top 5 routes each (pooled)\n')
        _print_table(pooled)
        print(f'\nSaved {output} and {summary}')
    else:
        output = Path(args.output or 'results/search_comparison.csv')
        _write(output, FIELDS, rows)
        print(f'{rows[0]["pairs"]} site pairs, {config["model"]} at {config["departure"]}, top 5 routes each\n')
        _print_table(rows)
        print(f'\nSaved {output}')
    print('Minutes lost = best route time minus the A* best route time. '
          'Top5 gap = mean extra minutes of the i-th route over A*\'s i-th route.')


if __name__ == '__main__':
    main()
