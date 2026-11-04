"""Independent checks of data leakage, numerical behaviour and routing correctness."""
import csv
from datetime import datetime, timedelta
import itertools
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from traffic.dataset import build_windows, calendar, read_series, score
from traffic.network import CAPACITY, haversine, load_network, travel_time, weighted_edges
from traffic.routing import top_k_routes
from traffic.settings import load_config


def toy_series(gap=None):
    start = datetime(2006, 10, 1)
    return {('0001', 'Road', 1): {start + timedelta(minutes=15*i): float(i % 20)
                                for i in range(6*96) if i != gap}}


def windows(series):
    return build_windows(series, 4, '2006-10-04', '2006-10-06')


def graph():
    nodes = {str(i): {'lat': -37.8+i*.01, 'lon': 145+i*.01} for i in range(5)}
    edges = [{'source': a, 'target': b, 'minutes': c} for a, b, c in
             [('0', '1', 1), ('1', '4', 5), ('0', '2', 2), ('2', '4', 2),
              ('1', '2', 1), ('2', '1', 1), ('0', '3', 3), ('3', '4', 2)]]
    return nodes, edges


class DataTests(unittest.TestCase):
    def test_chronological_cutoffs(self):
        _, splits = windows(toy_series())
        self.assertLess(max(splits[0]['timestamps']), min(splits[1]['timestamps']))
        self.assertLess(max(splits[1]['timestamps']), min(splits[2]['timestamps']))

    def test_scaler_and_profiles_ignore_future(self):
        data = toy_series(); before, _ = windows(data)
        for stamp in next(iter(data.values())):
            if stamp >= datetime(2006, 10, 4):
                next(iter(data.values()))[stamp] = 100000
        after, _ = windows(data)
        self.assertEqual(before, after)

    def test_gap_not_crossed(self):
        _, full = windows(toy_series()); _, missing = windows(toy_series(100))
        self.assertEqual(len(full[0]['ids']) - len(missing[0]['ids']), 5)

    def test_target_not_in_history(self):
        meta, splits = windows(toy_series())
        first = splits[0]
        history = first['x'][0]*meta[0]['scale'] + meta[0]['mean']
        np.testing.assert_allclose(history, [0, 1, 2, 3], atol=1e-5)
        self.assertEqual(first['actual'][0], 4)

    def test_empty_split_rejected(self):
        with self.assertRaises(ValueError):
            build_windows(toy_series(), 4, '2006-10-09', '2006-10-10')

    def test_bad_cutoff_order(self):
        with self.assertRaises(ValueError):
            build_windows(toy_series(), 4, '2006-10-06', '2006-10-04')

    def test_metrics_known_values(self):
        metric = score([10, 20], [13, 16])
        self.assertAlmostEqual(metric['rmse'], (12.5)**.5)
        self.assertAlmostEqual(metric['nrmse'], (12.5)**.5/15)
        self.assertEqual(metric['mae'], 3.5)

    def test_zero_mean_nrmse_undefined(self):
        self.assertIsNone(score([0, 0], [1, 1])['nrmse'])

    def test_nonfinite_metrics_rejected(self):
        with self.assertRaises(ValueError):
            score([1], [float('nan')])

    def test_calendar_wrap(self):
        np.testing.assert_allclose(calendar(datetime(2006, 10, 2)), calendar(datetime(2006, 10, 9)))


class TravelTests(unittest.TestCase):
    def test_free_flow_and_delay_units(self):
        minutes, speed, clipped = travel_time(1, 0)
        self.assertEqual((minutes, speed, clipped), (1.5, 60, False))

    def test_capacity_and_saturation(self):
        at = travel_time(1, CAPACITY); over = travel_time(1, CAPACITY + 1)
        self.assertAlmostEqual(at[1], 32, places=3)
        self.assertEqual(at[:2], over[:2]); self.assertTrue(over[2])

    def test_time_increases_with_flow(self):
        self.assertLess(travel_time(1, 500)[0], travel_time(1, 1200)[0])

    def test_invalid_inputs(self):
        for args in [(-1, 10), (1, -1), (1, float('nan')), (1, 10, 0), (1, 10, 61), (1, 10, 60, -1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                travel_time(*args)

    def test_distance_symmetric(self):
        a, b = (-37.8, 145), (-37.81, 145.01)
        self.assertEqual(haversine(a, a), 0)
        self.assertAlmostEqual(haversine(a, b), haversine(b, a))

    def test_flow_endpoint_switch(self):
        config = load_config(); edge = [{'source': 'a', 'target': 'b', 'distance_km': 1}]
        flows = {'a': 0, 'b': 1200}
        destination = weighted_edges(edge, flows, config)[0]['minutes']
        config['flow_site'] = 'source'
        self.assertGreater(destination, weighted_edges(edge, flows, config)[0]['minutes'])


class RouteTests(unittest.TestCase):
    def test_top_five_match_exhaustive_oracle(self):
        nodes, edges = graph(); costs = {(e['source'], e['target']): e['minutes'] for e in edges}
        expected = []
        for length in range(4):
            for middle in itertools.permutations(['1', '2', '3'], length):
                path = ('0', *middle, '4')
                if all((a,b) in costs for a,b in zip(path,path[1:])):
                    expected.append((sum(costs[a,b] for a,b in zip(path,path[1:])), path))
        actual, _ = top_k_routes(nodes, edges, '0', '4', 5)
        self.assertEqual([r['minutes'] for r in actual], sorted(v[0] for v in expected)[:5])
        self.assertEqual(len({tuple(r['path']) for r in actual}), 5)

    def test_routes_are_loopless(self):
        nodes, edges = graph()
        for route in top_k_routes(nodes, edges, '0', '4')[0]:
            self.assertEqual(len(route['path']), len(set(route['path'])))

    def test_unreachable(self):
        nodes, edges = graph()
        self.assertEqual(top_k_routes(nodes, edges, '4', '0')[0], [])

    def test_same_origin_destination(self):
        nodes, edges = graph()
        self.assertEqual(top_k_routes(nodes, edges, '0', '0')[0], [{'path': ['0'], 'minutes': 0}])

    def test_unknown_site(self):
        nodes, edges = graph()
        with self.assertRaises(ValueError):
            top_k_routes(nodes, edges, '99', '0')

    def test_invalid_route_count(self):
        nodes, edges = graph()
        for k in [0, 6]:
            with self.assertRaises(ValueError):
                top_k_routes(nodes, edges, '0', '4', k)

    def test_negative_edge_rejected(self):
        nodes, edges = graph(); edges[0]['minutes'] = -1
        with self.assertRaises(ValueError):
            top_k_routes(nodes, edges, '0', '4')

    def test_actual_network_connected_and_finite(self):
        nodes, edges = load_network(load_config())
        self.assertEqual(len(nodes), 40)
        seen, pending = set(), [next(iter(nodes))]
        while pending:
            site = pending.pop()
            if site in seen: continue
            seen.add(site)
            pending.extend(e['target'] for e in edges if e['source'] == site)
        self.assertEqual(seen, set(nodes))
        self.assertTrue(all(0 < e['distance_km'] < 20 for e in edges))


if __name__ == '__main__':
    unittest.main()
