"""场景资产生成（P0 资产层）：场景设定图提示词（模板 B）。

数据来源：剧本解析的场景 + 光影决策（决策引擎 表4）。
"""

from __future__ import annotations

from typing import Any, Dict, List

# 场景名归一化：LLM 解析波动产生的同义词 → 标准名（防场景锚点漂移）
SCENE_NORM = {
    "屋顶": "屋脊",
    "房顶": "屋脊",
    "屋檐": "屋脊",
    "屋脊/月下": "屋脊",
    "月下屋脊": "屋脊",
    "长街": "古镇青石长街",
    "青石街": "古镇青石长街",
    "古镇街道": "古镇青石长街",
}


def normalize_location(loc: str) -> str:
    """场景地点归一化：精确匹配优先，其次包含匹配。"""
    if loc in SCENE_NORM:
        return SCENE_NORM[loc]
    for k, v in SCENE_NORM.items():
        if k in loc:
            return v
    return loc


def generate_scene_prompt(
    location: str, time: str, lighting: str, mood: str, model_id: str,
) -> Dict[str, str]:
    """场景设定图提示词（模板 B：时代/建筑/材质/光影/情绪）。"""
    loc = location or "an undefined space"
    t = time or "night"
    light = lighting or "even ambient lighting"
    mood_word = mood or "neutral"

    prompt = (
        f"A wide establishing shot of {loc}, {t}, {light}, {mood_word} atmosphere, "
        f"cinematic composition, rule of thirds, film grain, DSLR."
    )
    return {
        "类型": "场景设定图",
        "模型": model_id,
        "场景": loc,
        "时间": t,
        "光影": light,
        "情绪基调": mood_word,
        "提示词": prompt,
        "比例": "16:9",
        "尺寸": "2K",
        "负面词": "deformed architecture, text, watermark, people, daylight, warm colors",
    }


def build_scene_assets(
    scenes: List[Dict[str, Any]],
    params: Dict[str, str],
    model_id: str,
    mood: str = "",
) -> List[Dict[str, str]]:
    """根据解析的场景列表 + 决策引擎的光影参数，生成场景资产。

    mood 为情绪基调（来自 features.emotion_tone，非决策输出）。
    地点先归一化（屋顶/房顶→屋脊），同地点+时间去重。
    """
    assets = []
    seen = set()
    for sc in scenes:
        loc = normalize_location(str(sc.get("location", "")).strip())
        t = str(sc.get("time", "")).strip()
        if not loc or "未识别" in loc or "未明确" in loc or "未知" in loc:
            continue
        key = f"{loc}|{t}"
        if key in seen:
            continue
        seen.add(key)
        assets.append(
            generate_scene_prompt(
                loc,
                t,
                lighting=params.get("光影", ""),
                mood=mood,
                model_id=model_id,
            )
        )
    return assets
