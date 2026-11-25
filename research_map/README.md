# OpenStreetMap research viewer

This is a geographical display of saved TBRGS outputs. It is separate from the Tkinter GUI.

## Run

From the repository root, double-click `run_map.bat`, or run:

```powershell
.\run_map.bat
```

Alternatively, with Python 3.10 or later:

```powershell
python research_map/serve_map.py
```

The launcher opens a local browser page and serves only this folder on 127.0.0.1. Keep its terminal open; press Ctrl+C to stop. No additional Python packages, model training, or PyTorch imports are needed. Internet is required for Leaflet and OpenStreetMap tiles. Do not open map.html directly as a file.

## Included example

The saved example is 2000 to 3002, 30 October 2006 at 08:00, LSTM, mean aggregation, A* (AS). Route 1 has a model estimate of 13.78 minutes. Click each alternative to highlight it; toggle its traffic overlay, or click a site or coloured road for details.

Use **Save route results** in the Tkinter GUI, then select that `outputs/gui_routes.json` with the viewer's file control. The cached road geometry covers only the five included site sequences and coordinates. Other journeys display a message instead of drawing straight lines; this release does not generate new road geometry automatically.

## Meaning and limitations

- TBRGS determines the SCATS sequence, predicted flows and estimated minutes.
- OSRM supplies driving-road geometry through the supplied points. It does not calculate the displayed TBRGS minutes. Road geometry is for visualisation and does not change the search graph or its weights.
- Traffic colours represent predicted flow divided by the assignment conversion equation's capacity: below 50%, 50–100%, and above 100%. These are not observed congestion categories.
- Detector-average coordinates are unverified. OSRM snapping to a nearby road does not establish the intended named intersection. Some points snap to side streets. The display is not verified navigation advice.
- The underlying historical data are from October 2006; the background and OSRM road network are not a reconstruction of 2006 roads.
- No usability study or real-world travel-time validation has been completed.
- Retain the visible OpenStreetMap attribution in report screenshots.

## Sources and provenance

`sample_routes.json` is the saved main GUI result used for the matching schematic figure. `road_geometry.json` contains five OSRM route responses reduced to paths, requested coordinates, geometry, legs and snapped waypoints. These were retrieved on 25 November 2026 from `https://router.project-osrm.org/route/v1/driving/` with `overview=full`, `geometries=geojson`, `steps=true` and `continue_straight=true`. It contains public SCATS locations, not personal GPS history.

- OpenStreetMap contributors: street-map data and background tiles, https://www.openstreetmap.org/copyright
- Tile usage policy: https://operations.osmfoundation.org/policies/tiles/
- OSRM: driving route geometry, https://project-osrm.org/docs/v5.24.0/api/
- Leaflet 1.9.4: interactive map rendering, https://leafletjs.com/

## Validation

Run `python research_map/check_data.py` to check that all five cached routes match the sample's site sequences and coordinates, have one geometry leg per graph edge, and contain finite coordinates. This is a consistency check, not an independent verification of road restrictions or intersection positions.
