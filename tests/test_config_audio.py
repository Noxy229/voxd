try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from voxd import audio, config


def test_config_instances_do_not_share_mutable_defaults():
    first, second = config.Config(), config.Config()
    first.set('edit.level', 'minimal')
    assert second.get('edit.level') == 'strong'


def test_toml_roundtrip_control_characters():
    data = {'audio': {'device': 'USB\n"mic"\t\\'}}
    assert tomllib.loads(config._dump(data)) == data


def test_old_defaults_migrate_without_resetting_custom_options(tmp_path, monkeypatch):
    path = tmp_path / 'config.toml'
    path.write_text('[setup]\nversion=1\ncompleted=true\n[edit]\n'
                    'model="qwen3-4b-q5_k_m"\nidle_unload_sec=90\nlevel="minimal"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', path)
    cfg = config.Config.load()
    assert cfg.get('edit.model') == ''
    assert cfg.get('edit.mode') == 'spelling'
    assert cfg.get('edit.idle_unload_sec') == 0
    assert cfg.get('edit.level') == 'minimal'
    assert cfg.get('setup.completed')


def test_recording_memory_is_bounded(monkeypatch):
    monkeypatch.setattr(audio, 'MAX_RECORD_SEC', 1)
    rec = audio.Recorder()
    rec._feed(b'x' * 64000)
    rec._feed(b'x' * 64000)
    assert len(rec.pcm) == audio.SAMPLE_RATE * 2
    assert rec.error


def test_monitor_does_not_accumulate_audio():
    monitor = audio.LevelMonitor(None, lambda _: None)
    monitor.rec._feed(b'x' * 3200)
    assert not monitor.rec.pcm
