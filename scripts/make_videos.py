#!/usr/bin/env python3
"""Сборка роликов: план → нарезка → рендер Remotion (без звука) → звук clean → проверка → Диск.

    python3 -m scripts.make_videos --mode test            # 2 тестовых ролика в Done/TEST_…
    python3 -m scripts.make_videos --mode test --seed 7   # воспроизвести монтаж
    python3 -m scripts.make_videos --local DIR            # без Диска (исходники из DIR, индекс из work/)

Шаг 4 фазы 1: шаблоны p_one_line и n_statement, только clean-звук (SFX).
Обложки, подписи, manifest и полная проверка качества — шаг 5.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analyze import drive                      # noqa: E402
from analyze.index import thresholds, usable   # noqa: E402
from audio import mix                          # noqa: E402
from planner import media                      # noqa: E402
from planner import templates                  # noqa: E402
from planner.templates import BUILDERS, Ctx    # noqa: E402

WORK = ROOT / "work"
REMOTION = ROOT / "remotion"
COMP_ID = {"p_one_line": "p-one-line", "n_statement": "n-statement"}
DUR_RANGE = {"p_one_line": (7, 12), "n_statement": (7, 10)}


def tallinn_now() -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Tallinn"))
    except Exception:                                    # noqa: BLE001
        return dt.datetime.now(dt.timezone.utc)


def load_shots(index: dict, cfg: dict) -> list[dict]:
    th = thresholds(index)
    excl = set(cfg.get("exclude_sources", {}))
    out = []
    for f in index["files"].values():
        if f.get("deleted") or f["name"] in excl:
            continue
        for s in f["shots"]:
            if usable(s, th, cfg):
                out.append({"shot": s, "file": f})
    return out


def render(props: dict, comp: str, out: Path, cfg: dict) -> Path:
    pfile = out.with_suffix(".props.json")
    pfile.write_text(json.dumps(props))
    cmd = ["npx", "remotion", "render", "src/index.ts", comp, str(out), f"--props={pfile}", "--muted",
           "--codec=h264", f"--video-bitrate={cfg['render']['video_bitrate']}", "--log=error"]
    if os.environ.get("REMOTION_BROWSER"):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    cmd.append("--timeout=60000")
    try:
        res = subprocess.run(cmd, cwd=REMOTION, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Remotion: рендер не уложился в 15 минут") from e
    if res.returncode != 0:
        raise RuntimeError(f"Remotion: {(res.stderr or res.stdout)[-1500:]}")
    return out


def probe_ok(path: Path, tmpl: str) -> list[str]:
    res = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-print_format", "json",
                          str(path)], capture_output=True, text=True)
    d = json.loads(res.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in d.get("streams", []) if s["codec_type"] == "audio"), None)
    errs = []
    if not v or (int(v["width"]), int(v["height"])) != (1080, 1920):
        errs.append("размер не 1080×1920")
    if not a:
        errs.append("нет аудио")
    dur = float(d.get("format", {}).get("duration", 0))
    lo, hi = DUR_RANGE[tmpl]
    if not lo - 0.3 <= dur <= hi + 0.3:
        errs.append(f"длительность {dur:.1f} с вне {lo}–{hi} с")
    return errs


def contact(video: Path, out: Path, n: int = 9) -> Path:
    """3×3 кадров ролика (для проверки глазами; в Done не кладётся)."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    tiles = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * (total - 1) / (n - 1)))
        ok, fr = cap.read()
        if ok:
            tiles.append(cv2.resize(fr, (360, 640)))
    cap.release()
    rows = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles) - len(tiles) % 3, 3)]
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="test", choices=["test"])
    ap.add_argument("--seed", type=int)
    ap.add_argument("--local", type=Path)
    ap.add_argument("--hdr-compare", action="store_true")
    args = ap.parse_args(argv)

    cfg = json.loads((ROOT / "config.json").read_text())
    texts = json.loads((ROOT / "texts.json").read_text())["items"]
    dcfg = cfg["drive"]
    seed = args.seed if args.seed is not None else int(time.time()) % 100000
    rng = random.Random(seed)
    now = tallinn_now()
    folder = f"TEST_{now:%Y-%m-%d_%H%M}"
    out_root = WORK / "out" / folder
    clips_dir = REMOTION / "public" / "clips"
    shutil.rmtree(clips_dir, ignore_errors=True)
    clips_dir.mkdir(parents=True)
    t0 = time.time()
    timing = {}

    index = json.loads((WORK / "clips_index.json").read_text()) if args.local else \
        drive.read_json(f"{dcfg['state']}/clips_index.json", {})
    shots = load_shots(index, cfg)
    print(f"Годных планов: {len(shots)}; seed {seed}", flush=True)

    # --- замер положения чехла по реальным кадрам (для хука и финала премиума)
    src_dir = WORK / "src"
    sizes = {f["name"]: f.get("size") for f in index["files"].values()}
    ids = {f["name"]: f.get("id") for f in index["files"].values()}
    local_src: dict[str, Path] = {}

    def get_src(name: str) -> Path:
        if name not in local_src:
            print(f"  исходник {name}", flush=True)
            local_src[name] = (args.local / name) if args.local else \
                drive.download(dcfg["sources"], name, src_dir / name, sizes.get(name), ids.get(name))
        return local_src[name]

    extents: dict[str, tuple | None] = {}

    def measure(s: dict):
        sid = s["shot"]["id"]
        if sid not in extents:
            try:
                extents[sid] = media.fg_extent(get_src(s["file"]["name"]), s["shot"]["start"], s["shot"]["end"],
                                               s["file"]["probe"]["hdr"])
            except Exception as e:                       # noqa: BLE001 — нет замера → рамка из разметки
                print(f"  замер {sid}: {e}", flush=True)
                extents[sid] = None
        return extents[sid]

    templates.MEASURE = measure

    # --- план на день: по одному ролику каждого стиля
    ctx = Ctx(shots, texts, rng, cfg["render"]["fps"], cfg["render"]["dissolve_frames"])
    plans, skipped = [], []
    for style in ("premium", "native"):
        n = cfg["style_mix"].get(style, 1)
        for _ in range(n):
            built = None
            for tmpl in cfg["templates"][style]:
                built = BUILDERS[tmpl](ctx)
                if built:
                    break
                skipped.append(tmpl)
            if built:
                plans.append(built)
                ctx.avoid_first.add(built.first_shot)
                ctx.avoid_color = built.color
                ctx.avoid_hooks.add(built.hook_id)
    if not plans:
        raise SystemExit("Не удалось собрать ни одного плана монтажа: мало годных исходников")
    if args.mode == "test":
        pass                                             # тест: оба стиля, чтобы владелец оценил

    # --- нарезка
    t = time.time()
    for name in sorted({s.name for p in plans for s in p.segments}):
        get_src(name)
    if args.hdr_compare:
        hdr_seg = next((s for p in plans for s in p.segments if s.hdr), None)
        if hdr_seg:
            media.hdr_compare(local_src[hdr_seg.name], hdr_seg.src_start + 0.5, WORK / "hdr_compare.jpg")
    k = 0
    for p in plans:
        for sg, clip in zip(p.segments, p.props["clips"]):
            rel = f"clips/c{k}.mp4"
            print(f"  нарезка {rel}: {sg.name} {sg.src_start:.1f}+{sg.src_dur:.1f}", flush=True)
            media.cut(local_src[sg.name], sg.src_start, sg.src_dur, REMOTION / "public" / rel,
                      cfg["render"]["fps"], cfg["render"]["crf"], sg.hdr, sg.bbox, cfg["render"]["hdr_tonemap"])
            clip["src"] = rel
            sg.out = rel
            k += 1
    timing["нарезка"] = time.time() - t

    # --- SFX
    sfx_dir = WORK / "sfx"
    sfx_listing = drive.list_files(dcfg["sfx"]) if not args.local else []
    sfx_ids = {f["Name"]: f.get("ID") for f in sfx_listing}
    lib = mix.library(sfx_listing)
    for p in plans:
        p.sfx = mix.pick(lib, p.sfx, rng)
        for c in p.sfx:
            if not (sfx_dir / c["file"]).exists():
                try:
                    drive.download(dcfg["sfx"], c["file"], sfx_dir / c["file"], file_id=sfx_ids.get(c["file"]))
                except drive.DriveError as e:                # без звука ролик всё равно собираем
                    print(f"  SFX «{c['file']}» не скачался: {e}", flush=True)
        p.sfx = [c for c in p.sfx if (sfx_dir / c["file"]).exists()]

    # --- рендер + звук
    results = []
    for i, p in enumerate(plans, 1):
        name = f"{i:02d}_{p.style}_{p.template}"
        d = out_root / name
        d.mkdir(parents=True, exist_ok=True)
        t = time.time()
        print(f"  рендер {name}…", flush=True)
        silent = render(p.props, COMP_ID[p.template], d / "_silent.mp4", cfg)
        timing[f"рендер {name}"] = time.time() - t
        audio = mix.render(p.sfx, sfx_dir, p.duration_s, d / "_clean.wav")
        final = mix.mux(silent, d / "_clean.wav", d / "video_clean.mp4")
        errs = probe_ok(final, p.template)
        contact(final, WORK / f"contact_{name}.jpg")
        print(f"  готово {name}", flush=True)
        for tmp in (silent, d / "_clean.wav", silent.with_suffix(".props.json")):
            tmp.unlink(missing_ok=True)
        results.append({"folder": name, "plan": p, "audio": audio, "errors": errs})
        print(f"{name}: {p.duration_s:.1f} с, хук {p.hook_id}, ошибок {len(errs)}", flush=True)

    # --- на Диск (Done/TEST_…)
    if not args.local:
        t = time.time()
        for r in results:
            print(f"  на Диск {r['folder']}", flush=True)
            drive.upload(out_root / r["folder"] / "video_clean.mp4", f"{dcfg['done']}/{folder}/{r['folder']}/video_clean.mp4")
        timing["загрузка на Диск"] = time.time() - t
    timing["всего"] = time.time() - t0

    # --- отчёт
    hooks = {t["id"]: t for t in texts}
    L = [f"# Шаг 4. Тестовые ролики ({folder})", "", f"seed: `{seed}` (повторить тот же монтаж: run с этим seed)", ""]
    for r in results:
        p = r["plan"]
        a = r["audio"]
        snd = "тишина (нативный стиль без SFX)" if a.get("silent") else f"{a['lufs']:.1f} LUFS, пик {a['true_peak']:.1f} dBTP"
        L += [f"## {r['folder']}",
              f"- {p.duration_s:.1f} с, {len(p.segments)} планов, цвет {p.color}",
              f"- текст: «{' / '.join(hooks[p.hook_id]['screens'])}» (`{p.hook_id}`)",
              f"- исходники: " + ", ".join(sorted({s.name for s in p.segments})),
              f"- звук: {snd}; SFX: " + (", ".join(f"{c['kind']} «{c['file']}» {c['t']:.1f} с" for c in p.sfx) or "нет"),
              "- проверка: " + ("✅" if not r["errors"] else "❌ " + "; ".join(r["errors"])), ""]
    if skipped:
        L.append(f"- Пропущены шаблоны (мало исходников): {', '.join(skipped)}")
    L += ["## Время", ""] + [f"- {k}: {v / 60:.1f} мин" for k, v in timing.items()]
    md = "\n".join(L)
    (WORK / "videos_report.md").write_text(md)
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md + "\n")
    return 1 if any(r["errors"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
