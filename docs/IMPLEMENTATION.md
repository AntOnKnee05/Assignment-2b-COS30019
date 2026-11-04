# Implementation notes

These are code documentation, not the assignment report.

## Data and models

Series identity is `(scats_site, location, vr_internal_loc)`. Site 4335 has two
detectors with the same description, so removing the internal ID would merge
distinct observations. IDs stay zero-padded. The checked V00-V95 interval header
defines interval starts, not the time component of the workbook Date.

`dataset.py` creates contiguous windows within each series and partitions them
by target timestamp. Validation/test context may include earlier observations.
Training-only mean and standard deviation normalise each detector; constant
series use a scale of at least 1. Missing intervals are not zero-filled. Scalers
and weekday/time fallback profiles never use validation or test counts.

LSTM and GRU share weights across 140 detector series. Each has one recurrent
layer (24 hidden units by default), an eight-dimensional series embedding,
cyclical target-time/weekday features and a small regression head. The prediction
is a learned correction to the last normalised count. Regression tree uses the
same 12 count inputs and calendar features plus the series identifier.

Adam minimises normalised MSE. Validation RMSE in original units selects neural
checkpoints. Tree depth is chosen from 6, 10 and 14 with minimum leaf size 20,
also using validation RMSE. Test results never select settings. All predicted
counts are clipped to nonnegative values. Reproducible seeds and deterministic
PyTorch operations are enabled; hardware/library versions may affect numbers.

## Evaluation and forecasting

RMSE = sqrt(mean((actual - predicted)^2)). NRMSE = RMSE / mean(actual).
NRMSE is undefined at a zero mean, not an accuracy percentage. MAE is also saved.

`metrics.csv` uses rolling one-step forecasts: each target has observed past
context, including earlier test observations. `recursive_metrics.csv` evaluates
four-step forecasts at complete held-out clock hours, feeding predictions back
after the first step. `hour_predictions.csv` compares hourly sums. These protocols
are separate and clearly labelled. Persistence repeats the last observed count.

Interactive inference never reads observations at/after departure. Missing past
inputs use training-only weekday/slot means, then slot means, then the training
mean. The fallback input count is disclosed. Future-date predictions with this
context are seasonal estimates, not validated live forecasts.

## Graph and conversion

The explicit corridors in `config/roads.json` follow the supplied map and location
names. Measured sites alone form vertices; intermediate unmeasured intersections
are collapsed. No inferred nearest-neighbour shortcuts are added. Edges are
bidirectional approximations and omit turn restrictions/freeway ramps.

Each site's coordinate is the mean of its unique valid detector coordinates;
zero coordinates are excluded. Haversine straight-line lengths approximate road
lengths. These coordinates are not corrected against a modern road map.

Four recursive predictions per detector are summed into hourly counts and then
aggregated per site. Default sum aggregation follows the site-volume
interpretation; mean is exposed as a sensitivity alternative. Destination flow
is the default from the brief; source flow is configurable because the conversion
guide states that convention instead.

For `q = -a*v^2 + b*v`, with `a=1.4648375` and `b=93.75`, the upper root is
`v=(b+sqrt(b*b-4*a*q))/(2*a)`. The guide assumes under-capacity traffic, so this
root is used and capped at 60 km/h. Capacity is `b*b/(4*a)` (about 1500). Above
capacity the quadratic has no real root, so flow is saturated at capacity and
the edge is flagged. This is an explicit numerical extension, not a measured
congestion model. Summed approaches frequently saturate and can diminish the
effect of different predictors on route choice.

Edge minutes = distance_km / speed_kmh * 60 + delay_seconds / 60.
Departure-hour weights are static. One delay per edge includes the destination
intersection; origin equals destination costs zero.

## Part A integration

The files under `traffic/part_a` were ported from the team's
[Part A commit e3d8399](https://github.com/AntOnKnee05/Assignment-2-COS30019/tree/e3d8399fa7270638e8ee87db88dc5d09f6469302).
Relative imports were adapted. A* adds best-cost pruning instead of enumerating
all simple search-tree paths. Its minimum edge-cost/distance scale preserves an
admissible distance heuristic. `routing.py` implements Yen's algorithm around
this A* solver to produce up to five unique loopless routes in cost order.

## Output files

| File in the active artifacts run | Contents |
|---|---|
| `manifest.json` | Settings, versions, SHA-256 data hash, scalers/profiles, split sizes |
| `TREE.joblib`, `LSTM.pt`, `GRU.pt` | Learned model parameters |
| `history.json` | Tree tuning and recurrent epoch validation results |
| `metrics.csv` | Validation/test RMSE, NRMSE, MAE and training seconds |
| `per_series_metrics.csv` | Held-out metrics for each detector |
| `test_predictions.csv` | All held-out actual counts and one-step predictions |
| `recursive_metrics.csv` | Four individual horizons and hourly-total errors |
| `hour_predictions.csv` | Held-out hourly totals and recursive predictions |
| `evaluation.png` | Comparison chart and sample predictions |

CLI and GUI regenerate recursive evaluation after training. `artifacts/latest.txt`
points to the current run; failed training cannot overwrite the previous run.
The training lock prevents concurrent writers. A processed-data hash mismatch
rejects inference until retraining. Saved artifacts contain Python serialization
and must come from a trusted source.

## Library references

- [PyTorch LSTM](https://docs.pytorch.org/docs/stable/generated/torch.nn.LSTM.html)
  and [GRU](https://docs.pytorch.org/docs/stable/generated/torch.nn.GRU.html):
  recurrent layer APIs and batch shapes.
- [DecisionTreeRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeRegressor.html):
  tree training and regularisation parameters.
- [RMSE](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.root_mean_squared_error.html):
  error metric interpretation; this project calculates the equivalent formula
  directly with NumPy.

The lecturer's example code is not copied into the solution. Regression tree is
implemented independently and tutor approval is still pending.
