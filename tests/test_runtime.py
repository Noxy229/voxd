import threading
from types import SimpleNamespace

from voxd import catalog
from voxd.config import Config
from voxd.session import Session


def test_compact_defaults_and_residency():
    cfg = Config()
    assert cfg.get('edit.model') == 'qwen3-1.7b-q4_k_m'
    assert cfg.get('edit.idle_unload_sec') == 0
    machine = SimpleNamespace(ram_mb=32768, best_gpu=None,
                              cpu=SimpleNamespace(logical_cores=16))
    assert catalog.recommend(machine).llm.id == cfg.get('edit.model')


def test_preload_warms_both_models(monkeypatch):
    session = Session(Config(), inject_enabled=False)
    ready = threading.Event()
    monkeypatch.setattr(session, '_get_engine', lambda: SimpleNamespace(load=lambda: None))
    monkeypatch.setattr(session.redactor, 'ensure', lambda: ready.set())
    session.preload()
    assert ready.wait(1), 'editing model must load before the first recording'
    session.redactor.close()


def test_busy_session_rejects_new_recording(monkeypatch):
    from voxd import audio
    session = Session(Config(), inject_enabled=False)
    session._busy = True
    def forbidden(*a, **kw):
        raise AssertionError('must not open microphone during insertion')
    monkeypatch.setattr(audio, 'Recorder', forbidden)
    session.start()
    assert not session.recording
    session._busy = False
    session.close()


def test_close_waits_for_warmup_and_unloads(monkeypatch):
    session = Session(Config(), inject_enabled=False)
    loaded, unloaded = [], []
    engine = SimpleNamespace(load=lambda: loaded.append(True),
                             unload=lambda: unloaded.append(True))
    monkeypatch.setattr(session, '_get_engine', lambda: engine)
    session._engine = engine
    monkeypatch.setattr(session.redactor, 'ensure', lambda: True)
    session.preload()
    session.close()
    assert unloaded
    assert not session._workers
    assert not session.redactor._watch.is_alive()


def test_punctuation_commands_preserve_question_and_newline():
    from voxd.redact import spoken_punctuation
    assert spoken_punctuation('Kannst du mir die Datei schicken Fragezeichen neue Zeile Danke') == (
        'Kannst du mir die Datei schicken?\nDanke')
    assert spoken_punctuation('Das bringt es auf den Punkt.') == 'Das bringt es auf den Punkt.'


def test_editor_cannot_silently_remove_question_or_requested_line_breaks(monkeypatch):
    session = Session(Config(), inject_enabled=False)
    monkeypatch.setattr(type(session.redactor), 'enabled', property(lambda _: True))
    monkeypatch.setattr(session.redactor, 'edit', lambda raw: 'Die Datei schicken.')
    try:
        out, note, _ = session._edit(
            'Kannst du mir die Datei schicken Fragezeichen neue Zeile Danke')
        assert out == 'Kannst du mir die Datei schicken?\nDanke'
        assert 'removed a question' in note
    finally:
        session.close()
