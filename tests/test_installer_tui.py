import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.widgets import Button, Select, Static

from voxd.installer_tui import InstallerApp, Options, command_for


def machine():
    return SimpleNamespace(cpu=SimpleNamespace(name='Test CPU', logical_cores=8),
                           ram_mb=8192, gpus=[], best_gpu=None)


def test_backend_arguments_do_not_use_shell_and_preserve_spaces(tmp_path):
    path = tmp_path / 'directory with spaces'
    windows = command_for(path, Options(install_dir=r'C:\Users\Example User\voxd'), True)
    assert windows[windows.index('-File') + 1] == str(path / 'install.ps1')
    assert windows[-1] == r'C:\Users\Example User\voxd'
    assert '-NonInteractive' in windows
    linux = command_for(path, Options(system_deps=False), False)
    assert linux[:2] == ['bash', str(path / 'install.sh')]
    assert '--non-interactive' in linux and '--no-system-deps' in linux


@pytest.mark.asyncio
async def test_keyboard_profile_selection_and_progress(tmp_path):
    app = InstallerApp(tmp_path, detector=machine)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        assert not app.query_one('#install', Button).disabled
        app.query_one('#profile', Select).focus()
        await pilot.press('enter', 'down', 'enter')
        assert app.query_one('#profile', Select).value == 'auto'
        app.receive('VOXD_EVENT {"stage":"models","fraction":0.5,"file":"encoder.onnx","bytes_per_sec":1048576}')
        assert app.stage == 4
        assert 'encoder.onnx' in str(app.query_one('#file', Static).content)
        app.receive('VOXD_EVENT not-json')  # corrupted output must stay harmless
        app.receive('[not rich markup] plain log output')


@pytest.mark.asyncio
async def test_real_subprocess_installs_only_after_start_and_retries(tmp_path, monkeypatch):
    # Controlled subprocess tests the actual stream/exit path without OS changes.
    marker = tmp_path / 'started'
    script = tmp_path / 'backend.py'
    script.write_text('from pathlib import Path\n'
                      f'Path({str(marker)!r}).write_text("yes")\n'
                      'print(\'VOXD_EVENT {"stage":"models","fraction":1,"file":"test"}\',flush=True)\n'
                      'raise SystemExit(3)\n')
    monkeypatch.setattr('voxd.installer_tui.command_for', lambda *a: [sys.executable, str(script)])
    app = InstallerApp(tmp_path, Options(system_deps=False), detector=machine)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        assert not marker.exists()
        await pilot.click('#install')
        for _ in range(40):
            await pilot.pause(.03)
            if marker.exists() and not app.running:
                break
        assert marker.exists()
        assert not app.succeeded
        assert app.exit_status == 1
        assert not app.query_one('#install', Button).disabled
        script.write_text('print(\'VOXD_EVENT {"stage":"shortcuts"}\',flush=True)\n')
        await pilot.click('#install')
        for _ in range(40):
            await pilot.pause(.03)
            if app.succeeded:
                break
        assert app.succeeded
        assert app.exit_status == 0


@pytest.mark.asyncio
async def test_cancellation_reaps_subprocess(tmp_path, monkeypatch):
    script = tmp_path / 'slow.py'
    script.write_text('import time\nprint("ready",flush=True)\ntime.sleep(30)\n')
    monkeypatch.setattr('voxd.installer_tui.command_for', lambda *a: [sys.executable, str(script)])
    app = InstallerApp(tmp_path, Options(system_deps=False), detector=machine)
    async with app.run_test(size=(90, 35)) as pilot:
        await pilot.pause()
        await pilot.click('#install')
        for _ in range(30):
            await pilot.pause(.02)
            if app.process:
                break
        proc = app.process
        assert proc is not None
        await app.stop_process()
        await pilot.pause(.1)
        assert proc.returncode is not None
        assert app.cancelled and not app.succeeded


@pytest.mark.asyncio
async def test_narrow_terminal_remains_navigable(tmp_path):
    app = InstallerApp(tmp_path, detector=machine)
    async with app.run_test(size=(65, 28)) as pilot:
        await pilot.pause()
        app.query_one('#profile', Select).focus()
        await pilot.press('tab')
        assert app.query_one('#language', Select).has_focus


@pytest.mark.asyncio
async def test_live_progress_keeps_working_while_cancel_dialog_is_open(tmp_path):
    app = InstallerApp(tmp_path, detector=machine)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        app.running = True
        app.action_quit_request()
        await pilot.pause()
        app.receive('VOXD_EVENT {"stage":"models","fraction":0.1,"file":"encoder.onnx"}')
        app.receive('Downloader is still running while the user chooses.')
        assert app.stage == 4
        await pilot.click('#keep')
        app.running = False


def test_curl_pipe_fetches_payload_and_forwards_arguments(tmp_path):
    import io
    import os
    import subprocess
    import tarfile
    import textwrap
    archive = tmp_path / 'source.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        content = b'#!/bin/bash\nprintf "PAYLOAD:%s\\n" "$*"\n'
        info = tarfile.TarInfo('voxd-main/install.sh')
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    stub = tmp_path / 'curl'
    stub.write_text(textwrap.dedent(f'''\
        #!/bin/bash
        while [[ $# -gt 0 ]]; do
            if [[ "$1" == -o ]]; then cp '{archive}' "$2"; exit; fi
            shift
        done
        exit 1
    '''))
    stub.chmod(0o755)
    source = Path('install.sh').read_text()
    result = subprocess.run(['bash', '-s', '--', '--non-interactive', '--compact'], input=source,
                            text=True, capture_output=True,
                            env=dict(os.environ, PATH=f'{tmp_path}:' + os.environ['PATH']))
    assert result.returncode == 0, result.stderr
    assert 'PAYLOAD:--non-interactive --compact' in result.stdout
