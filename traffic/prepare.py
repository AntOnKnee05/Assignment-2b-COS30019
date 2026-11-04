"""Convert the supplied XLS into long-format traffic observations.

Run: python -m traffic.prepare SOURCE.xls --output data/processed/scats_15min.csv
"""
import argparse
import csv
import json
import math
import os
import tempfile
from pathlib import Path

import xlrd

FIELDS = ['scats_site', 'location', 'vr_internal_loc', 'date', 'start_time', 'vehicle_count']


def integer(value, label):
    if isinstance(value, bool):
        raise ValueError(f'{label}: expected an integer')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label}: expected a number, got {value!r}') from None
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError(f'{label}: expected a finite nonnegative integer, got {value!r}')
    return int(number)


def site_id(value):
    """Normalize numeric Excel ids while preserving leading-zero site labels."""
    return str(integer(value, 'SCATS Number')).zfill(4)


def observations(sheet, datemode, stats):
    headers = sheet.row_values(1)
    required = ['SCATS Number', 'Location', 'VR Internal Loc', 'Date'] + [f'V{i:02}' for i in range(96)]
    for name in required:
        if headers.count(name) != 1:
            raise ValueError(f'Expected exactly one column named {name}')
    columns = {name: headers.index(name) for name in required}
    for i in range(96):
        start = sheet.cell_value(0, columns[f'V{i:02}'])
        if not isinstance(start, (float, int)) or not math.isclose(start * 1440, i * 15, abs_tol=1e-6):
            raise ValueError(f'Unexpected interval start for V{i:02}: {start!r}')
    seen = set()
    sites, series, dates = set(), set(), set()
    for row in range(2, sheet.nrows):
        values = sheet.row_values(row)
        if all(v == '' for v in values):
            continue
        site = site_id(values[columns['SCATS Number']])
        location = str(values[columns['Location']]).strip()
        if not location:
            raise ValueError(f'Missing location at Excel row {row + 1}')
        loc_id = integer(values[columns['VR Internal Loc']], 'VR Internal Loc')
        raw_date = values[columns['Date']]
        if sheet.cell_type(row, columns['Date']) != xlrd.XL_CELL_DATE:
            raise ValueError(f'Expected Excel date at row {row + 1}')
        # Ignore the time component in Date. Row 1 defines interval starts.
        day = xlrd.xldate_as_datetime(raw_date, datemode).date().isoformat()
        key = site, location, loc_id, day
        if key in seen:
            raise ValueError(f'Duplicate location/day at Excel row {row + 1}: {key}')
        seen.add(key)
        sites.add(site); series.add((site, location, loc_id)); dates.add(day)
        stats['source_rows'] += 1
        for i in range(96):
            col = columns[f'V{i:02}']
            value = values[col]
            if value == '' and sheet.cell_type(row, col) in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                count = ''  # Retain the time slot; never turn missing into zero.
                stats['missing_measurements'] += 1
            else:
                if sheet.cell_type(row, col) != xlrd.XL_CELL_NUMBER:
                    raise ValueError(f'Expected numeric count at row {row + 1}, V{i:02}')
                count = integer(value, f'row {row + 1}, V{i:02}')
                stats['sum_vehicle_counts'] += count
                stats['observed_measurements'] += 1
            stats['output_rows'] += 1
            yield [site, location, loc_id, day, f'{i // 4:02}:{i % 4 * 15:02}', count]
    stats.update(sites=len(sites), series=len(series), dates=len(dates),
                 first_date=min(dates) if dates else None,
                 last_date=max(dates) if dates else None)
    # Counts absent series-days within dates represented anywhere in the file.
    # This flags gaps without inventing measurements or assuming zero traffic.
    stats['absent_series_days'] = len(series) * len(dates) - len(seen)


def convert(source, output):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Output must differ from the source workbook')
    stats = dict(source_file=source.name, source_rows=0, output_rows=0,
                 missing_measurements=0, observed_measurements=0, sum_vehicle_counts=0)
    book = xlrd.open_workbook(str(source), on_demand=True)
    temporary = None
    try:
        sheet = book.sheet_by_name('Data')
        output.parent.mkdir(parents=True, exist_ok=True)
        # Validate while streaming, then replace output only after complete success.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.writer(handle)
            writer.writerow(FIELDS)
            writer.writerows(observations(sheet, book.datemode, stats))
        os.replace(temporary, output)
    finally:
        book.release_resources()
        if temporary and temporary.exists():
            temporary.unlink()
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/processed/scats_15min.csv'))
    args = parser.parse_args()
    try:
        stats = convert(args.source, args.output)
    except (ValueError, OSError, xlrd.XLRDError) as error:
        parser.exit(1, f'Preparation failed: {error}\n')
    summary = args.output.with_suffix('.summary.json')
    summary.write_text(json.dumps(stats, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(stats, indent=2))
    print(f'Saved {args.output} and {summary}')


if __name__ == '__main__':
    main()
