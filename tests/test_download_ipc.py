import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from voxd import download, ipc


@pytest.fixture
def http():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Length', '10')
            self.end_headers()
            self.wfile.write(b'truncated')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}/file'
    server.shutdown()
    thread.join()
    server.server_close()


def test_truncated_download_is_not_marked_complete(http, tmp_path):
    dest = tmp_path / 'model'
    with pytest.raises(download.DownloadError):
        download._fetch(http, dest)
    assert not dest.exists()
    assert dest.with_suffix('.part').exists()


def test_model_removal_rejects_paths_outside_catalogue(tmp_path, monkeypatch):
    monkeypatch.setattr(download, 'MODEL_DIR', tmp_path / 'models')
    assert not download.remove('../private')


def test_ipc_roundtrip_and_second_daemon_protection(tmp_path, monkeypatch):
    monkeypatch.setattr(ipc, 'runtime_dir', lambda: tmp_path)
    server = ipc.Server({'status': lambda: {'ready': True}}, log=lambda *a: None)
    server.start()
    try:
        assert ipc.send('status') == '{"ready": true}'
        with pytest.raises(RuntimeError):
            ipc.Server({}).start()
        assert ipc.send('status') == '{"ready": true}'
    finally:
        server.stop()
