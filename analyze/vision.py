"""Разметка плана зрением: 3 кадра (начало/середина/конец) → Claude → строгий JSON.

Модель и цены — в config.json → claude. Ответ проверяется по схеме, при ошибке
один повтор. Расход токенов копится в Usage.
"""
from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

SETTINGS = ["studio", "street", "indoor_lifestyle", "hands", "pocket_bag", "packaging",
            "wallet_before", "other"]
ACTIONS = ["static", "rotate", "open", "close", "insert", "carry", "reveal", "detail_macro"]
COLORS = ["cognac", "black", "both", "none"]
STYLES = ["premium", "native"]
WORLDS = ["gloves", "studio_paper", "street_hands", "packaging", "lifestyle_other"]
HANDS = ["none", "bare", "gloves"]
BACKGROUNDS = ["grey", "paper", "outdoor", "fabric", "other"]
STATES = ["open", "closed", "opening", "closing"]

SCHEMA = {
    "type": "object",
    "properties": {
        "case_visible_ratio": {"type": "number"},
        "case_bbox": {"type": "array", "items": {"type": "number"}},
        "color": {"type": "string", "enum": COLORS},
        "setting": {"type": "string", "enum": SETTINGS},
        "action": {"type": "string", "enum": ACTIONS},
        "style_fit": {"type": "array", "items": {"type": "string", "enum": STYLES}},
        "hero_score": {"type": "integer"},
        "notes": {"type": "string"},
        "world": {"type": "string", "enum": WORLDS},
        "hands": {"type": "string", "enum": HANDS},
        "background": {"type": "string", "enum": BACKGROUNDS},
        "both_colors_in_frame": {"type": "boolean"},
        "shows_inside": {"type": "boolean"},
        "shows_profile": {"type": "boolean"},
        "start_state": {"type": "string", "enum": STATES},
        "end_state": {"type": "string", "enum": STATES},
        "focus_ok": {"type": "boolean"},
    },
    "required": ["case_visible_ratio", "case_bbox", "color", "setting", "action", "style_fit",
                 "hero_score", "notes", "world", "hands", "background", "both_colors_in_frame",
                 "shows_inside", "shows_profile", "start_state", "end_state", "focus_ok"],
    "additionalProperties": False,
}

SYSTEM = """You tag raw video shots for Plaire, a brand that sells one product: a slim eco-leather \
condom case that looks like a mini wallet. Two colours: Cognac Brown and Midnight Black. \
It has a hidden magnetic closure and holds 2 condoms.

You get 3 frames of ONE shot (start, middle, end). Return JSON only:
- case_visible_ratio: share of the shot (0.0-1.0) where the Plaire case is clearly visible in frame.
- case_bbox: [x, y, w, h] of the case in the MIDDLE frame, normalised 0-1 (top-left origin); [0,0,0,0] if not visible.
- color: case colour seen: cognac | black | both | none.
- setting: studio (clean backdrop, controlled light) | street | indoor_lifestyle | hands (close-up in hands, neutral bg) | \
pocket_bag (going into / out of a pocket or bag) | packaging (box, unboxing) | \
wallet_before (the "before" problem: condom kept in a wallet, crushed wrapper, pocket without a case) | other.
- action: static | rotate | open | close | insert (condom goes in) | carry | reveal | detail_macro (texture, stitching, magnet close-up).
- style_fit: which edit styles the shot suits. premium = calm, clean, Apple-like product shot. \
native = real life, handheld, TikTok lifestyle. Can be both or empty.
- hero_score: 0-10, how strong the shot is as a hero / hook frame (sharp, case well lit and big, clean background).
- world: the "world" of the shot, so an editor never mixes worlds: gloves (white gloves, grey backdrop, catalogue / unboxing look) | studio_paper (case on light paper, usually from above, no hands) | street_hands (bare hands, outdoors / bench, daylight) | packaging (box, packaging is the subject) | lifestyle_other (pocket, bag, evening, city, home).
- hands: none | bare | gloves.
- background: grey | paper | outdoor | fabric | other.
- both_colors_in_frame: true only if a cognac AND a black case are visible at the same time.
- shows_inside: true only if the case is open and the condoms inside are clearly visible.
- shows_profile: true if the edge / thickness of the case is shown (side view, how slim it is).
- start_state / end_state: case state in the first and the last frame: open | closed | opening | closing.
- focus_ok: false if the case is blurry / out of focus in most frames.
- notes: very short, in Russian (до 12 слов): что в кадре и проблемы (смаз, пересвет, чужой бренд, лицо).
Be strict: blurry frames, the case partly out of frame, or no case lower the ratio and the score."""


