"""Modellkatalog und Empfehlung.

Jeder Eintrag traegt, woher die Tempoangabe stammt: `measured` heisst, auf
echter Hardware gemessen (siehe `measured_on`), `estimated` heisst geschaetzt.
Der Installer zeigt das an - geschaetzte Zahlen sollen nicht wie Messwerte
aussehen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HF = "https://huggingface.co"


@dataclass
class ModelFile:
    name: str
    url: str
    size_mb: int


@dataclass
class Model:
    id: str
    kind: str                      # "asr" | "llm" | "vad"
    engine: str                    # "parakeet" | "whispercpp" | "llamacpp"
    title: str
    blurb: str
    files: list[ModelFile]
    languages: str = "mehrsprachig"
    license: str = ""
    # Tempoangabe: Faktor gegenueber Echtzeit (hoeher ist besser)
    speed_cpu: float | None = None
    speed_gpu: float | None = None
    speed_source: str = "estimated"      # "measured" | "estimated"
    measured_on: str = ""
    min_ram_mb: int = 0
    min_vram_mb: int = 0
    needs_gpu: bool = False

    @property
    def size_mb(self) -> int:
        return sum(f.size_mb for f in self.files)


def _parakeet(tag: str, quant: str, enc_mb: int, dec_mb: int, join_mb: int,
              **kw) -> Model:
    repo = f"csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3{tag}"
    sfx = ".int8" if quant == "int8" else ""
    return Model(
        id=f"parakeet-tdt-0.6b-v3-{quant}", kind="asr", engine="parakeet",
        title=f"Parakeet TDT 0.6B v3 ({quant})",
        files=[ModelFile(f"encoder{sfx}.onnx", f"{HF}/{repo}/resolve/main/encoder{sfx}.onnx", enc_mb),
               ModelFile(f"decoder{sfx}.onnx", f"{HF}/{repo}/resolve/main/decoder{sfx}.onnx", dec_mb),
               ModelFile(f"joiner{sfx}.onnx", f"{HF}/{repo}/resolve/main/joiner{sfx}.onnx", join_mb),
               ModelFile("tokens.txt", f"{HF}/{repo}/resolve/main/tokens.txt", 1)],
        languages="25 Sprachen, u. a. Deutsch und Englisch",
        license="CC-BY-4.0 (NVIDIA)", **kw)


def _whisper(name: str, size_mb: int, title: str, blurb: str, **kw) -> Model:
    return Model(
        id=f"whisper-{name}", kind="asr", engine="whispercpp", title=title, blurb=blurb,
        files=[ModelFile(f"ggml-{name}.bin",
                         f"{HF}/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin", size_mb)],
        languages="99 Sprachen", license="MIT (OpenAI-Gewichte)", **kw)


def _qwen(size: str, quant: str, size_mb: int, repo: str, fname: str, **kw) -> Model:
    return Model(
        id=f"qwen3-{size}-{quant}".lower(), kind="llm", engine="llamacpp",
        title=f"Qwen3 {size} ({quant})",
        files=[ModelFile(fname, f"{HF}/{repo}/resolve/main/{fname}", size_mb)],
        languages="mehrsprachig", license="Apache-2.0", **kw)


# ------------------------------------------------------------------ Katalog

CATALOG: list[Model] = [
    # --- Spracherkennung ------------------------------------------------
    _parakeet(
        "-int8", "int8", 622, 12, 7,
        blurb="Der Standard. Erstaunlich schnell auf der CPU, setzt von sich aus "
              "Satzzeichen und Großschreibung. Braucht keine Grafikkarte.",
        speed_cpu=15.0, speed_gpu=None, speed_source="measured",
        measured_on="i5-13600KF, 8 Threads: 15× Echtzeit · nur 2 Kerne: 5× Echtzeit",
        min_ram_mb=2048),
    _whisper(
        "large-v3-turbo", 1625,
        "Whisper large-v3-turbo",
        blurb="Höchste Genauigkeit bei seltenen Wörtern und schwierigem Ton. "
              "Braucht eine Grafikkarte, auf der CPU zu langsam.",
        speed_cpu=0.3, speed_gpu=6.0, speed_source="measured",
        measured_on="RX 9070 XT: 6× Echtzeit · i5-13600KF CPU: 0,3× (unbrauchbar)",
        min_ram_mb=4096, min_vram_mb=2500, needs_gpu=True),
    _whisper(
        "large-v3-turbo-q5_0", 574,
        "Whisper large-v3-turbo (klein)",
        blurb="Wie oben, aber ein Drittel des Speicherbedarfs. Für Grafikkarten, "
              "auf denen es knapp wird.",
        speed_cpu=0.3, speed_gpu=2.0, speed_source="measured",
        measured_on="RX 9070 XT: 8,4 s Audio in 1,3 s",
        min_ram_mb=2048, min_vram_mb=1200, needs_gpu=True),
    _whisper(
        "small", 488, "Whisper small",
        blurb="Der alte Notnagel für schwache Rechner. Parakeet ist hier in fast "
              "jeder Hinsicht besser — nur falls Whisper aus anderen Gründen sein muss.",
        speed_cpu=1.5, speed_source="estimated", min_ram_mb=1536),

    # --- Stimmerkennung (Stille wegschneiden) ---------------------------
    Model(id="silero-vad", kind="vad", engine="whispercpp", title="Silero VAD",
          blurb="Erkennt, wo tatsächlich gesprochen wird. Verhindert, dass in "
                "Stillephasen Text erfunden wird.",
          files=[ModelFile("ggml-silero-v6.2.0.bin",
                           f"{HF}/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin", 1)],
          license="MIT"),

    # --- Redigieren -----------------------------------------------------
    _qwen("4B", "Q5_K_M", 2780, "unsloth/Qwen3-4B-Instruct-2507-GGUF",
          "Qwen3-4B-Instruct-2507-Q5_K_M.gguf",
          blurb="Versteht Selbstkorrekturen zuverlässig („nee, streich das“). "
                "Die empfohlene Wahl, wenn der Rechner sie tragen kann.",
          speed_cpu=2.5, speed_gpu=0.4, speed_source="measured",
          measured_on="RX 9070 XT: 0,3 s · i5-13600KF auf 8 E-Cores: 2–3 s",
          min_ram_mb=6144, min_vram_mb=3500),
    _qwen("4B", "Q4_K_M", 2500, "unsloth/Qwen3-4B-Instruct-2507-GGUF",
          "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
          blurb="Etwas kleiner und schneller als Q5, minimal ungenauer.",
          speed_cpu=3.0, speed_gpu=0.4, speed_source="estimated", min_ram_mb=5120,
          min_vram_mb=3000),
    _qwen("1.7B", "Q4_K_M", 1100, "unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf",
          blurb="Für schwache Rechner. Setzt Satzzeichen und entfernt Füllwörter, "
                "hat Selbstkorrekturen im Test aber teilweise übersehen.",
          speed_cpu=0.9, speed_gpu=0.2, speed_source="measured",
          measured_on="i5-13600KF auf 8 E-Cores: 0,7 s",
          min_ram_mb=3072, min_vram_mb=1600),
]

BY_ID = {m.id: m for m in CATALOG}


def get(model_id: str) -> Model | None:
    return BY_ID.get(model_id)


def of_kind(kind: str) -> list[Model]:
    return [m for m in CATALOG if m.kind == kind]


# ------------------------------------------------------------- Empfehlung

@dataclass
class Recommendation:
    asr: Model
    llm: Model | None
    vad: Model | None
    reason: str
    asr_device: str = "cpu"          # cpu | gpu
    llm_device: str = "cpu"
    alternatives: list[Model] = field(default_factory=list)

    @property
    def total_mb(self) -> int:
        return sum(m.size_mb for m in (self.asr, self.llm, self.vad) if m)


def recommend(machine) -> Recommendation:
    """Genau ein Vorschlag, in einem Satz begruendet.

    Grundsatz: Parakeet ist der Standard, weil es ueberall laeuft. Whisper
    kommt nur ins Spiel, wenn eine Grafikkarte da ist, die es auch traegt -
    auf der CPU ist es gemessen unbrauchbar (0,3x Echtzeit).
    """
    ram = machine.ram_mb
    gpu = machine.best_gpu
    vram = (gpu.vram_mb or 0) if gpu else 0
    cores = machine.cpu.logical_cores

    asr = BY_ID["parakeet-tdt-0.6b-v3-int8"]
    asr_device = "cpu"
    alternatives: list[Model] = []
    bits: list[str] = []

    if gpu and vram >= 4000:
        # Whisper waere moeglich - aber Parakeet bleibt der Vorschlag, weil es
        # die GPU frei laesst. Whisper steht als Alternative bereit.
        alternatives.append(BY_ID["whisper-large-v3-turbo"])
        bits.append(f"{gpu.name or gpu.vendor} mit {vram // 1024} GB erkannt")
    elif gpu and vram >= 1500:
        alternatives.append(BY_ID["whisper-large-v3-turbo-q5_0"])

    # Redigier-Stufe: Grafikkarte bevorzugt, sonst CPU, sonst gar nicht.
    llm: Model | None = None
    llm_device = "cpu"
    if gpu and vram >= 5000 and ram >= 6144:
        llm, llm_device = BY_ID["qwen3-4b-q5_k_m"], "gpu"
        bits.append("Selbstkorrektur läuft auf der Grafikkarte")
    elif ram >= 12288 and cores >= 8:
        llm, llm_device = BY_ID["qwen3-4b-q5_k_m"], "cpu"
        bits.append("Selbstkorrektur läuft auf dem Prozessor")
    elif ram >= 6144 and cores >= 4:
        llm, llm_device = BY_ID["qwen3-1.7b-q4_k_m"], "cpu"
        bits.append("kleines Sprachmodell für die Selbstkorrektur")
    else:
        bits.append("ohne Sprachmodell — Satzzeichen setzt Parakeet selbst")

    reason = ("Parakeet läuft auf jedem Prozessor schnell genug und lässt die "
              "Grafikkarte in Ruhe; " + ", ".join(bits) + ".")

    return Recommendation(asr=asr, llm=llm, vad=None, reason=reason,
                          asr_device=asr_device, llm_device=llm_device,
                          alternatives=alternatives)


if __name__ == "__main__":
    from . import hardware  # pragma: no cover
