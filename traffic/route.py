"""Predict traffic and find up to five routes from the command line."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from .network import load_network, weighted_edges
from .predict import Predictor
from .routing import top_k_routes
from .settings import load_config


def plan(config, predictor=None):
    stamp = datetime.fromisoformat(config['departure'])
    predictor = predictor or Predictor(config, config['model'])
    flows, fallback = predictor.site_flows(stamp, config['flow_aggregation'])
    nodes, edges = load_network(config)
    weighted = weighted_edges(edges, flows, config)
    routes, created = top_k_routes(nodes, weighted, config['origin'], config['destination'], int(config['routes']))
    return {'origin': config['origin'], 'destination': config['destination'], 'departure': stamp.isoformat(),
            'model': config['model'], 'flow_site': config['flow_site'], 'flow_aggregation': config['flow_aggregation'],
            'routes': routes, 'nodes_created': created, 'fallback_history_values': fallback,
            'capacity_clipped_edges': sum(e['capacity_clipped'] for e in weighted),
            'edge_count': len(weighted), 'flows': flows, 'nodes': nodes, 'edges': weighted,
            'assumption': 'Static departure-hour weights on a simplified corridor graph; no live traffic or turn restrictions.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--origin')
    parser.add_argument('--destination')
    parser.add_argument('--departure')
    parser.add_argument('--model', choices=['TREE', 'LSTM', 'GRU'])
    parser.add_argument('--routes', type=int)
    parser.add_argument('--output', default='outputs/routes.json')
    args = parser.parse_args()
    config = load_config(args.config)
    for key in ('origin', 'destination', 'departure', 'model', 'routes'):
        if getattr(args, key) is not None:
            config[key] = getattr(args, key)
    config['origin'], config['destination'] = str(config['origin']).zfill(4), str(config['destination']).zfill(4)
    try:
        result = plan(config)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Route planning failed: {error}\n')
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    for i, route in enumerate(result['routes'], 1):
        print(f'{i}. {" -> ".join(route["path"])} | {route["minutes"]:.2f} minutes')
    if not result['routes']:
        print('No route found.')
    print(f'Fallback history values: {result["fallback_history_values"]}; capacity-clipped edges: {result["capacity_clipped_edges"]}/{result["edge_count"]}')
    print(f'Saved {output}')


if __name__ == '__main__':
    main()
