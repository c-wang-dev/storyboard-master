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
    out = {}
    for key, allowed in mapping.items():
        val = str(features.get(key, "")).strip()
        # 精确匹配或包含匹配
        match = next((a for a in allowed if a in val), val)
        out[key] = match
    # content_type 需要映射到节奏表能用的词
    ct = str(features.get("content_type", "")).strip()
    ct_map = {"对白": "对白", "动作": "动作", "冲突": "动作", "追击": "动作",
              "情绪": "情绪戏", "环境": "情绪戏", "悬念": "悬念", "揭示": "悬念", "高潮": "爆发"}
    out["content_type"] = ct_map.get(ct, ct)
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
