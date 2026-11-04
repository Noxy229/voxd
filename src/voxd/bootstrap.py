"""Hardware-aware, transactional first installation shared by both installers."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from . import catalog, download, hardware, ipc
from .config import MODEL_DIR, STATE_DIR, Config, ensure_dirs


def installation_plan(machine, profile='auto') -> dict:
    rec = catalog.recommend(machine)
    model = catalog.get('parakeet-tdt-0.6b-v3-int8') if profile == 'compact' else rec.asr
    return {'model': model.id, 'download_mb': model.size_mb,
            'installed': download.is_installed(model.id), 'device': 'cpu',
            'ram_mb': machine.ram_mb, 'cores': machine.cpu.logical_cores,
            'gpus': [{'name': g.name, 'vendor': g.vendor, 'vram_mb': g.vram_mb}
                     for g in machine.gpus],
            'editing': 'offline dictionary + rules (no LLM)',
            'reason': rec.reason if profile == 'auto' else 'Compact recognition explicitly selected.'}


def provision(plan, language='de', progress=None):
    if ipc.daemon_running():
        raise RuntimeError('Quit voxd before installing/updating settings.')
    ensure_dirs()
    required = 256 * 1024 * 1024
    if not plan['installed']:
        required += plan['download_mb'] * 1024 * 1024
    if shutil.disk_usage(MODEL_DIR).free < required:
        raise RuntimeError('Not enough free space for the selected model and download reserve.')
    # Keep existing working settings if downloading or dictionary loading fails.
    download.fetch_all([plan['model']], progress)
    from .spelling import SpellingEditor
    editor = SpellingEditor(language)
    editor.load()
    editor.unload()
    cfg = Config.load()
    if cfg.problem:
        raise RuntimeError(cfg.problem)
    for key, value in {'asr.model': plan['model'], 'asr.device': 'cpu',
                       'edit.enabled': True, 'edit.mode': 'spelling',
                       'edit.model': '', 'edit.language': language,
                       'edit.idle_unload_sec': 0, 'setup.version': 3,
                       'setup.completed': True}.items():
        cfg.set(key, value)
    cfg.save()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Download models and save settings')
    parser.add_argument('--profile', choices=['auto', 'compact'], default='auto')
    parser.add_argument('--language', choices=['de', 'en'], default='de')
    args = parser.parse_args(argv)
    try:
        plan = installation_plan(hardware.detect(), args.profile)
        report = json.dumps(plan, indent=2, ensure_ascii=False)
        if sys.stdout is not None:
            print(report, flush=True)
        else:
            ensure_dirs()
            (STATE_DIR / 'installation.log').write_text(report + '\n', encoding='utf-8')
        if args.apply:
            last = [-1]
            def progress(p):
                percent = int(p.fraction * 100)
                if percent != last[0]:
                    if sys.stdout is not None:
                        if os.environ.get('VOXD_INSTALL_EVENTS') == '1':
                            print('VOXD_EVENT ' + json.dumps({'stage': 'models', 'file': p.file_name,
                                  'fraction': p.fraction, 'bytes_per_sec': p.bytes_per_sec}), flush=True)
                        else:
                            print(f'{p.file_name}: {percent}%', flush=True)
                    last[0] = percent
            provision(plan, args.language, progress)
            if sys.stdout is not None:
                print('voxd installation ready. Models preload when the application starts.')
        return 0
    except Exception as e:
        if sys.stderr is not None:
            print(f'Installation failed: {e}', file=sys.stderr)
        else:
            ensure_dirs()
            with (STATE_DIR / 'installation.log').open('a', encoding='utf-8') as log:
                log.write(f'Installation failed: {e}\n')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
