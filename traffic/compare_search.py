"""Compare the six Part A search methods as Yen's path solver on the real network.

Every ordered pair of SCATS sites is routed with each method under the same
predicted travel times. A* is the reference because it returns the cheapest
paths. The summary reports search effort (nodes created, time) and route
quality (how often the best route is optimal and the minutes lost).

    python -m traffic.compare_search --departure 2006-10-30T08:00 --model GRU
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
          'same_top_k_as_astar_pct', 'mean_best_route_sites']


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
        lost, optimal, same = [], 0, 0
        for (routes, _, _), (best, _, _) in zip(results, reference):
            gap = routes[0]['minutes'] - best[0]['minutes']
            lost.append(max(gap, 0.0))
            optimal += gap < TOLERANCE
            same += [r['path'] for r in routes] == [r['path'] for r in best]
        n = len(results)
        rows.append({'method': method, 'optimises': OPTIMISES[method], 'pairs': n,
                     'mean_nodes_created': round(sum(r[1] for r in results) / n, 1),
                     'mean_ms_per_query': round(1000 * sum(r[2] for r in results) / n, 3),
                     'best_route_optimal_pct': round(100 * optimal / n, 1),
                     'mean_minutes_lost': round(sum(lost) / n, 3),
                     'max_minutes_lost': round(max(lost), 3),
                     'same_top_k_as_astar_pct': round(100 * same / n, 1),
                     'mean_best_route_sites': round(sum(len(r[0][0]['path']) for r in results) / n, 2)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config')
    parser.add_argument('--departure')
    parser.add_argument('--model', choices=['TREE', 'LSTM', 'GRU'])
    parser.add_argument('--output', default='results/search_comparison.csv')
    args = parser.parse_args()
    config = load_config(args.config)
    for key in ('departure', 'model'):
        if getattr(args, key):
            config[key] = getattr(args, key)
    try:
        rows = compare(config)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Comparison failed: {error}\n')
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, FIELDS); writer.writeheader(); writer.writerows(rows)
    print(f'{rows[0]["pairs"]} site pairs, {config["model"]} at {config["departure"]}, top 5 routes each\n')
    print(f'{"Method":6} {"Nodes":>10} {"ms":>8} {"Optimal %":>10} {"Mean lost":>10} {"Max lost":>9} {"Same top5 %":>12}')
    for r in rows:
        print(f'{r["method"]:6} {r["mean_nodes_created"]:>10} {r["mean_ms_per_query"]:>8} {r["best_route_optimal_pct"]:>10}'
              f' {r["mean_minutes_lost"]:>10} {r["max_minutes_lost"]:>9} {r["same_top_k_as_astar_pct"]:>12}')
    print(f'\nMinutes lost = best route time minus the A* best route time. Saved {output}')


if __name__ == '__main__':
    main()
