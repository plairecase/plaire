"""3D-планы (инструкция 3D, этап 2): вставка в монтаж без нарушения правил fix-02/fix-03."""
import json
import random
from pathlib import Path

from planner import worlds
from planner.templates import Ctx

ROOT = Path(__file__).resolve().parents[1]


def shot(i, color, action, start_state, end_state, inside=False, profile=False, world="gloves"):
    return {"file": {"name": f"IMG_{i}.MOV", "id": f"f{i}", "probe": {"hdr": False}},
            "shot": {"id": f"s{i}", "start": 0.0, "end": 6.0, "dur": 6.0, "metrics": {"text_luma": 0.7},
                     "vision": {"world": world, "color": color, "action": action, "shows_inside": inside,
                                "two_visible": False, "start_state": start_state, "end_state": end_state,
                                "hero_score": 2, "case_bbox": [0.3, 0.4, 0.4, 0.3], "setting": "studio",
                                "shows_profile": profile, "hands": "gloves", "both_colors_in_frame": False}}}


def ctx(force):
    texts = json.loads((ROOT / "texts.json").read_text())["items"]
    shots = [shot(1, "cognac", "open", "open", "open", inside=True), shot(2, "cognac", "close", "open", "closed"),
             shot(3, "cognac", "rotate", "closed", "closed", profile=True), shot(4, "cognac", "static", "closed", "closed"),
             shot(5, "cognac", "static", "closed", "closed")]
    return Ctx(shots, texts, random.Random(1), 30, 8, models={"cognac": "models/cognac.glb", "black": "models/black.glb"},
               tunes={"cognac": {"tint": 0.85}}, force3d=force,
               beats=[round(i * 0.5, 3) for i in range(60)])


def test_two_segments_inside_video():
    p = worlds.build(ctx(["s_two_colours", "s_profile"]), "p_gloves_pov", "organic")
    assert p is not None
    roles = [x["role"] for x in p.shots]
    threes = [x["three"] for x in p.shots if x.get("three")]
    assert set(threes) == {"s_two_colours", "s_profile"}
    assert not p.shots[0].get("three")                        # хук реальный
    assert roles[-1] == "loop"
    for a, b in zip(p.shots, p.shots[1:]):                    # 3D не подряд
        assert not (a.get("three") and b.get("three"))
    dur = sum(x["dur"] for x in p.shots)
    assert abs(dur / 2.0 - round(dur / 2.0)) < 1e-6          # целые такты (120 BPM: такт 2 с)
    assert p.three["share"] <= 0.3 + 1e-6
    assert p.checks["text_shot_match"] and p.checks["color_consistency"] and p.checks["3d_not_first"]
    layers = [l for l in p.props["threeD"] if l["type"] in ("two_colours", "profile")]
    assert {l["type"] for l in layers} == {"two_colours", "profile"}
    for l in layers:
        assert 1.2 <= l["durationInFrames"] / 30 <= 1.8
    two = next(l for l in layers if l["type"] == "two_colours")
    assert two["model"] != two["model2"]
    texts = {sc["text"] for sc in p.props["screens"] if sc.get("three")}
    assert texts == {"Two colours.", "Ultra-slim."}
    assert len(p.segments) == len(p.props["clips"])          # 3D не режется из исходников


def test_no_3d_by_default():
    p = worlds.build(ctx([]), "p_gloves_pov", "organic")
    assert p is not None and not p.three["segment"]
