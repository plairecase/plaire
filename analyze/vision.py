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
    },
    "required": ["case_visible_ratio", "case_bbox", "color", "setting", "action", "style_fit",
                 "hero_score", "notes"],
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


def make_client():
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise VisionError("нет ANTHROPIC_API_KEY: разметка зрением невозможна")
    return anthropic.Anthropic(max_retries=4)


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


def validate(d: dict) -> dict:
    """Проверка и нормализация ответа. Ошибка → ValueError."""
    if set(d) != set(SCHEMA["required"]):
        raise ValueError(f"поля: {sorted(d)}")
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
            "style_fit": sorted(set(d["style_fit"])), "hero_score": hs, "notes": str(d["notes"])[:200]}


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
