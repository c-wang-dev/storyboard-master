# 分镜大师独立运行器（engine/）

把分镜大师的"规则 + 知识库"沉淀为**可独立运行的 Python 包**：输入剧本片段，输出结构化分镜与提示词包（JSON）。

**零第三方依赖**（仅 Python 标准库）——clone 仓库后直接可跑；LLM 调用用 OpenAI 兼容协议（urllib 实现），支持 DeepSeek / OpenAI / 通义等。

## 快速开始

```bash
# 规则解析（零 API，免费离线）
python -m storyboard -f 剧本.txt --no-llm

# LLM 解析（配 DeepSeek Key，效果最佳）
export DEEPSEEK_API_KEY=sk-xxx
python -m storyboard -f 剧本.txt -o 分镜.json

# 指定模型卡与输出
python -m storyboard "深夜，客厅里，张三紧张地环顾四周..." --model seedream-image-v5.0-pro -o out.json
```

## 架构

```
剧本片段
  → LLM 解析（parser.py：剧本 → 场景/角色/对白/动作 + 六维特征；content_type 六类归一化；失败降级规则解析）
  → 决策引擎（decision.py：六维 → 五表查表 → 仲裁 → 档位 → 图数；纯规则可测）
  → 电影语法（grammar.py：步骤0 场景类型 → 景别序列 → 机位语法 → 越轴提示）
  → 知识库加载（knowledge.py：运行时解析 ../knowledge/*.md，改 md 即改行为）
  → 提示词生成（prompts.py：按模型卡模板组装提示词包）
  → 帧级输出（frame.py：逐帧提示词 + 一致性建议 + 参数块）
  → 12 项质量自检（quality.py：对齐智能体配置的分镜质量闸门 12 项）
  → 输出 JSON
```

## 为什么这样设计

- **知识库驱动**：决策表、模型卡、负面清单运行时从 `knowledge/*.md` 解析——更新知识库即更新行为，不写死在代码里
- **确定性**：决策引擎是纯规则查表，同样输入永远同样输出（分镜大师核心卖点，可测试）
- **降级可用**：没有 API Key 也能跑（规则解析 + 完整决策引擎），只是剧本语义理解弱一些
- **可扩展**：CLI 之外预留接入 FastAPI/执行端的接口（见 `storyboard/cli.py` 的 `run()`）

## 测试

```bash
cd engine && python -m unittest discover -s tests -v
```

## 与 WorkBuddy 智能体的关系

本运行器是分镜大师决策逻辑的**独立代码形态**（"大脑"的可执行版本）；原智能体（agents/ + skills/）运行于 WorkBuddy 平台，两者共享同一套知识库规则。执行端（真实调用生图/生视频 API）可基于 `run()` 的输出继续扩展。
