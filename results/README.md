# Checked results - 10 November 2026

This directory records software checks and model evaluation, not the assignment
report. These snapshots correspond to `training_run.json` and the default
12-epoch configuration. The matching model weights are committed as the shared
team run `artifacts/run_20261110_115746_770832/`.

## Held-out one-step results

All models were evaluated on the same 62,688 test targets. Model selection used
61,536 validation targets; training used 276,168 contiguous windows.

| Model | RMSE (vehicles/15 min) | NRMSE | MAE |
|---|---:|---:|---:|
| Regression tree | 18.667 | 0.1851 | 12.205 |
| LSTM | 17.115 | 0.1697 | 11.362 |
| GRU | 17.187 | 0.1704 | 11.389 |
| Persistence baseline | 22.471 | 0.2228 | 14.735 |

See `metrics.csv` for full precision, validation scores and training times;
`per_series_metrics.csv` contains individual detector scores. `history.json`
records checkpoint selection. NRMSE is a normalised error, not accuracy.

## Recursive next-hour results

15,672 complete held-out detector-hours; no future actual values are fed back.

| Model | Hourly-total RMSE (vehicles/hour) | NRMSE |
|---|---:|---:|
| Regression tree | 58.270 | 0.1444 |
| LSTM | 51.237 | 0.1270 |
| GRU | 52.123 | 0.1292 |
| Persistence baseline | 108.907 | 0.2700 |

`recursive_metrics.csv` also includes each of the four horizons. These hourly
scores should not be compared directly with one-step scores in different units.

## Software checks

- 41 automated tests passed; full output is in `software_tests.txt`.
- 15 distinct real-data scenarios passed with all three models (45/45 runs):
  normal trips, edge cases, alternative flow settings and three invalid requests
  that are correctly rejected. `route_scenarios.csv` includes inputs, expected
  outcome, route count, best path, cost, created nodes, fallback/saturation
  counts, any error message, and - where recorded counts exist - site-flow MAE
  against actual traffic and minutes lost against the hindsight-best route.
  Under mean flow no scenario saturates an edge; the summed-flow scenario
  saturates 105 of 112. Every model's best route was also the best route under
  actual traffic in every scenario that could be re-costed (0.00 minutes lost).
- Top-five routes on a small graph were checked against exhaustive enumeration.
- Real-data shortest routes were checked against independent Dijkstra. All route
  results were checked for valid edges, uniqueness, no loops and sorted costs.
- Python modules compiled successfully. The GUI launched and its initial layout
  was visually inspected. On 10 November 2026 every GUI action was also driven
  by script against the committed models: Find routes for all three models
  (5 routes each), Save route results, Predict next hour (chart drawn), Load
  evaluation (8 rows), an off-boundary time (rejected with a message) and
  identical origin/destination (one 0-minute route). A full manual click-through
  with screenshots is still to be done for the report.

## Reproduce

From the repository root after installing requirements and preparing data:

```powershell
.\.venv\Scripts\python.exe -u -m traffic.train
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m traffic.check_scenarios
```

Training writes new results to the active artifacts run; it does not overwrite
these evaluation snapshots. The scenario command updates its CSV in this folder.
Library/hardware differences may cause small numerical changes. Road geometry,
flow saturation and seasonal fallback assumptions are described in the main README.
