"""提示词生成器：按模型卡模板组装提示词包。

生图模型：自然语言完整句子（主体 → 场景 → 光线 → 构图 → 画质）
生视频模型：三层结构（一句话概述 + 分镜时间戳 + 一致性说明）
"""

from __future__ import annotations

from typing import Any, Dict


_BRANDS = ["seedream", "seedance", "flux", "kling", "qwen", "wanxiang", "image"]


def _brand(model_id: str) -> str:
    for b in _BRANDS:
        if b in model_id.lower():
            return b
    return ""


def _card(cards: Dict[str, Dict[str, str]], model_id: str) -> Dict[str, str]:
    """按 model_id（如 seedream-5.0-pro / seedance-2.5）匹配模型卡。

    匹配顺序：① 规范化子串精确命中（key 或"模型ID"字段）；② 品牌关键词命中；③ 回退第一张。
    """
    norm = model_id.lower().replace("-", "").replace(".", "")
    for key, card in cards.items():
        if norm in key.lower() or norm in str(card.get("模型ID", "")).lower().replace("-", "").replace(".", ""):
            return card
    brand = _brand(model_id)
    if brand:
        for key, card in cards.items():
            hay = (key + str(card.get("模型ID", "")) + str(card.get("name", ""))).lower()
            if brand in hay:
                return card
    first = next(iter(cards.values()))
    first = dict(first)
    first["_fallback"] = True
    return first


def _join(items) -> str:
    return "，".join(str(x) for x in items if x)


def generate_image_prompt(
    features: Dict[str, str], params: Dict[str, str], card: Dict[str, str],
    subject: str = "主体人物", scene: str = "场景",
) -> str:
    """生图提示词：按模型卡公式组装自然语言句子。"""
    light = params.get("光影", "")
    comp = params.get("景别", "") + params.get("角度", "")
    move = params.get("运镜", "")
    formula = card.get("提示词公式", "主体 → 场景 → 光线 → 构图 → 画质")
    _ = formula  # 公式用于人工核对，此处按通用顺序组装

    parts = [
        f"{subject}位于{scene}",
        f"{light}光影" if light else None,
        f"{comp}景别视角" if comp else None,
        f"{move}运镜" if move else None,
        "写实电影质感，电影级摄影",
    ]
    return _join(parts) + "。"


def generate_video_prompt(
    features: Dict[str, str], params: Dict[str, str], card: Dict[str, str],
    subject: str = "主体人物", scene: str = "场景", action: str = "行动",
) -> str:
    """生视频提示词：三层结构（概述 + 时间戳分镜 + 一致性）。"""
    light = params.get("光影", "")
    move = params.get("运镜", "")
    duration = features.get("duration", "5s")

    overview = f"{subject}在{scene}中{action}，{light}氛围"
    storyboard_line = f"0-{duration}：{move}运镜，{params.get('景别', '中景')}，{action}"
    consistency = "保持角色外观、服装与首帧一致（参考图机制）"

    if "三层结构" in card.get("写法", ""):
        return f"{overview}。分镜时间戳：{storyboard_line}。一致性：{consistency}。"
    return f"{overview}。{storyboard_line}。{consistency}。"


def generate_prompt_pack(
    parsed: Dict[str, Any],
    params: Dict[str, str],
    cards: Dict[str, Dict[str, str]],
    model_id: str,
) -> Dict[str, Any]:
    """生成完整提示词包。"""
    card = _card(cards, model_id)
    features = parsed.get("features", {})

    # 从解析结果提取主体 / 场景 / 动作（LLM 版有真实值；规则版用占位）
    characters = parsed.get("characters", [])
    scenes = parsed.get("scenes", [])
    actions = parsed.get("actions", [])
    subject = "、".join(characters[:3]) if characters else "主体人物"
    loc = scenes[0].get("location", "") if scenes else ""
    if not loc or "未识别" in loc:
        scene = "场景"
    else:
        scene = loc
        if scenes[0].get("time") and "未识别" not in str(scenes[0].get("time", "")):
            scene = f"{scenes[0].get('time')}的{scene}"
    action = actions[0] if actions else "行动"
    card_type = card.get("类型", "生图")

    if card_type == "生视频":
        prompt = generate_video_prompt(features, params, card, subject, scene, action)
    else:
        prompt = generate_image_prompt(features, params, card, subject, scene)

    negative = ""
    if "支持" in card.get("负面词", ""):
        neg_items = [n["negative_word"] for n in params.get("negative_a", [])]
        negative = ", ".join(neg_items) if neg_items else ""

    return {
        "model_id": card.get("模型ID", model_id),
        "model_name": card.get("name", model_id),
        "type": card_type,
        "prompt": prompt,
        "negative_prompt": negative,
        "params": {
            "景别": params.get("景别"),
            "角度": params.get("角度"),
            "运镜": params.get("运镜"),
            "光影": params.get("光影"),
            "节奏": params.get("节奏"),
            "duration": features.get("duration", "5s"),
            "keyframes": features.get("keyframes"),
        },
        "consistency": card.get("一致性", "参考图机制"),
    }
