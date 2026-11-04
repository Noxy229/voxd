import os
import time
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from voxd.ui.overlay import Overlay
from voxd.ui.widgets import label
from voxd.ui.wizard import Wizard


@pytest.fixture(scope='module')
def qt():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def wizard(qt, monkeypatch):
    machine = SimpleNamespace(
        ram_mb=8192, best_gpu=None, cpu=SimpleNamespace(logical_cores=8),
        system={'os': 'linux', 'session': 'wayland', 'desktop': 'KDE'}, summary=lambda: [])
    monkeypatch.setattr(Wizard, 'list_inputs', lambda _: [{'label': 'Default', 'id': 7}])
    win = Wizard(machine=machine)
    yield win
    win.close()


def test_dynamic_text_is_not_interpreted_as_html(qt):
    assert label('<b>dictated text</b>').textFormat() == Qt.PlainText


def test_overlay_thinking_cancels_previous_hide(qt):
    overlay = Overlay()
    overlay.tray_only = False
    overlay.show_done('previous', hold_ms=10)
    overlay.show_thinking('next')
    assert not overlay._hide_timer.isActive()
    assert overlay.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert overlay.windowFlags() & Qt.WindowTransparentForInput
    overlay.dismiss()


def test_download_page_does_not_duplicate_rows(wizard):
    page = wizard.stack.widget(6)
    page.on_enter()
    count = page.rows.box.count()
    page.on_enter()
    assert page.rows.box.count() == count
    assert wizard.result()['audio_device'] is None
    wizard.stack.widget(4).combo.setCurrentIndex(1)
    assert wizard.result()['audio_device'] == 7


def test_finish_waits_for_download_and_returns_to_ui_thread(wizard, qt, monkeypatch):
    from voxd import download
    calls, finished = [], []
    monkeypatch.setattr(download, 'fetch_all', lambda ids, cb: calls.extend(ids))
    wizard.finished.connect(finished.append)
    wizard.stack.setCurrentIndex(6)
    wizard.next()
    deadline = time.monotonic() + 2
    while not finished and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.005)
    assert calls == ['parakeet-tdt-0.6b-v3-int8', 'qwen3-1.7b-q4_k_m']
    assert finished
    assert not wizard._downloading


def test_plasma_wayland_suppresses_focus_stealing_overlay(qt, monkeypatch):
    from voxd.ui import overlay as module
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    monkeypatch.setattr(module.QGuiApplication, "platformName", lambda: "wayland")
    win = Overlay()
    win.show_listening()
    assert win.tray_only
    assert not win.isVisible()
    assert not win._tick.isActive()
