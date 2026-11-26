#!/usr/bin/env python3
"""Индекс исходников: только новые и изменённые файлы.

    python3 -m analyze.index                 # обычный запуск (Диск + Claude)
    python3 -m analyze.index --local DIR     # без Диска: файлы из DIR (для проверки)
    python3 -m analyze.index --no-vision     # без Claude (только техника)
    python3 -m analyze.index --force         # переразметить всё

Ключ файла: ID на Диске + modTime + размер. Результат — clips_index.json
(в _autoedit_state на Диске и в work/), отчёт — work/index_report.md.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import datetime as dt
import json
import os
import shutil
import sys
import time
from pathlib import Path

from analyze import drive, probe, shots
from analyze import vision as vis

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mts", ".3gp"}
LIFESTYLE = {"street", "hands", "pocket_bag", "indoor_lifestyle"}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_key(f: dict) -> str:
    return f"{f.get('ID') or f['Name']}|{f.get('ModTime', '')}|{f.get('Size', '')}"


class Timer:
    def __init__(self):
        self.t = {}

    def run(self, name):
        timer = self

        class _C:
            def __enter__(self):
                self.s = time.time()

            def __exit__(self, *a):
                timer.t[name] = timer.t.get(name, 0) + time.time() - self.s
        return _C()


# ------------------------------------------------------------------ один файл
def index_file(path: Path, meta: dict, cfg: dict, client, usage, frames_dir: Path, timer: Timer) -> dict:
    icfg = cfg["index"]
    with timer.run("ffprobe"):
        info = probe.probe(path)
    with timer.run("декодирование"):
        rgb, fps = shots.decode_small(path, info["width"], info["height"])
    with timer.run("планы"):
        cuts = shots.find_cuts(rgb, fps)
        spans = shots.detect_shots(cuts, info["duration"], icfg["min_shot_s"], icfg["max_segment_s"])
        small = shots.to_gray(rgb)
        del rgb
    fid = meta.get("ID") or meta["Name"]
    entry = {"name": meta["Name"], "id": fid, "size": meta.get("Size"), "modtime": meta.get("ModTime"),
             "key": file_key(meta), "indexed_at": now(), "probe": info, "shots": []}
    jobs = []
    for a, b in spans:
        sid = f"{fid}#{a:.2f}-{b:.2f}"
        m = shots.shot_metrics(small, fps, a, b)
        pad = min(0.15, (b - a) / 6)
        ts = [a + pad, (a + b) / 2, b - pad]
        fpaths = []
        with timer.run("кадры"):
            for i, t in enumerate(ts):
                out = frames_dir / f"{abs(hash(sid)) % 10**10}_{i}.jpg"
                shots.extract_frame(path, t, out, icfg["frame_px"], info["hdr"])
                fpaths.append(out)
        m["sharpness"] = round(sorted(shots.sharpness(p) for p in fpaths)[1], 1)
        shot = {"id": sid, "start": a, "end": b, "dur": round(b - a, 3), "metrics": m,
                "vision": None, "vision_error": None, "thumb": str(fpaths[1])}
        entry["shots"].append(shot)
        jobs.append((shot, fpaths))

    if client is not None and jobs:
        with timer.run("разметка Claude"):
            with cf.ThreadPoolExecutor(max_workers=cfg["claude"]["max_workers"]) as ex:
                futs = {ex.submit(vis.tag_shot, client, usage, fp, cfg["claude"]["effort"]): s for s, fp in jobs}
                for fu in cf.as_completed(futs):
                    s = futs[fu]
                    try:
                        s["vision"] = fu.result()
                    except Exception as e:                      # noqa: BLE001 — пишем в отчёт
                        s["vision_error"] = str(e)[:300]
    return entry


# ------------------------------------------------------------------ годность плана
def thresholds(index: dict) -> dict:
    """Порог резкости — относительный: нижние 15 % библиотеки считаем мягкими."""
    vals = sorted(s["metrics"]["sharpness"] for f in index["files"].values() if not f.get("deleted")
                  for s in f["shots"])
    soft = vals[int(len(vals) * 0.15)] if len(vals) >= 7 else 0
    return {"sharp_min": soft}


def usable(s: dict, th: dict, cfg: dict) -> bool:
    m, v = s["metrics"], s.get("vision")
    if not v:
        return False
    return (v["case_visible_ratio"] >= cfg["index"]["case_visible_min"]
            and m["sharpness"] >= th["sharp_min"]
            and (m["clip_high"] or 0) < 0.05)


# ------------------------------------------------------------------ отчёт
def report(index: dict, new_files: list[str], skipped: list[str], errors: list[str], usage, timer: Timer,
           cfg: dict, vision_on: bool) -> str:
    files = [f for f in index["files"].values() if not f.get("deleted")]
    all_shots = [s for f in files for s in f["shots"]]
    tagged = [s for s in all_shots if s.get("vision")]
    th = thresholds(index)
    good = [s for s in all_shots if usable(s, th, cfg)]
    by = lambda key: collections.Counter(s["vision"][key] for s in tagged)
    L = ["# Шаг 3. Индекс исходников", ""]
    L.append(f"- Файлов в индексе: **{len(files)}**, новых сегодня: **{len(new_files)}**")
    L.append(f"- Планов: **{len(all_shots)}** (общая длина {sum(s['dur'] for s in all_shots):.0f} с), "
             f"размечено зрением: **{len(tagged)}**")
    L.append(f"- Годных для монтажа (чехол ≥ 80 % плана, резкий, без пересвета): **{len(good)}**")
    hdr = sum(1 for f in files if f["probe"]["hdr"])
    fps = collections.Counter(round(f["probe"]["fps"]) for f in files)
    orient = collections.Counter(f["probe"]["orientation"] for f in files)
    L.append(f"- Кадр: {', '.join(f'{k} {v}' for k, v in orient.items())}; fps: "
             f"{', '.join(f'{k} — {v}' for k, v in sorted(fps.items()))}; HDR: {hdr}")
    if not vision_on:
        L += ["", "⚠️ Разметка зрением не работала в этом запуске (причина в разделе «Ошибки»). Новые планы будут размечены при следующем запуске."]
    if tagged:
        names = {"studio": "студия", "street": "улица", "indoor_lifestyle": "дома/в помещении",
                 "hands": "в руках", "pocket_bag": "карман/сумка", "packaging": "упаковка",
                 "wallet_before": "«до»: кошелёк", "other": "другое"}
        L += ["", "## Что в кадре", "", "| обстановка | планов | годных |", "|---|---|---|"]
        good_ids = {s["id"] for s in good}
        for k, n in by("setting").most_common():
            g = sum(1 for s in tagged if s["vision"]["setting"] == k and s["id"] in good_ids)
            L.append(f"| {names.get(k, k)} | {n} | {g} |")
        col = by("color")
        L.append("")
        L.append(f"- Цвет чехла: cognac {col.get('cognac', 0)}, black {col.get('black', 0)}, "
                 f"оба {col.get('both', 0)}, нет чехла {col.get('none', 0)}")
        act = by("action")
        L.append("- Действие: " + ", ".join(f"{k} {v}" for k, v in act.most_common()))
        sf = collections.Counter(x for s in tagged for x in s["vision"]["style_fit"])
        L.append(f"- Подходит для стиля: премиум {sf.get('premium', 0)}, нативный {sf.get('native', 0)}")
        heroes = sorted(good, key=lambda s: -s["vision"]["hero_score"])[:5]
        if heroes:
            L += ["", "**Лучшие планы для хука:**"]
            for s in heroes:
                fname = index["files"][s["id"].split("#")[0]]["name"] if s["id"].split("#")[0] in index["files"] else s["id"]
                L.append(f"- `{fname}` {s['start']:.1f}–{s['end']:.1f} с — {s['vision']['hero_score']}/10, "
                         f"{s['vision']['notes']}")

        # доступность шаблонов фазы 1
        gs = collections.Counter(s["vision"]["setting"] for s in good)
        studio = sum(1 for s in good if s["vision"]["setting"] == "studio" or s["vision"]["action"] == "detail_macro")
        life = sum(gs[k] for k in ("street", "hands", "pocket_bag"))
        L += ["", "## Шаблоны фазы 1", ""]
        L.append(f"- `p_one_line` (нужно 2+ студийных): {'✅' if studio >= 2 else '❌'} есть {studio}")
        L.append(f"- `n_statement` (нужно 3+ улица/руки/карман): {'✅' if life >= 3 else '❌'} есть {life}")
        wb = by("setting").get("wallet_before", 0)
        L.append(f"- Кадры «до» (`wallet_before`) для будущего `n_wallet_vs_case`: {'есть ' + str(wb) if wb else 'нет'}")

        todo = []
        if studio < 4:
            todo.append("студия: чехол на светлом фоне, медленный поворот и открытие, 5–8 с")
        if gs["street"] < 3:
            todo.append("улица: чехол в руке на ходу, город, 3–5 с")
        if gs["pocket_bag"] < 2:
            todo.append("карман/сумка: достать чехол из джинсов или сумки, 3–5 с")
        if not wb:
            todo.append("«до»: презерватив в кошельке, мятая упаковка, 3–5 с")
        if col.get("black", 0) + col.get("both", 0) < 3:
            todo.append("больше планов с Midnight Black")
        if col.get("cognac", 0) + col.get("both", 0) < 3:
            todo.append("больше планов с Cognac Brown")
        L += ["", "## Что снять в следующий раз", ""] + ([f"- {t}" for t in todo] or ["- Пока хватает."])

    if skipped:
        L += ["", "## Пропущено (не видео)"] + [f"- `{n}`" for n in skipped]
    if errors:
        L += ["", "## Ошибки"] + [f"- {e}" for e in errors]
    verr = [s for s in all_shots if s.get("vision_error")]
    if verr:
        L.append(f"- Разметка не удалась для {len(verr)} планов: {verr[0]['vision_error']}")

    u = usage.as_dict() if usage else None
    L += ["", "## Время и расход", ""]
    for k, v in timer.t.items():
        L.append(f"- {k}: {v / 60:.1f} мин")
    if u:
        fmt = lambda n: f"{n:,}".replace(",", " ")
        L.append(f"- Claude ({u['model']}): {u['calls']} запросов, {fmt(u['input_tokens'])} вход / "
                 f"{fmt(u['output_tokens'])} выход токенов ≈ **${u['cost_usd']:.3f}**")
    return "\n".join(L)


def contact_sheet(index: dict, out: Path, cols: int = 8) -> Path | None:
    """Обзор: средний кадр каждого плана с подписью (для проверки разметки глазами)."""
    import cv2
    import numpy as np

    tiles = []
    for f in index["files"].values():
        if f.get("deleted"):
            continue
        for s in f["shots"]:
            p = s.get("thumb")
            img = cv2.imread(p) if p and Path(p).exists() else None
            if img is None:
                continue
            h = 320
            w = int(img.shape[1] * h / img.shape[0])
            img = cv2.resize(img, (w, h))
            canvas = np.full((h + 52, 200, 3), 245, np.uint8)
            x0 = max(0, (200 - w) // 2)
            crop = img[:, max(0, (w - 200) // 2): max(0, (w - 200) // 2) + 200]
            canvas[:h, x0:x0 + crop.shape[1]] = crop
            v = s.get("vision") or {}
            l1 = f"{f['name'][:14]} {s['start']:.0f}-{s['end']:.0f}s"
            l2 = f"{v.get('setting', '?')[:9]} {v.get('color', '?')[:6]} c{v.get('case_visible_ratio', 0):.1f} h{v.get('hero_score', '-')}"
            cv2.putText(canvas, l1, (4, h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1, cv2.LINE_AA)
            cv2.putText(canvas, l2, (4, h + 42), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1, cv2.LINE_AA)
            tiles.append(canvas)
    if not tiles:
        return None
    rows = []
    for i in range(0, len(tiles), cols):
        row = tiles[i:i + cols]
        row += [np.full_like(tiles[0], 255)] * (cols - len(row))
        rows.append(np.hstack(row))
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
    return out


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", type=Path, help="папка с видео вместо Диска")
    ap.add_argument("--no-vision", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    cfg = json.loads((ROOT / "config.json").read_text())
    dcfg = cfg["drive"]
    state_path = f"{dcfg['state']}/clips_index.json"
    WORK.mkdir(exist_ok=True)
    src_dir, frames_dir = WORK / "src", WORK / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    timer = Timer()

    # индекс: Диск → work/
    with timer.run("чтение состояния"):
        if args.local:
            local_idx = WORK / "clips_index.json"
            index = json.loads(local_idx.read_text()) if local_idx.exists() else {}
        else:
            index = drive.read_json(state_path, {})
    index.setdefault("version", 1)
    index.setdefault("files", {})

    # ключ Claude
    client, usage, vision_on, errors = None, None, False, []
    if not args.no_vision:
        try:
            client = vis.make_client()
            vis.check_key(client, cfg["claude"]["model"])
            usage = vis.Usage(cfg["claude"]["model"], cfg["claude"]["price_in_per_m"], cfg["claude"]["price_out_per_m"])
            vision_on = True
        except vis.VisionError as e:
            errors.append(f"Claude: {e}")
            client = None

    # список исходников
    with timer.run("список файлов"):
        if args.local:
            listing = [{"Name": p.name, "Size": p.stat().st_size, "ModTime": str(int(p.stat().st_mtime)),
                        "ID": p.name} for p in sorted(args.local.iterdir()) if p.is_file()]
        else:
            listing = drive.list_files(dcfg["sources"])
    videos = [f for f in listing if Path(f["Name"]).suffix.lower() in VIDEO_EXT]
    skipped = [f["Name"] for f in listing if f not in videos]
    live_ids = {f.get("ID") or f["Name"] for f in videos}
    for fid, f in index["files"].items():
        f["deleted"] = fid not in live_ids

    todo = []
    for f in videos:
        fid = f.get("ID") or f["Name"]
        old = index["files"].get(fid)
        untagged = old and vision_on and any(s.get("vision") is None for s in old["shots"])
        if args.force or not old or old.get("key") != file_key(f) or untagged:
            todo.append(f)

    new_files = []
    for i, f in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {f['Name']}", flush=True)
        try:
            with timer.run("скачивание"):
                local = (args.local / f["Name"]) if args.local else \
                    drive.download(dcfg["sources"], f["Name"], src_dir / f"{len(new_files)}{Path(f['Name']).suffix}")
            t0 = time.time()
            entry = index_file(local, f, cfg, client, usage, frames_dir, timer)
            print(f"    планов: {len(entry['shots'])}, {time.time() - t0:.0f} с", flush=True)
            index["files"][entry["id"]] = entry
            new_files.append(f["Name"])
            if not args.local:
                local.unlink(missing_ok=True)               # место на раннере
        except Exception as e:                               # noqa: BLE001 — один файл не валит индекс
            errors.append(f"`{f['Name']}`: {str(e)[:300]}")
        # промежуточное сохранение (если запуск оборвётся, сделанное не пропадёт)
        if not args.local and new_files and i % 5 == 0:
            drive.write_json(state_path, index)

    index["updated"] = now()
    if usage:
        hist = index.setdefault("usage_log", [])
        hist.append({"at": now(), **usage.as_dict()})
        index["usage_log"] = hist[-200:]
    out = WORK / "clips_index.json"
    out.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    if not args.local:
        with timer.run("запись состояния"):
            drive.write_json(state_path, index)

    md = report(index, new_files, skipped, errors, usage, timer, cfg, vision_on)
    (WORK / "index_report.md").write_text(md)
    contact_sheet(index, WORK / "index_contact.jpg")
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md + "\n")
    hard_fail = (todo and not new_files) or (not args.no_vision and not vision_on)
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
