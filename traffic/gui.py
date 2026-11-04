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
        for tab, title in ((self.routes_tab, 'Find routes'), (self.forecast_tab, 'Traffic prediction'), (self.training_tab, 'Train & evaluate')):
            self.tabs.add(tab, text=title)
        self.build_routes(); self.build_forecast(); self.build_training()
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
                if kind == 'log':
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
        self.map.delete('all')
        width, height = self.map.winfo_width(), self.map.winfo_height()
        if width < 20 or height < 20:
            return
        lons = [n['lon'] for n in self.nodes.values()]; lats = [n['lat'] for n in self.nodes.values()]
        points = {site: (40 + (n['lon'] - min(lons)) / (max(lons) - min(lons)) * (width - 80),
                         30 + (max(lats) - n['lat']) / (max(lats) - min(lats)) * (height - 60)) for site, n in self.nodes.items()}
        for edge in self.edges:
            self.map.create_line(*points[edge['source']], *points[edge['target']], fill='#d1dbe6', width=2)
        selected = self.table.selection()
        path = self.result['routes'][int(selected[0])]['path'] if selected and self.result else []
        for a, b in zip(path, path[1:]):
            self.map.create_line(*points[a], *points[b], fill='#007f9e', width=4, arrow='last')
        for site, (x, y) in points.items():
            color = '#008568' if path and site == path[0] else '#c34c41' if path and site == path[-1] else '#007f9e' if site in path else '#738299'
            self.map.create_oval(x-4, y-4, x+4, y+4, fill=color, outline='white')
            self.map.create_text(x+6, y-8, text=site, anchor='w', fill='#172b45', font=('Segoe UI', 9))
        self.map.create_text(14, 12, text='N ↑   Schematic network | Green: origin   Red: destination   Teal: selected route', anchor='nw', fill='#44566b')

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
