"""Inference checks independent of the quality of trained weights."""
from datetime import datetime, timedelta
import unittest
import numpy as np
import torch
from traffic.models import RecurrentPredictor, predict_normalized
from traffic.predict import Predictor


class LastValueTree:
    def predict(self, features):
        # Three history columns before four calendar columns and series id.
        return features[:, 2]


def predictor():
    instance = Predictor.__new__(Predictor)
    instance.window = 3
    instance.train_end = datetime(2006, 10, 22)
    instance.meta = [{'key': ['0001', 'Road', 1], 'mean': 0, 'scale': 1,
                      'profile': [7]*96, 'weekday_profile': {}}]
    stamp = datetime(2006, 10, 30, 8)
    instance.series = {('0001', 'Road', 1): {stamp-timedelta(minutes=15*i): float(i) for i in range(1, 4)}}
    instance.model = LastValueTree()
    return instance


class PredictionTests(unittest.TestCase):
    def test_recursive_forecast_does_not_read_future(self):
        model = predictor(); stamp = datetime(2006, 10, 30, 8)
        expected, _ = model.forecast(stamp)
        for i in range(4):
            model.series[('0001', 'Road', 1)][stamp+timedelta(minutes=15*i)] = 999999
        actual, fallback = model.forecast(stamp)
        np.testing.assert_array_equal(expected, actual)
        np.testing.assert_array_equal(actual, [[1, 1, 1, 1]])
        self.assertEqual(fallback, 0)

    def test_missing_history_uses_training_profile(self):
        model = predictor(); model.series = {}
        values, fallback = model.forecast(datetime(2006, 10, 30, 8))
        np.testing.assert_array_equal(values, [[7, 7, 7, 7]])
        self.assertEqual(fallback, 3)

    def test_hourly_flow_units(self):
        flows, _ = predictor().site_flows(datetime(2006, 10, 30, 8))
        self.assertEqual(flows['0001'], 4)

    def test_unaligned_time_rejected(self):
        with self.assertRaises(ValueError):
            predictor().forecast(datetime(2006, 10, 30, 8, 1))

    def test_training_date_rejected(self):
        with self.assertRaises(ValueError):
            predictor().forecast(datetime(2006, 10, 1))

    def test_unknown_aggregation_rejected(self):
        with self.assertRaises(ValueError):
            predictor().site_flows(datetime(2006, 10, 30, 8), 'median')

    def test_lstm_gru_batch_shapes_and_finite_outputs(self):
        for kind in ('LSTM', 'GRU'):
            with self.subTest(kind=kind):
                model = RecurrentPredictor(kind, 2, 4)
                data = {'x': np.ones((3, 12), dtype=np.float32),
                        'calendar': np.zeros((3, 4), dtype=np.float32), 'ids': np.array([0, 1, 0], dtype=np.int64)}
                result = predict_normalized(model, data)
                self.assertEqual(result.shape, (3,))
                self.assertTrue(np.isfinite(result).all())

    def test_recurrent_weights_roundtrip(self):
        from io import BytesIO
        for kind in ('LSTM', 'GRU'):
            model = RecurrentPredictor(kind, 2, 4)
            restored = RecurrentPredictor(kind, 2, 4)
            buffer = BytesIO(); torch.save(model.state_dict(), buffer); buffer.seek(0)
            restored.load_state_dict(torch.load(buffer, weights_only=True))
            values = (torch.ones(1, 3), torch.zeros(1, 4), torch.zeros(1, dtype=torch.long))
            torch.testing.assert_close(model(*values), restored(*values))
