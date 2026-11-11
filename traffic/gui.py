"""Tkinter interface: training, model evaluation, forecasts and route visualisation."""
import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .network import load_network
from .settings import ROOT, load_config


class App(tk.Tk):
    def __init__(self, config):
        super().__init__()
        self.config_data = config
        self.title('Boroondara Traffic & Route Planner')
        self.geometry(f'{min(1220, self.winfo_screenwidth()-80)}x{min(850, self.winfo_screenheight()-100)}')
        self.minsize(950, 650)
        self.configure(bg='#eef3f7')
        self.events, self.busy, self.result = queue.Queue(), False, None
        self.nodes, self.edges = load_network(config)
        self.vars = {}
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('TFrame', background='#eef3f7')
        style.configure('TLabel', background='#eef3f7', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10), padding=7)
        style.configure('Treeview', rowheight=28, font=('Segoe UI', 10))
        ttk.Label(self, text='Boroondara Traffic & Route Planner', font=('Segoe UI', 20, 'bold')).pack(anchor='w', padx=20, pady=(16, 3))
        ttk.Label(self, text='October 2006 SCATS data | LSTM, GRU and regression tree | Estimated travel times').pack(anchor='w', padx=20)
        self.tabs = ttk.Notebook(self); self.tabs.pack(fill='both', expand=True, padx=16, pady=12)
        self.routes_tab = ttk.Frame(self.tabs); self.forecast_tab = ttk.Frame(self.tabs); self.training_tab = ttk.Frame(self.tabs)
        self.scenarios_tab = ttk.Frame(self.tabs)
        for tab, title in ((self.routes_tab, 'Find routes'), (self.forecast_tab, 'Traffic prediction'),
                           (self.training_tab, 'Train & evaluate'), (self.scenarios_tab, 'Test scenarios')):
            self.tabs.add(tab, text=title)
        self.scenario_results = {}
        self.build_routes(); self.build_forecast(); self.build_training(); self.build_scenarios()
        self.status = tk.StringVar(value='Ready. First visit Train & evaluate if no models have been trained.')
        ttk.Label(self, textvariable=self.status, wraplength=1160).pack(fill='x', padx=20, pady=(0, 12))
        self.after(100, self.poll)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def field(self, parent, label, key, default, values=None, width=15):
        frame = ttk.Frame(parent); frame.pack(side='left', padx=5, pady=5)
        ttk.Label(frame, text=label).pack(anchor='w')
        variable = self.vars.setdefault(key, tk.StringVar(value=str(default)))
        if values is not None:
            widget = ttk.Combobox(frame, textvariable=variable, values=list(values), state='readonly', width=width)
        else:
            widget = ttk.Entry(frame, textvariable=variable, width=width)
        widget.pack()
        return widget

    def build_routes(self):
        form = ttk.Frame(self.routes_tab); form.pack(fill='x', padx=8, pady=6)
        cfg = self.config_data
        self.field(form, 'Origin site', 'origin', cfg['origin'], self.nodes)
        self.field(form, 'Destination site', 'destination', cfg['destination'], self.nodes)
        self.field(form, 'Date (YYYY-MM-DD)', 'date', cfg['departure'][:10])
        self.field(form, 'Time (HH:MM)', 'time', cfg['departure'][11:16], width=10)
        self.field(form, 'Model', 'model', cfg['model'], ['TREE', 'LSTM', 'GRU'], width=10)
        self.field(form, 'Routes', 'routes', cfg['routes'], range(1, 6), width=6)
        ttk.Button(form, text='Find routes', command=self.find_routes).pack(side='left', padx=10, pady=(20, 0))
        options = ttk.Frame(self.routes_tab); options.pack(fill='x', padx=8)
        self.field(options, 'Use traffic at', 'flow_site', cfg['flow_site'], ['destination', 'source'])
        self.field(options, 'Approach aggregation', 'flow_aggregation', cfg['flow_aggregation'], ['sum', 'mean'])
        self.field(options, 'Speed limit (km/h)', 'speed_limit_kmh', cfg['speed_limit_kmh'])
        self.field(options, 'Delay per edge (sec)', 'intersection_delay_seconds', cfg['intersection_delay_seconds'])
        ttk.Button(options, text='Save route results', command=self.save_routes).pack(side='left', padx=10, pady=(20, 0))
        ttk.Label(self.routes_tab, text='Simplified road graph; straight-line distances. Weights stay fixed for the departure hour. Not live navigation.',
                  foreground='#5a6575').pack(anchor='w', padx=14, pady=4)
        self.map = tk.Canvas(self.routes_tab, background='#ffffff', highlightthickness=0, height=350)
        self.map.pack(fill='both', expand=True, padx=14, pady=6)
        self.map.bind('<Configure>', lambda event: self.draw_map())
        self.table = ttk.Treeview(self.routes_tab, columns=('rank', 'minutes', 'path'), show='headings', height=5)
        for column, label, width in [('rank', 'Route', 65), ('minutes', 'Minutes', 95), ('path', 'SCATS site path (select to highlight)', 850)]:
            self.table.heading(column, text=label); self.table.column(column, width=width, stretch=column == 'path')
        self.table.pack(fill='x', padx=14, pady=6)
        self.table.bind('<<TreeviewSelect>>', lambda event: self.draw_map())

    def build_forecast(self):
        form = ttk.Frame(self.forecast_tab); form.pack(fill='x', padx=10, pady=10)
        self.field(form, 'SCATS site', 'forecast_site', self.config_data['origin'], self.nodes)
        self.field(form, 'Model', 'model', self.config_data['model'], ['TREE', 'LSTM', 'GRU'])
        ttk.Button(form, text='Predict next hour', command=self.predict_hour).pack(side='left', padx=10, pady=(20, 0))
        ttk.Label(self.forecast_tab, text='Uses the date/time and aggregation selected on Find routes. Four recursive 15-minute predictions.').pack(anchor='w', padx=15)
        self.forecast_summary = tk.StringVar(value='Choose a site and click Predict next hour.')
        ttk.Label(self.forecast_tab, textvariable=self.forecast_summary, wraplength=1100).pack(anchor='w', padx=15, pady=10)
        self.chart_frame = ttk.Frame(self.forecast_tab); self.chart_frame.pack(fill='both', expand=True, padx=15, pady=10)

    def build_training(self):
        form = ttk.Frame(self.training_tab); form.pack(fill='x', padx=10, pady=10)
        self.field(form, 'Maximum epochs', 'epochs', self.config_data['epochs'])
        self.field(form, 'History intervals', 'window', self.config_data['window'])
        ttk.Button(form, text='Prepare data', command=self.prepare_data).pack(side='left', padx=10, pady=(20, 0))
        ttk.Button(form, text='Train all 3 models', command=self.train_models).pack(side='left', padx=10, pady=(20, 0))
        ttk.Button(form, text='Load evaluation', command=self.load_metrics).pack(side='left', padx=10, pady=(20, 0))
        ttk.Label(self.training_tab, text='Training: before 22 Oct | Validation: 22-26 Oct | Test: 27-31 Oct (defaults; edit configuration to change).\n'
                  'RMSE: vehicles per 15 minutes. NRMSE: RMSE / mean actual count; lower is better, not an accuracy percentage.\n'
                  'Regression tree is implemented; tutor approval as the third model is pending.', wraplength=1100).pack(anchor='w', padx=15, pady=8)
        self.metrics = ttk.Treeview(self.training_tab, columns=('model', 'split', 'n', 'rmse', 'nrmse', 'mae'), show='headings', height=9)
        for col in self.metrics['columns']:
            self.metrics.heading(col, text=col.upper()); self.metrics.column(col, width=130, anchor='center')
        self.metrics.pack(fill='x', padx=15, pady=10)
        self.log = tk.Text(self.training_tab, height=12, bg='#162336', fg='#e8f2ff', font=('Consolas', 10), state='disabled')
        self.log.pack(fill='both', expand=True, padx=15, pady=10)

    def build_scenarios(self):
        """Tab that runs the 15 test scenarios with each model and shows each run's checks and routes."""
        form = ttk.Frame(self.scenarios_tab); form.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Button(form, text='Run 15 scenarios', command=self.run_scenarios).pack(side='left', padx=5)
        self.scenario_summary = tk.StringVar(value='15 distinct scenarios x 3 models (45 runs): normal trips, edge cases, alternative '
                                             'settings and invalid requests. Routes are checked independently; where real counts '
                                             'exist, predictions are compared with actual traffic.')
        ttk.Label(form, textvariable=self.scenario_summary, wraplength=900).pack(side='left', padx=12)
        columns = [('scenario', '#', 35), ('description', 'Scenario', 300), ('model', 'Model', 60), ('trip', 'Origin > Dest', 110),
                   ('departure', 'Departure', 130), ('routes', 'Routes', 60), ('best', 'Best min', 75),
                   ('flow', 'Flow MAE', 75), ('lost', 'Min lost', 70), ('checks', 'Checks', 60), ('result', 'Result', 60)]
        self.scenario_table = ttk.Treeview(self.scenarios_tab, columns=[c[0] for c in columns], show='headings', height=8)
        for key, label, width in columns:
            self.scenario_table.heading(key, text=label)
            self.scenario_table.column(key, width=width, anchor='w' if key == 'description' else 'center', stretch=key == 'description')
        self.scenario_table.tag_configure('PASS', background='#e3f4ea')
        self.scenario_table.tag_configure('FAIL', background='#f9dedb')
        self.scenario_table.pack(fill='x', padx=14, pady=8)
        self.scenario_table.bind('<<TreeviewSelect>>', lambda event: self.show_scenario())
        lower = ttk.Frame(self.scenarios_tab); lower.pack(fill='both', expand=True, padx=14, pady=(0, 8))
        self.scenario_map = tk.Canvas(lower, background='#ffffff', highlightthickness=0)
        self.scenario_map.pack(side='left', fill='both', expand=True)
        self.scenario_map.bind('<Configure>', lambda event: self.show_scenario())
        self.scenario_detail = tk.Text(lower, width=52, bg='#f7fafc', relief='flat', font=('Consolas', 9), state='disabled', wrap='word')
        self.scenario_detail.pack(side='left', fill='y', padx=(10, 0))
        self.scenario_detail.tag_configure('ok', foreground='#1b7a43'); self.scenario_detail.tag_configure('bad', foreground='#b3261e')
        self.scenario_detail.tag_configure('head', font=('Consolas', 10, 'bold'))

    def run_scenarios(self):
        try:
            cfg = {**self.selected_config(), 'routes': 5}  # scenarios always request the full top five
        except ValueError as error:
            messagebox.showerror('Check inputs', str(error)); return
        self.scenario_table.delete(*self.scenario_table.get_children()); self.scenario_results.clear()
        self.show_scenario()
        def calculate():
            from .check_scenarios import run_all
            rows = []
            for item in run_all(cfg, lambda text: self.events.put(('log', text))):
                self.events.put(('scenario', item)); rows.append(item[0])
            return rows
        self.work('Running 15 test scenarios...', calculate, self.scenarios_done)

    def add_scenario(self, item):
        row, result, checks = item
        number = lambda key: f'{row[key]:.2f}' if row[key] != '' else '-'
        best = 'rejected' if row['error'] else number('best_minutes')
        iid = f'{row["scenario"]}-{row["model"]}'; self.scenario_results[iid] = (row, result, checks)
        self.scenario_table.insert('', 'end', iid=iid, tags=(row['result'],), values=(
            row['scenario'], row['description'], row['model'], f'{row["origin"]} > {row["destination"]}',
            row['departure'].replace('T', ' '), row['routes'] if row['routes'] != '' else '-', best,
            number('flow_mae'), number('minutes_lost'), row['checks_passed'], row['result']))
        if len(self.scenario_results) == 1:
            self.scenario_table.selection_set(iid)

    def scenarios_done(self, rows):
        passed = sum(r['result'] == 'PASS' for r in rows)
        clipped = sum(r['capacity_clipped_edges'] or 0 for r in rows)
        text = (f'{passed}/{len(rows)} runs passed (15 scenarios x 3 models). Capacity-saturated edges across all runs: {clipped}. '
                f'Base aggregation: {self.vars["flow_aggregation"].get()}. Select a row to see its routes and checks.')
        self.scenario_summary.set(text); self.status.set(text)

    def show_scenario(self):
        selected = self.scenario_table.selection()
        row, result, checks = self.scenario_results.get(selected[0], (None, None, None)) if selected else (None, None, None)
        paths = [r['path'] for r in result['routes']] if result and not row['error'] else []
        self.draw_network(self.scenario_map, paths[0] if paths else [], paths[1:])
        self.scenario_detail.configure(state='normal'); self.scenario_detail.delete('1.0', 'end')
        if row:
            write = self.scenario_detail.insert
            write('end', f'Scenario {row["scenario"]}: {row["result"]}\n', 'head')
            write('end', f'{row["description"]}\n{row["model"]}, {row["origin"]} > {row["destination"]}, '
                         f'{row["departure"].replace("T", " ")}\nFlow: {row["flow_site"]} site, {row["flow_aggregation"]}\n'
                         f'Expected: {row["expected"]}\n\n')
            write('end', 'Checks\n', 'head')
            for name, ok in checks.items():
                write('end', ('  PASS  ' if ok else '  FAIL  ') + name + '\n', 'ok' if ok else 'bad')
            if row['error']:
                write('end', '\nError message shown to the user\n', 'head')
                write('end', f'  {row["error"]}\n')
            if not result or row['error']:
                self.scenario_detail.configure(state='disabled'); return
            write('end', '\nRoutes (best drawn solid, others dashed)\n', 'head')
            for rank, route in enumerate(result['routes'], 1):
                write('end', f'  {rank}. {route["minutes"]:.2f} min  {" > ".join(route["path"])}\n')
            write('end', f'\nSeasonal fallback inputs: {row["fallback_inputs"]}\n'
                         f'Saturated edges: {row["capacity_clipped_edges"]}/{result["edge_count"]}\n'
                         f'Search nodes created: {row["nodes_created"]}\n')
            write('end', '\nPrediction vs recorded traffic\n', 'head')
            if row['flow_mae'] == '':
                write('end', '  No recorded counts for this hour.\n')
            else:
                write('end', f'  Site flow MAE: {row["flow_mae"]:.1f} veh/h ({row["sites_with_actuals"]} sites)\n')
                if row['minutes_lost'] == '':
                    write('end', '  Some sites lack counts; route not re-costed.\n')
                else:
                    write('end', f'  Best route under actual traffic: {row["route_actual_minutes"]:.2f} min\n'
                                 f'  Best possible in hindsight: {row["hindsight_best_minutes"]:.2f} min\n'
                                 f'  Minutes lost: {row["minutes_lost"]:.2f}\n')
        self.scenario_detail.configure(state='disabled')

    def selected_config(self):
        cfg = dict(self.config_data)
        for key in ('origin', 'destination', 'model', 'flow_site', 'flow_aggregation'):
            cfg[key] = self.vars[key].get()
        cfg['departure'] = self.vars['date'].get() + 'T' + self.vars['time'].get()
        datetime.fromisoformat(cfg['departure'])
        for key in ('routes', 'epochs', 'window'):
            cfg[key] = int(self.vars[key].get())
        for key in ('speed_limit_kmh', 'intersection_delay_seconds'):
            cfg[key] = float(self.vars[key].get())
        if not 1 <= cfg['window'] <= 96 or not 1 <= cfg['epochs'] <= 1000:
            raise ValueError('History must be 1-96 intervals; epochs must be 1-1000')
        return cfg

    def work(self, label, function, done):
        if self.busy:
            messagebox.showinfo('Please wait', 'A task is already running.'); return
        self.busy = True; self.status.set(label)
        def worker():
            try:
                result = function()
                self.events.put(('done', (done, result)))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'scenario':
                    self.add_scenario(value)
                elif kind == 'log':
                    self.log.configure(state='normal'); self.log.insert('end', value + '\n')
                    self.log.see('end'); self.log.configure(state='disabled'); self.status.set(value)
                elif kind == 'error':
                    self.busy = False; self.status.set('Task failed: ' + value); messagebox.showerror('Task failed', value)
                else:
                    self.busy = False
                    callback, result = value
                    callback(result)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def find_routes(self):
        try:
            cfg = self.selected_config()
        except ValueError as error:
            messagebox.showerror('Check inputs', str(error)); return
        def calculate():
            from .route import plan
            return plan(cfg)
        self.work('Predicting traffic and finding routes...', calculate, self.show_routes)

    def show_routes(self, result):
        self.result = result
        self.table.delete(*self.table.get_children())
        for index, route in enumerate(result['routes']):
            self.table.insert('', 'end', iid=str(index), values=(index + 1, f'{route["minutes"]:.2f}', ' > '.join(route['path'])))
        if result['routes']:
            self.table.selection_set('0')
        self.status.set(f'{len(result["routes"])} route(s). Seasonal fallback inputs: {result["fallback_history_values"]}. '
                        f'Capacity saturation: {result["capacity_clipped_edges"]}/{result["edge_count"]} directed edges.')
        self.draw_map()

    def draw_map(self):
        selected = self.table.selection()
        path = self.result['routes'][int(selected[0])]['path'] if selected and self.result else []
        self.draw_network(self.map, path)

    def draw_network(self, canvas, path, alternatives=()):
        """Draw the schematic road network on `canvas`, highlighting `path` and dashing `alternatives`."""
        canvas.delete('all')
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 20 or height < 20:
            return
        lons = [n['lon'] for n in self.nodes.values()]; lats = [n['lat'] for n in self.nodes.values()]
        points = {site: (40 + (n['lon'] - min(lons)) / (max(lons) - min(lons)) * (width - 80),
                         45 + (max(lats) - n['lat']) / (max(lats) - min(lats)) * (height - 75)) for site, n in self.nodes.items()}
        for edge in self.edges:
            canvas.create_line(*points[edge['source']], *points[edge['target']], fill='#d1dbe6', width=2)
        for other in alternatives:
            for a, b in zip(other, other[1:]):
                canvas.create_line(*points[a], *points[b], fill='#e3a33b', width=2, dash=(5, 3))
        for a, b in zip(path, path[1:]):
            canvas.create_line(*points[a], *points[b], fill='#007f9e', width=4, arrow='last')
        for site, (x, y) in points.items():
            color = '#008568' if path and site == path[0] else '#c34c41' if path and site == path[-1] else '#007f9e' if site in path else '#738299'
            canvas.create_oval(x-4, y-4, x+4, y+4, fill=color, outline='white')
            canvas.create_text(x+6, y-8, text=site, anchor='w', fill='#172b45', font=('Segoe UI', 9))
        legend = 'N ↑   Schematic network | Green: origin   Red: destination   Teal: selected route'
        canvas.create_text(14, 12, text=legend + ('   Orange dashed: other routes' if alternatives else ''), anchor='nw', fill='#44566b')

    def save_routes(self):
        if not self.result:
            messagebox.showinfo('No results', 'Find routes first.'); return
        output = ROOT / 'outputs/gui_routes.json'; output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(self.result, indent=2), encoding='utf-8')
        self.status.set(f'Saved {output}')

    def predict_hour(self):
        try:
            cfg = self.selected_config(); site = self.vars['forecast_site'].get()
        except ValueError as error:
            messagebox.showerror('Check inputs', str(error)); return
        def calculate():
            import numpy as np
            from .predict import Predictor
            predictor = Predictor(cfg, cfg['model'])
            values, fallback = predictor.forecast(datetime.fromisoformat(cfg['departure']), 4)
            selected = values[[i for i, meta in enumerate(predictor.meta) if meta['key'][0] == site]]
            values = np.sum(selected, axis=0) if cfg['flow_aggregation'] == 'sum' else np.mean(selected, axis=0)
            return cfg, site, values, fallback
        self.work('Predicting the next hour...', calculate, self.show_forecast)

    def show_forecast(self, result):
        from datetime import timedelta
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        cfg, site, values, fallback = result
        for child in self.chart_frame.winfo_children():
            child.destroy()
        labels = [(datetime.fromisoformat(cfg['departure']) + timedelta(minutes=15*i)).strftime('%H:%M') for i in range(4)]
        figure = Figure(figsize=(9, 4), layout='constrained')
        ax = figure.add_subplot(111); ax.bar(labels, values, color='#007f9e')
        ax.set(title=f'{cfg["model"]}: site {site}, {cfg["departure"][:10]} ({cfg["flow_aggregation"]} of approaches)',
               ylabel='Predicted vehicles per 15 minutes', xlabel='Interval start')
        canvas = FigureCanvasTkAgg(figure, master=self.chart_frame); canvas.draw(); canvas.get_tk_widget().pack(fill='both', expand=True)
        self.forecast_summary.set(f'Next hour: {sum(values):.1f} predicted vehicles ({cfg["flow_aggregation"]} of approaches). '
                                  f'Seasonal fallback inputs across the network: {fallback}. These are estimates, not observed traffic.')
        self.status.set('Prediction complete.')

    def prepare_data(self):
        def prepare():
            from .prepare import convert
            return convert(self.config_data['source'], self.config_data['processed'])
        self.work('Preparing traffic data...', prepare,
                  lambda result: self.status.set(f'Prepared {result["output_rows"]:,} observations.'))

    def train_models(self):
        try:
            cfg = self.selected_config()
        except ValueError as error:
            messagebox.showerror('Check inputs', str(error)); return
        def train():
            from .train import train_all
            result = train_all(cfg, lambda text: self.events.put(('log', text)))
            from .evaluate import evaluate_hour
            evaluate_hour(cfg)
            return result
        self.work('Training all models; this can take several minutes...', train, self.training_done)

    def training_done(self, result):
        self.load_metrics(); self.status.set(f'Training complete: {result}')

    def load_metrics(self):
        try:
            from .predict import active_run
            with (active_run(self.config_data['artifacts']) / 'metrics.csv').open(encoding='utf-8') as handle:
                rows = list(csv.DictReader(handle))
            self.metrics.delete(*self.metrics.get_children())
            for row in rows:
                self.metrics.insert('', 'end', values=[row['model'], row['split'], row['n'],
                    f'{float(row["rmse"]):.3f}', f'{float(row["nrmse"]):.3f}' if row['nrmse'] else 'undefined', f'{float(row["mae"]):.3f}'])
            self.status.set('Loaded saved evaluation. Test results are rolling one-step forecasts.')
        except (ValueError, OSError) as error:
            messagebox.showerror('Evaluation unavailable', str(error))

    def close(self):
        if self.busy:
            messagebox.showinfo('Task running', 'Wait for the current task to finish before closing.'); return
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config')
    args = parser.parse_args()
    App(load_config(args.config)).mainloop()


if __name__ == '__main__':
    main()
