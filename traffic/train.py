"""Train all three models, select on validation only, and export held-out evaluation."""
import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import time

import joblib
import numpy as np
import torch
from sklearn.tree import DecisionTreeRegressor

from .dataset import build_windows, read_series, score
from .models import RecurrentPredictor, predict_normalized, tree_features, unscale
from .settings import load_config


def train_recurrent(kind, metadata, train, validation, config, log):
    torch.manual_seed(config['seed'])
    model = RecurrentPredictor(kind, len(metadata), config['hidden_size'])
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
    tensors = [torch.from_numpy(train[k]) for k in ('x', 'calendar', 'ids', 'y')]
    rng = np.random.default_rng(config['seed'])
    best, state, stale, history = float('inf'), None, 0, []
    for epoch in range(config['epochs']):
        model.train()
        order = rng.permutation(len(train['ids']))
        total = 0.0
        for start in range(0, len(order), config['batch_size']):
            ix = order[start:start + config['batch_size']]
            x, cal, ids, y = [t[ix] for t in tensors]
            optimizer.zero_grad()
            loss = torch.nn.functional.mse_loss(model(x, cal, ids), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
            total += float(loss.detach()) * len(ix)
        prediction = unscale(predict_normalized(model, validation), validation['ids'], metadata)
        metric = score(validation['actual'], prediction)['rmse']
        history.append({'epoch': epoch + 1, 'training_normalized_mse': total / len(order), 'validation_rmse': metric})
        log(f'{kind} epoch {epoch + 1}/{config["epochs"]}: validation RMSE {metric:.3f}')
        if metric < best:
            best, state, stale = metric, copy.deepcopy(model.state_dict()), 0
        else:
            stale += 1
            if stale >= config['patience']:
                break
    model.load_state_dict(state)
    return model, history


def train_all(config, log=print):
    torch.set_num_threads(config['threads'])
    torch.use_deterministic_algorithms(True)
    folder = Path(config['artifacts'])
    folder.mkdir(parents=True, exist_ok=True)
    # Refuse concurrent writers; incomplete training never replaces the active run.
    lock = folder / 'training.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Training is already running (artifacts/training.lock).') from None
    os.close(descriptor)
    try:
        return _train_run(config, folder, log)
    finally:
        lock.unlink(missing_ok=True)


def _train_run(config, folder, log):
    import platform
    import sklearn
    log('Loading data and creating contiguous forecasting windows...')
    metadata, splits = build_windows(read_series(config['processed']), config['window'],
                                     config['train_end'], config['validation_end'])
    train, validation, test = splits
    from datetime import datetime
    run = folder / datetime.now().strftime('run_%Y%m%d_%H%M%S_%f')
    run.mkdir()
    manifest = {'config': config, 'series': metadata,
                'versions': {'python': platform.python_version(), 'torch': str(torch.__version__),
                             'sklearn': sklearn.__version__, 'numpy': np.__version__},
                'data_sha256': hashlib.sha256(Path(config['processed']).read_bytes()).hexdigest(),
                'split_counts': {name: len(data['ids']) for name, data in zip(('train', 'validation', 'test'), splits)},
                'evaluation': 'rolling one-step, actual observed history; no test-target inputs',
                'third_model_approval': 'Regression tree: pending tutor confirmation'}
    metrics, per_series, histories, predictions = [], [], {}, {}
    for kind in ('TREE', 'LSTM', 'GRU'):
        start = time.perf_counter()
        if kind == 'TREE':
            best, model, trials = float('inf'), None, []
            for depth in (6, 10, 14):
                candidate = DecisionTreeRegressor(max_depth=depth, min_samples_leaf=20, random_state=config['seed'])
                candidate.fit(tree_features(train), train['y'])
                pred = unscale(predict_normalized(candidate, validation), validation['ids'], metadata)
                rmse = score(validation['actual'], pred)['rmse']
                trials.append({'max_depth': depth, 'validation_rmse': rmse})
                log(f'TREE depth {depth}: validation RMSE {rmse:.3f}')
                if rmse < best:
                    best, model = rmse, candidate
            histories[kind] = trials
            joblib.dump(model, run / 'TREE.joblib')
        else:
            model, histories[kind] = train_recurrent(kind, metadata, train, validation, config, log)
            torch.save(model.state_dict(), run / f'{kind}.pt')
        elapsed = time.perf_counter() - start
        for name, data in (('validation', validation), ('test', test)):
            prediction = unscale(predict_normalized(model, data), data['ids'], metadata)
            metrics.append({'model': kind, 'split': name, **score(data['actual'], prediction), 'training_seconds': elapsed})
            if name == 'test':
                predictions[kind] = prediction
                for index, meta in enumerate(metadata):
                    mask = data['ids'] == index
                    if mask.any():
                        per_series.append({'model': kind, 'site': meta['key'][0], 'location_id': meta['key'][2],
                                           'location': meta['key'][1], **score(data['actual'][mask], prediction[mask])})
        log(f'{kind} test RMSE: {metrics[-1]["rmse"]:.3f}')
    for name, data in (('validation', validation), ('test', test)):
        metrics.append({'model': 'PERSISTENCE', 'split': name,
                        **score(data['actual'], data['persistence']), 'training_seconds': 0.0})
    for filename, rows in (('metrics.csv', metrics), ('per_series_metrics.csv', per_series)):
        with (run / filename).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    with (run / 'test_predictions.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['site', 'location_id', 'location', 'timestamp', 'actual', 'persistence', 'TREE', 'LSTM', 'GRU'])
        for i, series_id in enumerate(test['ids']):
            key = metadata[series_id]['key']
            writer.writerow([key[0], key[2], key[1], test['timestamps'][i], float(test['actual'][i]),
                             float(test['persistence'][i]), *[float(predictions[k][i]) for k in ('TREE', 'LSTM', 'GRU')]])
    (run / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (run / 'history.json').write_text(json.dumps(histories, indent=2), encoding='utf-8')
    plot_evaluation(run, test, predictions, metrics)
    temporary = folder / 'latest.tmp'
    temporary.write_text(run.name, encoding='utf-8')
    os.replace(temporary, folder / 'latest.txt')
    log(f'Training complete. Models and evaluation: {run}')
    return run


def plot_evaluation(run, test, predictions, metrics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), layout='constrained')
    rows = [r for r in metrics if r['split'] == 'test']
    axes[0].bar([r['model'] for r in rows], [r['rmse'] for r in rows], color=['#8064a2', '#247ba0', '#159895', '#999999'])
    axes[0].set(ylabel='RMSE (vehicles / 15 min)', title='Held-out test comparison (lower is better)')
    index = np.flatnonzero(test['ids'] == test['ids'][0])[:96]
    axes[1].plot(test['actual'][index], label='Actual', color='black')
    for kind, values in predictions.items():
        axes[1].plot(values[index], label=kind, alpha=.8)
    axes[1].set(xlabel='15-minute sample', ylabel='Vehicles / 15 min', title='First 96 held-out samples for the first series')
    axes[1].legend(ncol=4)
    fig.savefig(run / 'evaluation.png', dpi=140); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--epochs', type=int)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.epochs is not None:
        if args.epochs < 1:
            parser.error('--epochs must be positive')
        config['epochs'] = args.epochs
    train_all(config, lambda message: print(message, flush=True))
    from .evaluate import evaluate_hour
    evaluate_hour(config)


if __name__ == '__main__':
    main()
