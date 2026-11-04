"""Shared LSTM/GRU across detector series, with series embeddings and calendar input."""
import numpy as np
import torch
from torch import nn


class RecurrentPredictor(nn.Module):
    def __init__(self, kind, series_count, hidden_size):
        super().__init__()
        if kind not in ('LSTM', 'GRU'):
            raise ValueError('Unknown recurrent model')
        self.rnn = getattr(nn, kind)(1, hidden_size, batch_first=True)
        self.embedding = nn.Embedding(series_count, 8)
        self.head = nn.Sequential(nn.Linear(hidden_size + 12, hidden_size), nn.ReLU(), nn.Linear(hidden_size, 1))

    def forward(self, history, calendar, ids):
        sequence, _ = self.rnn(history.unsqueeze(-1))
        features = torch.cat([sequence[:, -1], calendar, self.embedding(ids)], dim=1)
        # Learn a correction to persistence, a strong short-horizon baseline.
        return history[:, -1] + self.head(features).squeeze(-1)


def tree_features(data):
    return np.column_stack([data['x'], data['calendar'], data['ids']])


def predict_normalized(model, data, batch_size=4096):
    if not isinstance(model, nn.Module):
        return model.predict(tree_features(data))
    model.eval()
    chunks = []
    with torch.inference_mode():
        for start in range(0, len(data['ids']), batch_size):
            end = start + batch_size
            chunks.append(model(torch.from_numpy(data['x'][start:end]),
                                torch.from_numpy(data['calendar'][start:end]),
                                torch.from_numpy(data['ids'][start:end])).numpy())
    return np.concatenate(chunks)


def unscale(prediction, ids, metadata):
    means = np.array([item['mean'] for item in metadata])
    scales = np.array([item['scale'] for item in metadata])
    return np.maximum(0, prediction * scales[ids] + means[ids])
