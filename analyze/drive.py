"""Работа с Google Диском через rclone (remote `gdrive:`, корень = папка Plaire).

Пишем только в папку состояния (_autoedit_state) и Done. Исходники, 3D, SFX и
Music только читаем.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REMOTE = "gdrive:"
WRITABLE = ("_autoedit_state", "Done")


class DriveError(RuntimeError):
    pass


# сеть: таймауты и повторы, чтобы зависание Диска не съедало весь запуск
NET = ["--timeout", "60s", "--contimeout", "20s", "--low-level-retries", "5", "--retries", "3"]


def _run(*args: str, input_text: str | None = None, timeout: int = 900) -> str:
    try:
        res = subprocess.run(["rclone", *args, *NET], input=input_text, capture_output=True, text=True,
                             timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise DriveError(f"rclone {args[0]}: нет ответа {timeout} с") from e
    if res.returncode != 0:
        raise DriveError(f"rclone {args[0]}: {res.stderr.strip()[-800:]}")
    return res.stdout


def list_files(folder: str) -> list[dict]:
    """Файлы папки (без подпапок): Name, Size, ModTime, ID, MimeType."""
    out = _run("lsjson", f"{REMOTE}{folder}", "--files-only", "--fast-list")
    return json.loads(out or "[]")


def download(folder: str, name: str, dest: Path, size: int | None = None, file_id: str | None = None) -> Path:
    """Скачать файл; если в кеше уже лежит файл того же размера — не качать.
    Сначала по пути, при ошибке — по ID файла на Диске (не зависит от пробелов и спецсимволов в имени)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if size and dest.exists() and dest.stat().st_size == size:
        return dest
    try:
        _run("copyto", f"{REMOTE}{folder}/{name}", str(dest))
        return dest
    except DriveError:
        if not file_id:
            raise
    tmp = dest.parent / f".id_{file_id}"
    tmp.mkdir(exist_ok=True)
    _run("backend", "copyid", REMOTE, file_id, str(tmp) + "/")
    got = next(tmp.iterdir(), None)
    if not got:
        raise DriveError(f"файл {name} (ID {file_id}) не скачался")
    got.replace(dest)
    tmp.rmdir()
    return dest


def _check_writable(path: str) -> None:
    if not path.split("/")[0] in WRITABLE:
        raise DriveError(f"запись в «{path}» запрещена: можно только в {', '.join(WRITABLE)}")


def read_json(path: str, default):
    res = subprocess.run(["rclone", "cat", f"{REMOTE}{path}", *NET], capture_output=True, text=True, timeout=300)
    if res.returncode != 0:
        if "not found" in res.stderr.lower() or "doesn't exist" in res.stderr.lower():
            return default
        raise DriveError(f"rclone cat {path}: {res.stderr.strip()[-800:]}")
    return json.loads(res.stdout) if res.stdout.strip() else default


def write_json(path: str, data) -> None:
    _check_writable(path)
    _run("rcat", f"{REMOTE}{path}", input_text=json.dumps(data, ensure_ascii=False, indent=1))


def upload(local: Path, path: str) -> None:
    _check_writable(path)
    _run("copyto", str(local), f"{REMOTE}{path}")
