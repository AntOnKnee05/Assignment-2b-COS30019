"""Check the bundled map data without importing any ML libraries."""
import json
import math
from pathlib import Path


def check(folder):
    sample = json.loads((folder / 'sample_routes.json').read_text(encoding='utf-8-sig'))
    roads = json.loads((folder / 'road_geometry.json').read_text(encoding='utf-8-sig'))
    assert len(roads['routes']) == len(sample['routes']) == 5
    for saved, road in zip(sample['routes'], roads['routes']):
        assert saved['path'] == road['path']
        assert len(road['legs']) == len(saved['path']) - 1
        assert len(road['waypoints']) == len(saved['path'])
        requested = [list(map(float, pair.split(','))) for pair in road['coordinates'].split(';')]
        assert len(requested) == len(saved['path'])
        for site, (lon, lat) in zip(saved['path'], requested):
            node = sample['nodes'][site]
            assert abs(node['lat'] - lat) < 1e-8 and abs(node['lon'] - lon) < 1e-8
        geometry = road['geometry']
        assert geometry['type'] == 'LineString' and len(geometry['coordinates']) > 2
        for lon, lat in geometry['coordinates']:
            assert math.isfinite(lon) and math.isfinite(lat)
            assert 144 < lon < 146 and -39 < lat < -37
        for leg in road['legs']:
            assert leg['steps']
            assert all(step['geometry']['type'] == 'LineString' for step in leg['steps'])
        for a, b in zip(saved['path'], saved['path'][1:]):
            assert any(e['source'] == a and e['target'] == b for e in sample['edges'])
    print('PASS: five road geometries match the saved TBRGS routes and coordinates.')


if __name__ == '__main__':
    check(Path(__file__).resolve().parent)
