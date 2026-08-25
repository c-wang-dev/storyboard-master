"""CLI 入口：python -m storyboard <剧本文件或文本> [选项]

示例：
    python -m storyboard "深夜，客厅里，张三紧张地环顾四周..." -o out.json
    python -m storyboard -f script.txt --model seedream-image-v5.0-pro --api-key sk-xxx
    python -m storyboard -f script.txt --no-llm          # 强制规则解析（零 API）
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

from . import character, decision, frame, grammar, knowledge, parser, prompts, quality, scene

DEFAULT_KB = pathlib.Path(__file__).resolve().parents[2] / "knowledge"


def _load_knowledge(kb_dir):
    return knowledge.load_all(kb_dir)


def _find_binding_table(kb_dir):
    """自动探测 knowledge/项目绑定/*_角色绑定表.md（取第一个）。"""
    d = pathlib.Path(kb_dir) / "项目绑定"
    if d.is_dir():
        for f in sorted(d.glob("*_角色绑定表.md")):
            return f
    return None


def _load_binding(kb_dir, binding_path=None) -> dict:
    """加载绑定表：显式路径优先，否则自动探测。无表返回空 dict。"""
    if binding_path is None:
        binding_path = _find_binding_table(kb_dir)
    if not binding_path:
        return {}
    try:
        text = pathlib.Path(binding_path).read_text(encoding="utf-8")
        return character.parse_binding_table(text)
    except Exception:
        return {}


def run(script: str, model_id: str, kb_dir, api_key, base_url, llm_model,
        binding_path=None) -> dict:
    kb = _load_knowledge(kb_dir)
    cards = kb["model_cards"]
    binding = _load_binding(kb_dir, binding_path)

    # 1. 解析剧本（LLM 或规则）
    parsed = parser.parse_script(script, api_key=api_key, base_url=base_url, model=llm_model)
    features = parsed.get("features", {})

    # 2. 决策引擎
    params = decision.decide(features, kb["decision"])
    duration = decision.select_duration(features.get("info_point_count", 2))
    keyframes = decision.count_keyframes(duration, features.get("pace", "中"), params.get("运镜") or "")
    features["duration"] = duration
    features["keyframes"] = keyframes

    # 2.5 电影语法判断（步骤 0）+ 景别序列 + 逐帧景别
    grammar_result = grammar.judge_grammar(features, parsed.get("characters", []))
    shot_sequence = grammar.expand_shots(grammar_result["景别序列"], keyframes)

    # 3. 提示词包
    pack = prompts.generate_prompt_pack(
        parsed, params, cards, model_id, kb["decision"].get("negative_a", [])
    )

    # 3.5 资产层（P0）：角色资产（锚定卡+定妆照+三视图）+ 场景资产（设定图）
    # 必须先于帧级输出——帧提示词要注入角色外貌锚定、一致性建议要引用场景图
    character_assets = character.build_character_assets(
        script, kb["archetypes"], model_id, api_key, base_url, llm_model, binding=binding
    )
    scene_assets = scene.build_scene_assets(
        parsed.get("scenes", []), params, model_id, mood=features.get("emotion_tone", "")
    )

    # 3.6 帧级输出（P2）：逐帧提示词（含外貌锚定）+ 一致性建议（双参考图）+ 参数块
    card = prompts._card(cards, model_id)
    frame_output = frame.build_frames(
        parsed, params, grammar_result, shot_sequence, card, duration, keyframes,
        character_assets=character_assets,
        scene_assets=scene_assets,
    )

    # 先构建完整结果（供自检），再执行 12 项自检后塞回
    result = {
        "model": pack["model_id"],
        "duration_tier": duration,
        "keyframes": keyframes,
        "features": features,
        "scenes": parsed.get("scenes", []),
        "characters": parsed.get("characters", []),
        "audio_visual_params": {k: v for k, v in params.items() if v},
        "grammar": grammar_result,
        "shot_sequence": shot_sequence,
        "prompt_pack": pack,
        "frames": frame_output["frames"],
        "consistency": frame_output["consistency"],
        "param_block": frame_output["param_block"],
        "character_assets": character_assets,
        "scene_assets": scene_assets,
        "degraded": parsed.get("degraded"),
    }
    # 4. 12 项自检
    result["quality_check"] = quality.check(result)
    return result


def _load_env_file(env_path=None) -> None:
    """从 .env 文件读取环境变量（标准库实现，避免引入 python-dotenv）。

    .env 已被 .gitignore 排除，不会随仓库上传。
    """
    if env_path is None:
        env_path = pathlib.Path(__file__).resolve().parents[1] / ".env"
    if not pathlib.Path(env_path).is_file():
        return
    for line in pathlib.Path(env_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def main(argv=None) -> int:
    _load_env_file()
    ap = argparse.ArgumentParser(
        prog="storyboard",
        description="分镜大师独立运行器：剧本 → 分镜 + 提示词包（零依赖，仅标准库）",
    )
    ap.add_argument("script", nargs="?", help="剧本文本")
    ap.add_argument("-f", "--file", help="剧本文件路径")
    ap.add_argument("-o", "--output", help="输出 JSON 文件路径")
    ap.add_argument("--model", default="seedream-image-v5.0-pro", help="模型卡 ID（如 seedream-image-v5.0-pro / dreamina-seedance-2-5-260628）")
    ap.add_argument("--kb", default=str(DEFAULT_KB), help="知识库目录（默认 engine 上级的 knowledge/）")
    ap.add_argument("--binding", default=None, help="项目角色绑定表路径（默认自动探测 knowledge/项目绑定/）")
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

    api_key = None if args.no_llm else (args.api_key or os.environ.get("DEEPSEEK_API_KEY"))
    base_url = os.environ.get("LLM_BASE_URL") or args.base_url
    llm_model = os.environ.get("LLM_MODEL") or args.llm_model
    result = run(script, args.model, args.kb, api_key, base_url, llm_model,
                 binding_path=args.binding)

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
