"""12 项质量自检：对生成的提示词包做规则校验，不合格项列出并给出修复建议。

纯规则、零 API。对应分镜大师的"每条分镜必须完成 12 项质量自检"。
"""

from __future__ import annotations

from typing import Any, Dict, List


def check(prompt_pack: Dict[str, Any]) -> Dict[str, Any]:
    """执行 12 项自检，返回 {passed: bool, issues: [{item, level, advice}]}。"""
    issues: List[Dict[str, str]] = []
    p = prompt_pack.get("prompt", "")
    neg = prompt_pack.get("negative_prompt", "")
    params = prompt_pack.get("params", {})

    # 1. 提示词非空
    if not p or len(p.strip()) < 10:
        issues.append({"item": "1.提示词非空", "level": "error", "advice": "提示词为空或过短"})
    # 2. 提示词长度（Seedream 类中文 ≤300）
    if len(p) > 300:
        issues.append({"item": "2.提示词长度", "level": "warn", "advice": f"长度 {len(p)}，中文建议 ≤300 字"})
    # 3. 必含主体
    if "主体" in p and "主体人物" in p:
        issues.append({"item": "3.主体描述", "level": "warn", "advice": "未替换主体占位符"})
    # 4. 场景描述
    if "位于" not in p and "场景" not in p:
        issues.append({"item": "4.场景描述", "level": "warn", "advice": "缺少场景描述"})
    # 5. 景别
    if not params.get("景别"):
        issues.append({"item": "5.景别", "level": "error", "advice": "决策引擎未输出景别"})
    # 6. 角度
    if not params.get("角度"):
        issues.append({"item": "6.角度", "level": "warn", "advice": "未输出角度（对等关系可接受）"})
    # 7. 运镜
    if not params.get("运镜"):
        issues.append({"item": "7.运镜", "level": "warn", "advice": "未输出运镜（固定机位可接受）"})
    # 8. 光影
    if not params.get("光影"):
        issues.append({"item": "8.光影", "level": "warn", "advice": "未输出光影"})
    # 9. 模型合规（负面词与模型支持）
    if neg and "不用" in str(prompt_pack.get("model_name", "")):
        issues.append({"item": "9.模型合规", "level": "error", "advice": "该模型不支持负面词但已生成"})
    # 10. 负面词非空（支持负面词的模型）
    if prompt_pack.get("type") == "生图" and not neg and "支持" in str(prompt_pack.get("consistency", "")):
        issues.append({"item": "10.负面词", "level": "info", "advice": "可补充负面词防畸变"})
    # 11. 档位与图数
    if not params.get("keyframes"):
        issues.append({"item": "11.图数", "level": "info", "advice": "未计算关键帧数量"})
    # 12. 时长档位
    if params.get("duration") not in ("5s", "10s", "15s"):
        issues.append({"item": "12.时长档位", "level": "error", "advice": f"非法档位 {params.get('duration')}"})

    errors = [i for i in issues if i["level"] == "error"]
    return {
        "passed": len(errors) == 0,
        "total": 12,
        "issues": issues,
    }
