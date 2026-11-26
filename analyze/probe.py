"""ffprobe: разрешение, fps, длительность, поворот, цвет."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}


def probe(path: Path) -> dict:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe: {res.stderr.strip()[-400:]}")
    data = json.loads(res.stdout)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise RuntimeError("нет видеодорожки")
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)

    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    if not rot and v.get("tags", {}).get("rotate"):
        rot = int(v["tags"]["rotate"])
    rot = rot % 360
    w, h = int(v["width"]), int(v["height"])
    dw, dh = (h, w) if rot in (90, 270) else (w, h)

    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    dur = float(v.get("duration") or data.get("format", {}).get("duration") or 0)
    transfer = v.get("color_transfer", "")
    return {
        "width": dw, "height": dh, "rotation": rot, "fps": round(fps, 3), "duration": round(dur, 3),
        "codec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
        "color_space": v.get("color_space", ""), "color_transfer": transfer,
        "color_primaries": v.get("color_primaries", ""),
        "hdr": transfer in HDR_TRANSFERS, "has_audio": a is not None,
        "orientation": "vertical" if dh > dw else ("horizontal" if dw > dh else "square"),
    }
