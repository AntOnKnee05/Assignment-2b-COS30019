# COS30019 Assignment 2B - Traffic-Based Route Guidance

Predict traffic using LSTM, GRU and regression tree, estimate travel times, and find up to five routes between SCATS sites. Includes a Tkinter GUI, configuration, command-line tools and automated tests.

The report is excluded. Regression tree is implemented as the proposed third model; tutor approval is still pending. Lecturer example scripts are not included.

## 1. Download or update

Install Python 3.10+ with PATH enabled (tested with Python 3.13 on Windows).

```powershell
git clone https://github.com/AntOnKnee05/Assignment-2b-COS30019.git
cd Assignment-2b-COS30019
```

Already cloned? Open PowerShell in the repository and run `git pull`. Alternatively, download and extract the ZIP. Supplied datasets and PDFs are included; see [the inventory](docs/INPUTS.md).

## 2. Run the GUI

Double-click **run_app.bat**, or run:

```powershell
.\run_app.bat
```

The launcher creates the Python environment, installs dependencies, prepares missing processed data and opens the app. First installation requires internet access and downloads PyTorch. No activation or execution-policy changes are required.

### Train models once

1. Open **Train & evaluate**.
2. Keep **12 epochs** and **12 history intervals** initially.
3. Click **Train all 3 models** and leave the app open.
4. Follow the progress log. The evaluation table appears when training completes.

**Trained models are included.** The shared team run `artifacts/run_20261110_115746_770832/` is committed, so a fresh clone can find routes and predict traffic without training first; the numbers in [results](results/) come from this run. Training is optional and still supported: retraining creates a new local run (not tracked by Git) and the active run changes only after all three models train successfully. Commit a new shared run only when the team agrees to replace the official numbers.

### Find routes

1. Open **Find routes**.
2. Choose origin **2000**, destination **3002**.
3. Enter date **2006-10-30**, time **08:00**, model **GRU**, and **5** routes.
4. Click **Find routes**.
5. Select a result row to highlight its path. Times are in minutes.
6. Click **Save route results** to export `outputs/gui_routes.json`.

Use 15-minute boundaries (00, 15, 30 or 45). Dates before the training cutoff are rejected. Missing history and future dates use training-only seasonal fallback inputs; the status bar reports their count. These are planning estimates, not live traffic.

Defaults use destination-site traffic averaged across the site's detectors (mean approach flow), a 60 km/h speed limit and 30 seconds delay per edge. Source-site flow and summed (total site) flow are available for sensitivity checks; these change the assumptions.

### Predict traffic

Set date/time on Find routes. Open **Traffic prediction**, select a site/model and click **Predict next hour**. The chart shows four predicted 15-minute counts and their hourly sum. Later intervals use previous predictions, never future recorded counts.

### Read evaluation

Click **Load evaluation** on Train & evaluate. RMSE and MAE are in vehicles per 15 minutes. NRMSE is RMSE divided by the mean actual count. Lower is better; **NRMSE is not an accuracy percentage**. A zero actual mean makes NRMSE undefined.

### Run the 15 test scenarios

Open **Test scenarios** and click **Run 15 scenarios**. Fifteen distinct scenarios run with each of the three models (45 runs): normal trips (morning/evening peak, weekend, midnight, reverse direction), edge cases (same origin/destination, adjacent sites, a dead-end site with only one possible route, a forecast hour crossing midnight, the earliest permitted date, a date after the data), alternative settings (summed flow, source-site flow) and invalid requests that must be rejected (off-boundary time, date inside training, unknown site). Each row turns green (PASS) or red (FAIL) as it finishes. Select a row to draw its best route (solid) and other routes (dashed) and list its checks: best route equals an independent Dijkstra search, routes equal the cheapest loopless paths from an exhaustive search, expected route count, correct endpoints, no loops, no duplicates, sorted by time, and route time equals the sum of its edges. Rejection scenarios check that an explanatory error is shown instead. Where recorded counts exist for the forecast hour, the row also shows the model's site-flow error (MAE, vehicles/hour) and the minutes its best route loses against the best route in hindsight under actual traffic. Base aggregation and flow-site settings come from Find routes; scenarios 11 and 12 override them. The command-line version, `python -m traffic.check_scenarios`, saves the same results to `results/route_scenarios.csv`.

## 3. Run individual commands

Run from the repository root. No environment activation is needed.

