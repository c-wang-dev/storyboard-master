"""帧级输出层（P2）：逐帧提示词 + 一致性建议 + 参数块。

把语法层的景别序列展开为逐帧输出：每张关键帧一条自然语言提示词，
附按模型分档的一致性建议（参考图 / 首帧 / LoRA）与参数块。

数据来源：提示词模板.md 模板 C + 多帧一致性策略库.md + 参数速查表.md。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _extract_subject_scene(parsed: Dict[str, Any]) -> Tuple[str, str]:
    """提取主体 / 场景描述（与 prompts.py 规则一致）。"""
    characters = parsed.get("characters", [])
    scenes = parsed.get("scenes", [])
    subject = "、".join(characters[:3]) if characters else "主体人物"
    loc = str(scenes[0].get("location", "")) if scenes else ""
    scene = "场景"
    if loc and "未识别" not in loc and "未明确" not in loc and loc != "null":
        scene = loc
        t = str(scenes[0].get("time", "")) if scenes else ""
        if t and "未识别" not in t and "未明确" not in t and t != "null":
            scene = f"{t}的{scene}"
    return subject, scene


def _character_lookup(character_assets: List[Dict[str, Any]]) -> Dict[str, str]:
    """构建 角色名 → 外貌锚定短语 映射（从定妆照外观 + 锚定卡微表情提取）。

    一致性关键：分镜帧提示词必须携带角色外貌描述，生图模型才知道
    「沈孤鸿长什么样、穿什么」——否则每次生成都是新脸，黎三/沈孤鸿同脸化。
    """
    mapping: Dict[str, str] = {}
    for c in character_assets or []:
        name = c.get("name", "")
        if not name:
            continue
        portrait = c.get("portrait", {}) or {}
        anchor = c.get("anchor_card", {}) or {}
        parts = []
        appearance = portrait.get("外观", "") or c.get("appearance", "")
        if appearance:
            parts.append(appearance)
        micro = anchor.get("标志微表情", "")
        if micro:
            # 只取第一段标志性微表情；情绪矩阵（悲伤时/愤怒时…）是表演参考，不进生图提示词
            micro_short = micro.split("；")[0].split(";")[0].strip()
            if len(micro_short) > 25:
                micro_short = micro_short[:25]
            if micro_short:
                parts.append(f"表情：{micro_short}")
        if parts:
            mapping[name] = "；".join(parts)
    return mapping


def _subject_with_appearance(subject: str, char_map: Dict[str, str]) -> str:
    """把「沈孤鸿、黎三」升级为「沈孤鸿（外貌锚定）、黎三（外貌锚定）」。"""
    names = [n.strip() for n in subject.split("、") if n.strip()]
    anchored = []
    for n in names:
        if n in char_map and char_map[n]:
            anchored.append(f"{n}（{char_map[n]}）")
        else:
            anchored.append(n)
    return "、".join(anchored)


def _frame_actions(parsed: Dict[str, Any], content_type: str) -> List[str]:
    """提取逐帧动作：动作/悬念用 actions 列表；对白场景用「说话人+台词」驱动表演。

    对白帧必须携带台词/表演信息——生图模型靠它画出「谁在说话、什么神态」，
    否则对白帧只剩两个干站着的人。
    """
    if content_type == "对白":
        dialogues = parsed.get("dialogues", [])
        lines = []
        for d in dialogues[:3]:
            sp = str(d.get("speaker", "")).strip()
            tx = str(d.get("text", "")).strip()
            if sp and tx:
                lines.append(f"{sp}道：{tx}")
        return lines or [""]
    actions = parsed.get("actions", [])
    return [a for a in actions if a] or [""]


def _action_at(actions: List[str], idx: int, total: int, content_type: str) -> str:
    """按帧取动作：动作场景三段式（起势→顶点→受击），其他循环分配。"""
    if not actions or not actions[0]:
        return ""
    if content_type == "动作" and total > 1 and len(actions) >= 3:
        if idx == 0:
            return actions[0]           # 起势
        if idx == total - 1:
            return actions[-1]          # 受击 / 收势
        return actions[len(actions) // 2]  # 动作顶点
    return actions[idx % len(actions)]


def _frame_prompt(
    subject: str, scene: str, action: str,
    shot: str, angle: str, move: str, light: str,
) -> str:
    """单帧提示词：主体位于场景 + 动作 + 景别角度 + 运镜 + 光影 + 画质。"""
    parts = [f"{subject}位于{scene}"]
    if action:
        parts.append(action)
    comp = f"{shot}{angle}" if angle else shot
    if comp:
        parts.append(f"{comp}景别视角")
    if move:
        parts.append(f"{move}运镜")
    if light:
        parts.append(f"{light}光影")
    parts.append("写实电影质感，电影级摄影")
    return "，".join(p for p in parts if p) + "。"


def _consistency_advice(card: Dict[str, str]) -> Dict[str, Any]:
    """按模型卡分档生成一致性建议（参考图 / 首帧 / LoRA）。"""
    model_id = str(card.get("模型ID", "")).lower()
    name = str(card.get("name", ""))
    ctype = card.get("类型", "生图")

    if ctype == "生视频":
        if "seedance" in model_id or "seedance" in name.lower():
            return {
                "机制": "首帧 + 参考图",
                "建议": [
                    "参考图：角色定妆照（同一张贯穿全分镜）",
                    "首帧 = 对应分镜图（@Image1 锁身份）",
                    "参考图 ≤30 张图，锁服装 / 场景",
                ],
            }
        if "kling" in model_id or "可灵" in name:
            return {
                "机制": "首帧（必须）+ element reference",
                "建议": [
                    "参考图：角色定妆照（同一张贯穿全分镜）",
                    "首帧必须（图生视频必加首帧图）",
                    "开启 element reference 锁角色",
                ],
            }
        return {
            "机制": "首帧 / 参考图 / LoRA",
            "建议": [
                "参考图：角色定妆照（同一张贯穿全分镜）",
                "首帧图 + 参考图；需要精确角色可 LoRA 微调",
            ],
        }

    # 生图
    if "flux" in model_id or "Flux" in name:
        return {
            "机制": "角色 LoRA + 图生图（定妆照锁脸 + 场景图锁场景）",
            "建议": [
                "参考图1：角色定妆照（同一张贯穿全分镜，锁脸源）",
                "参考图2：场景设定图（同场景多机位贯穿，锁场景全貌）",
                "角色 LoRA 0.6（训练 25-30 张）+ 图生图 denoise 0.75",
            ],
        }
    return {
        "机制": "参考图机制（定妆照锁脸 + 场景图锁场景）",
        "建议": [
            "参考图1：角色定妆照（同一张贯穿全分镜，锁脸源）",
            "参考图2：场景设定图（同场景多机位贯穿，锁场景全貌）",
            "上传定妆照+场景图作参考图（Seedream ≤10 张锁脸 / 服装 / 场景）",
        ],
    }


def _param_block(card: Dict[str, str], duration: str, keyframes: int) -> Dict[str, Any]:
    """参数块：从模型卡抽参数基线 + 本次档位 / 图数。"""
    return {
        "model_id": card.get("模型ID", ""),
        "model_name": card.get("name", ""),
        "类型": card.get("类型", "生图"),
        "档位": duration,
        "图数": keyframes,
        "比例": card.get("比例", "16:9"),
        "尺寸": card.get("尺寸", "2K"),
        "负面词": "支持" if "支持" in card.get("负面词", "") else "不用",
        "提示词公式": card.get("提示词公式", ""),
    }


def build_frames(
    parsed: Dict[str, Any],
    params: Dict[str, str],
    grammar_result: Dict[str, Any],
    shot_sequence: List[str],
    card: Dict[str, str],
    duration: str,
    keyframes: int,
    character_assets: Optional[List[Dict[str, Any]]] = None,
    scene_assets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """帧级输出：逐帧提示词（含角色外貌锚定）+ 一致性建议 + 参数块。

    character_assets / scene_assets 用于：
    - 帧提示词注入角色外貌描述（锁脸，防同脸化/服装漂移）
    - 一致性建议标注「定妆照 + 场景图」双参考图（锁场景全貌）
    """
    subject, scene = _extract_subject_scene(parsed)
    char_map = _character_lookup(character_assets)
    subject = _subject_with_appearance(subject, char_map)
    content_type = parsed.get("features", {}).get("content_type", "动作")
    actions = _frame_actions(parsed, content_type)

    angle = params.get("角度", "")
    move = params.get("运镜", "") or grammar_result.get("运镜", "")
    light = params.get("光影", "")
    total = len(shot_sequence) if shot_sequence else keyframes

    frames: List[Dict[str, Any]] = []
    for i in range(total):
        shot = shot_sequence[i] if i < len(shot_sequence) else shot_sequence[-1]
        action = _action_at(actions, i, total, content_type)
        frames.append({
            "index": i + 1,
            "shot": shot,
            "angle": angle,
            "action": action,
            "prompt": _frame_prompt(subject, scene, action, shot, angle, move, light),
        })

    return {
        "frames": frames,
        "consistency": _consistency_advice(card),
        "param_block": _param_block(card, duration, keyframes),
    }
