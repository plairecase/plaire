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
from audio import music as music_mod           # noqa: E402
from planner import media                      # noqa: E402
from planner import templates                  # noqa: E402
from planner.templates import BUILDERS, Ctx    # noqa: E402
from planner import worlds                     # noqa: E402
from qc import vision_check                    # noqa: E402

WORK = ROOT / "work"
REMOTION = ROOT / "remotion"
COMP_ID = {"p_one_line": "p-one-line", "n_statement": "n-statement", "p_organic": "p-one-line",
           "p_gloves_pov": "p-one-line", "p_studio_to_life": "p-one-line"}
DUR_RANGE = {"p_one_line": (7, 12), "n_statement": (7, 10), "p_organic": (7, 10), "promote": (9, 15),
             "p_gloves_pov": (7, 10), "p_studio_to_life": (7, 10)}


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


def _frames(video: Path, idxs: list[int]):
    import cv2

    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(n - 1, i if i >= 0 else n + i)))
        ok, f = cap.read()
        if ok:
            out.append(f)
    cap.release()
    return out, n


def tail_black(video: Path) -> list[str]:
    """Нет чёрных кадров в последние 0.5 с (fix-03)."""
    fr, n = _frames(video, list(range(-15, 0)))
    dark = [f for f in fr if f.mean() < 12]
    return ["чёрные кадры в конце"] if dark else []


