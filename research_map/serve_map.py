"""Serve the geographic research viewer locally; no model dependencies needed."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

if __name__ == '__main__':
    folder = Path(__file__).resolve().parent
    with ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(folder))) as server:
        url = f'http://127.0.0.1:{server.server_port}/map.html'
        print(f'Open {url}\nPress Ctrl+C to stop.', flush=True)
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