### Install and prepare data

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m traffic.prepare "data/raw/Scats Data October 2006.xls"
```

Creates `data/processed/scats_15min.csv` and a summary JSON. Original inputs are unchanged. There are 402,432 observations, 40 sites, 140 detector series and 148 absent series-days. Missing days are not filled with zero.

### Train and evaluate all models

```powershell
.\.venv\Scripts\python.exe -u -m traffic.train
```

Add `--epochs 20` to change the maximum epochs. One epoch is suitable for a smoke run, not final model comparison. To regenerate recursive next-hour evaluation with existing models:

```powershell
.\.venv\Scripts\python.exe -m traffic.evaluate
```

### Find routes

```powershell
.\.venv\Scripts\python.exe -m traffic.route --origin 2000 --destination 3002 --departure 2006-10-30T08:00 --model GRU --routes 5
```

Models: `TREE`, `LSTM`, `GRU`. Results print and save to `outputs/routes.json`.

### Launch GUI manually

```powershell
.\.venv\Scripts\python.exe -m traffic.gui
```

### Plot recorded data only

The original `run_demo.bat` still runs the preparation/recorded-chart demo. Alternatively:

```powershell
.\.venv\Scripts\python.exe -m traffic.plot_day --site 0970 --location-id 1 --date 2006-10-01
Invoke-Item .\outputs\site_0970_day.png
```

This chart contains observations, not predictions.

## 4. Configuration and output files

Edit [config/default.json](config/default.json) for persistent defaults. GUI changes apply to that session. Training, evaluation, route and GUI commands accept `--config path/to/custom.json`; custom keys override defaults and paths resolve relative to the repository.

| Settings | Purpose |
|---|---|
| `train_end`, `validation_end` | Exclusive chronological cutoffs |
| `window` | Prior 15-minute observations; 12 means 3 hours |
| `epochs`, `patience` | Maximum epochs and early stopping |
| `hidden_size`, `batch_size`, `learning_rate`, `seed`, `threads` | Training parameters |
| `flow_site` | `destination` or `source` |
| `flow_aggregation` | `sum` or `mean` of approaches |
| `graph` | Explicit simplified corridor graph |

`artifacts/latest.txt` identifies the active run. Each run contains model weights, a manifest with data hash/scalers/profiles/settings/versions, training history, validation/test metrics, per-detector metrics, test predictions, recursive-hour metrics and predictions, and an evaluation chart. See [implementation details](docs/IMPLEMENTATION.md).

Processed CSV changes require retraining. Only load trusted model artifacts: joblib uses executable Python serialization. The GUI Prepare data button recreates the CSV; the preparation CLI also writes its quality summary.

## 5. Test the program

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m traffic.check_scenarios
```

The second command needs trained models. It verifies 15 real-data scenarios with all three models (45 runs) and writes `results/route_scenarios.csv`. Unit tests cover data gaps/leakage, metrics, model inference, conversion and routes. Saved evaluation/test evidence is in [results](results/), not an assignment report.

## 6. Assumptions to understand

- Training: 1-21 October; validation: 22-26 October; test: 27-31 October. Training-only scalers and profiles; contiguous per-detector windows.
- The road graph is a simplified bidirectional corridor graph, not an authoritative navigation map. Unmeasured sites are collapsed; turn restrictions and freeway ramps are omitted. Straight-line distances can underestimate road distances.
- The brief uses destination flow; the conversion guide says source flow. Both are configurable; destination is the default.
- The flow equation has no real solution above about 1,500 vehicles/hour (one road's capacity in the conversion guide). Flow is therefore taken as the mean of a site's detectors, roughly one approach. In the default example (2000 to 3002, GRU) no directed edge exceeds capacity at 03:00, 08:00, 12:00 or 17:00, and the best route time varies with traffic (12.3 to 13.7 minutes).
- Summing all detectors gives total site volume (about 5,000 vehicles/hour at site 2000 at 08:00). It is still selectable, but saturates 105 of 112 edges at peak, fixing those speeds at the turning point (about 32 km/h) so predictions barely affect routes. Saturated edges are flagged and counted.
- Edge weights stay fixed for the departure hour. One 30-second delay per traversed edge; no extra departure delay. Identical endpoints cost zero.
- Future dates use seasonal context when observations are unavailable. Only October 2006 was available for evaluation; no real-time data is connected.
- Regression-tree tutor approval remains pending. The report is intentionally excluded.

## Troubleshooting

| Problem | Action |
|---|---|
| Python not recognised | Install Python with PATH enabled, then reopen PowerShell. |
| Missing packages | Run the launcher or install requirements with the virtual-environment Python. |
| Models missing | Train all three models first. |
| Invalid time | Use ISO date and a 15-minute boundary on/after the training cutoff. |
| Training lock after an interrupted process | Confirm no training is running, then remove `artifacts/training.lock` and retry. |
| Processed data changed | Retrain to match the new CSV. |
| Many saturated edges | Check that approach aggregation is `mean`; `sum` exceeds the guide's capacity at most sites. |

## Acknowledgements

The course-supplied VicRoads data, map and conversion guide inform the implementation. The lecturer notebook informed prediction/NRMSE interpretation but its code is not included. The team's Part A A* was ported and adapted; sources and library references are listed in [implementation details](docs/IMPLEMENTATION.md).

ChatGPT/Codex assisted with implementation, testing and documentation. Team members should review and understand the code, confirm the third model with their tutor and accurately acknowledge contributions.
