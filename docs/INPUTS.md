# Supplied inputs

These files were supplied for COS30019 Assignment 2B and are preserved unchanged.
Paths below are relative to the repository root.

| File | Purpose | Used by current code? |
|---|---|---|
| `data/raw/Scats Data October 2006.xls` | October 2006 traffic counts in 15-minute intervals | Yes, input to `traffic.prepare` |
| `data/raw/SCATSSiteListingSpreadsheet_VicRoads.xls` | Reference listing of SCATS sites | No, retained for graph development |
| `data/raw/Traffic_Count_Locations_with_LONG_LAT.csv` | Traffic-count location coordinates | No, retained for location matching; do not assume its IDs directly match SCATS IDs |
| `docs/reference/COS30019-2026 S2-A2_B.pdf` | Assignment requirements and marking criteria | Reference document |
| `docs/reference/IBM data_Bor.pdf` | Boroondara road/site map | Reference document |
| `docs/reference/Traffic Flow to Travel Time Conversion v1.0.pdf` | Flow-to-travel-time conversion guide | Reference for a future implementation stage |

The converter supports the October workbook's `Data` sheet layout. It is not
a general importer for the other spreadsheet or CSV. Missing days in the supplied
traffic data are left missing; see the main README for validation results.

Run `run_demo.bat` on Windows to recreate the processed CSV, quality summary and
example plot. These outputs and Python packages are generated locally rather than
stored in Git. Use `run_app.bat` for the full GUI, training, prediction and routing
workflow. See the main README for road-graph and conversion assumptions.
