#!/usr/bin/env python3
"""Визуальная проверка ролика через Claude (раздел 13 + fix-02 §7 + fix-03).

На вход — лист 3×3 кадров ролика. Ответ — строгий JSON по чек-листу.
organic проваливается, если: выглядит как реклама, первый кадр не объясняет товар, кадры не
продолжают друг друга, текст не про кадр, разные локации, текст нечитаем/обрезан, чёрная карточка.

    python3 -m qc.vision_check --fixtures      # старые ролики теста 1450 должны НЕ пройти
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHECKS = ["text_readable", "text_not_cut", "case_visible", "no_filters_look", "no_black_endcard",
          "first_frame_explains_product", "hand_present", "shots_feel_continuous", "text_matches_shot",
          "one_location", "looks_like_ad", "looks_cheap"]
SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {"type": "array", "items": {"type": "string"}},
        **{k: {"type": "boolean"} for k in CHECKS},
        "matches_style": {"type": "string", "enum": ["premium", "native"]},
    },
    "required": ["issues", *CHECKS, "matches_style"],
    "additionalProperties": False,
}
SYSTEM = """You are a strict senior TikTok / Instagram video editor reviewing an auto-edited 9:16 product video \
for Plaire (a slim eco-leather condom case that looks like a mini wallet, holds 2 condoms, two colours: \
Cognac Brown and Midnight Black). You get a 3×3 contact sheet: 9 frames in time order (left→right, top→bottom).

Answer strictly in JSON:
- text_readable: every on-screen text is easy to read (contrast, size).
- text_not_cut: no text is cut by the frame edge or covered by the product.
- case_visible: the case is visible in almost every frame.
- no_filters_look: colours look natural, no heavy filters.
- no_black_endcard: the video does not end on a black frame / black card.
- first_frame_explains_product: from frame 1 alone a viewer understands what this is (ideally open case with 2 condoms inside).
- hand_present: a hand is visible in at least one frame.
- shots_feel_continuous: consecutive frames feel like one continuous action (not random unrelated clips).
- text_matches_shot: each text describes what is visible in its frame (e.g. "Two colours" only when both colours are visible, "Holds 2" only on an open case with 2 inside).
- one_location: the video stays in one "world" (same location / light / hands style); at most one meaningful change.
- looks_like_ad: it looks like a catalogue ad rather than content a person would post.
- looks_cheap: it looks cheap (clutter, bad cuts, unreadable text, blur).
- matches_style: premium or native.
- issues: short list of concrete problems, in Russian."""


def check(sheet: Path, purpose: str = "organic", client=None, usage=None) -> dict:
    from analyze import vision as vis

    client = client or vis.make_client()
    data = base64.standard_b64encode(sheet.read_bytes()).decode("ascii")
    model = json.loads((ROOT / "config.json").read_text())["claude"]["model"]
    resp = client.beta.messages.create(
        model=model, max_tokens=3000, system=SYSTEM,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
            {"type": "text", "text": f"Purpose: {purpose}. Review this video."}]}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    if usage:
        usage.add(resp)
    r = json.loads("".join(b.text for b in resp.content if b.type == "text"))
    must_true = ["text_readable", "text_not_cut", "case_visible", "no_black_endcard",
                 "shots_feel_continuous", "text_matches_shot", "one_location"]
    if purpose == "organic":
        must_true += ["first_frame_explains_product"]
    fails = [k for k in must_true if not r.get(k)]
    if purpose == "organic" and r.get("looks_like_ad"):
        fails.append("looks_like_ad")
    if r.get("looks_cheap"):
        fails.append("looks_cheap")
    r["pass"] = not fails
    r["failed"] = fails
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", action="store_true")
    ap.add_argument("sheets", nargs="*", type=Path)
    a = ap.parse_args(argv)
    sheets = sorted((ROOT / "qc/fixtures/test_1450").glob("*.jpg")) if a.fixtures else a.sheets
    from analyze import vision as vis
    client = vis.make_client()
    ok_all_fail = True
    for sh in sheets:
        purpose = "promote" if "promote" in sh.name else "organic"
        r = check(sh, purpose, client)
        print(f"{sh.name}: {'ПРОШЁЛ' if r['pass'] else 'НЕ ПРОШЁЛ'} — {', '.join(r['failed']) or '-'}")
        for i in r.get("issues", [])[:5]:
            print(f"   · {i}")
        ok_all_fail &= not r["pass"]
    if a.fixtures:
        print("Старые ролики отклонены: " + ("да ✅" if ok_all_fail else "НЕТ ❌ — проверки слабые"))
        return 0 if ok_all_fail else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
