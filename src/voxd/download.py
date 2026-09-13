"""Fetching models.

Downloads to a temporary name and renames on completion, so an interrupted
download can never look like a finished model. Resumes where the server allows
it, and reports progress so the wizard can show something truthful.
"""

from __future__ import annotations

import os
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import catalog
from .config import MODEL_DIR

UA = "voxd/0.1 (+https://github.com/Noxy229/voxd)"
CHUNK = 1 << 18


@dataclass
class Progress:
    model_id: str
    file_name: str
    done_bytes: int
    total_bytes: int
    file_index: int
    file_count: int
    bytes_per_sec: float = 0.0

    @property
    def fraction(self) -> float:
        return (self.done_bytes / self.total_bytes) if self.total_bytes else 0.0

    @property
    def eta_seconds(self) -> float | None:
        if self.bytes_per_sec <= 0 or not self.total_bytes:
            return None
        return max(0.0, (self.total_bytes - self.done_bytes) / self.bytes_per_sec)


class DownloadError(RuntimeError):
    pass


def model_dir(model_id: str) -> Path:
    return MODEL_DIR / model_id


def is_installed(model_id: str) -> bool:
    model = catalog.get(model_id)
    if model is None:
        return False
    d = model_dir(model_id)
    return all((d / f.name).exists() for f in model.files)


def installed_bytes(model_id: str) -> int:
    d = model_dir(model_id)
    if not d.exists():
        return 0
    return sum(p.stat().st_size for p in d.glob("*") if p.is_file())


def remove(model_id: str) -> bool:
    d = model_dir(model_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


def _fetch(url: str, dest: Path, on_chunk=None) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0

    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if have:
        req.add_header("Range", f"bytes={have}-")

    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if have and e.code in (416, 501):     # range not supported: start over
            part.unlink(missing_ok=True)
            have = 0
            resp = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60)
        else:
            raise DownloadError(f"{url}: HTTP {e.code}") from e
    except Exception as e:
        raise DownloadError(f"{url}: {e}") from e

    with resp:
        if resp.status == 200:
            have = 0                           # server ignored the range
        length = int(resp.headers.get("Content-Length") or 0)
        total = have + length
        mode = "ab" if have and resp.status == 206 else "wb"
        started, last = time.time(), have
        with open(part, mode) as fh:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                have += len(chunk)
                if on_chunk:
                    elapsed = max(1e-6, time.time() - started)
                    on_chunk(have, total, (have - last) / elapsed)
    os.replace(part, dest)


def fetch_model(model_id: str, on_progress=None) -> Path:
    """Download every file of a model. Returns its directory."""
    model = catalog.get(model_id)
    if model is None:
        raise DownloadError(f"unknown model: {model_id}")
    d = model_dir(model_id)
    d.mkdir(parents=True, exist_ok=True)

    for i, f in enumerate(model.files, start=1):
        dest = d / f.name
        if dest.exists():
            continue

        def report(done, total, rate, _f=f, _i=i):
            if on_progress:
                on_progress(Progress(model_id, _f.name, done,
                                     total or _f.size_mb * 1024 * 1024,
                                     _i, len(model.files), rate))
        _fetch(f.url, dest, report)
    return d


def fetch_all(model_ids: list[str], on_progress=None) -> list[Path]:
    return [fetch_model(mid, on_progress) for mid in model_ids
            if mid and not is_installed(mid)]
