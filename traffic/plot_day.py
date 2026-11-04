"""Plot one site's recorded traffic for one day, keeping detector series separate."""
import argparse
import csv
from datetime import date, datetime
from pathlib import Path

from .prepare import site_id


def load_day(source, site, internal_location, day):
    date.fromisoformat(day)
    selected = {}
    labels = set()
    with Path(source).open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            if (row['scats_site'], row['vr_internal_loc'], row['date']) != (site_id(site), str(internal_location), day):
                continue
            time = datetime.strptime(row['start_time'], '%H:%M')
            minute = time.hour * 60 + time.minute
            if minute % 15 or minute in selected:
                raise ValueError('Invalid or duplicate time slot in the selected series')
            labels.add(row['location'])
            selected[minute] = float(row['vehicle_count']) if row['vehicle_count'] else float('nan')
    if not selected:
        raise ValueError('No records match this site, internal location and date')
    if len(labels) != 1:
        raise ValueError('Selection contains multiple locations; do not mix series')
    return next(iter(labels)), [selected.get(i * 15, float('nan')) for i in range(96)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('data/processed/scats_15min.csv'))
    parser.add_argument('--site', default='0970')
    parser.add_argument('--location-id', type=int, default=1)
    parser.add_argument('--date', default='2006-10-01')
    parser.add_argument('--output', type=Path, default=Path('outputs/site_0970_day.png'))
    args = parser.parse_args()
    try:
        label, values = load_day(args.input, args.site, args.location_id, args.date)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Plot failed: {error}\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4.7), layout='constrained')
    ax.plot([i / 4 for i in range(96)], values, color='#1864ab', linewidth=1.8)
    ax.set(title=f'SCATS {site_id(args.site)} | Internal location {args.location_id} | {args.date}\n{label}',
           xlabel='Time of day (interval start)', ylabel='Vehicles per 15 minutes', xlim=(0,24), ylim=(0,None))
    ax.set_xticks(range(0,25,2), [f'{h:02}:00' for h in range(0,25,2)])
    ax.grid(alpha=.2)
    ax.spines[['top','right']].set_visible(False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)
    print(f'Saved {args.output}. Missing measurements appear as gaps, not zeros.')


if __name__ == '__main__':
    main()
