"""Нарезка выбранных отрезков в клипы для Remotion: 1080×1920, 30 к/с, SDR Rec.709, без звука.

Цвет и свет исходников не меняем. Единственная техническая нормализация — HDR (HLG/PQ) → SDR.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

W, H = 1080, 1920

TONEMAP = {
    # HLG/PQ → линейный свет → BT.709 с выбранным тонмаппингом
    "mobius": "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=mobius:desat=0,"
              "zscale=t=bt709:m=bt709:r=tv,format=yuv420p",
    "hable": "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
             "zscale=t=bt709:m=bt709:r=tv,format=yuv420p",
    "clip": "zscale=t=bt709:m=bt709:p=bt709:r=tv,format=yuv420p",
}


def crop_filter(bbox: list) -> str:
    """Заполнить 9:16; если исходник шире — центр кадра по чехлу."""
    cx = (bbox[0] + bbox[2] / 2) if bbox and bbox[2] > 0 else 0.5
    return (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{H}:x='max(0,min(iw-{W},iw*{cx:.3f}-{W}/2))':y='(ih-{H})/2'")


def cut(src: Path, start: float, dur: float, out: Path, fps: int, crf: int, hdr: bool,
        bbox: list, tonemap: str = "mobius", stabilize: bool = False, reverse: bool = False) -> Path:
    """Отрезок → клип 1080×1920. stabilize: двухпроходная стабилизация vidstab (дрожащая ручная съёмка)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tms = [TONEMAP[tonemap] + ","] if hdr else [""]
    if hdr:
        tms.append("")                                   # запасной путь без zscale
    err = ""
    for tm in tms:
        base = f"{tm}{crop_filter(bbox)},fps={fps}"
        stab = ""
        if stabilize:
            trf = out.with_suffix(".trf")
            det = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src),
                                  "-t", f"{dur:.3f}", "-vf", f"{base},vidstabdetect=shakiness=6:accuracy=12:result={trf}",
                                  "-f", "null", "-"], capture_output=True, text=True, timeout=300)
            if det.returncode == 0 and trf.exists():
                stab = (f",vidstabtransform=input={trf}:smoothing=15:optzoom=1:zoomspeed=0.2:interpol=bicubic,"
                        f"unsharp=5:5:0.5:3:3:0.0")
            else:
                stab = ",deshake=rx=48:ry=48"            # запасной встроенный стабилизатор
        # tpad: если исходник кончился раньше плана — держим последний кадр (никаких чёрных кадров)
        vf = f"{base}{stab}{',reverse' if reverse else ''},tpad=stop_mode=clone:stop_duration=1,format=yuv420p,setsar=1"
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
               "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
               "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-colorspace", "bt709", "-movflags", "+faststart", str(out)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            err = "нарезка дольше 5 минут"
            continue
        out.with_suffix(".trf").unlink(missing_ok=True)
        if res.returncode == 0:
            return out
        err = res.stderr[-400:]
    raise RuntimeError(f"нарезка {src.name} {start:.2f}+{dur:.2f}: {err}")


def reverse_head(clip: Path, dur: float, out: Path, crf: int) -> Path:
    """Первые dur секунд готового клипа задом наперёд (для бесшовного лупа)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-t", f"{dur:.3f}",
                    "-vf", "reverse,tpad=stop_mode=clone:stop_duration=1", "-t", f"{dur:.3f}",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
                    "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                    "-movflags", "+faststart", str(out)], check=True, timeout=300)
    return out


def hdr_compare(src: Path, t: float, out: Path) -> Path:
    """Отладка: один кадр HDR-исходника тремя способами рядом (mobius | hable | clip)."""
    import cv2
    import numpy as np

    tiles = []
    for name, tm in TONEMAP.items():
        p = out.with_name(f"_{name}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1",
                        "-vf", f"{tm},scale=360:-2", str(p)], check=True)
        img = cv2.imread(str(p))
        cv2.putText(img, name, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        tiles.append(img)
    h = min(i.shape[0] for i in tiles)
    cv2.imwrite(str(out), np.hstack([i[:h] for i in tiles]))
    return out


def fg_extent(src: Path, start: float, end: float, hdr: bool, n: int = 5) -> tuple[float, float] | None:
    """Где по вертикали в кадре предмет (чехол, руки) — по отличию от фона по краям кадра.
    Объединение по n кадрам плана. Возвращает (верх, низ) в долях высоты или None, если фон пёстрый."""
    import cv2
    import numpy as np

    tops, bots = [], []
    for i in range(n):
        t = start + (end - start) * (i + 0.5) / n
        vf = (TONEMAP["mobius"] + "," if hdr else "") + "scale=270:480"
        res = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1",
                              "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, timeout=60)
        if res.returncode != 0 or len(res.stdout) != 270 * 480 * 3:
            continue
        img = np.frombuffer(res.stdout, np.uint8).reshape(480, 270, 3)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        # фон по строкам из левой и правой полос: студийный градиент сверху вниз — не помеха
        strips = np.concatenate([lab[:, :14], lab[:, -14:]], axis=1)          # 480×28×3
        bg_row = np.median(strips, axis=1)                                    # 480×3
        k = 31
        pad = np.pad(bg_row, ((k // 2, k // 2), (0, 0)), mode="edge")
        bg_row = np.stack([np.convolve(pad[:, c], np.ones(k) / k, "valid") for c in range(3)], axis=1)
        resid = np.linalg.norm(strips - bg_row[:, None, :], axis=2)
        if np.median(resid) > 10:                            # пёстрый фон по краям — не измерить
            continue
        mask = (np.linalg.norm(lab - bg_row[:, None, :], axis=2) > 28).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        if mask.mean() > 0.7:
            continue
        rows = np.where(mask.mean(axis=1) > 0.04)[0]
        if len(rows):
            tops.append(rows[0] / 480)
            bots.append(rows[-1] / 480)
    if not tops:
        return None
    return round(float(min(tops)), 3), round(float(max(bots)), 3)
