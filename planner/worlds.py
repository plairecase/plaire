"""fix-03: монтаж «одного мира».

Ролик строится как одно непрерывное действие внутри одного мира и одного цвета:
хук (открытый чехол, видно 2 шт.) → действие (закрывает, щелчок) → доказательство (торец / ладонь)
→ [второй цвет — один план, только promote или план «оба цвета»] → луп (organic) или карточка (promote).
Каждый текст привязан к содержанию своего плана и живёт ровно этот план.

Шаблоны:
  p_gloves_pov     — мир «перчатки», один цвет (эталон A из fix-03, в премиум-подаче)
  p_studio_to_life — студия (бумага) → одна смена мира на улицу, тот же цвет (эталон B)
  promote          — на основе p_gloves_pov: + один план второго цвета + карточка с ценой (эталон C)
"""
from __future__ import annotations

import math

from planner.templates import (Ctx, Plan, Segment, bbox, brand, check_item, frames, seg, text_color,
                               usable_len)

COMPAT = {"open": {"open", "closing"}, "closed": {"closed", "opening"},
          "opening": {"open", "opening"}, "closing": {"closed", "closing"}}

# текст = план (fix-03, правило 2): какой тип плана разрешает какой «второй текст»
TEXT_FOR_ROLE = {"inside": "inside", "close": "close", "profile": "profile", "palm": "palm",
                 "studio_closed": "studio_closed", "street": "street", "second_color": "second_color",
                 "both": "both_colors", "macro": "macro"}


# 3D-планы (инструкция 3D, раздел 3): роль в монтаже и текст = план
SEG3D = {"s_two_colours": {"role": "both", "text": "p_sec_colours", "layer": "two_colours"},
         "s_profile": {"role": "profile", "text": "p_sec_slim", "layer": "profile"}}
FADE3D = 3                      # кадров кросс-фейда реальный ↔ 3D


def pseudo3d(scene: str, W: str, C: str) -> dict:
    """Псевдо-план 3D: занимает место в монтаже, но не режется из исходника."""
    return {"three": scene, "file": {"name": "3D", "id": "3d"},
            "shot": {"id": f"3d_{scene}", "start": 0.0, "dur": 0.0, "end": 0.0, "metrics": {},
                     "vision": {"world": W, "color": C, "hands": "none", "shows_inside": False, "action": "3d",
                                "both_colors_in_frame": scene == "s_two_colours", "hero_score": 0}}}


def nb3d(ib: float) -> int:
    """3D-план 1.2–1.8 с, целое число долей."""
    best = max(2, int(round(1.5 / ib)))
    while best * ib > 1.8 + 1e-6 and best > 2:
        best -= 1
    return best


def v(s: dict) -> dict:
    return s["shot"]["vision"]


# ------------------------------------------------------------------ роли планов
def is_inside(s):
    return v(s).get("shows_inside") and v(s)["action"] in ("open", "insert", "rotate", "static", "reveal") \
        and v(s).get("start_state", "open") in ("open", "opening")


def is_close(s):
    return v(s)["action"] in ("close", "open") or v(s).get("start_state") in ("open", "closing") \
        and v(s).get("end_state") in ("closed", "closing")


def is_profile(s):
    return bool(v(s).get("shows_profile"))


def is_palm(s):
    return v(s).get("start_state") == "closed" and v(s).get("end_state") == "closed"


ROLE_TEST = {"inside": is_inside, "close": is_close, "profile": is_profile, "palm": is_palm,
             "studio_closed": is_palm, "street": lambda s: True, "macro": lambda s: v(s)["action"] == "detail_macro"}

TEMPLATES = {
    "p_gloves_pov": {"world": "gloves", "steps": ["inside", "close", "profile", "palm"], "change": None},
    "p_studio_to_life": {"world": "studio_paper", "steps": ["inside", "studio_closed", "street"],
                         "change": {"step": "street", "world": "street_hands"}},
}


