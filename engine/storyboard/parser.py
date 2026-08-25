"""剧本解析器：LLM 语义解析（OpenAI 兼容协议）→ 结构化 JSON。

零第三方依赖：用标准库 urllib 直接调 OpenAI 兼容接口（DeepSeek / OpenAI / 通义等）。
未配置 API Key 或调用失败时，自动降级为规则解析（正则提取场景/对白/动作）。
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

_PARSE_SYSTEM_PROMPT = """你是一名影视分镜分析专家。请把用户提供的剧本片段解析为结构化 JSON。

【content_type 判别规则（核心字段，务必准确）】
content_type 决定后续镜头语言，必须从 6 类中选一个，不要自创、不要输出复合词（若混合多种，只填"主导类型"）：

1. 对白 —— 核心是人物对话/台词交锋，肢体动作只是辅助。判据：去掉台词，信息量大幅流失。
2. 动作 —— 核心是连续爆发、快节奏的肢体动作/打斗/追逐/位移。判据：动作是主体且节奏快。
3. 情绪 —— 核心是人物内心情绪的静态呈现（眼神/沉默/表情），无台词或极少。判据：镜头聚焦"反应"而非"行为"。
4. 环境 —— 核心是空镜/场景交代/氛围营造，人物非主体或不在场。判据：镜头主语是"空间"而非"人"。
5. 悬念 —— 核心是"蓄力/铺垫/未知逼近"，节奏慢，目的是制造紧张期待。判据：即使有动作，只要动作目的是"蓄势待发"而非"爆发"，就判悬念（如缓缓拔刀、手搭刀柄、慢动作逼近）。
6. 揭示 —— 核心是"关键信息/真相的揭晓/转折"。判据：镜头服务于"让观众看见某个关键东西"。

判别铁律（避免误判成"动作"）：
- 有动作但目的是"蓄力/铺垫" → 悬念
- 动作已收束、主体转为对白或反应 → 对白 或 情绪
- 只有连续爆发的快节奏肢体对抗 → 动作

示例（内容类型判定）：
- "甲：你终于来了。乙：我来取回属于我的东西。" → 对白
- "甲挥刀劈下，乙侧身闪过，反手一剑刺出。" → 动作
- "她望着窗外的雨，泪水无声滑落。" → 情绪
- "清晨的山谷，薄雾笼罩，远处传来鸟鸣。" → 环境
- "黑暗中，一只手缓缓搭上刀柄，刀光在指缝间若隐若现。" → 悬念
- "他掀开黑布，刀下躺着的，竟是自己的亲兄弟。" → 揭示

