"""Model catalogue and hardware-aware recommendation.

Every entry records where its speed figure comes from: `measured` means it was
timed on real hardware (see `measured_on`), `estimated` means it is an informed
guess. The installer surfaces that distinction — guesses must not be dressed up
as measurements.
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
    languages: str = "multilingual"
    license: str = ""
    # Speed as a multiple of real time — higher is better.
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
        languages="25 languages, including English and German",
        license="CC-BY-4.0 (NVIDIA)", **kw)


def _whisper(name: str, size_mb: int, title: str, blurb: str, **kw) -> Model:
    return Model(
        id=f"whisper-{name}", kind="asr", engine="whispercpp", title=title, blurb=blurb,
        files=[ModelFile(f"ggml-{name}.bin",
                         f"{HF}/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin", size_mb)],
        languages="99 languages", license="MIT (OpenAI weights)", **kw)


def _qwen(size: str, quant: str, size_mb: int, repo: str, fname: str, **kw) -> Model:
    return Model(
        id=f"qwen3-{size}-{quant}".lower(), kind="llm", engine="llamacpp",
        title=f"Qwen3 {size} ({quant})",
        files=[ModelFile(fname, f"{HF}/{repo}/resolve/main/{fname}", size_mb)],
        languages="multilingual", license="Apache-2.0", **kw)


# ----------------------------------------------------------------- Catalogue

CATALOG: list[Model] = [
    # --- Speech recognition ---------------------------------------------
    _parakeet(
        "-int8", "int8", 622, 12, 7,
        blurb="The default. Remarkably fast on CPU, and it punctuates and "
              "capitalises on its own. No graphics card required.",
        speed_cpu=15.0, speed_gpu=None, speed_source="measured",
        measured_on="i5-13600KF, 8 threads: 15x real time · only 2 cores: 5x real time",
        min_ram_mb=2048),
    _whisper(
        "large-v3-turbo", 1625, "Whisper large-v3-turbo",
        blurb="Highest accuracy on rare words and difficult audio. Needs a "
              "graphics card — on CPU it is too slow to be usable.",
        speed_cpu=0.3, speed_gpu=6.0, speed_source="measured",
        measured_on="RX 9070 XT: 6x real time · i5-13600KF CPU: 0.3x (unusable)",
        min_ram_mb=4096, min_vram_mb=2500, needs_gpu=True),
    _whisper(
        "large-v3-turbo-q5_0", 574, "Whisper large-v3-turbo (compact)",
        blurb="Same model, a third of the memory. For graphics cards where "
              "VRAM is tight.",
        speed_cpu=0.3, speed_gpu=2.0, speed_source="measured",
        measured_on="RX 9070 XT: 8.4 s of audio in 1.3 s",
        min_ram_mb=2048, min_vram_mb=1200, needs_gpu=True),
    _whisper(
        "small", 488, "Whisper small",
        blurb="The old fallback for weak machines. Parakeet beats it on almost "
              "every axis — pick this only if you specifically need Whisper.",
        speed_cpu=1.5, speed_source="estimated", min_ram_mb=1536),

    # --- Voice activity detection ---------------------------------------
    Model(id="silero-vad", kind="vad", engine="whispercpp", title="Silero VAD",
          blurb="Finds the stretches where someone is actually speaking, so the "
                "recogniser does not invent text during silence.",
          files=[ModelFile("ggml-silero-v6.2.0.bin",
                           f"{HF}/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin", 1)],
          license="MIT"),

    # --- Editing pass ----------------------------------------------------
    _qwen("4B", "Q5_K_M", 2780, "unsloth/Qwen3-4B-Instruct-2507-GGUF",
          "Qwen3-4B-Instruct-2507-Q5_K_M.gguf",
          blurb="Understands spoken self-corrections reliably (“no, scratch "
                "that”). The recommended choice where the machine can carry it.",
          speed_cpu=2.5, speed_gpu=0.4, speed_source="measured",
          measured_on="RX 9070 XT: 0.3 s · i5-13600KF on 8 E-cores: 2-3 s",
          min_ram_mb=6144, min_vram_mb=3500),
    _qwen("4B", "Q4_K_M", 2500, "unsloth/Qwen3-4B-Instruct-2507-GGUF",
          "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
          blurb="Slightly smaller and faster than Q5, marginally less precise.",
          speed_cpu=3.0, speed_gpu=0.4, speed_source="estimated", min_ram_mb=5120,
          min_vram_mb=3000),
    _qwen("1.7B", "Q4_K_M", 1100, "unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf",
          blurb="For weak machines. Punctuates and strips filler words, but it "
                "missed some self-corrections in testing.",
          speed_cpu=0.9, speed_gpu=0.2, speed_source="measured",
          measured_on="i5-13600KF on 8 E-cores: 0.7 s",
          min_ram_mb=3072, min_vram_mb=1600),
]

BY_ID = {m.id: m for m in CATALOG}


def get(model_id: str) -> Model | None:
    return BY_ID.get(model_id)


def of_kind(kind: str) -> list[Model]:
    return [m for m in CATALOG if m.kind == kind]


# --------------------------------------------------------- Recommendation

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
    """Exactly one suggestion, justified in a single sentence.

    Principle: Parakeet is the default because it runs everywhere. Whisper only
    enters the picture when there is a graphics card that can carry it — on CPU
    it was measured at 0.3x real time, which is unusable for dictation.
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
        # Whisper would be viable, but Parakeet stays the suggestion because it
        # leaves the graphics card alone. Whisper is offered as the alternative.
        alternatives.append(BY_ID["whisper-large-v3-turbo"])
        bits.append(f"found {gpu.name or gpu.vendor} with {vram // 1024} GB")
    elif gpu and vram >= 1500:
        alternatives.append(BY_ID["whisper-large-v3-turbo-q5_0"])

    llm: Model | None = None
    llm_device = "cpu"
    if ram >= 6144 and cores >= 4:
        llm = BY_ID["qwen3-1.7b-q4_k_m"]
        bits.append("a compact 4-bit editor stays loaded on the processor")
    else:
        bits.append("no language model — Parakeet punctuates on its own")

    reason = ("Parakeet is fast enough on any processor and leaves the graphics "
              "card alone; " + ", ".join(bits) + ".")

    return Recommendation(asr=asr, llm=llm, vad=None, reason=reason,
                          asr_device=asr_device, llm_device=llm_device,
                          alternatives=alternatives)