def pick_text(ctx: Ctx, role: str, used: set, shot: dict | None = None) -> dict | None:
    key = TEXT_FOR_ROLE.get(role)
    if key == "inside" and not (shot and v(shot).get("two_visible")):
        return None
    pool = [t for t in ctx.texts if t.get("style") == "premium" and t.get("kind") == "second"
            and t.get("action") == key and t["id"] not in used and not check_item(t)]
    return ctx.rng.choice(pool) if pool else None


def pick_hook(ctx: Ctx, first: dict, purpose: str, template: str) -> dict:
    pool = [t for t in ctx.texts if t.get("style") == "premium" and t.get("kind") == "hook"
            and t["id"] not in ctx.avoid_hooks and not check_item(t)
            and (purpose == "promote" or t.get("purpose") != "promote")       # бренд-хук — не в organic
            and (t.get("shot") != "both" or v(first).get("both_colors_in_frame"))]  # «два цвета» — только если оба в кадре
    # «Holds 2 / Two condoms» — только если в кадре видно обе штуки (fix-03, правило 2).
    # В текущих исходниках внутри виден один, поэтому хуки «про два» не берём, пока нет такого кадра.
    two_visible = bool(v(first).get("two_visible"))
    if template == "p_studio_to_life":
        pref = [t for t in pool if t["id"] == "p_hook_05"]                # «The condom case, redesigned.»
    elif two_visible:
        pref = [t for t in pool if t.get("shot") == "inside" and len(t["screens"]) == 1]
    else:
        pref = [t for t in pool if t.get("shot") != "inside" and len(t["screens"]) == 1
                and t["id"] in ("p_hook_02", "p_hook_05", "p_hook_17", "p_hook_06")]
    return ctx.rng.choice(pref or [t for t in pool if t.get("shot") != "inside"] or pool)


# ------------------------------------------------------------------ сборка
def build(ctx: Ctx, template: str, purpose: str = "organic", bpm_fallback: float = 120.0) -> Plan | None:
    spec = TEMPLATES[template]
    fps = ctx.fps
    W = spec["world"]
    in_world = [s for s in ctx.shots if v(s).get("world") == W and v(s)["color"] in ("cognac", "black")]
    if not in_world:
        return None

    # 1. мир и цвет: цвет, в котором есть хук «внутри видно 2 шт.» (и для смены мира — уличный план того же цвета)
    colors = []
    for c in ("black", "cognac"):
        cw = [s for s in in_world if v(s)["color"] == c]
        if not any(is_inside(s) for s in cw):
            continue
        if spec["change"]:
            other = [s for s in ctx.shots if v(s).get("world") == spec["change"]["world"] and v(s)["color"] == c]
            if not other:
                continue
        colors.append(c)
    if not colors:
        return None
    ctx.rng.shuffle(colors)
    if ctx.avoid_color in colors:                       # другой цвет, чем у прошлого ролика дня — если получится
        colors.remove(ctx.avoid_color)
        colors.append(ctx.avoid_color)
    for C in colors:
        plan = _build_color(ctx, template, purpose, bpm_fallback, spec, in_world, C)
        if plan:
            return plan
    return None


