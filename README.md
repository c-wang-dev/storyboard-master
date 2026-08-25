# Storyboard Master · 分镜大师

> AI film storyboard prompt engineer — script-to-storyboard pipeline with acting consistency, cinematography rules, and prompt quality evaluation. Knowledge-base driven, compatible with GPT-Image-2 / Seedream / Flux / Seedance / Kling / Wan.

<div align="center">

**剧本 → 结构化分镜 → 可直接投喂生图/生视频模型的提示词包**

`Decision-first` · `Knowledge-driven` · `Verifiable output`

</div>

## 项目定位

分镜大师是一个**决策端 Agent**：解析剧本片段，输出可解释的视听决策与高质量提示词包，由下游生图/生视频工具执行。核心设计原则：

- **决策可解释**：六维特征 → 五张决策表 → 冲突仲裁，每一步可追溯
- **质量可评估**：九要素帧级检测 + 双轨评测，输出好坏可量化回归
- **知识可沉淀**：视频学习 → 规则提炼 → 三查闸门写回，知识库随使用增长

```
剧本片段
   │
   ▼
┌─────────────────────────────────┐
│ ① 模型分流（死锁模型卡）           │  生图: GPT-Image-2 / Seedream 5.0 Pro / Flux
└─────────────────────────────────┘  生视频: Seedance 2.5 / 可灵 3.0 / 通义万相 2.7
   │
   ▼
┌─────────────────────────────────┐
│ ② 决策引擎（六维 → 五表 → 仲裁）    │  内容类型/信息焦点/情绪/权力/空间/节奏
└─────────────────────────────────┘  → 景别/角度/运镜/光影/节奏 + 时长档位
   │
   ▼
┌─────────────────────────────────┐
│ ③ 知识检索（三层降级）             │  语义检索 → MOC 导航 → 关键词兜底
└─────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────┐
│ ④ 表演一致性（四层机制）           │  性格范式 → 锚定卡 → 禁止清单 → 远景降级
└─────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────┐
│ ⑤ 提示词包输出 + 12 项质量自检     │  逐帧提示词/一致性建议/参数块/负面词
└─────────────────────────────────┘
   │
   ▼
   下游模型工具（生图/生视频 API）
```

## 核心能力

- **确定性决策引擎**（`engine/storyboard/decision.py`）：剧本片段 → 六维特征 → 五张决策表 + 冲突仲裁 → 档位/图数。**纯规则查表，同样输入永远同样输出**，可单元测试
- **领域知识库**（`knowledge/`）：32 份结构化 Markdown，覆盖镜头语言、电影语法、角色表演、视觉风格、6 张模型卡；Obsidian 双链组织 + 语义检索
- **多模型接入与模型分流**：生图 **GPT-Image-2** / Seedream 5.0 Pro / Flux；生视频 Seedance 2.5 / 可灵 3.0 / 通义万相 2.7。选定后死锁对应模型卡，杜绝跨模型参数污染
- **角色表演一致性（四层）**：L1 性格范式库（8 范式）→ L2 角色锚定卡（一次绑定全剧生效）→ L3 禁止表演清单（闸门）→ L4 远景体态降级。演技样本只存行为模式中性描述（脱敏，不复刻长相与声音）
- **跨片段一致性**：项目角色绑定表（别名归一防双脸）+ 定妆照/场景设定图双参考图 + 时间同义归一，实测跨片段外貌零漂移
- **物理后果必配**（蒸馏自 director-skills Motion Physics）：所有含动作的帧强制注入重量/摩擦/环境反应，打斗与日常动作双速查表，杜绝"画面飘"
- **质量评测闭环**：九要素帧级检测 + 智能体端双轨评测 + 成本台账与废片归因，输出质量可量化回归
- **知识治理与自我成长**：三层存储 + 三查闸门（查重/冲突仲裁/三要素）+ 参数保鲜管线（过时标 deprecated 不删）；检索未命中 → 生成候选标「待验证」→ 人工确认后才写回

## 评测数据（实测）

