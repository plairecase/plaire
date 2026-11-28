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
    stabilize: bool = False           # ручная/дрожащая съёмка → стабилизация при нарезке
    reverse: bool = False             # проиграть задом наперёд (луп: последний кадр = первый)
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
    purpose: str = "organic"           # organic | promote (fix-02)
    bpm: float = 0.0
    checks: dict = field(default_factory=dict)
    missing: list = field(default_factory=list)
    track: object = None               # audio.music.Track
    track_path: object = None


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
    beats: list | None = None  # доли музыки от начала ролика, с (None — сетка 120 BPM)
    models: dict = field(default_factory=dict)   # 3D: цвет → путь в remotion/public (models/cognac.glb)


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


SHAKY = 0.0015      # доля ширины кадра: выше — заметная тряска


def seg(s: dict, start: float, dur: float) -> Segment:
    v, m = s["shot"]["vision"], s["shot"]["metrics"]
    stab = v["setting"] in LIFESTYLE or (m.get("shake") or 0) > SHAKY
    return Segment(file_id=s["file"]["id"], name=s["file"]["name"], shot_id=s["shot"]["id"],
                   src_start=round(start, 3), src_dur=round(dur, 3), hdr=s["file"]["probe"]["hdr"],
                   bbox=v["case_bbox"], stabilize=stab)


def beat_grid(ctx: Ctx) -> list[float]:
    return ctx.beats or [round(i * 0.5, 3) for i in range(60)]           # без музыки — 120 BPM


def snap(t: float, ctx: Ctx, tol: float = 0.35) -> float:
    """Ближайшая доля музыки, если она рядом."""
    near = min(beat_grid(ctx), key=lambda b: abs(b - t))
    return near if abs(near - t) <= tol else t


TR_FRAMES = 7       # длительность энергичного перехода, кадров


def usable_len(s: dict, margin: float = 0.15) -> float:
    return s["shot"]["dur"] - 2 * margin


MEASURE = None          # функция (shot) → (верх, низ) по реальным кадрам; задаёт make_videos


def bbox(s: dict) -> tuple[float, float]:
    """Верх и низ предмета в кадре (0…1): замер по кадрам плана, иначе рамка от разметки."""
    if MEASURE is not None:
        m = MEASURE(s)
        if m:
            return m
    x, y, w, h = s["shot"]["vision"]["case_bbox"]
    return y, y + h


# хук премиума занимает y 300…~560 (2 строки) из 1920 → чехол должен начинаться ниже
HOOK_CLEAR = 0.30
# финал: вордмарк + eyebrow до y ≈ 450, ценник с y ≈ 1090 → чехол между ними
END_TOP, END_BOTTOM = 0.25, 0.53


def hook_fit(s: dict) -> float:
    top, _ = bbox(s)
    return 4.0 if top >= HOOK_CLEAR else (1.5 if top >= 0.24 else 0.0)


