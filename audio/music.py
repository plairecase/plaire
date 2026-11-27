"""Музыка: выбор трека из папки Music, ритм (librosa), лучший отрезок, микс с SFX.

Треки в Music — трендовые, скачанные из интернета: для бизнес-аккаунтов есть риск
заглушения звука. Название трека, BPM и секунда начала пишутся в отчёт и подпись,
чтобы этот же звук можно было найти в библиотеке TikTok/Instagram.
"""
from __future__ import annotations

import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".aif", ".aiff"}


@dataclass
class Track:
    file: str
    title: str
    bpm: float
    start_s: float                     # с какой секунды трека начинается ролик
    beats: list[float] = field(default_factory=list)      # доли от начала ролика, с
    downbeats: list[float] = field(default_factory=list)  # сильные доли (каждая 4-я)


def candidates(listing: list[dict], recent: set[str] | None = None) -> list[str]:
    names = [f["Name"] for f in listing if Path(f["Name"]).suffix.lower() in AUDIO_EXT]
    fresh = [n for n in names if n not in (recent or set())]
    return fresh or names


def analyze(path: Path, length_s: float, rng: random.Random) -> Track:
    """BPM, доли и отрезок трека с наибольшей энергией (обычно припев/дроп)."""
    import librosa
    import numpy as np

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    dur = len(y) / sr
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = librosa.frames_to_time(beat_frames, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    rms = librosa.feature.rms(y=y)[0]
    t_rms = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    need = length_s + 1.0
    ib = float(np.median(np.diff(beats))) if len(beats) > 2 else 60.0 / max(bpm, 60.0)
    if dur < need + 0.5:
        # короткий звук (например, из TikTok): играем с начала по кругу, сетку продлеваем ровным шагом
        base = list(beats) or [0.0]
        ext = []
        k = 0
        while (base[-1] if base else 0) + k * ib < need + ib:
            ext.append(base[-1] + k * ib)
            k += 1
        allb = sorted(set([float(b) for b in base] + ext[1:]))
        rel = [round(b, 3) for b in allb if b < need]
        first = rel[0] if rel else 0.0
        down = [round(b, 3) for i, b in enumerate(rel) if i % 4 == 0]
        return Track(file=path.name, title=Path(path.name).stem, bpm=round(bpm, 1), start_s=0.0,
                     beats=[round(float(b - first), 3) for b in rel], downbeats=[round(float(b - first), 3) for b in down])
    # кандидаты начала: сильные доли, после которых хватает трека
    starts = [b for i, b in enumerate(beats) if i % 4 == 0 and b + need < dur and b > 3.0] or [0.0]
    def energy(s):
        m = (t_rms >= s) & (t_rms < s + need)
        return float(rms[m].mean()) if m.any() else 0.0
    scored = sorted(starts, key=energy, reverse=True)
    start = scored[min(len(scored) - 1, rng.randrange(0, min(3, len(scored))))]  # одна из 3 самых ярких
    start = float(start)
    rel = [round(float(b) - start, 3) for b in beats if start <= b < start + need]
    first_idx = int(np.argmin(np.abs(beats - start))) if len(beats) else 0
    down = [round(float(b) - start, 3) for i, b in enumerate(beats) if start <= b < start + need and (i - first_idx) % 4 == 0]
    return Track(file=path.name, title=Path(path.name).stem, bpm=round(bpm, 1), start_s=round(start, 2),
                 beats=rel, downbeats=down)


def render(track: Track | None, track_path: Path | None, sfx_cues: list[dict], sfx_dir: Path,
           duration: float, out: Path) -> dict:
    """Музыка (fade in 0.3 с / out 0.8 с) + SFX на 8 дБ тише, затем −14 LUFS / −1 dBTP."""
    from audio import mix

    if not track or not track_path:
        return mix.render(sfx_cues, sfx_dir, duration, out)
    out.parent.mkdir(parents=True, exist_ok=True)
    music = out.with_name(out.stem + "_music.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-ss", f"{track.start_s:.3f}",
                    "-i", str(track_path),
                    "-t", f"{duration:.3f}", "-af",
                    f"aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.3,"
                    f"afade=t=out:st={max(0.0, duration - 0.8):.3f}:d=0.8", str(music)], check=True)
    cues = [{**c, "gain_db": c.get("gain_db", -6) - 8} for c in sfx_cues]      # SFX тише музыки
    if cues:
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(music)]
        parts = ["[0:a]anull[m]"]
        for i, c in enumerate(cues, 1):
            cmd += ["-i", str(sfx_dir / c["file"])]
            ms = int(c["t"] * 1000)
            parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:1.6,"
                         f"afade=t=out:st=1.2:d=0.4,volume={c['gain_db']}dB,adelay={ms}|{ms}[s{i}]")
        mixin = "[m]" + "".join(f"[s{i}]" for i in range(1, len(cues) + 1))
        fc = ";".join(parts) + f";{mixin}amix=inputs={len(cues) + 1}:normalize=0:duration=first[out]"
        both = out.with_name(out.stem + "_both.wav")
        subprocess.run(cmd + ["-filter_complex", fc, "-map", "[out]", str(both)], check=True)
        music.unlink(missing_ok=True)
        music = both
    m = mix._measure(music)
    ln = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(music), "-af", ln, "-ar", "48000", str(out)], check=True)
    after = mix._measure(out)
    if abs(float(after["input_i"]) + 14) > 1 or float(after["input_tp"]) > -1:    # дожать усилением + лимитер
        fixed = out.with_name(out.stem + "_fix.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", str(fixed)], check=True)
        fixed.replace(out)
        after = mix._measure(out)
    music.unlink(missing_ok=True)
    return {"silent": False, "lufs": float(after["input_i"]), "true_peak": float(after["input_tp"]),
            "music": {"file": track.file, "title": track.title, "bpm": track.bpm, "start_s": track.start_s}}
