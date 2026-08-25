"""场景资产生成（P0 资产层）：场景设定图提示词（模板 B）。

数据来源：剧本解析的场景 + 光影决策（决策引擎 表4）。
"""

from __future__ import annotations

from typing import Any, Dict, List


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
) -> List[Dict[str, str]]:
    """根据解析的场景列表 + 决策引擎的光影参数，生成场景资产。"""
    assets = []
    for sc in scenes:
        loc = sc.get("location", "")
        t = sc.get("time", "")
        if not loc or "未识别" in str(loc) or "未明确" in str(loc):
            continue
        assets.append(
            generate_scene_prompt(
                loc,
                t,
                lighting=params.get("光影", ""),
                mood=params.get("情绪基调", ""),
                model_id=model_id,
            )
        )
    return assets
