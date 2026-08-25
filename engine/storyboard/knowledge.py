"""知识库加载器：运行时解析 knowledge/*.md，保持"知识库单一来源"。

支持两种结构化格式：
1. Markdown 表格（决策表、交叉表、负面清单）
2. 字段列表（模型卡："- 字段：值"）
"""

from __future__ import annotations

import pathlib
import re
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Markdown 解析工具
# ---------------------------------------------------------------------------

def parse_md_table(block: str) -> List[Dict[str, str]]:
    """把一段含 Markdown 表格的文本解析为 list[dict]。

    | 表头A | 表头B |
    |-------|:-----:|
    | 值A1  | 值B1  |
    → [{"表头A": "值A1", "表头B": "值B1"}]
    """
    rows: List[List[str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # 跳过分隔行（如 |---|---| / |:---:|:---:|）
        if cells and all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    if not rows:
        return []
    header = rows[0]
    return [dict(zip(header, r)) for r in rows[1:] if len(r) == len(header)]


def split_by_heading(text: str) -> List[Dict[str, Any]]:
    """按标题（## 或 ### 开头）切分文档，返回 [{heading, body}]。"""
    pattern = re.compile(r"^(#{2,3})\s+(.*)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(
            {"level": len(m.group(1)), "heading": m.group(2).strip(), "body": text[m.end():end].strip()}
        )
    return sections


# ---------------------------------------------------------------------------
# 决策引擎知识加载（分镜决策引擎.md）
# ---------------------------------------------------------------------------

_TABLE_ALIAS = {
    "景别": "shot",
    "角度": "angle",
    "运镜": "move",
    "光影": "light",
    "节奏": "rhythm",
}


def load_decision_tables(kb_dir) -> Dict[str, Any]:
    """解析 分镜决策引擎.md → 决策表 / 仲裁 / 档位 / 图数 / 负面清单。"""
    path = pathlib.Path(kb_dir) / "分镜决策引擎.md"
    text = path.read_text(encoding="utf-8")

    result: Dict[str, Any] = {
        "tables": {},       # {shot/angle/move/light/rhythm: [ {表头:值} ]}
        "arbitration": [],  # 仲裁优先级
        "tiers": {},        # 档位定义（5s/10s/15s）
        "keyframes": {},    # 档位×节奏交叉表
        "negative_a": [],   # 负面词（A 层）
        "negative_b": [],   # 决策规避（B 层）
    }

    for sec in split_by_heading(text):
        heading, body = sec["heading"], sec["body"]

        # 五张决策表：### 表 1：景别表（...）
        m = re.match(r"表\s*\d+[：:]\s*(\S+?)表", heading)
        if m:
            key = _TABLE_ALIAS.get(m.group(1))
            if key:
                result["tables"][key] = parse_md_table(body)
            continue

        # 仲裁层
        if "仲裁" in heading:
            m = re.search(r"情绪基调\s*>\s*信息层级\s*>\s*权力关系", body)
            if m:
                result["arbitration"] = ["emotion", "info", "power"]
            continue

        # 三档选档表（5.1）
        if "选档" in heading:
            for row in parse_md_table(body):
                tier = row.get("档位", "").replace("s", "")
                if tier:
                    result["tiers"][tier] = row
            continue

        # 档位×节奏交叉表（5.2 定图数）
        if "定图数" in heading:
            for row in parse_md_table(body):
                tier = row.get("档位", "").replace("s", "")
                if tier:
                    result["keyframes"][tier] = row
            continue

        # 负面词 A 层 / B 层
        if heading.startswith("A 层"):
            result["negative_a"] = [
                {"negative_word": r.get("负面词", ""), "reason": r.get("规避的问题", "")}
                for r in parse_md_table(body)
                if r.get("负面词")
            ]
            continue
        if heading.startswith("B 层"):
            result["negative_b"] = [
                {"pattern": r.get("禁止模式", ""), "reason": r.get("原因", "")}
                for r in parse_md_table(body)
                if r.get("禁止模式")
            ]
            continue

    return result


# ---------------------------------------------------------------------------
# 模型卡加载（参数速查表.md）
# ---------------------------------------------------------------------------

def load_model_cards(kb_dir) -> Dict[str, Dict[str, str]]:
    """解析 参数速查表.md → {G1: {字段: 值}, G2: {...}, ...}。"""
    path = pathlib.Path(kb_dir) / "参数速查表.md"
    text = path.read_text(encoding="utf-8")

    cards: Dict[str, Dict[str, str]] = {}
    current: Dict[str, str] | None = None

    for line in text.splitlines():
        m = re.match(r"###\s+模型卡\s+(\S+)[：:]\s*(.*)", line.strip())
        if m:
            if current is not None:
                cards[current.get("_id", "unknown")] = current
            current = {"_id": m.group(1), "name": m.group(2).strip()}
            continue
        fm = re.match(r"-\s*([^：:]+)[：:]\s*(.*)", line.strip())
        if fm and current is not None:
            current[fm.group(1).strip()] = fm.group(2).strip()
    if current is not None:
        cards[current.get("_id", "unknown")] = current

    return cards


def load_all(kb_dir) -> Dict[str, Any]:
    """加载全部知识库结构（决策表 + 模型卡）。"""
    return {
        "decision": load_decision_tables(kb_dir),
        "model_cards": load_model_cards(kb_dir),
        "archetypes": load_archetypes(kb_dir),
    }


# ---------------------------------------------------------------------------
# 性格范式库加载（性格范式库.md）
# ---------------------------------------------------------------------------

def load_archetypes(kb_dir) -> Dict[str, Dict[str, Any]]:
    """解析 性格范式库.md → {范式名: {id, alias, alignment, 核心特征, ...}}。

    正反派依据标题位置（一、反派系 / 二、正派系）。
    """
    path = pathlib.Path(kb_dir) / "性格范式库.md"
    text = path.read_text(encoding="utf-8")

    villain_start = text.find("## 一、反派系")
    hero_start = text.find("## 二、正派系")
    if villain_start < 0 or hero_start < 0:
        return {}

    archetypes: Dict[str, Dict[str, Any]] = {}
    for sec, align in [(text[villain_start:hero_start], "反派"), (text[hero_start:], "正派")]:
        for m in re.finditer(r"###\s*(\d+)\.\s*([^\n（(]+)(?:（([^）)]+)）)?\s*\n", sec):
            num, name, alias = int(m.group(1)), m.group(2).strip().rstrip("型"), (m.group(3) or "").strip()
            body_start = m.end()
            nxt = re.search(r"\n###\s", sec[body_start:])
            body = sec[body_start: body_start + nxt.start()] if nxt else sec[body_start:]

            fields: Dict[str, Any] = {"id": num, "name": name, "alias": alias, "alignment": align}
            for key in ["核心特征", "标志性微表情", "英文提示词", "禁止表演"]:
                km = re.search(rf"-\s*\*\*{key}\*\*[：:]\s*(.+)", body)
                if km:
                    fields[key] = km.group(1).strip()
            tm = re.search(r"-\s*\*\*变体标签\*\*[：:]\s*(.+)", body)
            if tm:
                fields["tags"] = re.findall(r"#[\u4e00-\u9fa5A-Za-z]+", tm.group(1))
            em = re.search(r"情绪\s*×\s*程度\*\*[：:](.*?)(?=\n-\s*\*\*英文提示词)", body, re.S)
            if em:
                matrix = {}
                for line in em.group(1).splitlines():
                    lm = re.match(r"\s*-\s*([^\s（(]+)(?:（[^）)]+）)?[：:]\s*(.+)", line)
                    if lm:
                        matrix[lm.group(1).strip()] = lm.group(2).strip()
                fields["emotion_matrix"] = matrix
            archetypes[name] = fields
    return archetypes
