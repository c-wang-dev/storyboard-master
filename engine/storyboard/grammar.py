"""电影语法判断（P1 语法层）：步骤 0 电影语法 + 景别序列 + 运镜匹配 + 构图匹配。

数据来源：电影语言的语法核心规则.md 检查清单 + 决策引擎。
"""

from __future__ import annotations

from typing import Any, Dict, List

# 内容类型 → 语法场景类型 → 景别序列（镜头级递进）
SHOT_SEQUENCES: Dict[str, Dict[str, Any]] = {
    "悬念": {
        "场景类型": "静态情绪 + 悬念",
        "景别序列": ["大远景", "全景", "特写"],  # 递进，特写有情绪动机（威胁揭晓）
        "运镜": "缓慢推近 + 上摇",
        "构图": "E 类三分法 + 引导线；D 类俯仰对比",
        "节奏": "慢（蓄力）",
    },
    "揭示": {
        "场景类型": "揭示 / 转折",
        "景别序列": ["全景", "近景", "大特写"],
        "运镜": "推近 + 停帧",
        "构图": "B 类负空间 + D 类视角",
        "节奏": "慢（蓄力）",
    },
    "对白": {
        "场景类型": "对话（对峙变体）",
        "景别序列": ["全景", "近景", "特写", "大特写"],  # 全景锚定 → 特写情绪/道具
        "运镜": "固定机位 + 仰拍",
        "构图": "D 类视角心理 + B 类背拍留白",
        "节奏": "中（留气口）",
    },
    "动作": {
        "场景类型": "动作场面",
        "景别序列": ["全景", "近景", "中景", "大特写", "全景", "中景"],  # 起势→顶点→受击
        "运镜": "手持跟拍 + 快速推近",
        "构图": "C 类动作冲突（对角线 + 中轴分割）",
        "节奏": "快（1-2 秒/镜，动作匹配）",
    },
    "情绪": {
        "场景类型": "静态情绪",
        "景别序列": ["全景", "近景", "特写"],
        "运镜": "固定 + 慢推",
        "构图": "B 类人物关系 + 负空间",
        "节奏": "慢",
    },
    "环境": {
        "场景类型": "establishing / 空间展示",
        "景别序列": ["大远景", "全景"],
        "运镜": "摇 / 航拍",
        "构图": "E 类基础空间（三分法 + 引导线）",
        "节奏": "慢",
    },
}

# 人物数量 → 机位语法提示
CHARACTER_GRAMMAR: Dict[str, str] = {
    "1": "单人：主观 POV 或客观交代；特写需情绪动机",
    "2": "双人：外反拍/内反拍/过肩；保持关系线一侧",
    "3": "三人：三角形布局 + 枢轴演员",
    "4+": "群像：主镜头先行 → 局部切入 → 反应镜头",
}


def judge_grammar(features: Dict[str, str], characters: List[str]) -> Dict[str, Any]:
    """步骤 0 电影语法判断：场景类型 / 景别序列 / 机位语法 / 越轴提示。"""
    content_type = features.get("content_type", "")
    # content_type 到语法场景类型的映射（parser 输出可能是"动作/对白/情绪/环境/悬念/揭示/情绪戏"）
    kind = content_type
    if "对白" in content_type:
        kind = "对白"
    elif "动作" in content_type or "冲突" in content_type or "追击" in content_type:
        kind = "动作"
    elif "悬念" in content_type or "揭示" in content_type:
        kind = "悬念" if "悬念" in content_type else "揭示"
    elif "情绪" in content_type or "环境" in content_type:
        kind = "情绪"
    elif "环境" in content_type:
        kind = "环境"

    seq = SHOT_SEQUENCES.get(kind, SHOT_SEQUENCES["情绪"])

    # 收尾检测：运镜目的=离开 → 段落结束，用"近→远释放"序列
    if features.get("move_purpose") == "离开":
        seq = {
            "场景类型": "段落收尾",
            "景别序列": ["大远景", "中全景"],
            "运镜": "拉远 + 固定",
            "构图": "逆光剪影",
            "节奏": "慢（留白）",
        }

    n = len(characters)
    n_key = "1" if n <= 1 else ("2" if n == 2 else ("3" if n == 3 else "4+"))
    machine = CHARACTER_GRAMMAR.get(n_key, CHARACTER_GRAMMAR["2"])

    # 越轴提示
    axis_risk = "无越轴风险（单一纵深轴线）" if n <= 2 else "多人物注意轴线：用中性镜头过渡"

    return {
        "场景类型": seq["场景类型"],
        "人物数量": n,
        "机位语法": machine,
        "景别序列": seq["景别序列"],
        "运镜": seq["运镜"],
        "构图": seq["构图"],
        "节奏": seq["节奏"],
        "越轴提示": axis_risk,
        "匹配原则": "位置匹配 + 动作匹配 + 视线匹配（切点在动作中段）",
    }


def expand_shots(sequence: List[str], keyframes: int) -> List[str]:
    """把景别序列按图数展开为逐帧景别（循环使用序列，保持递进感）。"""
    if keyframes <= 0:
        return []
    shots = []
    for i in range(keyframes):
        shots.append(sequence[i % len(sequence)])
    return shots
