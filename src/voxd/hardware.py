"""Hardware detection, feeding the model recommendation.

Runs on Linux and Windows. Anything that cannot be determined becomes None, and
the recommendation logic then errs on the conservative side rather than guessing.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"


def _run(cmd, timeout=4):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


# ---------------------------------------------------------------- GPU

@dataclass
class Gpu:
    vendor: str                 # nvidia | amd | intel | apple | unknown
    name: str
    vram_mb: int | None = None
    backend: str | None = None  # cuda | vulkan | rocm | metal
    # Live values, only where the system exposes them (Linux/AMD via sysfs):
    vram_used_mb: int | None = None
    busy_percent: int | None = None
    _sysfs: str | None = None

    def free_mb(self) -> int | None:
        if self.vram_mb is None or self.vram_used_mb is None:
            return None
        return self.vram_mb - self.vram_used_mb


def _gpus_linux() -> list[Gpu]:
    out = []
    # Live values come from sysfs, and only amdgpu/i915 provide them.
    for dev in sorted(Path("/sys/class/drm").glob("card*/device")):
        total = dev / "mem_info_vram_total"
        if not total.exists():
            continue
        vendor_id = (dev / "vendor").read_text().strip() if (dev / "vendor").exists() else ""
        vendor = {"0x1002": "amd", "0x10de": "nvidia", "0x8086": "intel"}.get(vendor_id, "unknown")
        try:
            vram = int(total.read_text()) // (1024 * 1024)
        except Exception:
            vram = None
        g = Gpu(vendor=vendor, name="", vram_mb=vram, _sysfs=str(dev))
        out.append(g)

    # Fill in names via lspci - sysfs only knows numeric IDs.
    lspci = _run(["lspci", "-mm"])
    names = [ln for ln in lspci.splitlines() if re.search(r'"(VGA|3D|Display)', ln)]
    for g, ln in zip(out, names):
        m = re.findall(r'"([^"]*)"', ln)
        if len(m) >= 3:
            g.name = m[2].strip()          # field 2 is the chip; 3 would be the board vendor

    if not out:  # no sysfs data - at least recover the name
        for ln in names:
            m = re.findall(r'"([^"]*)"', ln)
            nm = m[2].strip() if len(m) >= 3 else "?"
            low = nm.lower()
            vendor = ("nvidia" if "nvidia" in low else
                      "amd" if ("amd" in low or "ati" in low) else
                      "intel" if "intel" in low else "unknown")
            out.append(Gpu(vendor=vendor, name=nm))

    # NVIDIA only reports VRAM through nvidia-smi.
    if shutil.which("nvidia-smi"):
        smi = _run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits"])
        rows = [r.split(",") for r in smi.strip().splitlines() if r.strip()]
        nv = [g for g in out if g.vendor == "nvidia"] or [Gpu("nvidia", "")]
        if nv[0] not in out:
            out.extend(nv)
        for g, row in zip(nv, rows):
            try:
                g.name = g.name or row[0].strip()
                g.vram_mb = int(row[1])
                g.vram_used_mb = int(row[2])
                g.busy_percent = int(row[3])
            except Exception:
                pass
    return out


def _gpus_windows() -> list[Gpu]:
    # PowerShell rather than WMIC - WMIC is gone from current Windows releases.
    ps = _run([
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,AdapterCompatibility | ConvertTo-Json -Compress",
    ], timeout=15)
    out = []
    try:
        data = json.loads(ps) if ps.strip() else []
        if isinstance(data, dict):
            data = [data]
        for d in data:
            nm = (d.get("Name") or "").strip()
            low = (nm + " " + (d.get("AdapterCompatibility") or "")).lower()
            vendor = ("nvidia" if "nvidia" in low else
                      "amd" if ("amd" in low or "radeon" in low) else
                      "intel" if "intel" in low else "unknown")
            ram = d.get("AdapterRAM")
            # AdapterRAM overflows above 4 GB (32-bit field) - prefer None over a lie.
            vram = int(ram) // (1024 * 1024) if isinstance(ram, int) and 0 < ram < 2**32 - 1 else None
            out.append(Gpu(vendor=vendor, name=nm, vram_mb=vram))
    except Exception:
        pass

    if shutil.which("nvidia-smi"):
        smi = _run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits"], timeout=15)
        for i, row in enumerate([r.split(",") for r in smi.strip().splitlines() if r.strip()]):
            try:
                g = next((x for x in out if x.vendor == "nvidia"), None) or Gpu("nvidia", "")
                if g not in out:
                    out.append(g)
                g.name = row[0].strip()
                g.vram_mb, g.vram_used_mb, g.busy_percent = int(row[1]), int(row[2]), int(row[3])
            except Exception:
                pass
    return out


def detect_gpus() -> list[Gpu]:
    try:
        gpus = _gpus_windows() if IS_WINDOWS else _gpus_linux() if IS_LINUX else []
    except Exception:
        gpus = []
    if IS_MAC and not gpus:
        gpus = [Gpu("apple", platform.processor() or "Apple Silicon", backend="metal")]
    for g in gpus:
        g.backend = _backend_for(g)
    # Largest first - the recommendation keys off the best card.
    gpus.sort(key=lambda g: (g.vram_mb or 0), reverse=True)
    return gpus


def _backend_for(g: Gpu) -> str | None:
    if g.vendor == "apple":
        return "metal"
    if g.vendor == "nvidia":
        return "cuda" if shutil.which("nvidia-smi") else "vulkan"
    if has_vulkan():
        return "vulkan"
    return None


_vulkan_cache: bool | None = None


def has_vulkan() -> bool:
    """Is a Vulkan loader present? A good enough proxy for "GPU is usable"."""
    global _vulkan_cache
    if _vulkan_cache is not None:
        return _vulkan_cache
    if IS_WINDOWS:
        _vulkan_cache = Path(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                             "vulkan-1.dll").exists()
    else:
        _vulkan_cache = any(Path(p).exists() for p in (
            "/usr/lib/libvulkan.so.1", "/usr/lib64/libvulkan.so.1",
            "/usr/lib/x86_64-linux-gnu/libvulkan.so.1"))
    return _vulkan_cache


def refresh_gpu_live(g: Gpu) -> Gpu:
    """Refresh VRAM usage and utilisation where the system offers them."""
    if g._sysfs:
        d = Path(g._sysfs)
        try:
            g.vram_used_mb = int((d / "mem_info_vram_used").read_text()) // (1024 * 1024)
            g.busy_percent = int((d / "gpu_busy_percent").read_text())
        except Exception:
            pass
    elif g.vendor == "nvidia" and shutil.which("nvidia-smi"):
        smi = _run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits"])
        row = smi.strip().splitlines()[:1]
        if row:
            try:
                used, busy = row[0].split(",")
                g.vram_used_mb, g.busy_percent = int(used), int(busy)
            except Exception:
                pass
    return g


# ---------------------------------------------------------------- CPU

@dataclass
class Cpu:
    name: str
    physical_cores: int
    logical_cores: int
    efficiency_cores: list[int] = field(default_factory=list)
    performance_cores: list[int] = field(default_factory=list)

    @property
    def has_hybrid(self) -> bool:
        return bool(self.efficiency_cores and self.performance_cores)


def detect_cpu() -> Cpu:
    logical = os.cpu_count() or 2
    name, physical = platform.processor() or "", logical
    perf: list[int] = []
    eff: list[int] = []

    if IS_LINUX:
        try:
            info = Path("/proc/cpuinfo").read_text()
            m = re.search(r"model name\s*:\s*(.+)", info)
            if m:
                name = m.group(1).strip()
            physical = len({ln.split(":")[1].strip()
                            for ln in info.splitlines() if ln.startswith("core id")}) or logical
        except Exception:
            pass
        # Performance and efficiency cores differ in maximum clock. That is the
        # most reliable signal available without extra packages.
        freqs: dict[int, int] = {}
        for c in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*")):
            f = c / "cpufreq/cpuinfo_max_freq"
            if f.exists():
                try:
                    freqs[int(c.name[3:])] = int(f.read_text())
                except Exception:
                    pass
        if freqs and len(set(freqs.values())) > 1:
            hi = max(freqs.values())
            perf = sorted(i for i, v in freqs.items() if v >= hi * 0.95)
            eff = sorted(i for i, v in freqs.items() if v < hi * 0.95)

    elif IS_WINDOWS:
        name = os.environ.get("PROCESSOR_IDENTIFIER", name)
        ps = _run(["powershell", "-NoProfile", "-Command",
                   "(Get-CimInstance Win32_Processor | "
                   "Measure-Object NumberOfCores -Sum).Sum"], timeout=15)
        try:
            physical = int(ps.strip()) or logical
        except Exception:
            pass

    return Cpu(name=name or "unknown", physical_cores=physical,
               logical_cores=logical, efficiency_cores=eff, performance_cores=perf)


# ---------------------------------------------------------------- RAM / OS

def total_ram_mb() -> int:
    if IS_LINUX:
        try:
            for ln in Path("/proc/meminfo").read_text().splitlines():
                if ln.startswith("MemTotal:"):
                    return int(ln.split()[1]) // 1024
        except Exception:
            pass
    elif IS_WINDOWS:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MS()
        st.dwLength = ctypes.sizeof(MS)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullTotalPhys) // (1024 * 1024)
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024)
    except Exception:
        return 4096


def detect_desktop() -> dict:
    """Which desktop are we on? Decides hotkey route and text injection."""
    if IS_WINDOWS:
        return {"os": "windows", "release": platform.release(), "session": "win32",
                "desktop": "windows"}
    if IS_MAC:
        return {"os": "macos", "release": platform.mac_ver()[0], "session": "quartz",
                "desktop": "aqua"}
    distro = ""
    try:
        for ln in Path("/etc/os-release").read_text().splitlines():
            if ln.startswith("PRETTY_NAME="):
                distro = ln.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return {
        "os": "linux",
        "distro": distro,
        "release": platform.release(),
        "session": os.environ.get("XDG_SESSION_TYPE", "unknown"),
        "desktop": (os.environ.get("XDG_CURRENT_DESKTOP")
                    or os.environ.get("DESKTOP_SESSION") or "unknown"),
        "package_manager": detect_package_manager(),
    }


def detect_package_manager() -> str | None:
    for mgr in ("pacman", "apt-get", "dnf", "zypper", "apk", "xbps-install", "emerge"):
        if shutil.which(mgr):
            return "apt" if mgr == "apt-get" else mgr
    return None


# ---------------------------------------------------------------- Gesamtbild

@dataclass
class Machine:
    cpu: Cpu
    ram_mb: int
    gpus: list[Gpu]
    system: dict

    @property
    def best_gpu(self) -> Gpu | None:
        usable = [g for g in self.gpus if g.backend and (g.vram_mb or 0) >= 2000]
        return usable[0] if usable else None

    def summary(self) -> list[tuple[str, str]]:
        """Rows for the installer - what was detected, stated plainly."""
        c = self.cpu
        cores = f"{c.physical_cores} cores / {c.logical_cores} threads"
        if c.has_hybrid:
            cores += (f"  ({len(c.performance_cores)} performance, "
                      f"{len(c.efficiency_cores)} efficiency threads)")
        rows = [("Processor", f"{c.name}"), ("Cores", cores),
                ("Memory", f"{self.ram_mb / 1024:.0f} GB")]
        if self.gpus:
            for g in self.gpus:
                v = f"{g.vram_mb / 1024:.0f} GB" if g.vram_mb else "size unknown"
                b = f", {g.backend}" if g.backend else ", not usable"
                rows.append(("Graphics", f"{g.name or g.vendor} — {v}{b}"))
        else:
            rows.append(("Graphics", "no discrete card detected"))
        s = self.system
        osname = s.get("distro") or s.get("os", "?")
        rows.append(("System", f"{osname} ({s.get('session', '?')}, {s.get('desktop', '?')})"))
        return rows

    def to_dict(self) -> dict:
        return {"cpu": asdict(self.cpu), "ram_mb": self.ram_mb,
                "gpus": [asdict(g) for g in self.gpus], "system": self.system}


def detect() -> Machine:
    return Machine(cpu=detect_cpu(), ram_mb=total_ram_mb(),
                   gpus=detect_gpus(), system=detect_desktop())


if __name__ == "__main__":
    m = detect()
    for k, v in m.summary():
        print(f"  {k:18s} {v}")
