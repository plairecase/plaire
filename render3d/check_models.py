#!/usr/bin/env python3
"""3D, этап 1: проверка моделей и контрольный лист (инструкция plaire-autoedit-3d.md, раздел 0).

1. Отчёт по каждой .glb: размеры, ось «вверх», материалы, текстуры, анимации, отдельный узел клапана.
2. Контрольный лист: модель в 4 ракурсах (сверху, 3/4, торец, сзади) на paper рядом с реальным кадром того же цвета.
3. Claude: «это один и тот же предмет?» + ΔE2000 цвета чехла. Не совпадает — подстройка материала (до 3 попыток),
   иначе цвет выключается в config.json → 3d.enabled_colors.

    python -m render3d.check_models            # Диск + Claude
    python -m render3d.check_models --local    # модели уже в remotion/public/models, без Claude
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REMOTION = ROOT / "remotion"
WORK = ROOT / "work" / "3d"
VIEWS = ["top", "three_quarter", "edge", "back"]
VIEW_RU = {"top": "top", "three_quarter": "3/4", "edge": "edge", "back": "back"}
FLAP_WORDS = ("flap", "lid", "cover", "top", "клапан", "door", "hinge")


# ------------------------------------------------------------------ 1. осмотр модели
def inspect(path: Path) -> dict:
    import pygltflib
    import trimesh

    g = pygltflib.GLTF2().load(str(path))
    scene = trimesh.load(str(path))
    ext = [float(x) for x in scene.extents]                    # glTF — метры
    up = "Y (стандарт glTF)"
    thin_axis = "XYZ"[int(np.argmin(ext))]
    mats = []
    for m in g.materials or []:
        pbr = m.pbrMetallicRoughness
        mats.append({"name": m.name, "base_color": [round(x, 3) for x in (pbr.baseColorFactor or [1, 1, 1, 1])] if pbr else None,
                     "roughness": pbr.roughnessFactor if pbr else None, "metalness": pbr.metallicFactor if pbr else None,
                     "base_texture": bool(pbr and pbr.baseColorTexture), "normal_map": bool(m.normalTexture)})
    nodes = [n.name or "" for n in g.nodes or []]
    flap = [n for n in nodes if any(w in n.lower() for w in FLAP_WORDS)]
    return {
        "file": path.name,
        "size_cm": [round(x * 100, 1) for x in ext],
        "thin_axis": thin_axis, "up": up,
        "meshes": len(g.meshes or []), "nodes": len(nodes), "node_names": nodes[:12],
        "materials": mats, "textures": len(g.textures or []), "images": len(g.images or []),
        "animations": len(g.animations or []), "flap_nodes": flap,
        "can_open": bool(g.animations) or bool(flap),
    }


# ------------------------------------------------------------------ 2. кадры
def render_view(model: str, view: str, tune: dict, out: Path) -> Path:
    props = out.with_suffix(".json")
    props.write_text(json.dumps({"model": model, "view": view, "tune": tune}))
    # кадр 20, а не 0: модели с текстурами нужно несколько кадров, чтобы отрисоваться
    cmd = ["npx", "remotion", "still", "src/index.ts", "model-still", str(out), f"--props={props}", "--frame=20",
           "--log=error"]
    if os.environ.get("REMOTION_BROWSER"):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    res = subprocess.run(cmd, cwd=REMOTION, capture_output=True, text=True, timeout=300)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout)[-800:])
    return out


def real_frame(color: str, index: dict, cfg: dict, get_src) -> tuple[Path | None, list | None]:
    """Лучший реальный план того же цвета: студия/перчатки, закрытый чехол, резкий."""
    from analyze import shots as sh

    best = None
    for f in index.get("files", {}).values():
        if f.get("deleted") or f["name"] in cfg.get("exclude_sources", {}):
            continue
        for s in f["shots"]:
            v = s.get("vision") or {}
            if v.get("color") != color or not v.get("focus_ok", True):
                continue
            score = v.get("hero_score", 0) + (3 if v.get("world") in ("studio_paper", "gloves") else 0) \
                + (2 if v.get("start_state") == "closed" else 0)
            if best is None or score > best[0]:
                best = (score, f, s)
    if not best:
        return None, None
    _, f, s = best
    out = WORK / f"real_{color}.jpg"
    sh.extract_frame(get_src(f["name"], f), (s["start"] + s["end"]) / 2, out, 960, f["probe"]["hdr"])
    return out, s["vision"]["case_bbox"]


# ------------------------------------------------------------------ 3. цвет: ΔE2000
def _lab(img_bgr):
    import cv2
    lab = cv2.cvtColor(img_bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    return lab


def mean_lab_real(path: Path, bbox: list) -> np.ndarray:
    import cv2
    im = cv2.imread(str(path))
    h, w = im.shape[:2]
    x, y, bw, bh = bbox if bbox and bbox[2] > 0 else (0.3, 0.3, 0.4, 0.4)
    cx, cy = x + bw / 2, y + bh / 2
    crop = im[int((cy - bh * 0.25) * h): int((cy + bh * 0.25) * h), int((cx - bw * 0.25) * w): int((cx + bw * 0.25) * w)]
    return _lab(crop).reshape(-1, 3).mean(0)


def lab3d(views: dict) -> np.ndarray:
    """Средний цвет 3D по виду сверху и 3/4 (на реальных кадрах чехол то плоско, то под углом)."""
    return (mean_lab_3d(views["top"]) + mean_lab_3d(views["three_quarter"])) / 2


def mean_lab_3d(path: Path) -> np.ndarray:
    import cv2
    im = cv2.imread(str(path))
    bg = im[10, 10].astype(int)
    d = np.abs(im.astype(int) - bg).sum(2)
    m = d > 90                                                  # сам чехол, без мягкой тени
    m = cv2.erode(m.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    return _lab(im)[m].mean(0) if m.any() else np.array([50.0, 0, 0])


def delta_e2000(l1, l2) -> float:
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lm, Cmp = (L1 + L2) / 2, (C1p + C2p) / 2
    hm = (h1p + h2p) / 2 if abs(h1p - h2p) <= 180 else (h1p + h2p + 360) / 2
    if C1p * C2p == 0:
        hm = h1p + h2p
    T = 1 - 0.17 * math.cos(math.radians(hm - 30)) + 0.24 * math.cos(math.radians(2 * hm)) \
        + 0.32 * math.cos(math.radians(3 * hm + 6)) - 0.20 * math.cos(math.radians(4 * hm - 63))
    dth = 30 * math.exp(-(((hm - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cmp ** 7 / (Cmp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lm - 50) ** 2 / math.sqrt(20 + (Lm - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cmp, 1 + 0.015 * Cmp * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


# ------------------------------------------------------------------ лист
def sheet_row(real: Path | None, views: dict, label: str, out: Path) -> Path:
    import cv2
    tiles = []
    for name, p in [("real video", real)] + [(VIEW_RU[v], views[v]) for v in VIEWS]:
        im = cv2.imread(str(p)) if p else np.full((1920, 1080, 3), 230, np.uint8)
        im = cv2.resize(im, (270, 480))
        cv2.rectangle(im, (0, 0), (270, 30), (255, 255, 255), -1)
        cv2.putText(im, name, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (20, 20, 20), 1, cv2.LINE_AA)
        tiles.append(im)
    row = np.hstack(tiles)
    cv2.putText(row, label, (8, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 200), 2, cv2.LINE_AA)
    cv2.imwrite(str(out), row, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return out


MATCH_SCHEMA = {
    "type": "object",
    "properties": {"match": {"type": "boolean"}, "color_match": {"type": "boolean"},
                   "texture_match": {"type": "boolean"}, "gloss_match": {"type": "boolean"},
                   "thickness_match": {"type": "boolean"}, "emboss_match": {"type": "boolean"},
                   "too_light": {"type": "boolean"}, "too_dark": {"type": "boolean"}, "too_shiny": {"type": "boolean"},
                   "too_matte": {"type": "boolean"}, "texture_too_rough": {"type": "boolean"},
                   "issues": {"type": "array", "items": {"type": "string"}}},
    "required": ["match", "color_match", "texture_match", "gloss_match", "thickness_match", "emboss_match",
                 "too_light", "too_dark", "too_shiny", "too_matte", "texture_too_rough", "issues"],
    "additionalProperties": False,
}


def ask_claude(client, usage, row: Path, model_cfg: dict) -> dict:
    data = base64.standard_b64encode(row.read_bytes()).decode("ascii")
    resp = client.beta.messages.create(
        model=model_cfg["model"], max_tokens=2500,
        system=("You compare a real product photo with 3D renders of a product model. Product: Plaire, a slim "
                "eco-leather condom case that looks like a mini wallet, embossed PLAIRE logo, magnetic closure."),
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
            {"type": "text", "text": "Tile 1 is a real video frame, tiles 2-5 are 3D renders (top, 3/4, edge, back) on "
                                     "paper. Is it the same object? Do colour, leather texture, gloss, thickness and "
                                     "the PLAIRE emboss match? Also say if the 3D is too light, too dark, too shiny, too "
                                     "matte, or if its leather grain is too rough compared with the real one. Issues in Russian, short."}]}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": MATCH_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    usage.add(resp)
    return json.loads("".join(b.text for b in resp.content if b.type == "text"))


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    a = ap.parse_args(argv)
    cfg = json.loads((ROOT / "config.json").read_text())
    dcfg = cfg["drive"]
    WORK.mkdir(parents=True, exist_ok=True)
    (REMOTION / "public" / "models").mkdir(parents=True, exist_ok=True)

    from analyze import drive
    models = {}
    if not a.local:
        for f in drive.list_files(dcfg["models3d"]):
            n = f["Name"].lower()
            col = "cognac" if "cognac" in n else ("black" if "black" in n else None)
            if n.endswith(".glb") and col:
                drive.download(dcfg["models3d"], f["Name"], REMOTION / "public" / "models" / f"{col}.glb", f.get("Size"), f.get("ID"))
                models[col] = f["Name"]
            elif n.endswith((".zip", ".json")) or "keyframes" in n:
                print(f"⚠️ {f['Name']}: это не готовая модель .glb")
    else:
        for p in (REMOTION / "public" / "models").glob("*.glb"):
            col = "cognac" if "cognac" in p.name else ("black" if "black" in p.name else None)
            if col:
                models[col] = p.name

    index = {} if a.local else drive.read_json(f"{dcfg['state']}/clips_index.json", {})
    src_cache = ROOT / "work" / "src"

    def get_src(name, f):
        return drive.download(dcfg["sources"], name, src_cache / name, f.get("size"), f.get("id"))

    client = usage = None
    if not a.local:
        from analyze import vision as vis
        client = vis.make_client()
        usage = vis.Usage(cfg["claude"]["model"], cfg["claude"]["price_in_per_m"], cfg["claude"]["price_out_per_m"])

    L = ["# 3D, этап 1: проверка моделей", ""]
    rows, enabled = [], []
    tunes = cfg.get("3d", {}).get("material", {})
    for col, fname in sorted(models.items()):
        info = inspect(REMOTION / "public" / "models" / f"{col}.glb")
        L += [f"## {fname}", "",
              f"- размеры: {' × '.join(str(x) for x in info['size_cm'])} см (ожидается ~7.6 × 8 × 1); тонкая ось: {info['thin_axis']}; вверх: {info['up']}",
              f"- сеток: {info['meshes']}, узлов: {info['nodes']} ({', '.join(info['node_names'][:6])})",
              f"- материалы: " + "; ".join(f"{m['name']} (цвет {m['base_color']}, roughness {m['roughness']}, "
                                           f"metal {m['metalness']}, текстура {'да' if m['base_texture'] else 'нет'}, "
                                           f"normal {'да' if m['normal_map'] else 'нет'})" for m in info["materials"]),
              f"- текстур: {info['textures']}, анимаций: {info['animations']}, узлы клапана: {info['flap_nodes'] or 'нет'}",
              f"- **можно показать открытым: {'да' if info['can_open'] else 'нет'}** (нужны анимация или отдельный узел клапана)"]
        real, bbox = (None, None) if a.local else real_frame(col, index, cfg, get_src)
        tune = dict(tunes.get(col) or {"roughness": None, "tint": 1.0})
        result, row = None, None
        for attempt in range(1, 4):
            import cv2 as _cv

            def is_blank(p):
                im = _cv.imread(str(p)).astype(int)
                return float(np.abs(im - im[10, 10]).sum(2).max()) < 30

            views = {}
            for v in VIEWS:
                for _ in range(3):  # пустой кадр рендера — перерисовать
                    views[v] = render_view(f"models/{col}.glb", v, tune, WORK / f"{col}_{v}.png")
                    if not is_blank(views[v]):
                        break
            blank = any(is_blank(views[v]) for v in VIEWS)
            if blank:
                L.append(f"- попытка {attempt}: ❌ рендер пустой (модель не отрисовалась) — это ошибка рендера, не модели")
                result = None
                break
            de = None
            if real:
                de = round(delta_e2000(mean_lab_real(real, bbox), lab3d(views)), 1)
            row = sheet_row(real, views, f"{col} attempt {attempt} dE={de}", WORK / f"row_{col}_{attempt}.jpg")
            result = ask_claude(client, usage, row, cfg["claude"]) if client else {"match": None, "issues": []}
            L.append(f"- попытка {attempt}: материал {tune}; ΔE2000 = {de}; Claude: совпадает = {result.get('match')}"
                     + (f"; {'; '.join(result.get('issues', [])[:3])}" if result.get("issues") else ""))
            ok = (result.get("match") is not False) and (de is None or de <= 6)
            if ok:
                break
            # подстройка только 3D (исходники не трогаем): блеск, фактура, светлота эко-кожи
            if result.get("too_shiny"):
                tune["roughness"] = 0.72
            elif result.get("too_matte") or (result.get("gloss_match") is False and not result.get("too_shiny")):
                tune["roughness"] = 0.45
            if result.get("texture_too_rough") or result.get("texture_match") is False:
                tune["normalScale"] = round((tune.get("normalScale") or 1.0) * 0.5, 2)
            l3, lr = lab3d(views)[0], (mean_lab_real(real, bbox)[0] if real else None)
            if result.get("too_light") or (lr is not None and l3 > lr + 3):
                tune["tint"] = round(tune.get("tint", 1.0) * 0.85, 3)
            elif result.get("too_dark") or (lr is not None and l3 < lr - 3):
                tune["tint"] = round(tune.get("tint", 1.0) * 1.2, 3)
        if row:
            rows.append(row)
        tunes[col] = tune
        if result is None:
            L.append(f"- ⚠️ проверку цвета {col} повторить после исправления рендера (3D пока не выключаю)")
            enabled.append(col)
        elif result.get("match") is not False:
            enabled.append(col)
        else:
            L.append(f"- ❌ после 3 попыток не совпадает — 3D для цвета {col} выключено")
        L.append("")
    if rows:
        import cv2
        cv2.imwrite(str(WORK / "sheet.jpg"), np.vstack([cv2.imread(str(r)) for r in rows]), [cv2.IMWRITE_JPEG_QUALITY, 88])
    if client:
        cfg.setdefault("3d", {})["material"] = tunes
        cfg["3d"]["enabled_colors"] = enabled
        (WORK / "config_3d.json").write_text(json.dumps(cfg["3d"], ensure_ascii=False, indent=2))
        L.append(f"Claude: {usage.calls} запросов ≈ ${usage.cost_usd:.3f}")
    md = "\n".join(L)
    (WORK / "report.md").write_text(md)
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
