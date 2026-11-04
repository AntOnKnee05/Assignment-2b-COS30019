"""Saved-model inference with observed past context or explicit seasonal fallback."""
from datetime import datetime
import json
import hashlib
from pathlib import Path
import joblib
import numpy as np
import torch

from .dataset import STEP, calendar, read_series
from .models import RecurrentPredictor, predict_normalized, unscale


def active_run(folder):
    folder = Path(folder)
    pointer = folder / 'latest.txt'
    if not pointer.exists():
        raise ValueError('Train models first: python -m traffic.train')
    run = folder / pointer.read_text(encoding='utf-8').strip()
    if run.parent.resolve() != folder.resolve():
        raise ValueError('Invalid model run path')
    return run


class Predictor:
    def __init__(self, config, kind):
        if kind not in ('TREE', 'LSTM', 'GRU'):
            raise ValueError('Choose TREE, LSTM or GRU')
        run = active_run(config['artifacts'])
        self.manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
        self.meta = self.manifest['series']
        trained = self.manifest['config']
        digest = hashlib.sha256(Path(config['processed']).read_bytes()).hexdigest()
        if digest != self.manifest['data_sha256']:
            raise ValueError('Processed data has changed since training. Retrain the models.')
        self.window = trained['window']
        self.train_end = datetime.fromisoformat(trained['train_end'])
        self.series = read_series(config['processed'])
        torch.set_num_threads(config['threads'])
        if kind == 'TREE':
            self.model = joblib.load(run / 'TREE.joblib')
        else:
            self.model = RecurrentPredictor(kind, len(self.meta), trained['hidden_size'])
            self.model.load_state_dict(torch.load(run / f'{kind}.pt', map_location='cpu', weights_only=True))
        self.kind = kind

    def forecast(self, stamp, steps=4):
        """Predict next steps recursively, never reading counts at/after departure.

        If past counts are unavailable, seed those inputs with training-only
        weekday/time means. Return fallback count so callers disclose this.
        """
        if stamp.tzinfo is not None or stamp.minute % 15 or stamp.second or stamp.microsecond:
            raise ValueError('Use local time on a 15-minute boundary (00, 15, 30 or 45)')
        if stamp < self.train_end:
            raise ValueError(f'Choose a date on or after {self.train_end.date()} (outside training)')
        if not 1 <= steps <= 96:
            raise ValueError('Forecast steps must be between 1 and 96')
        histories, fallback = [], 0
        for meta in self.meta:
            entries = self.series.get(tuple(meta['key']), {})
            history = []
            for i in range(self.window, 0, -1):
                t = stamp - STEP * i
                v = entries.get(t, float('nan'))
                if not np.isfinite(v):
                    slot = t.hour * 4 + t.minute // 15
                    v = meta['weekday_profile'].get(f'{t.weekday()}:{slot}', meta['profile'][slot])
                    fallback += 1
                history.append((v - meta['mean']) / meta['scale'])
            histories.append(history)
        x = np.array(histories, dtype=np.float32)
        ids = np.arange(len(self.meta), dtype=np.int64)
        forecasts = []
        for step in range(steps):
            data = {'x': x, 'ids': ids,
                    'calendar': np.array([calendar(stamp + STEP * step)] * len(ids), dtype=np.float32)}
            normalized = predict_normalized(self.model, data)
            values = unscale(normalized, ids, self.meta)
            forecasts.append(values)
            normalized = np.array([(v - m['mean']) / m['scale'] for v, m in zip(values, self.meta)], dtype=np.float32)
            x = np.column_stack([x[:, 1:], normalized])
        return np.array(forecasts).T, fallback

    def site_flows(self, stamp, aggregation='sum'):
        if aggregation not in ('sum', 'mean'):
            raise ValueError('Flow aggregation must be sum or mean')
        predictions, fallback = self.forecast(stamp, 4)
        by_site = {}
        for meta, values in zip(self.meta, predictions):
            by_site.setdefault(meta['key'][0], []).append(float(values.sum()))
        flows = {site: float(np.sum(v) if aggregation == 'sum' else np.mean(v)) for site, v in by_site.items()}
        return flows, fallback