> 口径：基于自创剧本《月夜刀光》5 片段，智能体端完整工作流生成，逐帧自动化检测。

| 指标 | 结果 |
|------|------|
| 智能体端评测总分 | **9.8 / 10**（双轨评测，可回归） |
| 九要素帧级覆盖 | **8/9 要素 100%**（景别/运镜/光影四要素/负面词/外貌锚定等） |
| 角色一致性 | 别名归一 **5/5** · 双参考图 **5/5** · 跨片段外貌零漂移 |
| 物理后果覆盖率 | 规则升级后 **36% → 61%**（打戏 10/10 帧、收刀/情绪 4/4 帧） |
| 决策引擎 | 纯规则确定性 · **18 个单元测试全过** |

## 快速开始

### 方式一：独立运行器（零依赖，clone 即用）

```bash
cd engine

# 规则解析（零 API，免费离线）
python -m storyboard -f examples/示例剧本_镖局夜战.txt --no-llm

# LLM 解析（配 DeepSeek Key，语义理解最佳）
export DEEPSEEK_API_KEY=sk-xxx
python -m storyboard -f examples/示例剧本_镖局夜战.txt -o 分镜.json

# 指定模型卡
python -m storyboard "深夜，客厅里，张三紧张地环顾四周..." --model seedream-image-v5.0-pro -o out.json

# 运行 18 个单元测试
python -m unittest discover -s tests -v
```

详见 [engine/README.md](engine/README.md)。

### 方式二：WorkBuddy 智能体（全功能）

1. 将 `agents/` 与 `skills/` 导入 WorkBuddy 专家市场（my-experts/plugins）
2. 将 `knowledge/` 挂载为 Obsidian 库（启用双链导航与语义检索）
3. 对话中调用「分镜大师」，输入剧本片段 → 完成模型分流 → 获取分镜与提示词包

## 目录结构

```
storyboard-master/
├── agents/                          # Agent 配置（角色、流程、硬规则）
├── skills/
│   └── storyboard-knowledge/        # 知识检索技能（三层检索降级）
├── knowledge/                       # 领域知识库（Obsidian Markdown，双链组织）
│   ├── 分镜决策引擎.md              # 决策表与仲裁规则（稳定层）
│   ├── 参数速查表.md                # 6 张模型卡（字段化，参数保鲜）
│   ├── 性格范式库.md / 角色微表情库.md
│   ├── 打斗动作库.md / 特效库.md / 转场与片段衔接库.md
│   ├── 视频学习记录/                # 影视案例五维分析归档（学习笔记）
│   └── 知识库治理规则.md            # 三层存储、三道闸门、容量红线
├── engine/                          # ★ 独立 Python 运行器（零依赖）
│   ├── storyboard/                  #   parser / decision / grammar / knowledge /
│   │                                #   prompts / frame / quality / cli
│   ├── tests/                       #   18 个单元测试（决策引擎+解析器，离线可跑）
│   └── examples/                    #   示例剧本 + 分镜输出 JSON
├── docs/ARCHITECTURE.md             # 架构说明（五层知识库/四层一致性/三道闸门）
├── examples/                        # 示例输出（整理补充中）
├── avatars/                         # 专家头像
├── plugin.json                      # WorkBuddy 专家包配置
├── LICENSE                          # MIT
└── README.md
```

## 技术栈

Markdown / Obsidian 双链知识库 · 自然语言提示词工程 · 多模型 API 适配 · 决策表规则引擎 · Python 标准库（零第三方依赖）· ffmpeg 视频量化分析

## 免责声明

- 知识库中的影视分析（视频学习记录、演技样本方法论等）为**个人学习与研究笔记**，仅作学术交流，不含影视素材原文与截图
- 演技样本库遵循严格脱敏：只存行为模式的中性描述，**绝不输出真实姓名、长相与声音特征**
- 本项目为个人项目，作者与任何影视作品版权方无关

## 相关链接

- 项目文档：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 独立运行器：[engine/README.md](engine/README.md)

## 许可证

[MIT License](LICENSE) © 2026 Storyboard Master contributors