def end_fit(s: dict) -> float:
    """Финал: чехол компактный и между вордмарком и ценником. Открытый/крутящийся чехол
    меняет размер внутри плана, поэтому предпочитаем статичный или медленный поворот."""
    top, bot = bbox(s)
    if top >= END_TOP and bot <= END_BOTTOM:
        v = 4.0
    elif top >= 0.33:                     # чехол в нижней части — ценник встанет сверху, под вордмарком
        v = 1.0
    else:
        v = -6.0                          # вордмарк или ценник закроют чехол
    act = s["shot"]["vision"]["action"]
    v += 1.0 if act in ("static", "rotate", "reveal") else (-2.0 if act in ("open", "close", "insert") else 0)
    return v


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
    # финал: компактный чехол важнее совпадения цвета (вордмарк и ценник не должны его закрывать)
    same = {id(x) for x in cand}
    last = take([x for x in cand + others if end_fit(x) > 0], end_s,
                lambda x: end_fit(x) + (2.0 if id(x) in same else 0.0), chosen) \
        or take(cand, end_s, end_fit, chosen)
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

    fps = ctx.fps
    # склейки — в долю музыки
    bounds, acc = [], 0.0
    for d in durs[:-1]:
        acc += d
        bounds.append(snap(acc, ctx))
    edges = [0.0] + bounds
    snapped = [b - a for a, b in zip(edges, bounds + [edges[-1] + durs[-1]])]
    if all(1.6 <= d <= usable_len(s) for d, s in zip(snapped, chosen)):
        durs = snapped                                   # иначе оставляем как было
    kinds = ["zoom", "push", "whip"]
    ctx.rng.shuffle(kinds)
    trans = [{"type": kinds[i % len(kinds)], "frames": TR_FRAMES} for i in range(len(durs) - 1)]
    segments, clips, t = [], [], 0.0
    for i, (s, d) in enumerate(zip(chosen, durs)):
        overlap = TR_FRAMES / fps if i > 0 else 0.0
        mid = s["shot"]["start"] + s["shot"]["dur"] / 2
        src_start = max(s["shot"]["start"] + 0.15, min(mid - (d + overlap) / 2,
                                                       s["shot"]["end"] - 0.15 - d - overlap))
        segments.append(seg(s, src_start, d + overlap))
        clip = {"src": "", "from": frames(t - overlap, fps), "durationInFrames": frames(d + overlap, fps),
                "pushIn": brand()["motion"]["push_in_scale"]}
        if i > 0:
            clip["transitionIn"] = trans[i - 1]
        if i < len(durs) - 1:
            clip["transitionOut"] = trans[i]
        clips.append(clip)
        t += d
    total = round(t, 3)
    end_from = total - durs[-1]

    screens, cursor = [], 0.0
    for i, txt in enumerate(screens_txt):
        h = hold_s(txt)
        if cursor + h > end_from - 0.2:                     # не наезжать на финал
            h = max(1.6, end_from - 0.2 - cursor)
        screens.append({"from": frames(cursor, fps), "durationInFrames": frames(h, fps), "text": txt,
                        "eyebrow": hook.get("eyebrow") if i == 0 else None, "animateIn": True})
        cursor += h
    p = brand()["product"]
    case_top, case_bot = bbox(chosen[-1])
    if case_bot * 1920 + 40 <= 1130:
        tag_top = int(max(1090, case_bot * 1920 + 40))          # ниже чехла, выше y 1248
    elif case_top >= 0.33:
        tag_top = 500                                           # чехол внизу: ценник под вордмарком
    else:
        tag_top = 1130
    end = {"from": frames(end_from, fps), "durationInFrames": frames(total, fps) - frames(end_from, fps),
           "color": text_color(chosen[-1]), "eyebrow": "The condom case", "price": p["price"],
           "site": p["site"].upper(), "shipping": p["shipping"], "tagTop": tag_top}

    sfx, last = [], -9.0
    for i in range(1, len(durs)):
        tt = round(sum(durs[:i]) - TR_FRAMES / fps - 0.1, 2)          # свист чуть раньше склейки
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
    """Нативный 7–10 с: одна фраза поверх жизни, склейки 0.4–1.2 с в долю музыки с толчками
    и одним свайпом (правка владельца 27.11.2026), финал — живой кадр."""
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
    final = max(rest, key=lambda s: (s["shot"]["vision"]["setting"] in ("street", "pocket_bag", "indoor_lifestyle"),
                                      s["shot"]["vision"]["case_visible_ratio"], s["shot"]["vision"]["hero_score"]))
    middle = [s for s in rest if s is not final][:4]
    order = [first] + middle
    if len(order) < 2:
        return None

    hook = pick_hook(ctx, "native")
    target = ctx.rng.uniform(7.5, 9.0)
    final_d = min(1.8, usable_len(final))
    grid = beat_grid(ctx)
    ib = sorted(b - a for a, b in zip(grid, grid[1:]))[len(grid) // 2] if len(grid) > 2 else 0.5
    lengths = [k * ib for k in (1, 2, 3) if 0.4 <= k * ib <= 1.25] or [0.5, 1.0]
    pointer = {s["shot"]["id"]: s["shot"]["start"] + 0.15 for s in order}
    fps = ctx.fps
    segments, clips, sfx, t, i, guard, whip_done = [], [], [], 0.0, 0, 0, False
    while t < target - final_d - 0.3 and guard < 40:
        guard += 1
        s = order[i % len(order)]
        i += 1
        d = ctx.rng.choice(lengths)
        p0 = pointer[s["shot"]["id"]]
        if p0 + d > s["shot"]["end"] - 0.15:
            if all(pointer[x["shot"]["id"]] + 0.5 > x["shot"]["end"] - 0.15 for x in order):
                break
            continue
        d = round(math.floor(d * fps) / fps, 3)
        clip = {"src": "", "from": frames(t, fps), "durationInFrames": frames(d, fps)}
        start = p0
        if clips:
            ov = 5 / fps
            if not whip_done and t > 2.5 and p0 - ov >= s["shot"]["start"] + 0.05:
                clip = {"src": "", "from": frames(t - ov, fps), "durationInFrames": frames(d + ov, fps),
                        "transitionIn": {"type": "whip", "frames": 5}}
                clips[-1]["transitionOut"] = {"type": "whip", "frames": 5}
                start, whip_done = p0 - ov, True
                sfx.append({"t": round(max(0.0, t - ov - 0.1), 2), "kind": "whoosh", "gain_db": -4})
            elif ctx.rng.random() < 0.6:
                clip["transitionIn"] = {"type": "punch", "frames": 5}
        segments.append(seg(s, start, d + (p0 - start)))
        clips.append(clip)
        pointer[s["shot"]["id"]] = p0 + d
        t += d
    if t < 4.0:
        return None
    fs = final["shot"]
    segments.append(seg(final, max(fs["start"] + 0.15, fs["start"] + fs["dur"] / 2 - final_d / 2), final_d))
    clips.append({"src": "", "from": frames(t, fps), "durationInFrames": frames(final_d, fps),
                  "transitionIn": {"type": "punch", "frames": 5}})
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
    return Plan("n_statement", "native", props, segments, sfx, hook["id"], total,
                first["shot"]["vision"]["color"], first["shot"]["id"])


# ------------------------------------------------------------------ p_organic (fix-02, только премиум)
OPENING = ("open", "close", "insert")


def grid_from(ctx: Ctx, bpm_fallback: float) -> tuple[float, float]:
    """(первая доля, длительность доли) — из трека, иначе из config.beat_grid_bpm."""
    if ctx.beats and len(ctx.beats) > 4:
        diffs = sorted(b - a for a, b in zip(ctx.beats, ctx.beats[1:]))
        ib = diffs[len(diffs) // 2]
        return 0.0, ib
    return 0.0, 60.0 / bpm_fallback


def pick_second(ctx: Ctx, action: str, color_pair: bool) -> dict | None:
    want = "colours" if color_pair else {"open": "open", "insert": "open", "close": "close",
                                        "static": "closed", "rotate": "closed"}.get(action, "any")
    pool = [t for t in ctx.texts if t.get("style") == "premium" and t.get("kind") == "second"
            and not check_item(t) and t["id"] not in ctx.avoid_hooks]
    exact = [t for t in pool if t.get("action") == want]
    anyp = [t for t in pool if t.get("action") == "any"]
    return ctx.rng.choice(exact or anyp or pool) if pool else None


def build_p_organic(ctx: Ctx, purpose: str = "organic", bpm_fallback: float = 120.0) -> Plan | None:
    """Премиум под ленту (fix-02 §5): первый план — действие, удар-наезд на доле 1, склейки на долях,
    длина — целое число тактов (7–10 с), хук виден с кадра 0, ≤ 3 текстов, концовка — бесшовный луп.
    promote: те же планы без лупа + карточка с ценой (≤ 20 % длины)."""
    fps = ctx.fps
    pool = [s for s in ctx.shots if s["shot"]["vision"]["setting"] in ("studio", "hands", "packaging")
            or "premium" in s["shot"]["vision"]["style_fit"]]
    if len(pool) < 3:
        return None
    _, ib = grid_from(ctx, bpm_fallback)
    bar = 4 * ib
    bars = next((n for n in (4, 5, 3) if 7.0 <= n * bar <= 10.0), 4)
    beats_total = bars * 4
    # раскладка по долям (fix-02): первая склейка ≤ 1.5 с, ни один план > 2 с (кроме лупа)
    first_b = 3 if 3 * ib <= 1.5 + 1e-6 else 2
    max_b = max(2, int(2.0 / ib + 1e-6))
    loop_b = (3 if 3 * ib <= 2.0 + 1e-6 else 2) if purpose == "organic" else 0
    mid_total = beats_total - first_b - loop_b
    k = math.ceil(mid_total / max_b)
    mids = [mid_total // k + (1 if i < mid_total % k else 0) for i in range(k)]
    slots = [first_b] + mids
    durs = [n * ib for n in slots]

    def fits(s, d):
        return usable_len(s) >= d

    def score(s, extra=0.0):
        return s["shot"]["vision"]["hero_score"] / 3 + ctx.rng.random() * 1.5 + extra

    used = []

    def take(cands, d, key):
        best, bv = None, -1e9
        for s in cands:
            if s in used or not fits(s, d):
                continue
            v = key(s) - (3 if any(u["file"]["id"] == s["file"]["id"] for u in used) else 0)
            if v > bv:
                best, bv = s, v
        if best:
            used.append(best)
        return best

    # 1. первый план — действие (fix-02 §3.1): открытый чехол / руки открывают; чехол ниже хука
    def first_key(s):
        v = s["shot"]["vision"]
        kk = 0.0
        if v["action"] in OPENING:
            kk += 6
        if v["setting"] == "hands":
            kk += 2
        if v["action"] == "static" and v["setting"] == "studio":
            kk -= 6                                  # не начинаем с лежащего закрытого чехла
        kk += hook_fit(s)
        if s["shot"]["id"] in ctx.avoid_first:
            kk -= 20
        return score(s, kk)
    first = take(pool, durs[0] + loop_b * ib + 0.2, first_key) or take(pool, durs[0], first_key)
    if not first:
        return None
    c0 = first["shot"]["vision"]["color"]
    roles = [
        lambda s: score(s, (2 if s["shot"]["vision"]["color"] == c0 else 0)          # герой, тот же цвет
                        + (2 if s["shot"]["vision"]["action"] in ("rotate", "static", "reveal") else 0)),
        lambda s: score(s, (5 if s["shot"]["vision"]["setting"] == "hands" else 0)    # руки (§3.3) / другой цвет
                        + (2 if s["shot"]["vision"]["color"] != c0 else 0)),
        lambda s: score(s, 4 if s["shot"]["vision"]["action"] in ("detail_macro", "close", "open") else 0),
    ]
    body = [first]
    for i, d in enumerate(durs[1:]):
        x = take(pool, d, roles[i % len(roles)])
        if not x:
            return None
        body.append(x)
    missing = [] if any(x["shot"]["vision"]["setting"] in ("hands", "pocket_bag") for x in body) else ["hands"]

    loop_beats = loop_b
    segs_d = durs

    segments, clips, sfx = [], [], []
    t = 0.0
    kinds = ["zoom", "punch", "whip"]
    ctx.rng.shuffle(kinds)
    whip_used = False
    s0 = first["shot"]
    first_src = s0["start"] + 0.15
    for i, (s, d) in enumerate(zip(body, segs_d)):
        tr = None
        if i > 0:
            k = kinds[(i - 1) % len(kinds)]
            if k == "whip" and whip_used:
                k = "punch"
            whip_used |= k == "whip"
            tr = {"type": k, "frames": 6 if k in ("zoom", "whip") else 4}
        ov = (tr["frames"] / fps) if tr and tr["type"] in ("zoom", "whip") else 0.0
        if i == 0:
            src = first_src
        else:
            mid = s["shot"]["start"] + s["shot"]["dur"] / 2
            src = max(s["shot"]["start"] + 0.15, min(mid - (d + ov) / 2, s["shot"]["end"] - 0.15 - d - ov))
        segments.append(seg(s, src, d + ov))
        clip = {"src": "", "from": frames(t - ov, fps), "durationInFrames": frames(t + d, fps) - frames(t - ov, fps),
                "pushIn": [1.0, 1.05] if i else [1.05, 1.05]}
        if i == 0:
            clip["transitionIn"] = {"type": "impact", "frames": 3}
        if tr:
            clip["transitionIn"] = tr
            clips[-1]["transitionOut"] = tr
            if tr["type"] in ("zoom", "whip"):
                sfx.append({"t": round(max(0.0, t - ov - 0.05), 2), "kind": "whoosh", "gain_db": -4})
        if s["shot"]["vision"]["action"] in ("open", "close") and i > 0:
            sfx.append({"t": round(t + ib, 2), "kind": "magnet", "gain_db": -6})
        clips.append(clip)
        t += d
    sfx.insert(0, {"t": 0.0, "kind": "click", "gain_db": -4})          # акцент на кадре 0

    end = None
    if purpose == "organic":
        # луп: последний план заканчивается ровно на кадре 0 — это обратный ход того же клипа,
        # что и первый план (поэтому первый клип режем длиннее: на всю длину лупа)
        ld = loop_beats * ib
        segments[0].src_dur = round(max(segments[0].src_dur, ld + 0.05), 3)
        segments.append(Segment(file_id=first["file"]["id"], name=first["file"]["name"], shot_id=s0["id"] + "#loop",
                                src_start=round(first_src, 3), src_dur=round(ld, 3), hdr=first["file"]["probe"]["hdr"],
                                bbox=first["shot"]["vision"]["case_bbox"], stabilize=segments[0].stabilize,
                                reverse=True))
        clips.append({"src": "", "from": frames(t, fps), "durationInFrames": frames(t + ld, fps) - frames(t, fps),
                      "pushIn": [1.08, 1.0], "transitionIn": {"type": "punch", "frames": 4}})
        t += ld
    else:
        # promote: карточка 1 такт на компактном плане
        cd = bar
        if cd > 0.2 * (t + cd) + 1e-6:
            cd = round(0.2 * t / 0.8, 3)
        cands = [x for x in pool if x not in body and end_fit(x) > 0] or [x for x in pool if x not in body]
        last = max(cands, key=lambda x: end_fit(x) + score(x)) if cands else body[1]
        ls = last["shot"]
        segments.append(seg(last, max(ls["start"] + 0.15, ls["start"] + ls["dur"] / 2 - cd / 2), cd))
        clips.append({"src": "", "from": frames(t, fps), "durationInFrames": frames(t + cd, fps) - frames(t, fps),
                      "pushIn": [1.0, 1.04], "transitionIn": {"type": "punch", "frames": 4}})
        case_top, case_bot = bbox(last)
        if case_bot * 1920 + 40 <= 1130:
            tag_top = int(max(1090, case_bot * 1920 + 40))
        elif case_top >= 0.33:
            tag_top = 500
        else:
            tag_top = 1130
        p = brand()["product"]
        end = {"from": frames(t, fps), "durationInFrames": frames(t + cd, fps) - frames(t, fps),
               "color": text_color(last), "eyebrow": "The condom case", "price": p["price"],
               "site": p["site"].upper(), "shipping": p["shipping"], "tagTop": tag_top}
        t += cd
    total = round(t, 3)

    # тексты: хук с кадра 0 (виден целиком), второй — на сильной доле у действия, исчезает за долю до конца
    hook = pick_hook(ctx, "premium")
    h_end = sum(segs_d[:2])                                   # хук на первых двух планах
    screens = [{"from": 0, "durationInFrames": frames(h_end, fps), "text": hook["screens"][0],
                "eyebrow": hook.get("eyebrow"), "animateIn": False}]
    if len(hook["screens"]) > 1:
        half = frames(segs_d[0], fps)
        screens = [{"from": 0, "durationInFrames": half, "text": hook["screens"][0], "eyebrow": hook.get("eyebrow"),
                    "animateIn": False},
                   {"from": half, "durationInFrames": frames(h_end, fps) - half, "text": hook["screens"][1],
                    "animateIn": True}]
    sec_shot = body[2] if len(body) > 2 else body[-1]
    sec = pick_second(ctx, sec_shot["shot"]["vision"]["action"],
                      sec_shot["shot"]["vision"]["color"] != c0)
    body_end = sum(segs_d)
    if sec and len(screens) < 3:
        s_from = frames(h_end, fps)
        s_to = frames(min(body_end, total - ib), fps)             # исчезает за 1 долю до конца
        if s_to - s_from >= fps:                                  # держится ≥ 1 с
            screens.append({"from": s_from, "durationInFrames": s_to - s_from, "text": sec["screens"][0],
                            "animateIn": True})
    if purpose == "promote" and end:
        screens = [x for x in screens if x["from"] + x["durationInFrames"] <= end["from"]] or screens[:1]
    # цвет текста — по кадру под каждым экраном (белый на светлом не читается)
    starts = [c["from"] for c in clips]
    for sc in screens:
        mid = sc["from"] + sc["durationInFrames"] // 2
        idx = max(i for i, st in enumerate(starts) if st <= max(sc["from"], 0)) if starts else 0
        idx2 = max(i for i, st in enumerate(starts) if st <= mid) if starts else 0
        shots_under = [body[i] if i < len(body) else first for i in {idx, idx2}]
        light = max((x["shot"]["metrics"].get("luma_top") or 0) for x in shots_under)
        sc["color"] = "ink" if light > 0.55 else "white"

    # проверки fix-02 §7
    cuts = [c["from"] + (c.get("transitionIn", {}).get("frames", 0)
                         if c.get("transitionIn", {}).get("type") in ("zoom", "whip") else 0) for c in clips[1:]]
    beat_frames = [frames(k * ib, fps) for k in range(beats_total + 8)]
    checks = {
        "first_cut_s": round(cuts[0] / fps, 2) if cuts else None,
        "cuts_on_beats": all(min(abs(c - b) for b in beat_frames) <= 1 for c in cuts),
        "whole_bars": abs(total / bar - round(total / bar)) * bar * fps <= 1 if purpose == "organic" else True,
        "max_shot_s": round(max(segs_d), 2),
        "price_on_screen": end is not None,
    }
    props = {"template": "p_organic", "style": "premium", "fps": fps, "durationInFrames": frames(total, fps),
             "clips": clips, "screens": screens, "textColor": text_color(first), "endFrame": end}
    plan = Plan("p_organic", "premium", props, segments, sfx, hook["id"], total, c0, s0["id"])
    plan.purpose, plan.bpm, plan.checks, plan.missing = purpose, round(60 / ib, 1), checks, missing
    return plan


BUILDERS = {"p_one_line": build_p_one_line, "n_statement": build_n_statement, "p_organic": build_p_organic}
