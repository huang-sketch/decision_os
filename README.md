# AI Decision OS

> 给创业者的理性决策操作系统。多 Agent 协作 × 冷静度校准 × 可解释建议。

---

## 一句话定位

输入一个创业想法，获得结构化诊断、风险评估、行动计划——以及一面防止冲动决策的镜子。

## 核心功能

| 功能 | 说明 |
|------|------|
| **创业成长诊断** | 4 Agent 闭环（创意验证 → 市场分析 → 策略建议 → 反思）自动生成决策报告 |
| **决策指数** | 综合分 0–100 + 可行性 / 市场 / 风险 / 资源四维评分，规则驱动、可解释 |
| **冷静度校准** | 4 道行为问题量化决策状态，低冷静度自动降级行动建议 + 输出防冲动处方 |
| **扩展决策空间** | 一键生成保守 / 当前 / 激进三方案对比，含推荐方案与置信度 |
| **7 天理性成长计划** | 诊断后一键生成 Day 1–7 行动清单，冷静度处方自动注入 |
| **多格式导出** | JSON 决策档案 + Markdown 报告，数据不落盘、不保存 |

## 目标人群

- 正在纠结要不要辞职创业的打工人
- 已启动副业、需要理性复盘和下一步规划的创业者
- 团队内部做方向决策时需要一份结构化参考

## 快速运行

```bash
# 1. 安装依赖
cd decision_os
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

# 2. 配置（可选，不配也能跑）
cp .env.example .env
# 默认 Mock 模式，填入 DASHSCOPE_API_KEY 后切换为通义千问

# 3. 启动
streamlit run app/web_app.py
```

打开浏览器 → 输入创业问题 → 点击「开始成长诊断」→ 查看报告。

## 技术架构

```
decision_os/
├── core/               # 内核层（不依赖 UI）
│   ├── context.py      # DecisionContext 统一数据容器
│   ├── engine.py       # 串行调度 + Reflection 回路
│   ├── orchestrator.py # 统一入口 run_decision / run_decision_space_expand
│   ├── schemas.py      # Agent 输出 JSON Schema
│   ├── base_agent.py   # BaseAgent + Mock / Qwen LLM 切换
│   └── variants.py     # 保守 / 激进方案规则生成
│
├── agents/             # 4 Agent + 冷静度评估
│   ├── idea_validator  # 创意验证
│   ├── market_analyzer # 市场分析
│   ├── strategy_advisor# 策略建议（含风险 + 资源）
│   ├── reflector       # 反思一致性校验
│   └── calm_evaluator  # 冷静度规则引擎（不调 LLM）
│
├── app/                # Streamlit UI 层
│   ├── web_app.py      # 主页面
│   ├── decision_metrics.py  # 决策指数 + 可视化
│   └── usage.py        # Token 用量估算
│
└── .env.example        # 环境变量模板
```

**关键设计**

- LLM 可插拔：默认 Mock 零成本运行，配置 Key 后无缝切换通义千问，失败自动回退
- 评分可解释：决策指数 = 四维规则映射 × 0.85 + 冷静度 × 0.15，不依赖黑盒模型
- 冷静度独立于 LLM：纯规则引擎，4 题 → 分数 → 降级 / 处方，延迟 ≈ 0

## 演示流程（3 分钟）

1. 打开页面，输入「我该不该辞职做 AI 自媒体？」
2. 填写现状 / 资源 / 约束（有 placeholder 引导）
3. 展开冷静度体检，调到「经常想换方向 + 没有止损线」
4. 点击「开始成长诊断」
5. 看到：决策指数 → 冷静度校准处方 → 核心判断 → 决策过程
6. 勾选「扩展决策空间」→ 再次诊断 → 三方案雷达图对比
7. 点击「生成 7 天理性成长计划」→ 下载 Markdown

## 未来规划

- [ ] 接入更多 LLM（GPT-4o / Claude / 本地模型）
- [ ] 多轮决策追踪：同一方向的第 2 次、第 3 次诊断自动对比
- [ ] 团队协作模式：多人投票 + 分歧可视化
- [ ] 行业知识库：注入垂直领域数据（餐饮 / SaaS / 内容电商）
- [ ] 移动端适配

---

MIT License · Built with Streamlit + DashScope
