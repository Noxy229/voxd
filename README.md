# voxd

Local dictation for Linux and Windows. Audio stays on the machine. Models are
fetched from Hugging Face during setup; dictation works offline afterwards.

## Install

Python 3.10 or newer:

```bash
./install.sh
```

Or install manually:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/voxd
```

First launch detects hardware, tests the microphone and downloads the selected
models. Download errors leave setup open for retry. `llama-server` from
[llama.cpp](https://github.com/ggml-org/llama.cpp) must be on PATH for the optional
editing pass. Parakeet runs in-process through sherpa-onnx. Linux audio needs
PortAudio, or a PipeWire/PulseAudio capture tool.

## Compact, resident models

The default recogniser is Parakeet TDT 0.6B v3 **INT8**, approximately 642 MB of
weights. The default editor is **Qwen3 1.7B Q4_K_M**, approximately 1.1 GB,
replacing the previous 4B Q5_K_M default (approximately 2.78 GB).
These are prequantised upstream weights; voxd does not recompress them itself.
Runtime memory also includes inference state, the context cache and Qt.

Both models preload in the background after setup and remain loaded until
`voxctl release` or exit. `edit.idle_unload_sec = 0` disables idle eviction;
a positive value opts back into eviction. The editor uses a 4096-token context.
The initial process launch still needs loading time. Once ready, repeated
activation avoids loading weights again; transcription and editing still take time.

The smaller editor can miss corrections that the 4B editor catches. A length
check rejects unusually short or long edits, but cannot detect every semantic
mistake. Raw dictation bypasses editing. Larger models remain in the catalogue
for explicit configuration. Systems below 6 GB RAM or four logical CPUs are
recommended recognition without an editor. Version-1 settings using the old
4B default migrate to the compact preset; missing weights reopen setup.

Upstream model files: [Qwen3 1.7B GGUF](https://huggingface.co/unsloth/Qwen3-1.7B-GGUF),
[Parakeet INT8](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8).

## KDE Plasma

Plasma Wayland and X11 have explicit setup and injection paths. Full end-to-end
operation still needs verification on the target desktop and applications.

On **Plasma Wayland**, install `wl-clipboard` and `ydotool`, then configure your
distribution's `ydotoold` service and uinput permissions. voxd first copies the
Unicode transcript and sends Ctrl+V through ydotool. If key injection is
unavailable, text remains in the clipboard for manual Ctrl+V. `wtype` is not a
required Plasma dependency: KWin does not provide its virtual-keyboard route.
`xdotool` is reserved for X11 and is not used as a misleading Wayland fallback.

At the end of setup, voxd creates three application launchers using the absolute
`voxctl` path. Open **System Settings → Keyboard → Shortcuts → Add New → Application**,
search for **voxd**, and assign:

| Action | Suggested shortcut | Command |
|---|---|---|
| Start/finish dictation | Meta+H | `voxctl toggle` |
| Dictate without editing | Meta+Shift+H | `voxctl raw-toggle` |
| Discard recording | Meta+Alt+H | `voxctl cancel` |

KDE resolves conflicts in its native UI; voxd does not overwrite existing global
shortcuts. GNOME, Hyprland and Sway have separate shortcut backends. Other desktops
receive manual binding instructions. niri and river do not have automatic backends.

Plasma Wayland uses tray status and error notifications. A real KWin smoke test
showed that Qt's ordinary overlay stole keyboard focus despite its no-focus flag;
that surface is therefore suppressed on Plasma Wayland. A native layer-shell
overlay remains future work. Other sessions use the noninteractive overlay.
Clipboard managers such as Klipper may retain dictated text. voxd does not delete
clipboard history. Successful paste restores previous nonempty text clipboard
contents; arbitrary MIME formats and clipboard-manager history are not preserved.

## Controls and settings

`voxd` starts the tray application. `voxd --setup` reopens setup. `voxctl status`
reports model and session state; `voxctl release` explicitly frees model memory.
The next recording loads it again. `voxctl quit` shuts down capture and workers
before unloading models. A new dictation is ignored while the previous result
is being processed, to prevent cross-talk and insertion into the wrong session.

Settings use the platform's configuration directory (on Linux,
`$XDG_CONFIG_HOME/voxd/config.toml`, normally `~/.config/voxd/config.toml`).
Downloaded weights live in the corresponding data directory. To start on login,
add `voxd` through Plasma's **Autostart** settings using its installed absolute path.

Audio recordings are capped at ten minutes. Microphone level monitoring does not
retain audio. Transcripts are kept in memory for raw reinsertion, but are not
included in normal completion logs or `voxctl status`.

## Development and verification

```bash
.venv/bin/pip install -e '.[dev]' build
QT_QPA_PLATFORM=offscreen .venv/bin/pytest
.venv/bin/ruff check src tests
.venv/bin/python -m build
```

Tests cover model residency wiring, configuration migration, session concurrency,
shutdown, Plasma launchers and paste fallback, download truncation, IPC, and Qt
setup behavior. Offscreen tests cannot prove real KWin focus, portal behavior,
ydotool permissions or dictation accuracy. Windows code is not hardware verified.
See [release verification](docs/RELEASE.md) before publishing.

## License

MIT — see [LICENSE](LICENSE). Dependencies and model weights retain their own
licenses: sherpa-onnx (Apache-2.0), Parakeet weights (CC-BY-4.0), Qwen3 (Apache-2.0),
Qt/PySide6 (LGPL-3.0), llama.cpp and whisper.cpp (MIT).
