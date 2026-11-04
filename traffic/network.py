"""Map metadata and the assignment's simplified flow-to-speed equation."""
import json
import math
from pathlib import Path
from statistics import mean
import xlrd
from .prepare import site_id

QUADRATIC = 1.4648375
LINEAR = 93.75
CAPACITY = LINEAR ** 2 / (4 * QUADRATIC)


def haversine(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    value = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(value)))


def travel_time(distance_km, flow_hour, speed_limit=60, delay_seconds=30):
    """Return minutes, km/h, and whether flow exceeds the guide's capacity.

    Use the upper (under-capacity) root specified by the guide's assumptions.
    The parabola has no real root above capacity: saturate at its turning-point
    speed and disclose clipping. Do not silently take sqrt of a negative number.
    """
    if not all(math.isfinite(x) for x in (distance_km, flow_hour, speed_limit, delay_seconds)):
        raise ValueError('Travel inputs must be finite')
    if distance_km < 0 or flow_hour < 0 or not 0 < speed_limit <= 60 or delay_seconds < 0:
        raise ValueError('Distance, flow and delay must be nonnegative; speed limit must be in (0, 60]')
    effective = min(flow_hour, CAPACITY)
    speed = min(speed_limit, (LINEAR + math.sqrt(max(0, LINEAR ** 2 - 4 * QUADRATIC * effective))) / (2 * QUADRATIC))
    return distance_km / speed * 60 + delay_seconds / 60, speed, flow_hour > CAPACITY


def load_network(config):
    book = xlrd.open_workbook(config['source'], on_demand=True)
    coordinates, descriptions = {}, {}
    try:
        sheet = book.sheet_by_name('Data')
        headers = sheet.row_values(1)
        cols = {key: headers.index(key) for key in ('SCATS Number', 'Location', 'NB_LATITUDE', 'NB_LONGITUDE')}
        for row in range(2, sheet.nrows):
            site = site_id(sheet.cell_value(row, cols['SCATS Number']))
            location = str(sheet.cell_value(row, cols['Location']))
            lat, lon = [float(sheet.cell_value(row, cols[k])) for k in ('NB_LATITUDE', 'NB_LONGITUDE')]
            descriptions.setdefault(site, set()).add(location)
            # Some detectors have (0, 0). Only use valid Melbourne coordinates.
            if -39 < lat < -37 and 144 < lon < 146:
                coordinates.setdefault(site, set()).add((lat, lon))
    finally:
        book.release_resources()
    nodes = {}
    for site, names in sorted(descriptions.items()):
        if site not in coordinates:
            raise ValueError(f'No usable coordinates for site {site}')
        pairs = coordinates[site]
        nodes[site] = {'lat': mean(p[0] for p in pairs), 'lon': mean(p[1] for p in pairs),
                       'name': ' / '.join(sorted(names))}
    roads = json.loads(Path(config['graph']).read_text(encoding='utf-8'))
    edges = {}
    for corridor in roads['corridors']:
        for a, b in zip(corridor['sites'], corridor['sites'][1:]):
            if a not in nodes or b not in nodes or a == b:
                raise ValueError(f'Invalid corridor edge {a} -> {b}')
            distance = haversine((nodes[a]['lat'], nodes[a]['lon']), (nodes[b]['lat'], nodes[b]['lon']))
            for source, target in ((a, b), (b, a)):
                edges[source, target] = {'source': source, 'target': target, 'distance_km': distance, 'road': corridor['road']}
    return nodes, list(edges.values())


def weighted_edges(edges, flows, config):
    if config['flow_site'] not in ('source', 'destination'):
        raise ValueError('flow_site must be source or destination')
    result = []
    for edge in edges:
        site = edge['source'] if config['flow_site'] == 'source' else edge['target']
        if site not in flows:
            raise ValueError(f'No prediction for site {site}')
        minutes, speed, clipped = travel_time(edge['distance_km'], flows[site],
                                              config['speed_limit_kmh'], config['intersection_delay_seconds'])
        result.append({**edge, 'minutes': minutes, 'speed_kmh': speed,
                       'flow_hour': flows[site], 'capacity_clipped': clipped})
    return result
