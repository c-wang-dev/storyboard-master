"""CLI 入口：python -m storyboard <剧本文件或文本> [选项]

示例：
    python -m storyboard "深夜，客厅里，张三紧张地环顾四周..." -o out.json
    python -m storyboard -f script.txt --model seedream-5.0-pro --api-key sk-xxx
    python -m storyboard -f script.txt --no-llm          # 强制规则解析（零 API）
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

from . import decision, knowledge, parser, prompts, quality

DEFAULT_KB = pathlib.Path(__file__).resolve().parents[2] / "knowledge"


def _load_knowledge(kb_dir):
    return knowledge.load_all(kb_dir)


def run(script: str, model_id: str, kb_dir, api_key, base_url, llm_model) -> dict:
    kb = _load_knowledge(kb_dir)
    cards = kb["model_cards"]

    # 1. 解析剧本（LLM 或规则）
    parsed = parser.parse_script(script, api_key=api_key, base_url=base_url, model=llm_model)
    features = parsed.get("features", {})

    # 2. 决策引擎
    params = decision.decide(features, kb["decision"])
    duration = decision.select_duration(features.get("info_point_count", 2))
    keyframes = decision.count_keyframes(duration, features.get("pace", "中"), params.get("运镜") or "")
    features["duration"] = duration
    features["keyframes"] = keyframes

    # 3. 提示词包
    pack = prompts.generate_prompt_pack(parsed, params, cards, model_id)

    # 4. 12 项自检
    report = quality.check(pack)

    return {
        "model": pack["model_id"],
        "duration_tier": duration,
        "keyframes": keyframes,
        "audio_visual_params": {k: v for k, v in params.items() if v},
        "prompt_pack": pack,
        "quality_check": report,
        "degraded": parsed.get("degraded"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="storyboard",
        description="分镜大师独立运行器：剧本 → 分镜 + 提示词包（零依赖，仅标准库）",
    )
    ap.add_argument("script", nargs="?", help="剧本文本")
    ap.add_argument("-f", "--file", help="剧本文件路径")
    ap.add_argument("-o", "--output", help="输出 JSON 文件路径")
    ap.add_argument("--model", default="seedream-5.0-pro", help="模型卡 ID（如 seedream-5.0-pro / seedance-2.5）")
    ap.add_argument("--kb", default=str(DEFAULT_KB), help="知识库目录（默认 engine 上级的 knowledge/）")
    ap.add_argument("--api-key", default=os.environ.get("DEEPSEEK_API_KEY"), help="LLM API Key（默认读 DEEPSEEK_API_KEY）")
    ap.add_argument("--base-url", default=parser.DEFAULT_BASE_URL, help="LLM API Base URL（OpenAI 兼容）")
    ap.add_argument("--llm-model", default=parser.DEFAULT_MODEL, help="LLM 模型名")
    ap.add_argument("--no-llm", action="store_true", help="强制规则解析，不调用 API")
    args = ap.parse_args(argv)

    if args.file:
        script = pathlib.Path(args.file).read_text(encoding="utf-8")
    elif args.script:
        script = args.script
    else:
        ap.print_help()
        return 1

    api_key = None if args.no_llm else args.api_key
    result = run(script, args.model, args.kb, api_key, args.base_url, args.llm_model)

    if args.output:
        pathlib.Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"✓ 结果已保存: {args.output}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
