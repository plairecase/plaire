#!/usr/bin/env python3
"""Шаг 1 фазы 1: проверка доступа к Google Диску и дерево папки Plaire.

Что делает:
  * читает дерево `gdrive:` (корень = папка Plaire) на глубину 2;
  * показывает папки, сколько в них файлов и каких типов;
  * ищет папки из config.json (Done, SFX, Music, 3D) и угадывает папку с исходниками;
  * проверяет, что в 3D лежат .glb, а не .zip / данные Polycam;
  * подсвечивает «опасные» символы в именах (кириллица, ／, лишние пробелы);
  * проверяет запись: создаёт `_autoedit_state/healthcheck.txt`.
    Больше ничего не пишет и ничего не удаляет.

Результат: Markdown в summary GitHub Actions + work/drive_check.json.
Только стандартная библиотека Python, нужен rclone с remote `gdrive:`.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

REMOTE = "gdrive:"
ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"

VIDEO = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mts", ".hevc", ".3gp"}
IMAGE = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}
AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".aif", ".aiff"}
MODEL = {".glb", ".gltf"}
ARCHIVE = {".zip", ".rar", ".7z"}
POLYCAM_HINTS = {"keyframes", "cameras", "mesh_info.json", "polycam.mp4"}


def rclone(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["rclone", *args], input=input_text, capture_output=True, text=True)


def human(n: int) -> str:
    size = float(n)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if size < 1024 or unit == "ТБ":
            return f"{size:.0f} {unit}" if unit == "Б" else f"{size:.1f} {unit}"
        size /= 1024
    return str(n)


def kind(name: str, mime: str = "") -> str:
    ext = Path(name).suffix.lower()
    if mime.startswith("application/vnd.google-apps."):
        return "google_doc"
    for label, exts in (("video", VIDEO), ("image", IMAGE), ("audio", AUDIO),
                        ("model3d", MODEL), ("archive", ARCHIVE)):
        if ext in exts:
            return label
    return "other"


def name_warnings(name: str) -> list[str]:
    w = []
    if name != name.strip():
        w.append("пробел в начале/конце")
    if "  " in name:
        w.append("двойной пробел")
    for ch in sorted(set(name)):
        if ord(ch) < 128:
            continue
        cat = unicodedata.category(ch)
        uname = unicodedata.name(ch, "?")
        if "CYRILLIC" in uname:
            w.append("кириллица")
        elif "FULLWIDTH" in uname or ch in "／∕⁄":
            w.append(f"спецсимвол «{ch}» ({uname}) вместо обычного")
        elif cat.startswith(("Z", "C")):
            w.append(f"невидимый символ U+{ord(ch):04X}")
    return sorted(set(w))


def list_tree(path: str = "", depth: int = 2) -> list[dict]:
    res = rclone("lsjson", f"{REMOTE}{path}", "-R", "--max-depth", str(depth), "--fast-list")
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip()[-1500:])
    items = json.loads(res.stdout or "[]")
    if path:
        for it in items:
            it["Path"] = f"{path}/{it['Path']}"
    return items


def summarize_folder(items: list[dict], folder: str) -> dict:
    prefix = folder + "/"
    files = [i for i in items if not i["IsDir"] and i["Path"].startswith(prefix)
             and "/" not in i["Path"][len(prefix):]]
    subdirs = [i["Name"] for i in items if i["IsDir"] and i["Path"].startswith(prefix)
               and "/" not in i["Path"][len(prefix):]]
    kinds = collections.Counter(kind(f["Name"], f.get("MimeType", "")) for f in files)
    exts = collections.Counter(Path(f["Name"]).suffix.lower() or "(без расширения)" for f in files)
    return {
        "path": folder,
        "files": len(files),
        "bytes": sum(max(f.get("Size", 0), 0) for f in files),
        "kinds": dict(kinds),
        "exts": dict(exts.most_common()),
        "subdirs": sorted(subdirs),
        "samples": sorted(f["Name"] for f in files)[:8],
    }


def find_dir(items: list[dict], wanted: str) -> str | None:
    """Ищет папку по пути из config.json, без учёта регистра и пробелов по краям."""
    norm = lambda p: "/".join(part.strip().casefold() for part in p.split("/"))
    target = norm(wanted)
    candidates = [target]
    if target.startswith("plaire/"):          # "Plaire/3D" может значить "3D внутри корня Plaire"
        candidates.append(target[len("plaire/"):])
    for cand in candidates:
        for it in items:
            if it["IsDir"] and norm(it["Path"]) == cand:
                return it["Path"]
    return None


def check_3d(path: str) -> dict:
    items = list_tree(path, depth=3)
    files = [i for i in items if not i["IsDir"]]
    glb = [i["Path"] for i in files if Path(i["Name"]).suffix.lower() in MODEL]
    zips = [i["Path"] for i in files if Path(i["Name"]).suffix.lower() in ARCHIVE]
    polycam = sorted({i["Name"] for i in items if i["Name"].lower() in POLYCAM_HINTS})
    if glb:
        verdict = "ok"
    elif zips or polycam:
        verdict = "not_models"
    else:
        verdict = "empty"
    return {"path": path, "glb": glb, "archives": zips, "polycam_markers": polycam,
            "files": len(files), "verdict": verdict}


def write_test(state_dir: str) -> dict:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    target = f"{REMOTE}{state_dir}/healthcheck.txt"
    mk = rclone("mkdir", f"{REMOTE}{state_dir}")
    if mk.returncode != 0:
        return {"ok": False, "step": "mkdir", "error": mk.stderr.strip()[-800:]}
    up = rclone("rcat", target, input_text=f"plaire-autoedit healthcheck {stamp}\n")
    if up.returncode != 0:
        err = up.stderr.strip()[-800:]
        return {"ok": False, "step": "upload", "error": err,
                "no_quota": "storageQuotaExceeded" in err or "storage quota" in err.lower()}
    chk = rclone("lsjson", target)
    ok = chk.returncode == 0 and json.loads(chk.stdout or "[]") != []
    return {"ok": ok, "step": "verify", "error": "" if ok else chk.stderr.strip()[-800:]}


def sa_email() -> str | None:
    f = os.environ.get("GDRIVE_SA_FILE")
    if not f or not Path(f).exists():
        return None
    try:
        return json.load(open(f)).get("client_email")
    except Exception:
        return None


def build_report(cfg: dict) -> tuple[str, dict, bool]:
    drive_cfg = cfg["drive"]
    mode = os.environ.get("GDRIVE_AUTH_MODE", "?")
    email = sa_email()
    lines = ["# Шаг 1. Проверка Google Диска", ""]
    lines.append(f"- Способ входа: **{'сервисный аккаунт' if mode == 'service_account' else mode}**")
    if email:
        lines.append(f"- Email сервисного аккаунта: `{email}` — папке `Plaire` нужен доступ «Редактор» для него.")

    try:
        items = list_tree()
    except RuntimeError as e:
        lines += ["", "## ❌ Не удалось прочитать папку Plaire", "", "```", str(e), "```", "",
                  "Что проверить:",
                  "1. `GDRIVE_ROOT_ID` — это ID папки Plaire (часть ссылки после `/folders/`).",
                  "2. Папка Plaire открыта для email сервисного аккаунта (выше) с правами «Редактор».",
                  "3. В Google Cloud для проекта включён Google Drive API."]
        return "\n".join(lines), {"ok": False, "error": str(e)}, False

    top_dirs = sorted(i["Path"] for i in items if i["IsDir"] and "/" not in i["Path"])
    top_files = [i for i in items if not i["IsDir"] and "/" not in i["Path"]]
    folders = {d: summarize_folder(items, d) for d in top_dirs}
    for d in top_dirs:                          # подпапки 2-го уровня
        for sub in folders[d]["subdirs"]:
            p = f"{d}/{sub}"
            folders[p] = summarize_folder(items, p)

    # --- дерево ---
    lines += ["", "## Дерево `Plaire` (глубина 2)", "", "```", "Plaire/"]
    for f in sorted(top_files, key=lambda x: x["Name"]):
        lines.append(f"├── {f['Name']}  ({human(f.get('Size', 0))})")
    for d in top_dirs:
        s = folders[d]
        kinds = ", ".join(f"{k} {v}" for k, v in sorted(s["kinds"].items())) or "пусто"
        lines.append(f"├── {d}/   [файлов: {s['files']}, {human(s['bytes'])}; {kinds}]")
        for name in s["samples"][:5]:
            lines.append(f"│     · {name}")
        if s["files"] > 5:
            lines.append(f"│     · … ещё {s['files'] - 5}")
        for sub in s["subdirs"]:
            ss = folders[f"{d}/{sub}"]
            lines.append(f"│   ├── {sub}/   [файлов: {ss['files']}, {human(ss['bytes'])}]")
    lines.append("```")

    # --- папки из config.json ---
    report: dict = {"ok": True, "auth_mode": mode, "top_dirs": top_dirs, "folders": folders}
    found = {}
    lines += ["", "## Папки из config.json", "", "| ключ | в config | найдено на Диске |", "|---|---|---|"]
    for key in ("models3d", "sfx", "music", "done", "state"):
        path = find_dir(items, drive_cfg[key])
        found[key] = path
        mark = f"✅ `{path}`" if path else ("— будет создана при первой записи" if key in ("state", "done") else "❌ не найдена")
        lines.append(f"| {key} | `{drive_cfg[key]}` | {mark} |")
    report["found"] = found

    # --- угадываем исходники ---
    known = {p for p in found.values() if p}
    cands = sorted(
        ((d, folders[d]["kinds"].get("video", 0)) for d in top_dirs if d not in known),
        key=lambda x: -x[1])
    cands = [c for c in cands if c[1] > 0]
    src_cfg = drive_cfg.get("sources", "")
    src_found = None if src_cfg.startswith("<") else find_dir(items, src_cfg)
    lines += ["", "## Где исходники"]
    if src_found:
        lines.append(f"- В config указано `{src_cfg}` → найдено `{src_found}` "
                     f"({folders[src_found]['kinds'].get('video', 0)} видео).")
    elif cands:
        lines.append("- В config папка не указана. Кандидаты (по числу видео):")
        for d, n in cands[:5]:
            sub = folders[d]["subdirs"]
            extra = f", подпапок: {len(sub)}" if sub else ""
            lines.append(f"  - `{d}` — {n} видео{extra}")
    else:
        lines.append("- ❌ Не нашёл ни одной папки с видео на первом уровне.")
    report["source_candidates"] = cands

    # --- 3D ---
    lines += ["", "## 3D"]
    p3d = found.get("models3d")
    if p3d:
        r3d = check_3d(p3d)
        report["models3d"] = r3d
        if r3d["verdict"] == "ok":
            lines.append(f"- ✅ Найдено .glb: {len(r3d['glb'])}")
            lines += [f"  - `{g}`" for g in r3d["glb"][:10]]
        elif r3d["verdict"] == "not_models":
            lines.append("- ⚠️ В папке нет .glb. Там архивы или данные Polycam — это ещё не модели. "
                         "Нужны готовые `.glb` (в Polycam: Export → GLB).")
            lines += [f"  - `{z}`" for z in r3d["archives"][:10]]
            if r3d["polycam_markers"]:
                lines.append(f"  - признаки Polycam: {', '.join(r3d['polycam_markers'])}")
        else:
            lines.append("- Папка 3D пустая (для фазы 1 не нужна).")
    else:
        lines.append(f"- Папка `{drive_cfg['models3d']}` не найдена (для фазы 1 не нужна).")

    # --- имена ---
    warn_rows = []
    for it in items:
        if it["IsDir"] or "/" not in it["Path"]:
            w = name_warnings(it["Name"])
            if w:
                warn_rows.append((it["Path"], w))
    lines += ["", "## Имена с особыми символами"]
    if warn_rows:
        lines.append("Эти имена я буду писать в config.json **точно так**, как они на Диске:")
        for p, w in warn_rows[:20]:
            lines.append(f"- `{p}` — {', '.join(w)}")
    else:
        lines.append("- Нет. Все имена папок — обычные латинские буквы.")
    report["name_warnings"] = warn_rows

    gdocs = [i["Path"] for i in items if kind(i["Name"], i.get("MimeType", "")) == "google_doc"]
    if gdocs:
        lines += ["", f"- Документы Google (не файлы, монтаж их не читает): {len(gdocs)}"]

    # --- запись ---
    state_dir = found.get("state") or drive_cfg["state"]
    wt = write_test(state_dir)
    report["write_test"] = wt
    lines += ["", "## Проверка записи"]
    if wt["ok"]:
        lines.append(f"- ✅ Записал `{state_dir}/healthcheck.txt`. Писать в `Done` и `_autoedit_state` получится.")
    elif wt.get("no_quota"):
        lines += ["- ❌ Читать получается, **записывать нет**: у сервисного аккаунта нет своего места на Диске "
                  "(ошибка `storageQuotaExceeded`). Google не даёт сервисным аккаунтам создавать файлы "
                  "в обычном «Моём диске».",
                  "- Как исправить — README.md, раздел «Если запись не работает»: "
                  "либо общий диск (Google Workspace), либо вход через OAuth в статусе «In production»."]
    else:
        lines += [f"- ❌ Запись не прошла на шаге `{wt['step']}`:", "```", wt.get("error", ""), "```",
                  "- Проверьте, что у сервисного аккаунта права «Редактор», а не «Читатель»."]

    lines += ["", "## Что мне нужно от вас", "",
              "1. Какая папка — исходники (одна, всё вперемешку)?",
              "2. Верно ли найдены `3D`, `SFX`, `Music`, `Done`?",
              "3. Ответьте «ок» или поправьте — после этого перейду к шагу 2 (brand.json, валидатор, texts.json)."]
    all_ok = wt["ok"]
    return "\n".join(lines), report, all_ok


def main() -> int:
    cfg = json.loads((ROOT / "config.json").read_text())
    md, report, ok = build_report(cfg)
    WORK.mkdir(exist_ok=True)
    (WORK / "drive_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (WORK / "drive_check.md").write_text(md)
    print(md)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(md + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
