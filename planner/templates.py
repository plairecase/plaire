"""Шаблоны фазы 1: выбор планов и текста → план монтажа (props для Remotion + список нарезок + звуки).

Каждый шаблон — функция build_<id>(ctx) → Plan или None (если исходников не хватает,
тогда в Plan.missing пишется, что снять).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from qc.text_check import brand, check_item

LIFESTYLE = ("street", "hands", "pocket_bag", "indoor_lifestyle")


@dataclass
class Segment:
    file_id: str
    name: str
    shot_id: str
    src_start: float
    src_dur: float
    hdr: bool
    bbox: list
    out: str = ""                     # clips/cN.mp4 — заполняет media.prepare


@dataclass
class Plan:
    template: str
    style: str
    props: dict
    segments: list[Segment]
    sfx: list[dict] = field(default_factory=list)      # {"t": сек, "kind": whoosh|click|...}
    hook_id: str = ""
    duration_s: float = 0.0
    color: str = ""
    first_shot: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class Ctx:
    shots: list[dict]          # годные планы: shot + file (name, id, probe)
    texts: list[dict]
    rng: random.Random
    fps: int
    dissolve: int
    avoid_first: set = field(default_factory=set)
    avoid_color: str | None = None
    avoid_hooks: set = field(default_factory=set)


# ------------------------------------------------------------------ помощники
def frames(sec: float, fps: int) -> int:
    return int(round(sec * fps))


def hold_s(text: str) -> float:
    """Сколько держать экран: ≥ min_hold_s и не быстрее 3 слов в секунду, плюс время появления."""
    words = len(text.split())
    return round(max(brand()["text_rules"]["min_hold_s"], words / 3) + 0.5, 2)


def pick_hook(ctx: Ctx, style: str) -> dict:
    pool = [t for t in ctx.texts if t.get("style") == style and t.get("kind") == "hook"
            and t["id"] not in ctx.avoid_hooks and not check_item(t)]
    if not pool:
        raise RuntimeError(f"нет годных хуков стиля {style} в texts.json")
    return ctx.rng.choice(pool)


def weighted_order(ctx: Ctx, items: list[dict], key) -> list[dict]:
    """Сортировка по весу с долей случайности (чтобы ролики отличались день ото дня)."""
    return sorted(items, key=lambda s: -(key(s) + ctx.rng.random() * 3))


def text_color(shot: dict) -> str:
    return "ink" if (shot["shot"]["metrics"].get("luma_top") or 0) > 0.6 else "white"


def seg(s: dict, start: float, dur: float) -> Segment:
    return Segment(file_id=s["file"]["id"], name=s["file"]["name"], shot_id=s["shot"]["id"],
                   src_start=round(start, 3), src_dur=round(dur, 3), hdr=s["file"]["probe"]["hdr"],
                   bbox=s["shot"]["vision"]["case_bbox"])


def usable_len(s: dict, margin: float = 0.15) -> float:
    return s["shot"]["dur"] - 2 * margin


def bbox(s: dict) -> tuple[float, float]:
    """Верх и низ чехла в кадре (0…1)."""
    x, y, w, h = s["shot"]["vision"]["case_bbox"]
    return y, y + h


# хук премиума занимает y 300…~560 (2 строки) из 1920 → чехол должен начинаться ниже
HOOK_CLEAR = 0.30
# финал: вордмарк + eyebrow до y ≈ 450, ценник с y ≈ 1090 → чехол между ними
END_TOP, END_BOTTOM = 0.24, 0.56


def hook_fit(s: dict) -> float:
    top, _ = bbox(s)
    return 4.0 if top >= HOOK_CLEAR else (1.5 if top >= 0.24 else 0.0)


def end_fit(s: dict) -> float:
    top, bot = bbox(s)
    return 4.0 if (top >= END_TOP and bot <= END_BOTTOM) else (1.5 if bot <= 0.60 else 0.0)


# ------------------------------------------------------------------ p_one_line
def build_p_one_line(ctx: Ctx) -> Plan | None:
    """Премиум 7–12 с: одна сильная фраза на 2–3 героических планах + финал с ценником."""
    pool = [s for s in ctx.shots
            if (s["shot"]["vision"]["setting"] == "studio" or s["shot"]["vision"]["action"] == "detail_macro")]
    if len(pool) < 2:
        return None
    colors = {}
    for s in pool:
        colors.setdefault(s["shot"]["vision"]["color"], []).append(s)
    color_opts = [c for c, v in colors.items() if len(v) >= 2 and c in ("cognac", "black")]
    if ctx.avoid_color in color_opts and len(color_opts) > 1:
        color_opts.remove(ctx.avoid_color)
    color = ctx.rng.choice(color_opts) if color_opts else None
    cand = colors[color] if color else pool
    cand = weighted_order(ctx, cand, lambda s: s["shot"]["vision"]["hero_score"])

    hook = pick_hook(ctx, "premium")
    screens_txt = hook["screens"]
    hook_total = sum(hold_s(t) for t in screens_txt)
    end_s = 2.8

    def take(cands, need, score, chosen):
        best, best_v = None, -1e9
        used_files = {c["file"]["id"] for c in chosen}
        for s in cands:
            if s in chosen or usable_len(s) < min(need, 2.0):
                continue
            if not chosen and s["shot"]["id"] in ctx.avoid_first:
                continue
            v = score(s) + s["shot"]["vision"]["hero_score"] / 3 + ctx.rng.random() * 1.5
            v -= 3 if s["file"]["id"] in used_files else 0           # разные файлы, если можно
            v += min(usable_len(s), need) / need                     # хватает длины
            if v > best_v:
                best, best_v = s, v
        return best

    others = [s for s in pool if s not in cand]
    chosen = []
    first = take(cand, max(2.2, hook_total + 0.3), hook_fit, chosen)
    if not first:
        return None
    chosen.append(first)
    last = take(cand, end_s, end_fit, chosen) or take(others, end_s, end_fit, chosen)
    if not last:
        return None
    middle = take(cand, 2.2, lambda s: 0, chosen + [last]) or take(others, 2.2, lambda s: 0, chosen + [last])
    if middle:
        chosen.append(middle)
    chosen.append(last)
    want = [max(2.2, hook_total + 0.3)] + ([2.2] if middle else []) + [end_s]
    # добрать длительность до ≥ 7.5 с за счёт более длинных планов
    durs = [min(n, usable_len(s)) for s, n in zip(chosen, want)]
    short = 7.5 - sum(durs)
    for i in range(len(durs)):
        if short <= 0:
            break
        add = min(short, usable_len(chosen[i]) - durs[i], 4.5 - durs[i])
        if add > 0:
            durs[i] += add
            short -= add
    if sum(durs) < 6.8:
        return None

    fps, dis = ctx.fps, ctx.dissolve
    segments, clips, t = [], [], 0.0
    for i, (s, d) in enumerate(zip(chosen, durs)):
        overlap = dis / fps if i > 0 else 0.0
        mid = s["shot"]["start"] + s["shot"]["dur"] / 2
        src_start = max(s["shot"]["start"] + 0.15, min(mid - (d + overlap) / 2,
                                                       s["shot"]["end"] - 0.15 - d - overlap))
        segments.append(seg(s, src_start, d + overlap))
        clips.append({"src": "", "from": frames(t - overlap, fps), "durationInFrames": frames(d + overlap, fps),
                      "pushIn": brand()["motion"]["push_in_scale"], "dissolveInFrames": dis if i else 0})
        t += d
    total = round(t, 3)
    end_from = total - durs[-1]

    screens, cursor = [], 0.0
    for i, txt in enumerate(screens_txt):
        h = hold_s(txt)
        if cursor + h > end_from - 0.2:                     # не наезжать на финал
            h = max(1.6, end_from - 0.2 - cursor)
        screens.append({"from": frames(cursor, fps), "durationInFrames": frames(h, fps), "text": txt,
                        "eyebrow": hook.get("eyebrow") if i == 0 else None, "animateIn": i > 0})
        cursor += h
    p = brand()["product"]
    _, case_bot = bbox(chosen[-1])
    tag_top = int(min(1130, max(1090, case_bot * 1920 + 40)))   # ниже чехла, но выше y 1248
    end = {"from": frames(end_from, fps), "durationInFrames": frames(total, fps) - frames(end_from, fps),
           "color": text_color(chosen[-1]), "eyebrow": "The condom case", "price": p["price"],
           "site": p["site"].upper(), "shipping": p["shipping"], "tagTop": tag_top}

    sfx, last = [], -9.0
    for i in range(1, len(durs)):
        tt = round(sum(durs[:i]) - dis / fps / 2 - 0.15, 2)
        if tt - last >= 1.5:
            sfx.append({"t": max(0.0, tt), "kind": "whoosh", "gain_db": -6})
            last = tt
    tag_t = round(end_from + 0.3, 2)
    if tag_t - last >= 1.5:
        sfx.append({"t": tag_t, "kind": "click", "gain_db": -8})

    props = {"template": "p_one_line", "style": "premium", "fps": fps, "durationInFrames": frames(total, fps),
             "clips": clips, "screens": screens, "textColor": text_color(chosen[0]), "endFrame": end}
    return Plan("p_one_line", "premium", props, segments, sfx, hook["id"], total,
                color or chosen[0]["shot"]["vision"]["color"], chosen[0]["shot"]["id"])


# ------------------------------------------------------------------ n_statement
CUTS = [0.5, 0.7, 0.8, 1.0, 1.0, 1.2]


def build_n_statement(ctx: Ctx) -> Plan | None:
    """Нативный 7–10 с: одна фраза поверх жизни, быстрые прямые склейки 0.4–1.2 с, финал — живой кадр."""
    pool = [s for s in ctx.shots if s["shot"]["vision"]["setting"] in LIFESTYLE]
    # белый текст на светлом кадре не читается (дизайн-система): светлый верх кадра — мимо
    dark = [s for s in pool if (s["shot"]["metrics"].get("luma_top") or 0) <= 0.62]
    if len(dark) >= 3:
        pool = dark
    if len(pool) < 3:
        return None
    pool = weighted_order(ctx, pool, lambda s: s["shot"]["vision"]["hero_score"]
                          + (3 if "native" in s["shot"]["vision"]["style_fit"] else 0)
                          + (1 if s["shot"]["vision"]["color"] != ctx.avoid_color else 0))
    first = next((s for s in pool if s["shot"]["id"] not in ctx.avoid_first), pool[0])
    rest = [s for s in pool if s is not first]
    # финал: самый «чистый» план с чехлом
    final = max(rest, key=lambda s: (s["shot"]["vision"]["case_visible_ratio"], s["shot"]["vision"]["hero_score"]))
    middle = [s for s in rest if s is not final][:4]
    order = [first] + middle
    if len(order) < 2:
        return None

    hook = pick_hook(ctx, "native")
    target = ctx.rng.uniform(7.5, 9.0)
    final_d = min(1.8, usable_len(final))
    pointer = {s["shot"]["id"]: s["shot"]["start"] + 0.15 for s in order}
    fps = ctx.fps
    segments, clips, t, i, guard = [], [], 0.0, 0, 0
    while t < target - final_d - 0.3 and guard < 40:
        guard += 1
        s = order[i % len(order)]
        i += 1
        d = ctx.rng.choice(CUTS)
        p0 = pointer[s["shot"]["id"]]
        if p0 + d > s["shot"]["end"] - 0.15:
            if all(pointer[x["shot"]["id"]] + 0.5 > x["shot"]["end"] - 0.15 for x in order):
                break
            continue
        d = round(math.floor(d * fps) / fps, 3)
        segments.append(seg(s, p0, d))
        clips.append({"src": "", "from": frames(t, fps), "durationInFrames": frames(d, fps)})
        pointer[s["shot"]["id"]] = p0 + d
        t += d
    if t < 4.0:
        return None
    fs = final["shot"]
    segments.append(seg(final, max(fs["start"] + 0.15, fs["start"] + fs["dur"] / 2 - final_d / 2), final_d))
    clips.append({"src": "", "from": frames(t, fps), "durationInFrames": frames(final_d, fps)})
    t += final_d
    total = round(t, 3)

    txts = hook["screens"]
    screens = []
    if len(txts) == 1:
        screens.append({"from": 0, "durationInFrames": frames(total, fps), "text": txts[0], "animateIn": False})
    else:
        half = frames(total / 2, fps)
        screens.append({"from": 0, "durationInFrames": half, "text": txts[0], "animateIn": False})
        screens.append({"from": half, "durationInFrames": frames(total, fps) - half, "text": txts[1],
                        "animateIn": False})
    props = {"template": "n_statement", "style": "native", "fps": fps, "durationInFrames": frames(total, fps),
             "clips": clips, "screens": screens, "textColor": "white", "endFrame": None}
    return Plan("n_statement", "native", props, segments, [], hook["id"], total,
                first["shot"]["vision"]["color"], first["shot"]["id"])


BUILDERS = {"p_one_line": build_p_one_line, "n_statement": build_n_statement}
