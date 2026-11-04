"""Keyboard-first installation dashboard. Runs before the application is installed."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Select,
    Static,
)

from . import hardware
from .bootstrap import installation_plan

STAGES = [('preflight', 'Vorbereitung'), ('dependencies', 'Systempakete'),
          ('environment', 'Python-Umgebung'), ('application', 'Anwendung'),
          ('models', 'Sprachgewichte'), ('shortcuts', 'Startmenü / Autostart')]
ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))')


@dataclass(frozen=True)
class Options:
    profile: str = 'compact'
    language: str = 'de'
    autostart: bool = False
    system_deps: bool = True
    install_dir: str = ''


def command_for(payload: Path, options: Options, windows: bool) -> list[str]:
    """Structured arguments; paths and choices never pass through a shell."""
    if options.profile not in ('compact', 'auto') or options.language not in ('de', 'en'):
        raise ValueError('Ungültiges Installationsprofil')
    if windows:
        cmd = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
               str(payload / 'install.ps1'), '-NonInteractive']
        if options.profile == 'compact':
            cmd.append('-Compact')
        if options.language == 'en':
            cmd.append('-English')
        if options.autostart:
            cmd.append('-Autostart')
        if options.install_dir:
            cmd += ['-InstallDir', options.install_dir]
    else:
        cmd = ['bash', str(payload / 'install.sh'), '--non-interactive']
        if options.profile == 'compact':
            cmd.append('--compact')
        if options.language == 'en':
            cmd.append('--english')
        if options.autostart:
            cmd.append('--autostart')
        if not options.system_deps:
            cmd.append('--no-system-deps')
    return cmd


class ConfirmCancel(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id='cancel-dialog'):
            yield Label('Installation abbrechen?')
            yield Static('Laufende Schritte werden beendet. Modelldownloads lassen sich fortsetzen.\n'
                         'Bereits installierte Systempakete werden nicht zurückgerollt.')
            with Horizontal():
                yield Button('Weiter installieren', id='keep', variant='primary')
                yield Button('Abbrechen', id='confirm-cancel', variant='error')

    @on(Button.Pressed)
    def choose(self, event: Button.Pressed):
        self.dismiss(event.button.id == 'confirm-cancel')


class InstallerApp(App[int]):
    TITLE = 'voxd'
    SUB_TITLE = 'TERMINAL INSTALLER'
    BINDINGS = [('s', 'install', 'Installieren'), ('r', 'retry', 'Wiederholen'),
                ('q', 'quit_request', 'Beenden'), ('ctrl+q', 'quit_request', 'Beenden'),
                ('ctrl+c', 'quit_request', 'Abbrechen')]
    CSS = '''
    Screen { background: #0c1118; color: #d7e2ea; }
    Header { background: #111d29; color: #70dcc3; }
    Footer { background: #111d29; }
    #body { height: 1fr; padding: 0 1; }
    #overview { height: 21; }
    .panel { border: round #3c667b; padding: 0 1; margin: 0 1 0 0; }
    #hardware-panel { width: 1fr; height: 100%; }
    #options { width: 1fr; height: auto; }
    .heading { color: #70dcc3; text-style: bold; margin-bottom: 1; }
    #hardware { height: auto; }
    #model { height: auto; color: #a9b6c9; margin-top: 1; }
    .field { margin-top: 0; color: #98adc0; }
    Select { height: 3; margin: 0; }
    Checkbox { height: 3; padding: 0; }
    Input { height: 3; }
    #activity { height: 1fr; min-height: 8; margin-top: 1; }
    #steps { width: 27; height: 100%; }
    #step-list { height: auto; }
    #log-panel { width: 1fr; height: 100%; }
    #log { height: 1fr; }
    #status { height: auto; padding: 0 1; margin-top: 1; color: #70dcc3; }
    #file { height: 1; padding: 0 1; color: #a9b6c9; }
    ProgressBar { padding: 0 1; height: 1; }
    #buttons { height: 3; align-horizontal: right; margin-top: 1; }
    #buttons Button { margin-left: 1; min-width: 18; }
    #cancel-dialog { width: 65; height: auto; border: round #dfaa6d; padding: 1 2; background: #111d29; }
    #cancel-dialog Static { margin: 1 0; }
    #cancel-dialog Horizontal { height: 3; }
    ConfirmCancel { align: center middle; background: #00000080; }
    .narrow #overview { layout: vertical; height: auto; max-height: 9999; }
    .narrow #hardware-panel { width: 100%; height: auto; }
    .narrow #options { width: 100%; }
    .narrow #steps { display: none; }
    .narrow #activity { min-height: 10; height: 15; }
    '''

    def __init__(self, payload: Path, options: Options | None = None, *, detector=hardware.detect):
        super().__init__()
        self.payload = payload.resolve()
        self.initial = options or Options()
        self.detector = detector
        self.machine = None
        self.running = False
        self.succeeded = False
        self.cancelled = False
        self.process = None
        self.stage = -1
        self.exit_status = 2

    @property
    def main_screen(self):
        return self.screen_stack[0]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id='body'):
            with Horizontal(id='overview'):
                with Vertical(classes='panel', id='hardware-panel'):
                    yield Static('01  HARDWARE', classes='heading')
                    yield Static('Hardware wird geprüft …', id='hardware', markup=False)
                    yield Static('', id='model', markup=False)
                with Vertical(classes='panel', id='options'):
                    yield Static('02  AUSWAHL', classes='heading')
                    yield Label('Spracherkennung', classes='field')
                    yield Select([('Kompakt · unter 1 GB', 'compact'),
                                  ('Automatisch · nach Hardware', 'auto')],
                                 value=self.initial.profile, allow_blank=False, id='profile')
                    yield Label('Wörterbuch', classes='field')
                    yield Select([('Deutsch · kein LLM', 'de'), ('Englisch · kein LLM', 'en')],
                                 value=self.initial.language, allow_blank=False, id='language')
                    yield Checkbox('Bei Anmeldung starten', self.initial.autostart, id='autostart')
                    if sys.platform != 'win32':
                        yield Checkbox('Systempakete installieren (sudo)', self.initial.system_deps, id='system-deps')
                    else:
                        yield Label('Installationsordner', classes='field')
                        yield Input(value=self.initial.install_dir, id='install-dir')
            with Horizontal(id='activity'):
                with Vertical(classes='panel', id='steps'):
                    yield Static('03  ABLAUF', classes='heading')
                    yield Static('', id='step-list', markup=False)
                with Vertical(classes='panel', id='log-panel'):
                    yield Static('04  LIVE-AUSGABE', classes='heading')
                    yield RichLog(id='log', markup=False, highlight=False, wrap=True, max_lines=600)
        yield Static('Hardwareprüfung läuft …', id='status', markup=False)
        yield Static('', id='file', markup=False)
        yield ProgressBar(total=100, show_eta=False, id='progress')
        with Horizontal(id='buttons'):
            yield Button('Beenden', id='quit')
            yield Button('Installieren', id='install', variant='primary', disabled=True)
        yield Footer()

    async def on_mount(self):
        self._steps()
        self.run_worker(self.detect(), exclusive=True, group='hardware')

    def on_resize(self, event):
        self.set_class(event.size.width < 88, 'narrow')

    async def detect(self):
        try:
            self.machine = await asyncio.to_thread(self.detector)
            gpu = '\n'.join(f'{g.name or g.vendor}\nVRAM: {g.vram_mb or "unbekannt"} MiB'
                            for g in self.machine.gpus) or 'GPU: nicht erkannt'
            self.main_screen.query_one('#hardware', Static).update(
                f'{self.machine.cpu.name}\n{self.machine.cpu.logical_cores} CPU-Threads\n'
                f'RAM: {self.machine.ram_mb / 1024:.1f} GiB\n\n{gpu}\n\n'
                f'Erkennung: CPU · Korrektur: Wörterbuch')
            self.update_model()
            self.main_screen.query_one('#install', Button).disabled = False
            self.main_screen.query_one('#status', Static).update('Bereit. Auswahl prüfen und mit S installieren.')
            self.main_screen.query_one('#log', RichLog).write('Anwendung noch nicht installiert. Tab wechselt zwischen den Feldern.')
        except Exception as error:
            self.main_screen.query_one('#status', Static).update(f'Hardwareprüfung fehlgeschlagen: {error}')

    @on(Select.Changed, '#profile')
    def update_model(self):
        if self.machine is None:
            return
        plan = installation_plan(self.machine, str(self.main_screen.query_one('#profile', Select).value))
        self.main_screen.query_one('#model', Static).update(
            f'{plan["model"]}\nDownload: ~{plan["download_mb"]} MB'
            + (' · schon vorhanden' if plan['installed'] else '')
            + '\nKorrektur: ~1 MB Wörterbuch, keine LLM-Gewichte.\n'
            + ('Volle Präzision. Keine GPU-Beschleunigung.' if plan['download_mb'] > 1000
               else 'INT8 · bleibt nach App-Start im Speicher.'))

    def options(self):
        return Options(str(self.main_screen.query_one('#profile', Select).value),
                       str(self.main_screen.query_one('#language', Select).value),
                       self.main_screen.query_one('#autostart', Checkbox).value,
                       self.main_screen.query_one('#system-deps', Checkbox).value if sys.platform != 'win32' else False,
                       self.main_screen.query_one('#install-dir', Input).value if sys.platform == 'win32' else '')

    def _steps(self):
        self.main_screen.query_one('#step-list', Static).update('\n'.join(
            f'{"✓" if i < self.stage or self.succeeded else "▶" if i == self.stage else "○"} {name}'
            for i, (_, name) in enumerate(STAGES)))

    def receive(self, line: str):
        line = ''.join(c for c in ANSI.sub('', line) if c >= ' ' or c == '\t').strip()
        if not line:
            return
        if line.startswith('VOXD_EVENT '):
            try:
                data = json.loads(line[11:])
                key = data.get('stage')
                if key in dict(STAGES):
                    self.stage = next(i for i, (k, _) in enumerate(STAGES) if k == key)
                    self._steps()
                    self.main_screen.query_one('#status', Static).update(f'Schritt {self.stage + 1}/6 · {dict(STAGES)[key]}')
                if 'fraction' in data:
                    self.main_screen.query_one('#progress', ProgressBar).update(total=100, progress=max(0, min(100, float(data['fraction']) * 100)))
                    rate = data.get('bytes_per_sec', 0) / (1024 * 1024)
                    self.main_screen.query_one('#file', Static).update(f'{data.get("file", "")} · {rate:.1f} MiB/s')
                else:
                    self.main_screen.query_one('#progress', ProgressBar).update(total=None)
                return
            except (ValueError, TypeError, AttributeError):
                pass
        self.main_screen.query_one('#log', RichLog).write(Text(line[:2000]))

    @on(Button.Pressed, '#install')
    def install_clicked(self):
        self.action_install()

    def action_install(self):
        if self.running or self.machine is None or self.succeeded:
            return
        self.run_worker(self.install(), exclusive=True, group='install')

    def action_retry(self):
        self.action_install()

    async def install(self):
        if self.running:
            return
        self.running = True
        self.cancelled = False
        options = self.options()
        for widget in self.query('Select, Checkbox, Input'):
            widget.disabled = True
        self.main_screen.query_one('#install', Button).disabled = True
        try:
            # Authenticate on the real terminal; sudo never reads from a log pipe.
            if sys.platform != 'win32' and options.system_deps:
                with self.suspend():
                    auth = subprocess.run(['sudo', '-v'], check=False)
                if auth.returncode:
                    raise RuntimeError('sudo-Anmeldung fehlgeschlagen. Nichts installiert.')
            args = command_for(self.payload, options, sys.platform == 'win32')
            env = dict(os.environ, VOXD_INSTALL_EVENTS='1', PYTHONUNBUFFERED='1',
                       PYTHONIOENCODING='utf-8', PIP_PROGRESS_BAR='off',
                       PIP_DISABLE_PIP_VERSION_CHECK='1')
            self.process = await asyncio.create_subprocess_exec(
                *args, cwd=self.payload, env=env, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, limit=1024 * 1024,
                start_new_session=sys.platform != 'win32')
            while chunk := await self.process.stdout.readline():
                self.receive(chunk.decode('utf-8', errors='replace'))
            result = await self.process.wait()
            if self.cancelled:
                raise RuntimeError('Abgebrochen. Bereits ausgeführte Schritte bleiben erhalten.')
            if result:
                raise RuntimeError(f'Installationsschritt fehlgeschlagen (Exit {result}). Siehe Live-Ausgabe.')
            self.succeeded = True
            self.exit_status = 0
            self._steps()
            self.main_screen.query_one('#progress', ProgressBar).update(total=100, progress=100)
            self.main_screen.query_one('#status', Static).update('Fertig · voxd ist installiert. Start über das App-Menü.')
            self.main_screen.query_one('#file', Static).update('Plasma: ydotoold/uinput kann noch eingerichtet werden müssen.')
            self.main_screen.query_one('#quit', Button).label = 'Schließen'
        except Exception as error:
            self.exit_status = 1
            self.main_screen.query_one('#status', Static).update(str(error))
            self.main_screen.query_one('#log', RichLog).write(Text(str(error), style='bold red'))
            self.main_screen.query_one('#progress', ProgressBar).update(total=100, progress=0)
        finally:
            if self.process is not None and self.process.returncode is None:
                await self.stop_process()
            self.process = None
            self.running = False
            for widget in self.query('Select, Checkbox, Input'):
                widget.disabled = self.succeeded
            button = self.main_screen.query_one('#install', Button)
            button.disabled = self.succeeded
            button.label = 'Fertig' if self.succeeded else 'Erneut versuchen'

    async def stop_process(self):
        self.cancelled = True
        proc = self.process
        if proc is None or proc.returncode is not None:
            return
        try:
            if sys.platform == 'win32':
                killer = await asyncio.create_subprocess_exec('taskkill', '/PID', str(proc.pid), '/T', '/F',
                                                               stdout=asyncio.subprocess.DEVNULL,
                                                               stderr=asyncio.subprocess.DEVNULL)
                await killer.wait()
            else:
                os.killpg(proc.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                if sys.platform == 'win32':
                    proc.kill()
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
                await proc.wait()
        except ProcessLookupError:
            pass

    @on(Button.Pressed, '#quit')
    def quit_clicked(self):
        self.action_quit_request()

    def action_quit_request(self):
        if not self.running:
            self.exit(self.exit_status)
        elif (sys.platform != 'win32' and self.stage == 1
              and self.options().system_deps):
            self.notify('Systempakete werden gerade eingerichtet. Bitte diesen Schritt beenden lassen.',
                        severity='warning', timeout=6)
        else:
            self.push_screen(ConfirmCancel(), self.cancel_answer)

    async def cancel_answer(self, confirmed):
        if confirmed and self.running:
            await self.stop_process()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, default=Path.cwd())
    parser.add_argument('--profile', choices=['auto', 'compact'], default='compact')
    parser.add_argument('--language', choices=['de', 'en'], default='de')
    parser.add_argument('--autostart', action='store_true')
    parser.add_argument('--no-system-deps', action='store_true')
    parser.add_argument('--install-dir', default='')
    args = parser.parse_args(argv)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print('Ein interaktives Terminal wird benötigt. Für Skripte: install.sh --non-interactive.', file=sys.stderr)
        return 2
    app = InstallerApp(args.payload, Options(args.profile, args.language, args.autostart,
                                            not args.no_system_deps, args.install_dir))
    return app.run() or 0


if __name__ == '__main__':
    raise SystemExit(main())