def loop_ssim(video: Path) -> float:
    """SSIM первого и последнего кадра (без зоны текста), для лупа ≥ 0.85."""
    import cv2

    fr, n = _frames(video, [0, -1])
    if len(fr) < 2:
        return 0.0
    a, b = (cv2.cvtColor(cv2.resize(f, (270, 480)), cv2.COLOR_BGR2GRAY).astype(float)[200:] for f in fr)
    c1, c2 = 6.5, 58.5
    ma, mb, va, vb = a.mean(), b.mean(), a.var(), b.var()
    cov = ((a - ma) * (b - mb)).mean()
    return round(((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma ** 2 + mb ** 2 + c1) * (va + vb + c2)), 3)


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

    # --- музыка (правка владельца 27.11.2026: только версия с музыкой)
    music_dir = WORK / "music"
    mlisting = [] if args.local else drive.list_files(dcfg["music"])
    mids = {f["Name"]: f.get("ID") for f in mlisting}
    tracks_pool = music_mod.candidates(mlisting)
    rng.shuffle(tracks_pool)
    if args.local and (args.local / "_music").exists():
        tracks_pool = [p.name for p in (args.local / "_music").iterdir()]
        music_dir = args.local / "_music"

    all_tracks = list(tracks_pool)
    broken: set[str] = set()

    def next_track():
        if not tracks_pool:                              # треков меньше, чем роликов — повторяем
            tracks_pool.extend(t for t in all_tracks if t not in broken)
            rng.shuffle(tracks_pool)
        while tracks_pool:
            name = tracks_pool.pop()
            try:
                path = music_dir / name if args.local else drive.download(dcfg["music"], name, music_dir / name,
                                                                         file_id=mids.get(name))
                return music_mod.analyze(path, 13.0, rng), path
            except Exception as e:                       # noqa: BLE001 — битый трек пропускаем
                broken.add(name)
                print(f"  трек {name}: {e}", flush=True)
        return None, None

    # --- SFX-библиотека
    sfx_dir = WORK / "sfx"
    sfx_listing = drive.list_files(dcfg["sfx"]) if not args.local else []
    sfx_ids = {f["Name"]: f.get("ID") for f in sfx_listing}
    lib = mix.library(sfx_listing)

    def make_plan(vi: int, style: str, purpose: str):
        track, tpath = next_track()
        ctx.beats = track.beats if track else None
        order = list(cfg["templates"][style])
        rng.shuffle(order)                               # разные шаблоны день ото дня
        for tmpl in order:
            if tmpl in worlds.TEMPLATES:
                built = worlds.build(ctx, tmpl, purpose, bpm_cycle[vi % len(bpm_cycle)])
            elif tmpl == "p_organic":
                built = BUILDERS[tmpl](ctx, purpose, bpm_cycle[vi % len(bpm_cycle)])
            else:
                built = BUILDERS[tmpl](ctx)
            if built:
                built.track, built.track_path = track, tpath
                return built
            skipped.append(f"{tmpl} ({purpose})")
        return None

    clip_no = [0]

    def produce(p, name: str) -> dict:
        """Нарезка → рендер → звук → проверки (техника, план fix-03, визуальная Claude)."""
        t1 = time.time()
        for sg in p.segments:
            get_src(sg.name)
        for sg, clip in zip(p.segments, p.props["clips"]):
            rel = f"clips/c{clip_no[0]}.mp4"
            clip_no[0] += 1
            print(f"  нарезка {rel}: {sg.name} {sg.src_start:.1f}+{sg.src_dur:.1f}"
                  f"{' +стабилизация' if sg.stabilize else ''}{' (луп)' if sg.reverse else ''}", flush=True)
            if sg.reverse and p.segments[0].out:
                # луп = обратный ход первого клипа: последний кадр ролика точно равен первому
                media.reverse_head(REMOTION / "public" / p.segments[0].out, sg.src_dur,
                                   REMOTION / "public" / rel, cfg["render"]["crf"])
            else:
                media.cut(local_src[sg.name], sg.src_start, sg.src_dur, REMOTION / "public" / rel,
                          cfg["render"]["fps"], cfg["render"]["crf"], sg.hdr, sg.bbox, cfg["render"]["hdr_tonemap"],
                          stabilize=sg.stabilize, reverse=sg.reverse)
            clip["src"] = rel
            sg.out = rel
        timing["нарезка"] = timing.get("нарезка", 0) + time.time() - t1
        p.sfx = mix.pick(lib, p.sfx, rng)
        for c in p.sfx:
            if not (sfx_dir / c["file"]).exists():
                try:
                    drive.download(dcfg["sfx"], c["file"], sfx_dir / c["file"], file_id=sfx_ids.get(c["file"]))
                except drive.DriveError as e:                # без звука ролик всё равно собираем
                    print(f"  SFX «{c['file']}» не скачался: {e}", flush=True)
        p.sfx = [c for c in p.sfx if (sfx_dir / c["file"]).exists()]
        d = out_root / name
        d.mkdir(parents=True, exist_ok=True)
        t1 = time.time()
        print(f"  рендер {name}…", flush=True)
        silent = render(p.props, COMP_ID[p.template], d / "_silent.mp4", cfg)
        timing["рендер"] = timing.get("рендер", 0) + time.time() - t1
        audio = music_mod.render(p.track, p.track_path, p.sfx, sfx_dir, p.duration_s, d / "_audio.wav")
        final = mix.mux(silent, d / "_audio.wav", d / "video.mp4")
        errs = probe_ok(final, "promote" if p.purpose == "promote" else p.template)
        errs += tail_black(final)
        if p.purpose == "organic":
            ss = loop_ssim(final)
            p.checks["loop_ssim"] = ss
            if ss < 0.85:
                errs.append(f"луп разорван (SSIM {ss:.2f} < 0.85)")
        for k in ("world_consistency", "hands_consistency", "color_consistency", "text_shot_match", "inside_early"):
            if k in p.checks and not p.checks[k]:
                errs.append(f"план: {k}")
        sheet = WORK / f"contact_{name}.jpg"
        contact(final, sheet)
        vq = None
        if vision_client is not None:
            try:
                vq = vision_check.check(sheet, p.purpose, vision_client, vision_usage)
                if not vq["pass"]:
                    errs.append("визуально: " + ", ".join(vq["failed"]))
            except Exception as e:                       # noqa: BLE001 — нет ответа → не блокируем
                print(f"  визуальная проверка: {e}", flush=True)
        for tmp in (silent, d / "_audio.wav", silent.with_suffix(".props.json")):
            tmp.unlink(missing_ok=True)
        (WORK / "plans").mkdir(exist_ok=True)
        (WORK / "plans" / f"{name}.json").write_text(json.dumps(
            {"props": p.props, "shots": getattr(p, "shots", []), "checks": p.checks, "visual": vq,
             "errors": errs}, ensure_ascii=False, indent=1, default=str))
        print(f"{name}: {p.duration_s:.1f} с, хук {p.hook_id}, ошибок {len(errs)}", flush=True)
        return {"folder": name, "plan": p, "audio": audio, "errors": errs, "visual": vq}

    # визуальная проверка (Claude): нужен ключ; без него — только технические проверки
    vision_client = vision_usage = None
    if not args.local:
        try:
            from analyze import vision as vis
            vision_client = vis.make_client()
            vision_usage = vis.Usage(cfg["claude"]["model"], cfg["claude"]["price_in_per_m"],
                                     cfg["claude"]["price_out_per_m"])
        except Exception as e:                           # noqa: BLE001
            print(f"  визуальная проверка недоступна: {e}", flush=True)

    # --- ролики дня: каждый слот — до 3 попыток (раздел 13)
    ctx = Ctx(shots, texts, rng, cfg["render"]["fps"], cfg["render"]["dissolve_frames"])
    skipped: list[str] = []
    bpm_cycle = cfg.get("beat_grid_bpm", [120])
    want = [(st, "organic") for st in ("premium", "native") for _ in range(cfg["style_mix"].get(st, 0))]
    is_promote_day = now.strftime("%a") in cfg.get("promote_days", [])
    if args.mode == "test" or is_promote_day:
        want.append(("promote", "promote"))               # fix-02: promote по понедельникам (в тесте — всегда)
    results = []
    for vi, (style, purpose) in enumerate(want):
        best = None
        for attempt in range(3):
            p = make_plan(vi, style, purpose)
            if not p:
                break
            name = f"{len(results) + 1:02d}_{p.template}_{p.purpose}"
            r = produce(p, name)
            r["attempts"] = attempt + 1
            ctx.avoid_hooks.add(p.hook_id)
            if not r["errors"]:
                best = r
                break
            print(f"  попытка {attempt + 1} не прошла проверки: {'; '.join(r['errors'])}", flush=True)
            if best is None or len(r["errors"]) < len(best["errors"]):
                best = r
        if best:
            results.append(best)
            ctx.avoid_first.add(best["plan"].first_shot)
            ctx.avoid_color = best["plan"].color
    if not results:
        raise SystemExit("Не удалось собрать ни одного ролика: мало годных исходников для шаблонов «одного мира»")

    # --- на Диск (Done/TEST_…)
    if not args.local:
        t = time.time()
        for r in results:
            print(f"  на Диск {r['folder']}", flush=True)
            drive.upload(out_root / r["folder"] / "video.mp4", f"{dcfg['done']}/{folder}/{r['folder']}/video.mp4")
        timing["загрузка на Диск"] = time.time() - t
    timing["всего"] = time.time() - t0

    # --- отчёт
    hooks = {t["id"]: t for t in texts}
    L = [f"# Шаг 4. Тестовые ролики ({folder})", "", f"seed: `{seed}` (повторить тот же монтаж: run с этим seed)", ""]
    for r in results:
        p = r["plan"]
        a = r["audio"]
        snd = "тишина" if a.get("silent") else f"{a['lufs']:.1f} LUFS, пик {a['true_peak']:.1f} dBTP"
        mu = a.get("music")
        snd = (f"музыка «{mu['title']}», {mu['bpm']:.0f} BPM, с {mu['start_s']:.1f} с; " if mu
               else "⚠️ без музыки (папка Music пустая); ") + snd
        L += [f"## {r['folder']}",
              f"- {p.purpose}, {p.duration_s:.1f} с, {len(p.segments)} планов, цвет {p.color}, сетка {p.bpm:.0f} BPM",
              (f"- fix-03: мир {p.checks.get('world')} {int(p.checks.get('world_share', 0) * 100)} %, смен мира "
               f"{p.checks.get('world_changes')} {'✅' if p.checks.get('world_consistency') else '❌'} · руки "
               f"{'✅' if p.checks.get('hands_consistency') else '❌'} · цвет {'✅' if p.checks.get('color_consistency') else '❌'}"
               f" · текст = план {'✅' if p.checks.get('text_shot_match') else '❌'} · внутри в первые 3 с "
               f"{'✅' if p.checks.get('inside_early') else '❌'}" if 'world' in p.checks else "- fix-03: —"),
              "- планы: " + " → ".join(f"{x['role']} ({x['world']}, {x['color']}{', руки ' + x['hands'] if x['hands'] != 'none' else ''})"
                                       for x in getattr(p, 'shots', [])),
              "- тексты: " + " → ".join(f"«{sc['text']}»" for sc in p.props['screens']),
              f"- проверки: первая склейка {p.checks.get('first_cut_s')} с, склейки на долях "
              f"{'✅' if p.checks.get('cuts_on_beats', True) else '❌'}, целые такты {'✅' if p.checks.get('whole_bars', True) else '❌'}, "
              f"самый длинный план {p.checks.get('max_shot_s')} с, цена на экране: {'да' if p.checks.get('price_on_screen') else 'нет'}"
              + (f", не хватает: {', '.join(p.missing)}" if p.missing else ""),
              f"- текст: «{' / '.join(hooks[p.hook_id]['screens'])}» (`{p.hook_id}`)",
              f"- исходники: " + ", ".join(sorted({s.name for s in p.segments})),
              f"- звук: {snd}; SFX: " + (", ".join(f"{c['kind']} «{c['file']}» {c['t']:.1f} с" for c in p.sfx) or "нет"),
              f"- попыток: {r.get('attempts', 1)}; луп SSIM: {p.checks.get('loop_ssim', '—')}",
              "- визуально (Claude): " + ("—" if not r.get("visual") else
                                          ("✅" if r["visual"]["pass"] else "❌ " + ", ".join(r["visual"]["failed"]))
                                          + ("; " + "; ".join(r["visual"].get("issues", [])[:3]) if r["visual"].get("issues") else "")),
              "- проверка: " + ("✅" if not r["errors"] else "❌ " + "; ".join(r["errors"])), ""]
    if skipped:
        L.append(f"- Пропущены шаблоны (мало исходников): {', '.join(skipped)}")
    L += ["## Время", ""] + [f"- {k}: {v / 60:.1f} мин" for k, v in timing.items()]
    if vision_usage and vision_usage.calls:
        u = vision_usage.as_dict()
        L.append(f"- Claude (визуальная проверка): {u['calls']} запросов ≈ ${u['cost_usd']:.3f}")
    md = "\n".join(L)
    (WORK / "videos_report.md").write_text(md)
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md + "\n")
    return 1 if any(r["errors"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
