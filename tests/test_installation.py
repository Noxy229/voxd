from types import SimpleNamespace

import pytest

from voxd import bootstrap, config
from voxd.spelling import SpellingEditor


def machine(ram=8192, cores=4, vram=None):
    gpu = SimpleNamespace(name='Test GPU', vendor='nvidia', vram_mb=vram) if vram else None
    return SimpleNamespace(ram_mb=ram, cpu=SimpleNamespace(logical_cores=cores),
                           best_gpu=gpu, gpus=[gpu] if gpu else [])


def test_default_has_no_llm_and_small_asr(monkeypatch):
    monkeypatch.setattr(bootstrap.download, 'is_installed', lambda _: False)
    plan = bootstrap.installation_plan(machine())
    assert plan['download_mb'] < 1000
    assert plan['model'].endswith('int8')
    assert 'no LLM' in plan['editing']


def test_hardware_selection_and_compact_override():
    strong = machine(ram=32768, cores=16, vram=12288)
    assert bootstrap.installation_plan(strong)['model'].endswith('fp32')
    assert bootstrap.installation_plan(strong, 'compact')['model'].endswith('int8')
    assert bootstrap.installation_plan(machine(ram=4096, vram=12288))['model'].endswith('int8')


def test_failed_download_never_marks_setup_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap.ipc, 'daemon_running', lambda: False)
    monkeypatch.setattr(bootstrap, 'ensure_dirs', lambda: None)
    monkeypatch.setattr(bootstrap, 'MODEL_DIR', tmp_path)
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'config.toml')
    def fail(*args):
        raise RuntimeError('network offline')
    monkeypatch.setattr(bootstrap.download, 'fetch_all', fail)
    with pytest.raises(RuntimeError, match='offline'):
        bootstrap.provision({'model': 'parakeet-tdt-0.6b-v3-int8',
                             'download_mb': 640, 'installed': True})
    assert not config.CONFIG_PATH.exists()


def test_provision_preserves_audio_and_commits_only_after_success(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap.ipc, 'daemon_running', lambda: False)
    monkeypatch.setattr(bootstrap, 'ensure_dirs', lambda: None)
    monkeypatch.setattr(config, 'ensure_dirs', lambda: None)
    monkeypatch.setattr(bootstrap, 'MODEL_DIR', tmp_path)
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'config.toml')
    config.CONFIG_PATH.write_text('[audio]\ndevice=7\n')
    fetched = []
    monkeypatch.setattr(bootstrap.download, 'fetch_all', lambda ids, cb: fetched.extend(ids))
    bootstrap.provision({'model': 'parakeet-tdt-0.6b-v3-int8', 'download_mb': 640,
                         'installed': True}, 'en')
    cfg = config.Config.load()
    assert cfg.get('setup.completed')
    assert cfg.get('audio.device') == 7
    assert cfg.get('edit.language') == 'en'
    assert cfg.get('edit.model') == ''
    assert fetched == ['parakeet-tdt-0.6b-v3-int8']


def test_real_german_dictionary_preserves_protected_tokens():
    editor = SpellingEditor('de')
    assert editor.edit('das ist wirklcih gut') == 'Das ist wirklich gut'
    text = 'Qwen Noxy229 https://exmaple.com `wirklcih` user@example.com'
    assert editor.edit(text) == text
    assert editor.edit('das ist einn test') == 'Das ist einn test'  # ambiguous
    assert editor.edit('Kannst du das Fragezeichen neue Zeile Danke') == 'Kannst du das?\nDanke'
    assert editor.edit('https://exmaple.com') == 'https://exmaple.com'
    editor.unload()
    assert editor._spell is None


def test_plan_only_does_not_provision(monkeypatch):
    monkeypatch.setattr(bootstrap.hardware, 'detect', lambda: machine())
    def forbidden(*a):
        raise AssertionError('plan-only invocation must not write settings')
    monkeypatch.setattr(bootstrap, 'provision', forbidden)
    assert bootstrap.main([]) == 0
