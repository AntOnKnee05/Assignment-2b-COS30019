# COS30019 Assignment 2B

Traffic prediction and route guidance for Boroondara. This first implementation
prepares the supplied October 2006 SCATS workbook and plots a recorded series.
It is not yet the complete Part B system.

## 1. Get the project

You need Python 3.10 or newer, Git (if cloning), and an internet connection for
the first dependency installation. Check Python in PowerShell:

```powershell
python --version
```

For your first download, open PowerShell in the folder where you want to keep
the project, then run:

```powershell
git clone https://github.com/AntOnKnee05/Assignment-2b-COS30019.git
cd Assignment-2b-COS30019
```

If you already have the repository, open PowerShell in that repository folder
and run `git pull` instead. Alternatively, download the ZIP from GitHub and
extract it before running the program. All required input files are included.

## 2. Run the demo (easiest option)

Double-click `run_demo.bat` in the project folder, or run this in PowerShell
from that folder:

```powershell
.\run_demo.bat
```

The launcher creates a Python environment if needed, installs dependencies,
converts the included traffic workbook, and saves a chart for site **0970**,
internal location **1**, on **1 October 2006**. Wait until it prints `Done.`,
then press any key to close the launcher.

The following files will be created inside the project folder:

| File | What it contains |
|---|---|
| `data/processed/scats_15min.csv` | 402,432 traffic observations from the supplied workbook |
| `data/processed/scats_15min.summary.json` | Counts of sites, series, observations and missing data |
| `outputs/site_0970_day.png` | A chart of recorded traffic for the example day |

Open the PNG in File Explorer, or use PowerShell:

```powershell
Invoke-Item .\outputs\site_0970_day.png
```

The demo saves a chart; it does not open a GUI. Prediction models, route finding
and the GUI are still under development. Running the demo again recreates these
generated files.

## 3. Run individual steps (optional)

If you ran the demo successfully, setup and data preparation are already done.
To run manually, use the following commands from the project folder.

### Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No activation is required for the commands below. The supplied datasets are in
`data/raw/` and the assignment brief, map and conversion guide are in
`docs/reference/`. See [the input inventory](docs/INPUTS.md) for their roles.
Generated data, plots and the virtual environment are excluded from Git because
they can be recreated. The original workbook is never edited.

### Prepare the traffic data

```powershell
.\.venv\Scripts\python.exe -m traffic.prepare "data/raw/Scats Data October 2006.xls"
```

Optional output override:
`--output data/processed/scats_15min.csv`.

The converter reads the `Data` sheet and writes:

- `data/processed/scats_15min.csv`: one row per location and 15-minute interval.
- `data/processed/scats_15min.summary.json`: source and quality counts.

Columns: `scats_site`, `location`, `vr_internal_loc`, `date`, `start_time`,
`vehicle_count`. Site identifiers remain zero-padded strings, e.g. `0970`.
Excel may automatically remove leading zeros if you open a CSV directly; import
that column as text when viewing it in Excel.

Each series is identified by site, location description and internal location ID.
Keep these identifiers together when building training sequences. Site 4335
contains two different internal locations with the same description and different
counts; they must not be collapsed as duplicates.

The Date field's time component is ignored. V00-V95 are mapped using the checked
interval-start header: 00:00, 00:15, ... 23:45. Counts must be finite nonnegative
integers. Invalid measurements and duplicate location-days fail validation.
A failed conversion leaves an existing CSV intact instead of publishing a partial
replacement. Blank measurements stay blank, valid zeros stay zero, and absent days
are not fabricated or filled. Output follows workbook order; sort each series by
date and time before training.

Validated on the supplied workbook on 4 November 2026:

| Measure | Value |
|---|---:|
| Source location-days | 4,192 |
| Sites | 40 |
| Separate location series | 140 |
| Dates | 31 (1-31 October 2006) |
| Output observations | 402,432 |
| Blank measurements within supplied rows | 0 |
| Absent series-days across the 31 observed dates | 148 |
| Sum of all recorded counts | 41,845,199 |

The sum counts observations at different locations, not unique vehicles across
Boroondara. The first hour for site 0970, location 1, on 1 October is
86 + 83 + 52 + 58 = 279 recorded vehicles.

### Plot one day

```powershell
.\.venv\Scripts\python.exe -m traffic.plot_day --site 0970 --location-id 1 --date 2006-10-01
```

The chart is saved as `outputs/site_0970_day.png`. For another series, supply the
site, internal location ID and date, and optionally `--output outputs/my_day.png`.
Use `--input` to select a different prepared CSV. A selection that mixes different
location descriptions is rejected. Missing intervals appear as gaps, not zeros.
The chart shows recorded traffic, not predictions.

| Argument | Meaning in the example |
|---|---|
| `--site 0970` | SCATS intersection/site identifier |
| `--location-id 1` | Internal measurement location at that site |
| `--date 2006-10-01` | Date to display, in year-month-day format |

Choose combinations that exist in the prepared CSV. To keep a new chart without
replacing the example, add `--output outputs/my_day.png` to the command.

## 4. Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Nine tests cover interval/date decoding, zero-padded IDs, separate internal
locations, duplicate detection, missing values, invalid counts, interval headers,
atomic output replacement and plotting selection. The real workbook conversion
and chart generation were also checked locally.

A successful run ends with `Ran 9 tests` and `OK`.

## Troubleshooting

| Problem | What to do |
|---|---|
| `python` is not recognised or opens the Microsoft Store | Install Python 3.10 or newer with the option to add Python to PATH, then reopen PowerShell. |
| PowerShell cannot find `run_demo.bat` | Open PowerShell in the extracted/cloned project folder and use `.\run_demo.bat`. |
| Dependency installation fails | Check your internet connection and the displayed error, then rerun the launcher. |
| The prepared CSV is missing | Run the demo or the data preparation command before plotting. |
| No matching series is found | Check that the site, internal location ID and date exist together in the prepared CSV. Some days are absent. |
| No chart window opens | Open `outputs/site_0970_day.png` manually; plotting saves a file. |

## Next implementation stages

- Split each series chronologically into training, validation and test periods.
  Fit scalers on training data only and do not create windows across missing days.
- Train and evaluate LSTM, GRU and a third tutor-approved model.
- Implement the supplied flow-to-travel-time conversion. Resolve the discrepancy
  between the brief (destination site's volume) and conversion guide (starting
  site's volume) before choosing the convention.
- Build the road graph and integrate up to five routes from Part A.
- Add the required GUI, default configuration and end-to-end tests.

Those stages are not implemented in this commit. The CSV is preparatory data,
not yet model-ready windows or a trained predictor.

## Acknowledgement

The dataset is the course-supplied VicRoads SCATS workbook. ChatGPT/Codex assisted
with preprocessing, plotting, tests and documentation. Team members should review
the code, understand the data assumptions and record actual contributions.
