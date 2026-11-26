#!/usr/bin/env python3
"""Валидатор текстов Plaire: экранные тексты, подписи, хэштеги.

Все правила берутся из brand.json, здесь их нет.
Без прохождения валидатора текст не используется.

Использование:
    python3 -m qc.text_check            # проверить весь texts.json
    python3 -m qc.text_check "текст"    # проверить один экран

В коде:
    from qc.text_check import check_screen, check_item, check_caption
    errors = check_screen("Holds 2. Feels like nothing.")   # [] = прошёл
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "a": 1}


@lru_cache(maxsize=1)
def brand() -> dict:
    return json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- помощники
def words(text: str) -> list[str]:
    """Слова экрана: токены, где есть хотя бы буква или цифра (">" и "·" не считаются)."""
    return [t for t in text.split() if any(ch.isalnum() for ch in t)]


def _phrase_re(phrase: str) -> re.Pattern:
    p = re.escape(phrase.lower())
    return re.compile(rf"(?<![a-z0-9]){p}(?![a-z0-9])")


def _has_emoji(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF or cp == 0xFE0F:
            return True
        if unicodedata.category(ch) == "So" and ch not in "©®™":
            return True
    return False


def split_phrase(text: str, max_words: int | None = None) -> list[str]:
    """Делит фразу длиннее лимита на экраны, по возможности по знакам препинания."""
    max_words = max_words or brand()["text_rules"]["max_words_per_screen"]
    toks = text.split()
    if len(words(text)) <= max_words:
        return [text]
    screens, cur = [], []
    for i, t in enumerate(toks):
        cur.append(t)
        n = len(words(" ".join(cur)))
        rest = len(words(" ".join(toks[i + 1:])))
        punct_break = t[-1] in ".,:;—" and n >= 2
        if n >= max_words or (punct_break and rest and rest <= max_words):
            screens.append(" ".join(cur))
            cur = []
    if cur:
        screens.append(" ".join(cur))
    return screens


# ---------------------------------------------------------------- правила
def _common_errors(text: str) -> list[str]:
    """Правила для любого текста: экран, подпись, слайд."""
    b, p = brand(), brand()["product"]
    low = text.lower()
    errs: list[str] = []

    for ph in b["forbidden_phrases"]:
        if _phrase_re(ph).search(low):
            errs.append(f"запрещённая фраза «{ph}»")
    for ph in b["unverified_claims"]:
        if _phrase_re(ph).search(low):
            errs.append(f"непроверенное утверждение «{ph}» (нет в фактах brand.json)")

    # кожа — только эко-кожа
    for m in re.finditer(r"(?<![a-z])leather", low):
        before = low[max(0, m.start() - 4):m.start()]
        if before not in ("eco-", "eco "):
            errs.append("«leather» без «eco-»: чехол из эко-кожи")
            break

    # цена: только €29
    price_num = re.sub(r"\D", "", p["price"])
    for m in re.finditer(r"(?:€|eur\s?)\s?(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s?(?:€|eur\b|euro)", low):
        val = m.group(1) or m.group(2)
        if val != price_num:
            errs.append(f"цена «{m.group(0).strip()}» не совпадает с {p['price']}")

    # возврат: только 14 дней
    for m in re.finditer(r"(\d+)[\s-]?days?\b", low):
        if int(m.group(1)) != p["returns_days"]:
            errs.append(f"«{m.group(0)}»: в brand.json возврат {p['returns_days']} дней")

    # вместимость: только 2
    for m in re.finditer(r"\bholds?\s+(\w+)", low):
        n = m.group(1)
        val = int(n) if n.isdigit() else NUM_WORDS.get(n)
        if val is not None and val != 2:
            errs.append(f"«{m.group(0)}»: чехол вмещает 2")

    # доставка: дословно как в brand.json
    if "shipping" in low or "delivery" in low:
        allowed = [p["shipping"].lower(), p["shipping_short"].lower()]
        if not any(a in low for a in allowed):
            errs.append(f"доставка не дословно: нужно «{p['shipping']}» или «{p['shipping_short']}»")
    if "delivery" in low and "shipping" not in low:
        errs.append("слово «delivery»: пишем только «shipping» как в brand.json")

    # лишние числа (не цена, не 2, не 14)
    ok_nums = {price_num, "2", str(p["returns_days"])}
    for m in re.finditer(r"(?<![#\w])(\d+)(?![\w])", low):
        if m.group(1) not in ok_nums:
            errs.append(f"число «{m.group(1)}» не из фактов brand.json")
    if "%" in text:
        errs.append("проценты не используем")

    if _has_emoji(text):
        errs.append("эмодзи и символы-стикеры запрещены")
    if b["text_rules"].get("no_exclamation") and "!" in text:
        errs.append("восклицательный знак запрещён")
    return errs


def check_screen(text: str, role: str = "screen") -> list[str]:
    """Один экран текста в ролике / на слайде. role: screen | eyebrow | callout | price | fine."""
    b = brand()
    errs = _common_errors(text)
    limit = b["text_rules"]["max_words_per_screen"]
    n = len(words(text))
    if n == 0:
        errs.append("пустой экран")
    if role != "eyebrow" and n > limit:
        errs.append(f"{n} слов на экране, максимум {limit}")
    if role != "eyebrow":
        allowed_caps = set(b["text_rules"]["allowed_caps_words"])
        for w in words(text):
            core = w.strip(".,:;—>·|•")
            letters = [c for c in core if c.isalpha()]
            if len(letters) >= 3 and core.isupper() and core not in allowed_caps:
                errs.append(f"КАПС «{core}»: только sentence case (заглавными — только eyebrow)")
    if "#" in text:
        errs.append("хэштеги на экране не нужны")
    return errs


def check_item(item: dict) -> list[str]:
    """Запись из texts.json: все экраны + eyebrow."""
    errs = []
    if item.get("style") not in ("premium", "native"):
        errs.append("style должен быть premium или native")
    screens = item.get("screens") or []
    if not screens:
        errs.append("нет screens")
    if item.get("style") == "native" and len(screens) > 2:
        errs.append("нативный стиль: одна фраза или две подряд")
    for i, s in enumerate(screens, 1):
        errs += [f"экран {i}: {e}" for e in check_screen(s)]
    if item.get("eyebrow"):
        if item.get("style") == "native":
            errs.append("в нативном стиле eyebrow нет")
        errs += [f"eyebrow: {e}" for e in check_screen(item["eyebrow"], role="eyebrow")]
    return errs


def has_keyword(text: str) -> bool:
    return brand()["product"]["keyword"].lower() in text.lower()


def check_caption(text: str, platform: str, screen_texts: list[str] | None = None) -> list[str]:
    """Подпись TikTok / Instagram. screen_texts — тексты на экране этого ролика."""
    b = brand()
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("[sound:"))
    errs = _common_errors(body)
    tags = re.findall(r"#\w+", body.lower())
    for t in tags:
        if t in b["forbidden_hashtags"]:
            errs.append(f"хэштег {t} не используем")
    if not 3 <= len(tags) <= 5:
        errs.append(f"хэштегов {len(tags)}, нужно 3–5")
    first = next((l for l in body.splitlines() if l.strip()), "")
    if not has_keyword(first) and not any(has_keyword(s) for s in (screen_texts or [])):
        errs.append(f"«{b['product']['keyword']}» нет ни на экране, ни в первой строке подписи")
    if platform == "tiktok":
        if "#condomcase" not in tags or "#plaire" not in tags:
            errs.append("TikTok: нужны #condomcase и #plaire")
    elif platform == "instagram":
        if b["product"]["site"] not in body.lower():
            errs.append(f"Instagram: нужна строка «Link in bio — {b['product']['site']}»")
    else:
        errs.append(f"неизвестная платформа {platform}")
    return errs


# ---------------------------------------------------------------- банк texts.json
def check_bank(path: Path | None = None, min_per_style: int = 15) -> list[str]:
    path = path or ROOT / "texts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    errs, ids = [], set()
    counts = {"premium": 0, "native": 0}
    for it in data["items"]:
        iid = it.get("id", "?")
        if iid in ids:
            errs.append(f"{iid}: повтор id")
        ids.add(iid)
        errs += [f"{iid}: {e}" for e in check_item(it)]
        if it.get("kind") == "hook" and it.get("style") in counts:
            counts[it["style"]] += 1
    for style, n in counts.items():
        if n < min_per_style:
            errs.append(f"хуков стиля {style}: {n}, нужно минимум {min_per_style}")
    for c in data.get("caption_ctas", []):
        errs += [f"{c.get('id', '?')}: {e}" for e in _common_errors(c.get("text", ""))]
    return errs


def main(argv: list[str]) -> int:
    if argv:
        errs = check_screen(" ".join(argv))
        print("✅ прошёл" if not errs else "\n".join(f"❌ {e}" for e in errs))
        return 1 if errs else 0
    errs = check_bank()
    data = json.loads((ROOT / "texts.json").read_text(encoding="utf-8"))
    n = len(data["items"])
    if errs:
        print(f"❌ texts.json: {len(errs)} ошибок")
        print("\n".join(f"  - {e}" for e in errs))
        return 1
    print(f"✅ texts.json: {n} текстов, все прошли проверку")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
