"""Evaluate recursive next-hour forecasts separately from rolling one-step scores."""
import argparse
import csv
from datetime import datetime
import json
import numpy as np
from .dataset import STEP, build_windows, calendar, read_series, score
from .models import predict_normalized, unscale
from .predict import Predictor, active_run
from .settings import load_config


def evaluate_hour(config):
    run = active_run(config['artifacts'])
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    trained = manifest['config']
    metadata, (_, _, test) = build_windows(read_series(config['processed']), trained['window'],
                                          trained['train_end'], trained['validation_end'])
    lookup = {(int(i), t): float(y) for i, t, y in zip(test['ids'], test['timestamps'], test['actual'])}
    indexes, targets = [], []
    for index, (series_id, stamp) in enumerate(zip(test['ids'], test['timestamps'])):
        stamp = datetime.fromisoformat(stamp)
        keys = [(int(series_id), (stamp + STEP * step).isoformat(timespec='minutes')) for step in range(4)]
        if stamp.minute == 0 and all(key in lookup for key in keys):
            indexes.append(index); targets.append([lookup[key] for key in keys])
    if not indexes:
        raise ValueError('No complete held-out hours to evaluate')
    actual = np.array(targets)
    ids = test['ids'][indexes]
    times = [datetime.fromisoformat(test['timestamps'][i]) for i in indexes]
    rows = []
    hourly_predictions = {}
    for kind in ('TREE', 'LSTM', 'GRU', 'PERSISTENCE'):
        if kind == 'PERSISTENCE':
            predictions = np.repeat(test['persistence'][indexes, None], 4, axis=1)
        else:
            predictor = Predictor(config, kind)
            x = test['x'][indexes].copy()
            predictions = []
            for step in range(4):
                data = {'ids': ids, 'x': x,
                        'calendar': np.array([calendar(t + STEP * step) for t in times], dtype=np.float32)}
                normalized = predict_normalized(predictor.model, data)
                values = unscale(normalized, ids, metadata)
                predictions.append(values)
                normalized = np.array([(v - metadata[i]['mean']) / metadata[i]['scale'] for v, i in zip(values, ids)], dtype=np.float32)
                x = np.column_stack([x[:, 1:], normalized])
            predictions = np.array(predictions).T
        for step in range(4):
            rows.append({'model': kind, 'measure': f'interval_{step+1}', 'units': 'vehicles/15min',
                         **score(actual[:, step], predictions[:, step])})
        rows.append({'model': kind, 'measure': 'hour_total', 'units': 'vehicles/hour',
                     **score(actual.sum(axis=1), predictions.sum(axis=1))})
        hourly_predictions[kind] = predictions.sum(axis=1)
    with (run / 'recursive_metrics.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (run / 'hour_predictions.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['site', 'location_id', 'timestamp', 'actual_hour', 'TREE', 'LSTM', 'GRU', 'PERSISTENCE'])
        for index, (series_id, stamp) in enumerate(zip(ids, times)):
            key = metadata[series_id]['key']
            writer.writerow([key[0], key[2], stamp.isoformat(), float(actual[index].sum()),
                             *[float(hourly_predictions[k][index]) for k in ('TREE', 'LSTM', 'GRU', 'PERSISTENCE')]])
    print(f'Saved recursive next-hour evaluation: {run / "recursive_metrics.csv"}', flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config')
    args = parser.parse_args(); evaluate_hour(load_config(args.config))


if __name__ == '__main__':
    main()
