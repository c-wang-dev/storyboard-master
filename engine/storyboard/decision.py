"""确定性决策引擎：六维特征 → 五张决策表 → 仲裁 → 档位 → 图数。

纯规则、零 API、可测试。同样的输入永远得到同样的输出（分镜大师核心卖点）。
"""

from __future__ import annotations

from typing import Any, Dict, List


def _lookup(table: List[Dict[str, str]], key_col: str, value: str, out_col: str) -> str | None:
    """在决策表中按 key_col=value 精确匹配，返回 out_col 的值。"""
    if not value:
        return None
    for row in table:
        if row.get(key_col, "").strip() == value.strip():
            return row.get(out_col, "").strip() or None
    # 宽松匹配：候选键包含输入值（如输入"环境"命中"环境 / 世界观 / 位置"）
    for row in table:
        cand = row.get(key_col, "").strip()
        if cand and value and value in cand:
            return row.get(out_col, "").strip() or None
    return None


def decide(features: Dict[str, str], knowledge: Dict[str, Any]) -> Dict[str, Any]:
    """根据六维特征查五张决策表，输出视听参数包。

    features 字段（来自 parser，或使用者手工指定）：
        info_focus   信息焦点：环境/关系/动作/情绪/细节
        power        权力关系：强势/弱势/对等/主观/失衡
        move_purpose 运动目的：追击/聚焦/离开/关联/不安/对峙
        emotion_tone 情绪基调：压抑/希望/神秘/悲怆/威胁
        content_type 内容类型：对白/动作/情绪/环境/悬念/揭示
        emotion      情绪强度：平静/紧张/爆发
        pace         节奏倾向：快/慢/中
    """
    tables = knowledge.get("tables", {})

    # 五表查表（每张表独立，输入维度不同，天然少冲突）
    params = {
        "景别": _lookup(tables.get("shot", []), "信息焦点", features.get("info_focus", ""), "决策景别"),
        "角度": _lookup(tables.get("angle", []), "权力关系", features.get("power", ""), "决策角度"),
        "运镜": _lookup(tables.get("move", []), "运动目的", features.get("move_purpose", ""), "决策运镜"),
        "光影": _lookup(tables.get("light", []), "情绪基调", features.get("emotion_tone", ""), "决策光影"),
    }

    # 节奏表：按内容类型 + 情绪强度
    rhythm = _lookup(tables.get("rhythm", []), "情绪强度 / 内容", features.get("content_type", ""), "决策节奏")
    if not rhythm:
        rhythm = _lookup(tables.get("rhythm", []), "情绪强度 / 内容", features.get("emotion", ""), "决策节奏")
    params["节奏"] = rhythm

    # 仲裁：情绪基调 > 信息层级 > 权力关系
    # 冲突场景：情绪强（紧张/爆发）时景别向近景/特写让步（情绪优先）
    emotion = features.get("emotion", "")
    if emotion in ("紧张", "爆发") and params.get("景别"):
        if "远景" in params["景别"] or "全景" in params["景别"]:
            params["景别"] = "近景 / 特写"  # 情绪优先，覆盖信息层级
    if emotion == "爆发" and params.get("运镜") == "拉远":
        params["运镜"] = "快速剪辑 + 特写堆叠"  # 情绪压倒运动目的

    return params


def select_duration(info_point_count: int) -> str:
    """三档选档：按信息点数定档位（5s / 10s / 15s）。"""
    if info_point_count <= 1:
        return "5s"
    if info_point_count <= 3:
        return "10s"
    return "15s"


def count_keyframes(duration: str, pace: str, move_type: str = "固定机位") -> int:
    """档位 × 节奏交叉表定图数，再按运镜复杂度修正。

    pace: 慢 / 中 / 快
    """
    table = {
        "5s": {"慢": (1, 2), "中": (2, 2), "快": (3, 6)},
        "10s": {"慢": (2, 4), "中": (3, 5), "快": (5, 10)},
        "15s": {"慢": (4, 8), "中": (5, 8), "快": (10, 20)},
    }
    lo, hi = table.get(duration, table["10s"]).get(pace, table["10s"]["中"])

    # 运镜复杂度修正：固定 1 张 / 简单运镜 2 张 / 复杂 3 张 / 动作 2-3 张
    move_map = {
        "固定机位": (1, 1),
        "推近": (2, 2),
        "拉远": (2, 2),
        "摇": (2, 2),
        "跟 / 移": (2, 3),
        "手持": (2, 3),
    }
    mlo, mhi = move_map.get(move_type, (1, 3))
    lo = max(lo, mlo)
    hi = min(hi, mhi)
    # 若修正后下界超过上界，取上界（防止 5s 快节奏 + 复杂运镜超界）
    return max(lo, min(hi, max(lo, mlo))) if lo > hi else max(lo, min(hi, max(lo, mlo)))


def video_segments(duration: str) -> Dict[str, int]:
    """视频工具换算：档位 → 段数与首尾帧数。"""
    table = {
        "5s": {"segments": 1, "frames": 2},
        "10s": {"segments": 2, "frames": 4},
        "15s": {"segments": 3, "frames": 6},
    }
    return table.get(duration, table["10s"])