def _build_color(ctx, template, purpose, bpm_fallback, spec, in_world, C):
    fps = ctx.fps
    W = spec["world"]
    pool = [s for s in in_world if v(s)["color"] == C]
    change_pool = [s for s in ctx.shots if spec["change"] and v(s).get("world") == spec["change"]["world"]
                   and v(s)["color"] == C]

    # 2. сетка темпа: длина — целое число тактов, первая склейка ≤ 1.5 с, планы ≤ 2 с (кроме лупа/карточки)
    if ctx.beats and len(ctx.beats) > 4:
        diffs = sorted(b - a for a, b in zip(ctx.beats, ctx.beats[1:]))
        ib = diffs[len(diffs) // 2]
    else:
        ib = 60.0 / bpm_fallback
    bar = 4 * ib
    scenes3d = [sc for sc in ctx.force3d if sc in SEG3D and W != "street_hands"
                and (ctx.models.get(C) if sc != "s_two_colours" else (ctx.models.get("black") and ctx.models.get("cognac")))]
    seg3d_s = len(scenes3d) * nb3d(ib) * ib
    fits = [n for n in (4, 3, 5) if 7.0 <= n * bar <= 10.0]
    bars = next((n for n in fits if seg3d_s <= ctx.max3d_share * n * bar + 1e-6), max(fits) if fits else 4)
    B = bars * 4
    steps = list(spec["steps"])
    first_b = 3 if 3 * ib <= 1.5 + 1e-6 else 2
    max_b = max(2, int(2.0 / ib + 1e-6))
    n_mid = len(steps) - 1
    tail_min = 2 if purpose == "organic" else 0
    mid_total = min(B - first_b - tail_min, n_mid * max_b)
    mids = [mid_total // n_mid + (1 if i < mid_total % n_mid else 0) for i in range(n_mid)] if n_mid else []
    if any(m < 2 for m in mids):
        return None
    slots = [first_b] + mids
    loop_b = B - sum(slots) if purpose == "organic" else 0

    # 3. планы по ролям, с непрерывностью действия (end_state → start_state)
    used: list = []

    def score(s, role, prev):
        sc = v(s)["hero_score"] / 3 + ctx.rng.random()
        if ROLE_TEST.get(role, lambda x: True)(s):
            sc += 6
        if prev is not None:
            a, b = v(prev).get("end_state"), v(s).get("start_state")
            if a and b:
                sc += 2 if b in COMPAT.get(a, set()) else -3
        if any(u["file"]["id"] == s["file"]["id"] and u["shot"]["id"] != s["shot"]["id"] for u in used):
            sc += 0.5                                   # тот же дубль — хорошо для непрерывности
        if s["shot"]["id"] in ctx.avoid_first and not used:
            sc -= 20
        return sc

    chosen = []
    for i, (role, nb) in enumerate(zip(steps, slots)):
        d = nb * ib
        src_pool = change_pool if (spec["change"] and role == spec["change"]["step"]) else pool
        cands = [s for s in src_pool if s not in used and usable_len(s) >= d]
        if role == "inside":
            cands = [s for s in cands if is_inside(s)]
        if not cands:
            if role in ("inside",) or (spec["change"] and role == spec["change"]["step"]):
                return None
            continue                                    # необязательная роль: пропускаем, доли уйдут в луп
        best = max(cands, key=lambda s: score(s, role, chosen[-1][0] if chosen else None))
        used.append(best)
        chosen.append((best, role, nb))
    if len(chosen) < 3:
        return None

    # 3D-планы (раздел 3): внутри ролика — после хука и до лупа/карточки, не подряд; хук всегда реальный
    for sc in sorted(scenes3d, key=lambda x: x != "s_profile"):   # торец — на место реального торца, потом остальные
        e = (pseudo3d(sc, W, C), SEG3D[sc]["role"], nb3d(ib))
        k = next((j for j, (s_, r_, _) in enumerate(chosen) if j > 0 and r_ == SEG3D[sc]["role"]
                  and not s_.get("three")), None)
        if k is not None:                                # 3D заменяет реальный план той же роли (торец)
            used.remove(chosen[k][0])
            chosen[k] = e
            continue
        pos = min(2, len(chosen))
        while pos < len(chosen) and (chosen[pos - 1][0].get("three") or chosen[pos][0].get("three")):
            pos += 1
        if chosen[pos - 1][0].get("three"):
            continue
        chosen.insert(pos, e)
    # длина — целые такты: укорачиваем реальные планы середины, при нехватке убираем последний
    limit = B - tail_min
    while sum(nb for _, _, nb in chosen) > limit:
        reals = [j for j, (s_, _, _) in enumerate(chosen) if j > 0 and not s_.get("three")]
        big = [j for j in reals if chosen[j][2] > 2]
        if big:
            j = max(big, key=lambda j: chosen[j][2])
            chosen[j] = (chosen[j][0], chosen[j][1], chosen[j][2] - 1)
        elif len(reals) > 1:
            used.remove(chosen[reals[-1]][0])
            chosen.pop(reals[-1])
        else:
            break
    for j in range(len(chosen) - 1, 0, -1):              # два 3D-плана подряд — второй убираем
        if chosen[j][0].get("three") and chosen[j - 1][0].get("three"):
            chosen.pop(j)
    if sum(nb for _, _, nb in chosen) > limit:
        return None
    if purpose == "organic":
        loop_b = B - sum(nb for _, _, nb in chosen)

    # 4. promote: один план второго цвета (того же мира) + карточка
    second = None
    if purpose == "promote":
        other_c = "cognac" if C == "black" else "black"
        both = [s for s in ctx.shots if v(s).get("world") == W and v(s).get("both_colors_in_frame")]
        oc = both or [s for s in in_world if v(s)["color"] == other_c and (is_inside(s) or v(s)["action"] == "open")]
        oc = [s for s in oc if usable_len(s) >= 2 * ib]
        if oc:
            second = max(oc, key=lambda s: v(s)["hero_score"])
            chosen.append((second, "both" if second in both else "second_color", min(max_b, 3)))

    # 5. клипы и тексты
    segments, clips, screens, sfx = [], [], [], [{"t": 0.0, "kind": "click", "gain_db": -4}]
    used_texts = set()
    hook = pick_hook(ctx, chosen[0][0], purpose, template)
    t = 0.0
    seg3d_layers, clip_roles, after3d = [], [], []
    pal = brand()["palette"]
    for i, (s, role, nb) in enumerate(chosen):
        d = nb * ib
        if s.get("three"):
            sc3 = s["three"]
            # предыдущий реальный план уходит под 3D на 3 кадра (кросс-фейд реальный → 3D)
            clips[-1]["durationInFrames"] += FADE3D
            segments[-1].src_dur = round(segments[-1].src_dur + FADE3D / fps, 3)
            other = "black" if C == "cognac" else "cognac"
            layer = {"type": SEG3D[sc3]["layer"], "scene": sc3, "from": frames(t, fps),
                     "durationInFrames": frames(t + d, fps) - frames(t, fps), "fade": FADE3D,
                     "afterClip": len(clips) - 1, "ink": pal.get("ink", "#1d1d1b"),
                     "bg": pal.get("paper", "#F5F4F0") if W == "studio_paper" else None}
            if sc3 == "s_two_colours":
                layer.update(model=ctx.models["cognac"], model2=ctx.models["black"],
                             tune=ctx.tunes.get("cognac"), tune2=ctx.tunes.get("black"))
            else:
                layer.update(model=ctx.models[C], tune=ctx.tunes.get(C))
            seg3d_layers.append(layer)
            tt = next((x for x in ctx.texts if x["id"] == SEG3D[sc3]["text"]), None)
            if tt:
                used_texts.add(tt["id"])
                screens.append({"from": frames(t, fps), "durationInFrames": frames(t + d, fps) - frames(t, fps),
                                "text": tt["screens"][0], "eyebrow": None, "animateIn": True, "role": role,
                                "shot": s["shot"]["id"], "action": tt.get("action"), "three": sc3})
            sfx.append({"t": round(t, 2), "kind": "whoosh", "gain_db": -8})
            t += d
            continue
        tr = None
        prev3d = i > 0 and bool(chosen[i - 1][0].get("three"))
        if i > 0:
            # смена мира — на сильной доле, энергично; внутри мира — короткий толчок (match on action)
            changed = v(s).get("world") != v(chosen[i - 1][0]).get("world")
            tr = {"type": "zoom", "frames": 6} if changed else {"type": "punch", "frames": 4}
            if prev3d:
                tr = {"type": "cut", "frames": 0}          # 3D растворяется поверх (кросс-фейд 3 кадра)
        ov = (tr["frames"] / fps) if tr and tr["type"] == "zoom" else (FADE3D / fps if prev3d else 0.0)
        clip_roles.append(role)
        after3d.append(prev3d)
        if i == 0:
            src = s["shot"]["start"] + 0.15
        else:
            mid = s["shot"]["start"] + s["shot"]["dur"] / 2
            src = max(s["shot"]["start"] + 0.15, min(mid - (d + ov) / 2, s["shot"]["end"] - 0.15 - d - ov))
        segments.append(seg(s, src, d + ov))
        clip = {"src": "", "from": frames(t - ov, fps), "durationInFrames": frames(t + d, fps) - frames(t - ov, fps),
                "pushIn": [1.0, 1.05]}
        if i == 0:
            clip["transitionIn"] = {"type": "impact", "frames": 3}
        if tr:
            clip["transitionIn"] = tr
            if tr["type"] == "zoom":
                clips[-1]["transitionOut"] = tr
                sfx.append({"t": round(max(0.0, t - ov - 0.05), 2), "kind": "whoosh", "gain_db": -4})
        if role == "close" and v(s)["action"] in ("close", "open"):
            sfx.append({"t": round(t + ib, 2), "kind": "magnet", "gain_db": -6})
        clips.append(clip)
        # текст = этот план (хук — на первом); исчезает вместе с планом
        if i == 0:
            txt = {"text": hook["screens"][0], "eyebrow": hook.get("eyebrow"), "id": hook["id"]}
            tt = None
        elif role == "second_color":
            want_id = "p_sec_cognac" if v(s)["color"] == "cognac" else "p_sec_black"     # текст = цвет в кадре
            tt = next((x for x in ctx.texts if x["id"] == want_id), None)
        else:
            tt = pick_text(ctx, role, used_texts, s)
        if i > 0:
            txt = {"text": tt["screens"][0], "id": tt["id"], "action": tt.get("action")} if tt else None
        if txt:
            used_texts.add(txt["id"])
            screens.append({"from": frames(t, fps), "durationInFrames": frames(t + d, fps) - frames(t, fps),
                            "text": txt["text"], "eyebrow": txt.get("eyebrow"), "animateIn": i > 0,
                            "role": role, "shot": s["shot"]["id"], "action": txt.get("action")})
        t += d

    first = chosen[0][0]
    end = None
    if purpose == "organic":
        ld = loop_b * ib
        lov = FADE3D / fps if chosen[-1][0].get("three") else 0.0    # луп заходит под растворяющийся 3D
        segments[0].src_dur = round(max(segments[0].src_dur, ld + lov + 0.05), 3)
        segments.append(Segment(file_id=first["file"]["id"], name=first["file"]["name"],
                                shot_id=first["shot"]["id"] + "#loop", src_start=segments[0].src_start,
                                src_dur=round(ld + lov, 3), hdr=first["file"]["probe"]["hdr"],
                                bbox=v(first)["case_bbox"], stabilize=segments[0].stabilize, reverse=True))
        clips.append({"src": "", "from": frames(t - lov, fps), "durationInFrames": frames(t + ld, fps) - frames(t - lov, fps),
                      "pushIn": [1.08, 1.0],
                      "transitionIn": {"type": "cut", "frames": 0} if lov else {"type": "punch", "frames": 4}})
        clip_roles.append("loop")
        after3d.append(bool(chosen[-1][0].get("three")))
        chosen.append((first, "loop", loop_b))
        t += ld
    else:
        cd = round(min(bar, 0.2 / 0.8 * t), 3)                        # карточка ≤ 20 % длины
        last = max([s for s in pool if s not in used] or pool,
                   key=lambda s: (is_palm(s), v(s)["hero_score"]))
        ls = last["shot"]
        segments.append(seg(last, max(ls["start"] + 0.15, ls["start"] + ls["dur"] / 2 - cd / 2), cd))
        p = brand()["product"]
        top, bot = bbox(last)
        tag_top = 500                                                  # цена под вордмарком, всегда
        need_top = (tag_top + 140 + 40) / 1920                         # низ строки доставки + 40 px
        shift_px, scale = 0.0, 1.0
        if top < need_top:
            # сдвигаем кадр вниз (с увеличением, чтобы не открыть край), пока чехол не уйдёт ниже текста
            for _ in range(20):
                scale = 1 + 2 * shift_px / 1920 + 0.02
                new_top = 0.5 + (top - 0.5) * scale + shift_px / 1920
                if new_top >= need_top:
                    break
                shift_px += 30
        clips.append({"src": "", "from": frames(t, fps), "durationInFrames": frames(t + cd, fps) - frames(t, fps),
                      "pushIn": [scale, scale], "offsetY": round(shift_px), "transitionIn": {"type": "punch", "frames": 4}})
        clip_roles.append("card")
        after3d.append(bool(chosen[-1][0].get("three")))
        end = {"from": frames(t, fps), "durationInFrames": frames(t + cd, fps) - frames(t, fps),
               "color": text_color(last), "eyebrow": "The condom case", "price": p["price"],
               "site": p["site"].upper(), "shipping": p["shipping"], "tagTop": tag_top}
        chosen.append((last, "card", 0))
        t += cd
    total = round(t, 3)

    # 3D-модель чехла (раздел 8 + правка владельца 28.11.2026): цвет модели = цвет ролика
    three = list(seg3d_layers)
    model = ctx.models.get(C)
    fly_used = False
    if model:
        seg_s = sum(l["durationInFrames"] for l in seg3d_layers) / fps
        cands = [k for k in range(1, len(clips)) if clip_roles[k] not in ("loop", "card") and not after3d[k]
                 and not any(l["afterClip"] == k for l in seg3d_layers)]
        street = next((k for k in cands if clip_roles[k] == "street"), None)
        idx = street if street is not None else (2 if 2 in cands else (cands[0] if cands else None))
        # 3D не больше max_share длины (раздел 1); пролёт ≈ 0.4 с
        if idx is not None and (seg_s + 12 / fps) <= ctx.max3d_share * total + 1e-6:
            # пролёт на сильной склейке в середине (для студия→улица — ровно на смене мира)
            cut = clips[idx]["from"] + (clips[idx].get("transitionIn", {}).get("frames", 0)
                                        if clips[idx].get("transitionIn", {}).get("type") == "zoom" else 0)
            if clips[idx].get("transitionIn", {}).get("type") == "zoom":
                clips[idx]["transitionIn"] = {"type": "punch", "frames": 4}       # 3D заменяет зум-переход
                clips[idx - 1].pop("transitionOut", None)
            fly = 12                                       # кадр закрыт целиком на 8–10-м кадре — там склейка
            three.append({"type": "fly", "model": model, "tune": ctx.tunes.get(C), "from": max(0, cut - 9),
                          "durationInFrames": fly})
            sfx.append({"t": round(max(0.0, (cut - 9) / fps), 2), "kind": "whoosh", "gain_db": -3})
            fly_used = True
        if end:
            # финал promote: 3D-чехол медленно поворачивается на бумаге под вордмарком и ценой
            three.append({"type": "hero", "model": model, "tune": ctx.tunes.get(C), "from": end["from"],
                          "durationInFrames": end["durationInFrames"]})
            end["color"] = "ink"
            end["tagTop"] = 500

    # цвет текста по зоне текста плана (fix-03): ink — только светло и спокойно, иначе белый (+ плашка на пёстром)
    for sc in screens:
        if sc.get("three"):
            sc["color"], sc["plate"] = "ink", False        # уточняется по фону мира в make_videos
            continue
        sh = next(s for s, _, _ in chosen if s["shot"]["id"] == sc["shot"])
        m = sh["shot"]["metrics"]
        lum = m.get("text_luma") or m.get("luma_top") or 0.5
        # светлый фон (серая бумага, перчатки, небо) — тёмный текст; тёмный — белый с тенью
        sc["color"] = "ink" if lum > 0.55 else "white"
        sc["plate"] = False                       # плашки выглядят шаблонно (визуальная проверка) — без них
        # текст не ложится на чехол и руки: если предмет высоко, текст уходит под него (в безопасной зоне)
        top, bot = bbox(sh)
        block = 120 if not sc.get("eyebrow") else 180       # высота блока текста, px (1–2 строки)
        if top * 1920 < 300 + block + 30:
            y_below = int(bot * 1920 + 40)
            if y_below + block <= 1248:
                sc["top"] = y_below
            elif top * 1920 > 300:
                sc["top"] = 300
            else:
                sc["top"] = 270                               # выше уже нельзя (интерфейс TikTok)

    plan = Plan(template, "premium", {
        "template": template, "style": "premium", "fps": fps, "durationInFrames": frames(total, fps),
        "clips": clips, "screens": screens, "textColor": "white", "endFrame": end, "threeD": three}, segments, sfx,
        hook["id"], total, C, first["shot"]["id"])
    plan.purpose, plan.bpm = purpose, round(60 / ib, 1)
    plan.uses3d = bool(three)
    plan.three = {"transition": "fly" if fly_used else None,
                  "segment": [l["scene"] for l in seg3d_layers] or None, "model": C,
                  "share": round(sum(l["durationInFrames"] for l in three if l["type"] != "hero") / fps / total, 2)}
    plan.world = W
    plan.shots = [{"shot": s["shot"]["id"], "file": s["file"]["name"], "role": r, "world": v(s).get("world"),
                   "hands": v(s).get("hands"), "color": v(s)["color"], "inside": bool(v(s).get("shows_inside")),
                   "both": bool(v(s).get("both_colors_in_frame")), "dur": round(nb * ib, 3) if nb else None,
                   "three": s.get("three")}
                  for s, r, nb in chosen]
    plan.missing = [] if any(x["hands"] in ("bare", "gloves") for x in plan.shots) else ["hands"]
    plan.checks = plan_qc(plan, ib)
    return plan


# ------------------------------------------------------------------ проверки fix-03 по плану монтажа
ALLOWED = {"inside": {"inside"}, "close": {"close"}, "profile": {"profile"}, "palm": {"palm", "studio_closed"},
           "studio_closed": {"studio_closed", "palm", "profile"}, "street": {"street"},
           "second_color": {"second_color"}, "both": {"both_colors"}, "macro": {"macro"}}


def plan_qc(plan: Plan, ib: float) -> dict:
    fps = plan.props["fps"]
    with_loop = [x for x in plan.shots if x["role"] != "card"]
    shots = [x for x in with_loop if x["role"] != "loop"]
    total = sum(x["dur"] or 0 for x in with_loop) or 1
    worlds = [x["world"] for x in shots]
    main = max(set(worlds), key=worlds.count)
    share = sum(x["dur"] or 0 for x in with_loop if x["world"] == main) / total
    changes = lambda key: sum(1 for a, b in zip(shots, shots[1:]) if a[key] != b[key])
    hands_seq = [x["hands"] for x in shots if x["hands"] in ("bare", "gloves")]
    color_changes = [(a, b) for a, b in zip(shots, shots[1:]) if a["color"] != b["color"]]
    # текст = план: «второй» текст стоит только на своём типе плана, и живёт не дольше плана + 1 доля
    text_ok = True
    clips = plan.props["clips"]
    for sc in plan.props["screens"][1:]:
        if sc.get("action") not in ALLOWED.get(sc.get("role"), set()):
            text_ok = False
        end = sc["from"] + sc["durationInFrames"]
        cuts_inside = [c["from"] for c in clips if sc["from"] < c["from"] < end - round(ib * fps)]
        if cuts_inside:
            text_ok = False
    cuts = [c["from"] + (c.get("transitionIn", {}).get("frames", 0) if c.get("transitionIn", {}).get("type") == "zoom" else 0)
            for c in clips[1:]]
    t, inside_early = 0.0, False
    for x in shots:
        if t < 3.0 and x["inside"]:
            inside_early = True
        t += x["dur"] or 0
    return {
        "world": main, "world_share": round(share, 2), "world_changes": changes("world"),
        "world_consistency": share >= 0.75 and changes("world") <= 1,
        "hands_consistency": sum(1 for a, b in zip(hands_seq, hands_seq[1:]) if a != b) <= 1,
        "color_consistency": len(color_changes) <= 1 and all(b["both"] or b["role"] == "second_color" or a["both"]
                                                             for a, b in color_changes),
        "text_shot_match": text_ok,
        "inside_early": inside_early,
        "first_cut_s": round(cuts[0] / fps, 2) if cuts else None,
        "max_shot_s": round(max((x["dur"] or 0) for x in shots), 2),
        "price_on_screen": plan.props.get("endFrame") is not None,
        "3d_share": getattr(plan, "three", {}).get("share", 0),
        "3d_share_ok": getattr(plan, "three", {}).get("share", 0) <= 0.3 + 1e-6,
        "3d_not_first": not (shots and shots[0].get("three")),
    }
