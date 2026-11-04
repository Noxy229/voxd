"""Optional real-model smoke test. Uses installed weights, never the microphone.

Run: .venv/bin/python tools/model_smoke.py
"""
import json
import socket
import time

from voxd.config import Config
from voxd.session import Callbacks, Session


def main():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    cfg = Config()
    cfg.set('edit.port', port)
    cfg.set('edit.mode', 'llm')
    cfg.set('edit.model', 'qwen3-1.7b-q4_k_m')
    session = Session(cfg, Callbacks(on_log=lambda *args: None), inject_enabled=False)
    try:
        start = time.monotonic()
        assert session.redactor.ensure(timeout=60), 'editor unavailable'
        print(json.dumps({'load_seconds': round(time.monotonic() - start, 3)}))
        for raw, expected in [
            ('Das Meeting ist am Dienstag, nein, am Mittwoch um drei Uhr.', 'Mittwoch'),
            ('Der Server läuft auf Port achttausend, nein, auf Port dreitausend.', 'dreitausend'),
            ('Kannst du mir die Datei schicken Fragezeichen neue Zeile Danke', '?\n'),
        ]:
            start = time.monotonic()
            text, note, _ = session._edit(raw)
            assert expected in text, (expected, text)
            print(json.dumps({'text': text, 'note': note,
                              'seconds': round(time.monotonic() - start, 3)}, ensure_ascii=False))
        assert session.redactor._proc.poll() is None, 'editor not resident'
        engine = session._get_engine()
        engine.load()
        assert not engine.transcribe(b'\x00' * 32000).text, 'silence produced words'
        print('Real-model smoke passed (synthetic inputs; not an accuracy benchmark).')
    finally:
        session.close()


if __name__ == '__main__':
    main()
