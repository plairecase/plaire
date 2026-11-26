"""Разбивка на планы и технические метрики плана.

Метрики (все 0…1, кроме sharpness):
  sharpness  — дисперсия лапласиана на кадре 512 px (медиана 3 кадров), больше = резче
  exposure   — средняя яркость; clip_high / clip_low — доля пересвета / провала
  motion     — средняя разница соседних кадров (0 = статика)
  shake      — дрожание камеры: разброс быстрых сдвигов кадра (0 = штатив)
  luma_top   — яркость верхних 30 % кадра (для цвета текста)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

SAMPLE_FPS = 10
SMALL_W = 160


# ------------------------------------------------------------ планы
def find_cuts(rgb: np.ndarray, fps: float) -> list[float]:
    """Склейки по уменьшенным цветным кадрам (быстро, без полного декодирования).
    Склейка = резкий скачок разницы соседних кадров относительно соседей."""
    if len(rgb) < 3:
        return []
    f = rgb.astype(np.float32) / 255.0
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2, 3))          # разница кадр→кадр
    cuts, last = [], -1e9
    for i, v in enumerate(d):
        lo, hi = max(0, i - 10), min(len(d), i + 11)
        local = np.median(np.concatenate([d[lo:i], d[i + 1:hi]])) if hi - lo > 1 else 0
        t = (i + 1) / fps
        if v > 0.10 and v > 4 * local + 0.02 and t - last >= 0.3:
            cuts.append(round(t, 3))
            last = t
    return cuts


def detect_shots(cuts: list[float], duration: float, min_len: float, max_seg: float) -> list[tuple[float, float]]:
    """Планы между склейками. Короче min_len — выбрасываем,
    длиннее max_seg — режем на равные куски (их размечаем отдельно)."""
    bounds = [0.0] + [c for c in cuts if 0 < c < duration] + [duration]
    out = []
    for a, b in zip(bounds, bounds[1:]):
        length = b - a
        if length < min_len:
            continue
        n = max(1, int(np.ceil(length / max_seg)))
        step = length / n
        for i in range(n):
            out.append((round(a + i * step, 3), round(a + (i + 1) * step, 3)))
    return out


# ------------------------------------------------------------ кадры
def _tonemap_filter(hdr: bool) -> str:
    if not hdr:
        return ""
    return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


def extract_frame(path: Path, t: float, out: Path, long_side: int = 512, hdr: bool = False) -> Path:
    """Один кадр JPEG, длинная сторона long_side. HDR → SDR только для анализа."""
    scale = f"scale='if(gt(iw,ih),{long_side},-2)':'if(gt(iw,ih),-2,{long_side})'"
    for tm in ([_tonemap_filter(True)] if hdr else []) + [""]:
        res = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
             "-vf", tm + scale, "-q:v", "3", str(out)], capture_output=True, text=True)
        if res.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
    raise RuntimeError(f"не удалось извлечь кадр {t:.2f} с: {res.stderr.strip()[-300:]}")


def decode_small(path: Path, width: int, height: int) -> tuple[np.ndarray, float]:
    """Весь ролик в цвете, SMALL_W px, SAMPLE_FPS кадров в секунду → (rgb[N,h,w,3], fps).
    Декодер пропускает лишнее (-skip_frame nokey не используем: нужна точность склеек)."""
    h = max(2, int(round(SMALL_W * height / width / 2)) * 2)
    res = subprocess.run(
        ["ffmpeg", "-v", "error", "-threads", "0", "-i", str(path),
         "-vf", f"fps={SAMPLE_FPS},scale={SMALL_W}:{h}:flags=fast_bilinear,format=rgb24",
         "-f", "rawvideo", "-"], capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg decode: {res.stderr.decode(errors='ignore')[-300:]}")
    buf = np.frombuffer(res.stdout, dtype=np.uint8)
    n = buf.size // (SMALL_W * h * 3)
    return buf[: n * SMALL_W * h * 3].reshape(n, h, SMALL_W, 3), float(SAMPLE_FPS)


def to_gray(rgb: np.ndarray) -> np.ndarray:
    return (rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114).astype(np.uint8)


# ------------------------------------------------------------ метрики
def sharpness(jpg: Path) -> float:
    img = cv2.imread(str(jpg), cv2.IMREAD_GRAYSCALE)
    return float(cv2.Laplacian(img, cv2.CV_64F).var()) if img is not None else 0.0


def shot_metrics(frames: np.ndarray, fps: float, start: float, end: float) -> dict:
    a, b = int(start * fps), max(int(start * fps) + 1, int(end * fps))
    seg = frames[a:b].astype(np.float32) / 255.0
    if len(seg) == 0:
        return {"exposure": None, "clip_high": None, "clip_low": None, "motion": None,
                "shake": None, "luma_top": None}
    mid = seg[len(seg) // 2]
    top = mid[: max(1, int(mid.shape[0] * 0.3))]
    motion = float(np.mean(np.abs(np.diff(seg, axis=0)))) if len(seg) > 1 else 0.0

    shifts = []
    win = cv2.createHanningWindow(seg.shape[2:0:-1], cv2.CV_32F)
    for i in range(1, len(seg)):
        (dx, dy), _ = cv2.phaseCorrelate(seg[i - 1], seg[i], win)
        shifts.append((dx, dy))
    shake = 0.0
    if len(shifts) >= 3:
        s = np.array(shifts)                       # сдвиг кадра к кадру, px
        smooth = np.stack([np.convolve(s[:, k], np.ones(3) / 3, "same") for k in (0, 1)], axis=1)
        jitter = (s - smooth)[1:-1]                # быстрые рывки = тряска, плавное = панорама
        shake = float(np.sqrt(np.mean(jitter ** 2)) / seg.shape[2])   # доля ширины кадра
    return {
        "exposure": round(float(seg.mean()), 4),
        "clip_high": round(float((seg > 0.98).mean()), 4),
        "clip_low": round(float((seg < 0.02).mean()), 4),
        "motion": round(motion, 4),
        "shake": round(shake, 5),
        "luma_top": round(float(top.mean()), 4),
    }
