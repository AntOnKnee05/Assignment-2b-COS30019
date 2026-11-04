"""Repository-relative configuration, independent of the launch directory."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_config(path=None):
    config = json.loads((ROOT / 'config/default.json').read_text(encoding='utf-8'))
    if path:
        config.update(json.loads(Path(path).read_text(encoding='utf-8')))
    for key in ('source', 'processed', 'artifacts', 'graph'):
        config[key] = str((ROOT / config[key]).resolve())
    if not 1 <= int(config['window']) <= 96:
        raise ValueError('window must be between 1 and 96')
    for key in ('epochs', 'patience', 'batch_size', 'hidden_size', 'threads'):
        if int(config[key]) < 1:
            raise ValueError(f'{key} must be positive')
    if not 0 < float(config['learning_rate']) < 1:
        raise ValueError('learning_rate must be between zero and one')
    return config
