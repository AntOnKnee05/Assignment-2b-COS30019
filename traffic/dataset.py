"""Chronological forecasting windows; no targets or missing gaps leak into inputs."""
import csv
from datetime import datetime, timedelta
import numpy as np

STEP = timedelta(minutes=15)


def read_series(path):
    series = {}
    with open(path, newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            key = (row['scats_site'].zfill(4), row['location'], int(row['vr_internal_loc']))
            stamp = datetime.fromisoformat(row['date'] + 'T' + row['start_time'])
            if stamp.minute % 15 or stamp.second:
                raise ValueError('Observations must be aligned to 15-minute intervals')
            entries = series.setdefault(key, {})
            if stamp in entries:
                raise ValueError(f'Duplicate timestamp for {key}: {stamp}')
            value = float(row['vehicle_count']) if row['vehicle_count'] else float('nan')
            if not np.isnan(value) and (not np.isfinite(value) or value < 0):
                raise ValueError('Counts must be finite and nonnegative')
            entries[stamp] = value
    if not series:
        raise ValueError('No traffic observations found')
    return dict(sorted(series.items()))


def calendar(stamp):
    angle = 2 * np.pi * (stamp.hour * 60 + stamp.minute) / 1440
    weekday = 2 * np.pi * stamp.weekday() / 7
    return [np.sin(angle), np.cos(angle), np.sin(weekday), np.cos(weekday)]


def score(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if actual.size == 0 or actual.shape != predicted.shape:
        raise ValueError('Metrics require matching nonempty arrays')
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError('Metrics require finite values')
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    mean = float(np.mean(actual))
    return {'n': int(actual.size), 'rmse': rmse,
            'nrmse': rmse / mean if mean > 0 else None,
            'mae': float(np.mean(np.abs(actual - predicted)))}


def build_windows(series, window, train_end, validation_end):
    """Cutoffs are exclusive; validation/test may use earlier observed context.

    Evaluation is rolling one-step prediction, not a multi-day open-loop forecast.
    All normalisation and fallback seasonal profiles use only training dates.
    """
    train_end, validation_end = map(datetime.fromisoformat, (train_end, validation_end))
    if train_end >= validation_end:
        raise ValueError('Training cutoff must precede validation cutoff')
    if window < 1:
        raise ValueError('window must be positive')
    metadata, rows = [], [[], [], []]
    for index, (key, entries) in enumerate(series.items()):
        train = [(t, v) for t, v in sorted(entries.items()) if t < train_end and np.isfinite(v)]
        if not train:
            raise ValueError(f'No training data for {key}')
        values = np.array([v for _, v in train])
        mean, scale = float(values.mean()), max(float(values.std()), 1.0)
        slots, weekdays = {}, {}
        for t, v in train:
            slot = t.hour * 4 + t.minute // 15
            slots.setdefault(slot, []).append(v)
            weekdays.setdefault(f'{t.weekday()}:{slot}', []).append(v)
        metadata.append({'key': list(key), 'mean': mean, 'scale': scale,
                         'profile': [float(np.mean(slots[i])) if i in slots else mean for i in range(96)],
                         'weekday_profile': {k: float(np.mean(v)) for k, v in weekdays.items()}})
        for stamp, target in sorted(entries.items()):
            history = [entries.get(stamp - STEP * i, float('nan')) for i in range(window, 0, -1)]
            if not np.isfinite(target) or not np.isfinite(history).all():
                continue
            split = 0 if stamp < train_end else 1 if stamp < validation_end else 2
            rows[split].append((index, stamp, (np.array(history) - mean) / scale,
                                calendar(stamp), (target - mean) / scale, target, history[-1]))
    datasets = []
    for name, split in zip(('train', 'validation', 'test'), rows):
        if not split:
            raise ValueError(f'No complete windows in {name}; check cutoffs and window size')
        datasets.append({
            'ids': np.array([r[0] for r in split], dtype=np.int64),
            'timestamps': [r[1].isoformat(timespec='minutes') for r in split],
            'x': np.array([r[2] for r in split], dtype=np.float32),
            'calendar': np.array([r[3] for r in split], dtype=np.float32),
            'y': np.array([r[4] for r in split], dtype=np.float32),
            'actual': np.array([r[5] for r in split], dtype=np.float32),
            'persistence': np.array([r[6] for r in split], dtype=np.float32)})
    return metadata, datasets
