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
    """按 model_id（如 seedream-image-v5.0-pro / dreamina-seedance-2-5-260628）匹配模型卡。

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


def _audio_recipe(content_type: str, dialogues: list) -> str:
    """按片段类型取音频配方（音频指令配方库 表二）。台词逐字用剧本原文。"""
    dlg_lines = []
    for d in (dialogues or [])[:3]:
        tx = str(d.get("text", "")).strip()
        if tx:
            dlg_lines.append(f'Dialogue:"{tx}"')
    if content_type == "对白":
        base = "No BGM（台词驱动，压 BGM）"
        return ("；".join(dlg_lines) + "，" + base) if dlg_lines else base
    if content_type == "动作":
        return "No BGM，动作音效为主（金属碰撞/破风声，剪辑点踩命中帧）"
    if content_type == "悬念":
        return "No BGM 或极低频氛围乐（蓄力静默，收尾一刀声）"
    if content_type in ("情绪", "环境"):
        return "BGM 描述（氛围乐铺底/渐弱收尾），无对白"
    return "No BGM"


def _time_blocks(content_type: str, duration: str, move: str, shot: str, action: str) -> str:
    """细化时间戳：按片段类型分 2-4 段（对齐原版模板 D）。"""
    try:
        num = int(str(duration).replace("s", "").strip())
    except (TypeError, ValueError):
        num = 10
    if content_type == "动作":
        pts = [(0, num // 5), (num // 5, num * 3 // 5), (num * 3 // 5, num)]
    elif content_type == "对白":
        pts = [(0, num * 3 // 10), (num * 3 // 10, num * 6 // 10), (num * 6 // 10, num)]
    else:
        pts = [(0, num // 2), (num // 2, num)]
    seg = []
    for a, b in pts:
        if b > a:
            seg.append(f"[{a}-{b}s] {move}运镜，{shot}，{action}")
    return "；".join(seg)


def generate_video_prompt(
    features: Dict[str, str], params: Dict[str, str], card: Dict[str, str],
    subject: str = "主体人物", scene: str = "场景", action: str = "行动",
    dialogues: list = None,
) -> str:
    """生视频提示词：对齐模板 D 六块（一句话/时间戳/对白/音频/一致性）。"""
    light = params.get("光影", "")
    move = params.get("运镜", "")
    duration = features.get("duration", "5s")
    content_type = str(features.get("content_type", "")).strip()

    overview = f"{subject}在{scene}中{action}，{light}氛围"
    blocks = _time_blocks(content_type, duration, move, params.get("景别", "中景"), action)
    audio = _audio_recipe(content_type, dialogues)
    dlg = ""
    if content_type == "对白":
        dlg_lines = [f'{d.get("speaker", "")}:"{d.get("text", "")}"'
                     for d in (dialogues or [])[:2] if d.get("speaker") and d.get("text")]
        if dlg_lines:
            dlg = "；".join(dlg_lines)
    consistency = "首帧 @Image1 = 对应分镜图；参考图=角色定妆照+场景设定图（锁身份/服装/场景）"

    parts = [f"【一句话】{overview}", f"【分镜时间戳】{blocks}"]
    if dlg:
        parts.append(f"【对白】{dlg}")
    parts.append(f"【音频】{audio}")
    parts.append(f"【一致性】{consistency}")
    return "。".join(parts) + "。"


def generate_prompt_pack(
    parsed: Dict[str, Any],
    params: Dict[str, str],
    cards: Dict[str, Dict[str, str]],
    model_id: str,
    negative_a: list = None,
) -> Dict[str, Any]:
    """生成完整提示词包。negative_a 为负面词列表（来自知识库决策引擎 A 层）。"""
    card = _card(cards, model_id)
    features = parsed.get("features", {})

    # 从解析结果提取主体 / 场景 / 动作（LLM 版有真实值；规则版用占位）
    characters = parsed.get("characters", [])
    scenes = parsed.get("scenes", [])
    dialogues = parsed.get("dialogues", [])
    actions = parsed.get("actions", [])
    subject = "、".join(characters[:3]) if characters else "主体人物"
    loc = scenes[0].get("location", "") if scenes else ""
    if not loc or "未识别" in loc or "未明确" in loc or "未知" in loc or loc == "null":
        scene = "场景"
    else:
        scene = loc
        t = str(scenes[0].get("time", "")) if scenes else ""
        if t and "未识别" not in t and "未明确" not in t and "未知" not in t and t != "null":
            scene = f"{t}的{scene}"
    # 对白场景动作取台词（谁道：说什么）；否则用 actions
    action = actions[0] if actions else ""
    if not action and dialogues:
        d0 = dialogues[0]
        sp = str(d0.get("speaker", "")).strip()
        tx = str(d0.get("text", "")).strip()
        if sp and tx:
            action = f"{sp}道：{tx}"
    if not action:
        action = "行动"
    card_type = card.get("类型", "生图")

    if card_type == "生视频":
        prompt = generate_video_prompt(
            features, params, card, subject, scene, action,
            dialogues=dialogues,
        )
    else:
        prompt = generate_image_prompt(features, params, card, subject, scene)

    negative = ""
    if "支持" in card.get("负面词", ""):
        neg_items = [n["negative_word"] for n in (negative_a or []) if n.get("negative_word")]
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