@dataclass
class Usage:
    model: str
    price_in: float
    price_out: float
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    errors: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, resp) -> None:
        u = resp.usage
        with self._lock:
            self.calls += 1
            self.input_tokens += (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) \
                + (getattr(u, "cache_creation_input_tokens", 0) or 0)
            self.output_tokens += u.output_tokens or 0

    @property
    def cost_usd(self) -> float:
        return self.input_tokens / 1e6 * self.price_in + self.output_tokens / 1e6 * self.price_out

    def as_dict(self) -> dict:
        return {"model": self.model, "calls": self.calls, "errors": self.errors,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cost_usd": round(self.cost_usd, 4)}


class VisionError(RuntimeError):
    pass


def clean_key(raw: str) -> str:
    """Секрет должен быть одной строкой sk-ant-…; если вставили пример команды curl,
    достаём ключ из него. Сам ключ никуда не печатаем."""
    import re

    raw = (raw or "").strip()
    if re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", raw):
        return raw
    found = re.findall(r"sk-ant-[A-Za-z0-9_\-]{20,}", raw)
    if len(set(found)) == 1:
        return found[0]
    if not raw:
        raise VisionError("нет секрета ANTHROPIC_API_KEY: разметка зрением невозможна")
    raise VisionError("в секрете ANTHROPIC_API_KEY не ключ: там текст на несколько строк "
                      "(похоже на пример команды curl). Нужна только строка вида sk-ant-api03-…")


def make_client():
    import anthropic

    key = clean_key(os.environ.get("ANTHROPIC_API_KEY", ""))
    return anthropic.Anthropic(api_key=key, max_retries=4, timeout=90.0)


def check_key(client, model: str) -> None:
    """Бесплатная проверка: ключ действует и модель доступна (Models API, без токенов)."""
    import anthropic

    try:
        client.models.retrieve(model)
    except anthropic.AuthenticationError as e:
        raise VisionError("ключ ANTHROPIC_API_KEY не подходит (неверный или удалён)") from e
    except anthropic.PermissionDeniedError as e:
        raise VisionError("у ключа нет доступа к API") from e
    except anthropic.NotFoundError as e:
        raise VisionError(f"модель {model} недоступна для этого ключа") from e
    except anthropic.APIConnectionError as e:
        raise VisionError("не удалось связаться с API Claude (сеть или неверный формат ключа)") from e


def validate(d: dict) -> dict:
    """Проверка и нормализация ответа. Ошибка → ValueError."""
    if set(d) != set(SCHEMA["required"]):
        raise ValueError(f"поля: {sorted(d)}")
    if d["world"] not in WORLDS or d["hands"] not in HANDS or d["background"] not in BACKGROUNDS \
            or d["start_state"] not in STATES or d["end_state"] not in STATES:
        raise ValueError("enum (world/hands/background/state)")
    r = float(d["case_visible_ratio"])
    if not 0 <= r <= 1:
        raise ValueError("case_visible_ratio вне 0..1")
    bbox = [float(x) for x in d["case_bbox"]]
    if len(bbox) != 4 or any(not -0.01 <= x <= 1.01 for x in bbox):
        raise ValueError("case_bbox")
    if d["color"] not in COLORS or d["setting"] not in SETTINGS or d["action"] not in ACTIONS:
        raise ValueError("enum")
    if any(s not in STYLES for s in d["style_fit"]):
        raise ValueError("style_fit")
    hs = int(d["hero_score"])
    if not 0 <= hs <= 10:
        raise ValueError("hero_score вне 0..10")
    return {"case_visible_ratio": round(r, 3), "case_bbox": [round(min(max(x, 0), 1), 4) for x in bbox],
            "color": d["color"], "setting": d["setting"], "action": d["action"],
            "style_fit": sorted(set(d["style_fit"])), "hero_score": hs, "notes": str(d["notes"])[:200],
            "world": d["world"], "hands": d["hands"], "background": d["background"],
            "both_colors_in_frame": bool(d["both_colors_in_frame"]), "shows_inside": bool(d["shows_inside"]),
            "shows_profile": bool(d["shows_profile"]), "start_state": d["start_state"],
            "end_state": d["end_state"], "focus_ok": bool(d["focus_ok"])}


def _b64(p: Path) -> str:
    return base64.standard_b64encode(p.read_bytes()).decode("ascii")


def tag_shot(client, usage: Usage, frames: list[Path], effort: str = "low") -> dict:
    content = []
    for label, f in zip(("start", "middle", "end"), frames):
        content.append({"type": "text", "text": f"Frame: {label}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": _b64(f)}})
    content.append({"type": "text", "text": "Tag this shot."})
    last_err = None
    for _ in range(2):                                   # ответ + 1 повтор
        resp = client.beta.messages.create(
            model=usage.model,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        usage.add(resp)
        if resp.stop_reason == "refusal":
            last_err = "модель отказалась размечать кадр"
            continue
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            return validate(json.loads(text))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            last_err = f"ответ не по схеме: {e}"
    with usage._lock:
        usage.errors += 1
    raise VisionError(last_err or "нет ответа")
