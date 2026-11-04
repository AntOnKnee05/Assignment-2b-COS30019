# COS30019 Assignment 2B

Traffic prediction and route guidance for Boroondara. This first implementation
prepares the supplied October 2006 SCATS workbook and plots a recorded series.
It is not yet the complete Part B system.

## Setup on Windows

Use Python 3.10 or newer from the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No activation is required for the commands below. Keep your supplied datasets
locally. Raw workbooks, generated data, plots and the virtual environment are
excluded from Git. The original workbook is never edited.

## Prepare the traffic data

```powershell
.\.venv\Scripts\python.exe -m traffic.prepare "C:\Users\Fyone\Downloads\Scats Data October 2006.xls"
```

Replace the path with your own workbook location. Optional output override:
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

## Plot one day

```powershell
.\.venv\Scripts\python.exe -m traffic.plot_day --site 0970 --location-id 1 --date 2006-10-01
```

The chart is saved as `outputs/site_0970_day.png`. For another series, supply the
site, internal location ID and date, and optionally `--output outputs/my_day.png`.
Use `--input` to select a different prepared CSV. A selection that mixes different
location descriptions is rejected. Missing intervals appear as gaps, not zeros.
The chart shows recorded traffic, not predictions.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Nine tests cover interval/date decoding, zero-padded IDs, separate internal
locations, duplicate detection, missing values, invalid counts, interval headers,
atomic output replacement and plotting selection. The real workbook conversion
and chart generation were also checked locally.

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
