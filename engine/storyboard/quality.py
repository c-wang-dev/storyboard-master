"""12 项质量自检（P3）：对齐智能体配置的分镜质量闸门 12 项。

对 run() 的完整输出做规则校验，不合格项列出并给出修复建议。
纯规则、零 API。已将历史 SD 概念（tag/CFG/Steps/IP-Adapter/ControlNet）
适配为自然语言系（参考图 / 首帧 / LoRA）。

12 项（对应 agents/storyboard-master.md 4.4）：
 1 电影语法判断（步骤0）  2 决策引擎五表  3 决策头完整  4 提示词语法
 5 镜头运动关键词        6 光影描述      7 一致性建议  8 参数块
 9 语法体现（逐帧）       10 负面词      11 档位秒数   12 表演一致性
"""

from __future__ import annotations

from typing import Any, Dict, List


def check(result: Dict[str, Any]) -> Dict[str, Any]:
    """执行 12 项自检，返回 {passed: bool, total: int, issues: [{item, level, advice}]}。"""
    issues: List[Dict[str, str]] = []
    grammar = result.get("grammar", {})
    params = result.get("audio_visual_params", {})
    pack = result.get("prompt_pack", {})
    frames = result.get("frames", [])
    prompt = pack.get("prompt", "")
    model_id = str(pack.get("model_id", "")).lower()

    # 1. 步骤 0 电影语法判断（场景类型 / 景别序列）
    if not grammar.get("场景类型") or not grammar.get("景别序列"):
        issues.append({"item": "1.电影语法判断", "level": "error",
                       "advice": "未完成步骤 0（场景类型/景别序列缺失）"})

    # 2. 决策引擎五表（景别/角度/运镜/光影/节奏）
    for k in ("景别", "角度", "运镜", "光影", "节奏"):
        if not params.get(k):
            issues.append({"item": f"2.决策引擎-{k}", "level": "warn",
                           "advice": f"决策表未输出{k}"})

    # 3. 决策头完整（档位 / 图数）
    if not result.get("duration_tier") or not result.get("keyframes"):
        issues.append({"item": "3.决策头", "level": "error",
                       "advice": "档位/图数缺失"})

    # 4. 提示词语法（自然语言完整句子 + 主体已替换，非占位符）
    if not prompt:
        issues.append({"item": "4.提示词语法", "level": "error",
                       "advice": "提示词为空"})
    elif "主体人物" in prompt or "主体占位" in prompt:
        issues.append({"item": "4.提示词语法", "level": "warn",
                       "advice": "主体占位符未替换"})

    # 5. 镜头运动关键词显式写入提示词
    move = params.get("运镜", "")
    if move and move not in prompt:
        issues.append({"item": "5.镜头运动", "level": "warn",
                       "advice": f"运镜关键词「{move}」未写入提示词"})

    # 6. 光影描述写入提示词
    light = params.get("光影", "")
    if light and light not in prompt:
        issues.append({"item": "6.光影", "level": "warn",
                       "advice": f"光影描述「{light}」未写入提示词"})

    # 7. 一致性建议（参考图 / 首帧 / LoRA）
    consistency = result.get("consistency", {})
    if not consistency.get("建议"):
        issues.append({"item": "7.一致性建议", "level": "error",
                       "advice": "一致性建议缺失"})

    # 8. 参数块（模型ID / 尺寸 / 比例）
    pb = result.get("param_block", {})
    if not pb.get("model_id"):
        issues.append({"item": "8.参数块", "level": "error",
                       "advice": "参数块缺失模型ID"})

    # 9. 语法体现（景别序列展开为逐帧）
    if not frames:
        issues.append({"item": "9.语法体现", "level": "error",
                       "advice": "无逐帧输出"})
    elif len(frames) != result.get("keyframes", -1):
        issues.append({"item": "9.语法体现", "level": "warn",
                       "advice": f"逐帧数 {len(frames)} ≠ 图数 {result.get('keyframes')}"})

    # 10. 负面词（按模型区分：Flux 不写，即梦/Seedream 写）
    neg = pack.get("negative_prompt", "")
    is_flux = "flux" in model_id
    if is_flux and neg:
        issues.append({"item": "10.负面词", "level": "error",
                       "advice": "Flux 不写负面词，但已生成"})
    elif not is_flux and pack.get("type") == "生图" and not neg:
        issues.append({"item": "10.负面词", "level": "info",
                       "advice": "支持负面词但未写（可补充防畸变）"})

    # 11. 档位秒数（5s/10s/15s）
    if result.get("duration_tier") not in ("5s", "10s", "15s"):
        issues.append({"item": "11.档位秒数", "level": "error",
                       "advice": f"非法档位 {result.get('duration_tier')}"})

    # 12. 表演一致性（角色锚定卡 + 禁止表演清单）
    chars = result.get("character_assets", [])
    if not chars:
        issues.append({"item": "12.表演一致性", "level": "info",
                       "advice": "角色锚定卡未接入（无 API Key 或角色未提取），跳过禁止表演检查"})
    else:
        missing = [c.get("name", "?") for c in chars
                   if not c.get("anchor_card", {}).get("禁止表演")]
        if missing:
            issues.append({"item": "12.表演一致性", "level": "warn",
                           "advice": f"角色 {missing} 锚定卡缺禁止表演清单（无法拦截范式外表演）"})

    errors = [i for i in issues if i["level"] == "error"]
    return {
        "passed": len(errors) == 0,
        "total": 12,
        "issues": issues,
    }
