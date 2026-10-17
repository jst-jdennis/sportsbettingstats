"""The archive tool must finish a run even when a server trickles bytes forever."""
import http.server
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/fast":
            body = b"<!doctype html><html>fast</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/slow":
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.end_headers()
            try:
                while True:
                    self.wfile.write(b"x" * 10)
                    self.wfile.flush()
                    time.sleep(0.25)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_response(404)
            self.end_headers()


def test_archive_docs_run_ends_despite_a_trickling_server(tmp_path: Path):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = dict(os.environ, WPDC_FETCH_DEADLINE="2", WPDC_DOC_DEADLINE="6", WPDC_ARCHIVE_WORKERS="3",
               NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
    base = f"http://127.0.0.1:{port}"
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-m", "wpdc_ingest.archive_docs", str(tmp_path), f"{base}/fast", f"{base}/slow", f"{base}/missing"],
                          cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, timeout=60)
    elapsed = time.time() - t0
    srv.shutdown()
    recs = {json.loads(l)["url"].rsplit("/", 1)[1]: json.loads(l) for l in (tmp_path / "index.jsonl").read_text().splitlines()}
    assert proc.returncode == 1  # one or more documents failed
    assert recs["fast"]["file"].endswith(".html")
    assert "exceeded 2s" in recs["slow"]["error"]
    assert "404" in recs["missing"]["error"]
    assert elapsed < 20, elapsed
