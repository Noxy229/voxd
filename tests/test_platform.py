from types import SimpleNamespace

from voxd.hotkeys import linux as hotkeys
from voxd.inject import linux


def test_plasma_creates_launchers_with_absolute_command(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'KDE')
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path))
    monkeypatch.setattr(hotkeys.shutil, 'which', lambda _: None)
    result = hotkeys.apply({'toggle': 'Super+H', 'raw': 'Super+Shift+H'},
                           '/opt/my app/bin/voxctl')
    assert not result.ok  # user must confirm conflicts in KDE's native UI
    assert 'Shortcuts' in result.manual_hint
    text = (tmp_path / 'applications/org.voxd.toggle.desktop').read_text()
    assert 'Exec="/opt/my app/bin/voxctl" toggle' in text


def test_kwin_paste_falls_back_after_wtype_protocol_failure(monkeypatch):
    monkeypatch.setattr(linux, 'WAYLAND', True)
    monkeypatch.setattr(linux.shutil, 'which', lambda name: name)
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd[0])
        return SimpleNamespace(returncode=1 if cmd[0] == 'wtype' else 0)
    monkeypatch.setattr(linux, '_run', run)
    assert linux._press_paste()
    assert calls == ['wtype', 'ydotool']


def test_plasma_clipboard_order(monkeypatch):
    monkeypatch.setattr(linux, 'WAYLAND', True)
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'KDE')
    assert linux.default_order()[0] == 'clipboard'


def test_failed_paste_keeps_transcript(monkeypatch):
    writes = []
    monkeypatch.setattr(linux, 'get_clipboard', lambda: b'previous')
    monkeypatch.setattr(linux, 'set_clipboard', lambda value: writes.append(value) or True)
    monkeypatch.setattr(linux, '_press_paste', lambda: False)
    monkeypatch.setattr(linux.time, 'sleep', lambda _: None)
    assert not linux.type_clipboard('Grüße')
    assert writes == ['Grüße']
