"""
分镜大师：知识库驱动的 AI 分镜 Agent（独立运行器）

将分镜大师的"规则 + 知识库"沉淀为可独立运行的 Python 包：
输入剧本片段，输出结构化分镜与提示词包（JSON）。
仅标准库，零第三方依赖；LLM 调用使用 OpenAI 兼容协议（urllib 实现）。

模块：
- knowledge: 运行时解析 knowledge/*.md（决策表 / 模型卡 / 负面清单）
- decision:  确定性决策引擎（六维 → 五表 → 仲裁 → 档位 → 图数）
- parser:    LLM 剧本解析（OpenAI 兼容），失败自动降级规则解析
- prompts:   按模型卡模板组装提示词包
- quality:   12 项质量自检
- cli:       命令行入口
"""

__version__ = "0.1.0"
