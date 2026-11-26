"""Звук версии clean: только SFX из папки SFX. Громкость −14 LUFS, true peak ≤ −1 dBTP (loudnorm, 2 прохода)."""
from __future__ import annotations

import json
import random
import re
import subprocess
from pathlib import Path

# классификация по имени файла (раздел 9 инструкции)
KINDS = {
    "whoosh": ("whoosh", "swoosh", "swish", "air", "wind", "swipe", "slide"),
    "click": ("click", "tap", "tick", "button"),
    "magnet": ("magnet", "snap", "clasp", "lock"),
    "rise": ("rise", "riser", "charge", "build"),
}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aiff", ".aif", ".flac", ".ogg"}


def classify(name: str) -> str | None:
    low = name.lower()
    for kind, words in KINDS.items():
        if any(w in low for w in words):
            return kind
    return None


def library(listing: list[dict]) -> dict[str, list[str]]:
    lib: dict[str, list[str]] = {}
    for f in listing:
        if Path(f["Name"]).suffix.lower() in AUDIO_EXT:
            k = classify(f["Name"])
            if k:
                lib.setdefault(k, []).append(f["Name"])
    return lib


def pick(lib: dict, cues: list[dict], rng: random.Random) -> list[dict]:
    out = []
    for c in cues:
        names = lib.get(c["kind"]) or (lib.get("whoosh") if c["kind"] == "magnet" else None)
        if names:
            out.append({**c, "file": rng.choice(sorted(names))})
    return out


def _measure(src: Path) -> dict:
    res = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af",
                          "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.S)
    return json.loads(m.group(0)) if m else {}


def render(cues: list[dict], sfx_dir: Path, duration: float, out: Path) -> dict:
    """Собирает дорожку: SFX по времени, громкость, нормализация. Возвращает замеры."""
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_name(out.stem + "_raw.wav")
    if not cues:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=48000", "-t", f"{duration:.3f}", str(out)],
                       check=True)
        return {"silent": True, "lufs": None, "true_peak": None}
    cmd = ["ffmpeg", "-v", "error", "-y"]
    parts = []
    for i, c in enumerate(cues):
        cmd += ["-i", str(sfx_dir / c["file"])]
        ms = int(c["t"] * 1000)
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=out:st=1.2:d=0.4,"
                     f"atrim=0:1.6,volume={c.get('gain_db', -6)}dB,adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(cues)))
    fc = ";".join(parts) + f";{mix}amix=inputs={len(cues)}:normalize=0,apad,atrim=0:{duration:.3f}[out]"
    subprocess.run(cmd + ["-filter_complex", fc, "-map", "[out]", "-ar", "48000", str(raw)], check=True)
    m = _measure(raw)
    if m and m.get("input_i") not in (None, "-inf"):
        ln = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
              f"linear=true")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", ln, "-ar", "48000", str(out)],
                       check=True)
    else:
        raw.replace(out)
    after = _measure(out)
    raw.unlink(missing_ok=True)
    return {"silent": False, "lufs": float(after.get("input_i", "nan")), "true_peak": float(after.get("input_tp", "nan"))}


def mux(video: Path, audio: Path, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True)
    return out
