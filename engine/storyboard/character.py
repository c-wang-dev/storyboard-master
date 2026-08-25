"""角色资产生成（P0 资产层）：正反派判定 → 性格范式匹配 → 角色锚定卡 → 定妆照/三视图提示词。

对应提示词模板.md 的模板 A1（定妆照）/ A2（三视图），数据来源：性格范式库.md。
支持项目角色绑定表覆盖：绑定角色用表内固定外观（单一来源），禁止 LLM 重新提取（防跨片段漂移）。
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Dict, List, Optional

_CHAR_SYSTEM_PROMPT = """你是影视角色分析专家。请从剧本中提取所有角色，并为每个角色匹配性格范式。

可选的 8 种性格范式（必须从中选一个，不要自创）：
反派系：阳奉阴违、背地阴狠、阴鸷深沉、暴戾外放、骄纵轻浮
正派系：隐忍坚毅、豪爽直率、温润儒雅

输出严格 JSON：
{
  "characters": [
    {
      "name": "角色名",
      "alignment": "正派|反派",
      "archetype": "隐忍坚毅",
      "appearance": "年龄+体型+脸型+五官+发型发色+服装配饰的中文外观描述（一句话）"
    }
  ]
}
"""


def parse_binding_table(text: str) -> Dict[str, Dict[str, str]]:
    """解析项目角色绑定表 md：剧本角色名 → {范式, 外观}。

    外观是角色外观的单一来源——绑定角色禁止再走 LLM 提取（否则跨片段漂移）。
    """
    result: Dict[str, Dict[str, str]] = {}
    headers: List[str] = []
    in_table = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and "剧本角色名" in s:
            in_table = True
            headers = [h.strip() for h in s.strip("|").split("|")]
            continue
        if not in_table or not s.startswith("|") or s.startswith("|---"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < len(headers):
            continue
        row = dict(zip(headers, cells))
        name = row.get("剧本角色名", "").strip()
        if not name or name == "剧本角色名":
            continue
        archetype = row.get("角色锚定卡", "").strip()
        archetype = re.sub(r"[\[\]]", "", archetype)  # 去双链 [[]]
        if "§" in archetype:
            archetype = archetype.split("§")[-1].strip()
        appearance = row.get("外观（定妆照描述）", "").strip()
        result[name] = {"范式": archetype, "外观": appearance}
    return result


def extract_characters(
    script: str, api_key: Optional[str], base_url: str, model: str,
) -> List[Dict[str, str]]:
    """LLM 提取角色（名/正反派/范式/外观）。失败返回空列表（不阻塞）。"""
    if not api_key:
        return []
    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _CHAR_SYSTEM_PROMPT},
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
        return json.loads(body["choices"][0]["message"]["content"]).get("characters", [])
    except Exception:
        return []


def _match_archetype(name: str, archetypes: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """按范式名精确/模糊匹配。"""
    if name in archetypes:
        return archetypes[name]
    for key, arch in archetypes.items():
        if name and (name in key or key in name):
            return arch
    return None


def build_anchor_card(
    name: str, archetype: Dict[str, Any],
) -> Dict[str, str]:
    """生成角色锚定卡（全片常驻）。"""
    return {
        "角色名": name,
        "性格范式": f"{archetype.get('name')}（{archetype.get('alias')}）" if archetype.get("alias") else archetype.get("name"),
        "正反派": archetype.get("alignment", "未定"),
        "人格类型": archetype.get("核心特征", ""),
        "标志微表情": archetype.get("标志性微表情", ""),
        "情绪矩阵": json.dumps(archetype.get("emotion_matrix", {}), ensure_ascii=False),
        "英文提示词": archetype.get("英文提示词", ""),
        "禁止表演": archetype.get("禁止表演", ""),
        "常驻声明": "✓ 全片常驻",
    }


def generate_portrait_prompt(
    name: str, appearance: str, archetype: Dict[str, Any], model_id: str,
) -> Dict[str, str]:
    """定妆照提示词（模板 A1）。"""
    micro = archetype.get("标志性微表情", "")
    desc = appearance or "a distinctive character"
    prompt = (
        f"A front-facing character portrait, head and shoulders composition, looking at viewer: "
        f"{desc}, {micro}, even frontal lighting on the face, clean plain background, "
        f"portrait photography, 85mm lens, shallow depth of field."
    )
    return {
        "类型": "定妆照",
        "模型": model_id,
        "角色": name,
        "外观": appearance,
        "表情（锚定卡标志微表情）": micro,
        "提示词": prompt,
        "比例": "3:4",
        "尺寸": "2K",
        "负面词": "deformed, bad anatomy, extra fingers, smiling, exaggerated expression, open-mouth shouting",
        "一致性要点": "正脸、无遮挡、均匀打光，脸占画面 25-40% —— 此张即全片参考图母本",
    }


def generate_turnaround_prompt(
    name: str, appearance: str, model_id: str,
) -> Dict[str, str]:
    """三视图提示词（模板 A2，参考图驱动）。"""
    prompt = (
        f"A character turnaround reference of the same person, three separate views — "
        f"front, side, and back — identical face, hair and outfit in all views: "
        f"{appearance or 'a distinctive character'}, standing straight, arms at sides, "
        f"neutral calm expression, plain white background, reference sheet style, clean lines."
    )
    return {
        "类型": "三视图",
        "模型": model_id,
        "角色": name,
        "提示词": prompt,
        "一致性": "上传定妆照作参考图（Seedream 参考图 ≤10 张，用 1 张锁身份）",
        "比例": "16:9",
        "尺寸": "2K",
        "负面词": "deformed, bad anatomy, extra fingers, inconsistent face between views, different outfits",
        "备注": "三视图不硬出三格：逐视角生成，后期拼版",
    }


def build_character_assets(
    script: str,
    archetypes: Dict[str, Dict[str, Any]],
    model_id: str,
    api_key: Optional[str],
    base_url: str,
    llm_model: str,
    binding: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """完整角色资产：提取 → 锚定卡 → 定妆照 → 三视图。

    binding: 项目角色绑定表解析结果 {角色名: {范式, 外观}}。
    绑定的角色用固定范式+外观（单一来源，防跨片段漂移）；未绑定角色走 LLM 提取。
    """
    binding = binding or {}
    chars = extract_characters(script, api_key, base_url, llm_model)
    assets = []
    for c in chars:
        name = c.get("name", "未命名角色")
        b = binding.get(name)
        if b:
            arch = _match_archetype(b.get("范式", ""), archetypes)
            if not arch:
                continue
            appearance = b.get("外观", "") or c.get("appearance", "")
        else:
            arch = _match_archetype(c.get("archetype", ""), archetypes)
            if not arch:
                continue
            appearance = c.get("appearance", "")
        assets.append({
            "name": name,
            "alignment": arch.get("alignment"),
            "archetype": arch.get("name"),
            "anchor_card": build_anchor_card(name, arch),
            "portrait": generate_portrait_prompt(name, appearance, arch, model_id),
            "turnaround": generate_turnaround_prompt(name, appearance, model_id),
            "appearance": appearance,
            "bound": name in binding,  # 标记是否来自绑定表（单一来源）
        })
    return assets