输出格式（严格 JSON，不要多余文字）：
{
  "scenes": [{"location": "地点", "time": "时间/氛围"}],
  "characters": ["角色名列表"],
  "dialogues": [{"speaker": "角色", "text": "台词"}],
  "actions": ["动作/事件列表"],
  "features": {
    "content_type": "对白|动作|情绪|环境|悬念|揭示",
    "info_focus": "环境|关系|动作|情绪|细节",
    "emotion": "平静|紧张|爆发",
    "power": "强势|弱势|对等|主观|失衡",
    "move_purpose": "追击|聚焦|离开|关联|不安|对峙",
    "emotion_tone": "压抑|希望|神秘|悲怆|威胁",
    "pace": "快|慢|中",
    "info_point_count": 信息点数(整数)
  }
}
"""

# content_type 归一化：标准类型 → 同义词/子类（包含匹配用）
_CONTENT_TYPE_MAP = [
    ("对白", ["对白", "对话", "台词", "文戏"]),
    ("动作", ["动作", "冲突", "追击", "打斗", "战斗", "武戏", "追逐", "高潮", "爆发"]),
    ("情绪", ["情绪", "心理", "内心"]),
    ("环境", ["环境", "空镜", "场景", "氛围", "交代"]),
    ("悬念", ["悬念", "蓄力", "铺垫", "蓄势"]),
    ("揭示", ["揭示", "揭晓", "转折", "反转", "真相"]),
]


def _normalize_content_type(ct: str) -> str:
    """把 LLM 任意 content_type 归一化到 6 类标准集（对白/动作/情绪/环境/悬念/揭示）。

    处理复合类型（"动作收束+对白" 取主导词）、近义词（"对话"→对白、"蓄力"→悬念）。
    """
    if not ct:
        return "动作"
    s = str(ct).strip()
    # 拆复合类型，取第一个主导词（prompt 已要求主导类型唯一，此处兜底）
    main = re.split(r"[+＋、,，/／\s]", s)[0].strip() or s
    for std, aliases in _CONTENT_TYPE_MAP:
        if any(a in main for a in aliases):
            return std
    return "动作"


def parse_script(
    script: str,
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """解析剧本。有 API Key 走 LLM，否则降级规则解析。"""
    if api_key:
        try:
            return _parse_with_llm(script, api_key, base_url, model)
        except Exception as e:
            # 调用失败 → 降级，附错误说明（不阻塞主流程）
            result = _parse_with_rules(script)
            result["degraded"] = f"llm_error: {e}"
            return result
    result = _parse_with_rules(script)
    result["degraded"] = "no_api_key"
    return result


def _parse_with_llm(script: str, api_key: str, base_url: str, model: str) -> Dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": script[:6000]},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    data = json.loads(content)
    # 归一化特征
    features = data.get("features", {})
    data["features"] = _normalize_features(features)
    data["raw"] = script
    return data


def _normalize_features(features: Dict[str, Any]) -> Dict[str, str]:
    """把 LLM 可能给出的任意值归一化到决策表能查的候选集。"""
    mapping = {
        "info_focus": ["环境", "关系", "动作", "情绪", "细节"],
        "emotion": ["平静", "紧张", "爆发"],
        "power": ["强势", "弱势", "对等", "主观", "失衡"],
        "move_purpose": ["追击", "聚焦", "离开", "关联", "不安", "对峙"],
        "emotion_tone": ["压抑", "希望", "神秘", "悲怆", "威胁"],
        "pace": ["快", "慢", "中"],
    }
    # 同义词归一化：LLM 可能输出候选集外的近义词（如悬念场景的"蓄势"）
    synonyms = {
        "move_purpose": {
            "蓄势": "聚焦", "蓄力": "聚焦", "铺垫": "聚焦", "逼近": "聚焦",
            "僵持": "对峙", "威压": "对峙", "静止": "对峙",
            "追逐": "追击", "跟随": "追击", "跟踪": "追击",
            "收束": "离开", "结束": "离开", "远去": "离开",
            "慌乱": "不安",
        },
    }
    out = {}
    for key, allowed in mapping.items():
        val = str(features.get(key, "")).strip()
        # 先同义词替换，再精确/包含匹配
        for syn, std in synonyms.get(key, {}).items():
            if syn in val:
                val = std
                break
        match = next((a for a in allowed if a in val), val)
        out[key] = match
    # content_type 归一化到 6 类标准集（对白/动作/情绪/环境/悬念/揭示）
    out["content_type"] = _normalize_content_type(features.get("content_type", ""))
    try:
        out["info_point_count"] = int(features.get("info_point_count", 2))
    except (TypeError, ValueError):
        out["info_point_count"] = 2
    return out


def _parse_with_rules(script: str) -> Dict[str, Any]:
    """规则降级解析：正则提取基本结构 + 默认特征（保证零 API 可跑）。"""
    lines = [l.strip() for l in script.splitlines() if l.strip()]
    dialogues = []
    actions = []
    characters: List[str] = []
    for line in lines:
        m = re.match(r"^([\u4e00-\u9fa5A-Za-z0-9]{1,6})[：:]\s*(.+)$", line)
        if m and len(line) < 60:
            speaker, text = m.group(1), m.group(2)
            dialogues.append({"speaker": speaker, "text": text})
            if speaker not in characters:
                characters.append(speaker)
        else:
            actions.append(line)

    info_points = len(dialogues) + len(actions)
    features = {
        "content_type": "对白" if dialogues else "动作",
        "info_focus": "情绪" if dialogues else "动作",
        "emotion": "平静",
        "power": "对等",
        "move_purpose": "聚焦" if dialogues else "对峙",
        "emotion_tone": "神秘" if dialogues else "压抑",
        "pace": "中",
        "info_point_count": max(info_points, 1),
    }
    return {
        "scenes": [{"location": "未识别（规则解析）", "time": "未识别"}],
        "characters": characters,
        "dialogues": dialogues,
        "actions": actions,
        "features": features,
        "raw": script,
    }
