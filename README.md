# Storyboard Master（分镜大师）

面向影视创作者的 **AI 分镜 Agent 工具**：把剧本解析为结构化分镜，并输出可直接用于文生图/文生视频模型的提示词包。

> 项目定位：Agent 负责"决策"（剧本 → 视听参数 → 提示词），生图/生视频由下游模型工具执行。知识库 + 规则闸门保证生成质量稳定、可复用、可追溯。

## 核心能力

- **确定性决策引擎**：剧本片段 → 内容类型/信息焦点/情绪强度/权力关系/空间关系/节奏倾向六维特征 → 景别/角度/运镜/光影/节奏五张决策表 + 冲突仲裁 → 可解释的视听参数
- **领域知识库**（`knowledge/`）：32 份结构化文档，覆盖镜头语言、电影语法、角色表演、视觉风格、模型参数
- **多模型接入与 Tool Use 路由**：即梦 image2、Seedream 5.0 Pro、Flux（生图）；Seedance 2.5、可灵 3.0、通义万相 2.7（生视频）；模型分流机制避免跨模型参数污染
- **角色表演一致性**：性格范式 → 角色锚定卡 → 禁止表演清单 → 远景体态降级，四层机制解决跨镜头表演漂移；样本库只存行为模式中性描述（脱敏，不复刻长相与声音）
- **质量护栏**：18 项质量闸门、证据分层（机器实测 vs 视觉推断）、知识写回三查（查重/冲突仲裁/三要素）、成本台账与废片归因
- **自我成长工作流**：检索未命中 → 生成候选标记"待验证"→ 人工确认后才写回知识库，防止错误知识污染

## 目录结构

```
storyboard-master/
├── agents/                          # Agent 配置（角色、流程、硬规则）
├── skills/
│   └── storyboard-knowledge/        # 知识检索技能（三层检索降级）
├── knowledge/                       # 领域知识库（Obsidian Markdown，双链组织）
│   ├── 分镜决策引擎.md              # 决策表与仲裁规则
│   ├── 参数速查表.md                # 6 张模型卡（字段化）
│   ├── 性格范式库.md / 角色微表情库.md
│   ├── 打斗动作库.md / 特效库.md / 转场与片段衔接库.md
│   ├── 视频学习记录/                # 影视案例五维分析归档（学习笔记）
│   └── 知识库治理规则.md            # 三层存储、三道闸门、容量红线
├── engine/                          # ★ 独立 Python 运行器（零依赖）
│   ├── storyboard/                  #   knowledge / decision / parser / prompts / quality / cli
│   ├── tests/                       #   决策引擎单元测试（离线可跑）
│   └── examples/                    #   示例：剧本 → 分镜 JSON
├── knowledge/                       # 领域知识库（Obsidian Markdown，双链组织）
│   ├── 分镜决策引擎.md              # 决策表与仲裁规则
│   ├── 参数速查表.md                # 6 张模型卡（字段化）
│   ├── 性格范式库.md / 角色微表情库.md
│   ├── 打斗动作库.md / 特效库.md / 转场与片段衔接库.md
│   ├── 视频学习记录/                # 影视案例五维分析归档（学习笔记）
│   └── 知识库治理规则.md            # 三层存储、三道闸门、容量红线
├── docs/ARCHITECTURE.md             # 架构说明
└── examples/                        # 示例输出
```

## 快速开始

### 方式一：Python 运行器（零依赖，clone 即用）

```bash
cd engine
python -m storyboard -f examples/示例剧本_镖局夜战.txt --no-llm    # 规则解析，免费离线
export DEEPSEEK_API_KEY=sk-xxx
python -m storyboard -f examples/示例剧本_镖局夜战.txt -o 分镜.json # LLM 解析，效果最佳
python -m unittest discover -s tests -v                            # 运行测试
```

详见 [engine/README.md](engine/README.md)。

### 方式二：WorkBuddy 智能体（全功能）

1. 将 `agents/` 与 `skills/` 导入 WorkBuddy 专家市场（my-experts/plugins）
2. 将 `knowledge/` 挂载为 Obsidian 库（启用双链导航）
3. 对话中调用"分镜大师"，输入剧本片段 → 按提示完成模型分流 → 获取分镜与提示词包

### 环境依赖（语义检索，可选）

- Obsidian + smart-connections 插件（本地嵌入 bge-micro-v2，零 API key）
- Node.js 与 `@yejianye/smart-connections-mcp`
- 未配置时自动降级：MOC 导航 → 关键词检索（检索失败不阻塞主流程）

## 技术栈

Markdown / Obsidian 双链知识库 · 自然语言提示词工程 · 多模型 API 适配 · ffmpeg 视频量化分析 · Python 工具链

## 示例

- 剧本 → 分镜决策 → 提示词包：见 `examples/`（含《月夜刀光》片段示例）
- 视频学习 → 规则沉淀：`knowledge/视频学习记录/`（含《卧虎藏龙》全片 672 镜头量化分析）

## 许可证

- **代码与配置**（engine/、agents/、skills/、docs/）：[MIT](LICENSE)
- **知识库内容**（knowledge/）：[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.zh)（非商业使用；含影视作品分析，仅供学习研究）

## 免责声明

- 知识库中的影视分析（视频学习记录、演技样本方法论等）为**个人学习与研究笔记**，仅作学术交流，不含影视素材原文与截图
- 演技样本库遵循严格脱敏：只存行为模式的中性描述，**绝不输出真实姓名、长相与声音特征**
- 本项目为个人项目，作者与任何影视作品版权方无关

## 相关链接

- 本仓库：GitHub
- 项目文档：docs/ARCHITECTURE.md
