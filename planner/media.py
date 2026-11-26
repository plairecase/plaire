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
        bbox: list, tonemap: str = "mobius") -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    tms = [TONEMAP[tonemap] + ","] if hdr else [""]
    if hdr:
        tms.append("")                                   # запасной путь без zscale
    err = ""
    for tm in tms:
        vf = f"{tm}{crop_filter(bbox)},fps={fps},format=yuv420p,setsar=1"
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
               "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
               "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-colorspace", "bt709", "-movflags", "+faststart", str(out)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return out
        err = res.stderr[-400:]
    raise RuntimeError(f"нарезка {src.name} {start:.2f}+{dur:.2f}: {err}")


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
